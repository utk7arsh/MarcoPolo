import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { demoSnapshot } from '../data/demo'
import type { Snapshot } from './schema'
import type { Connection, Transport } from './transport'
import { DashboardStore } from './store'

function harness() {
  let receive!: (snapshot: Snapshot) => void
  let connect!: (connection: Connection) => void
  const transport: Transport = {
    start: (onSnapshot, onConnection) => {
      receive = onSnapshot
      connect = onConnection
      return vi.fn()
    },
    send: vi.fn(async () => {}),
  }
  const store = new DashboardStore(transport)
  const stop = store.start()
  const snapshot = demoSnapshot()
  receive(structuredClone(snapshot))
  connect('live')
  return { store, transport, receive, connect, snapshot, stop }
}
beforeEach(() => vi.useFakeTimers())
afterEach(() => vi.useRealTimers())
describe('dashboard state and commands', () => {
  it('ignores stale/repeated snapshots and accepts a new stream', () => {
    const { store, receive, snapshot, stop } = harness()
    const old = structuredClone(snapshot)
    old.data.items = []
    receive(old)
    expect(store.getSnapshot().snapshot!.data.items).toHaveLength(4)
    receive({ ...old, streamId: 'server-restarted', sequence: 0 })
    expect(store.getSnapshot().snapshot!.data.items).toHaveLength(0)
    stop()
  })
  it('waits for phone acknowledgement rather than the HTTP response', async () => {
    const { store, receive, snapshot, transport, stop } = harness()
    snapshot.data.navigation.state = 'idle'
    snapshot.sequence++
    receive(structuredClone(snapshot))
    await store.command('find', 'keys')
    const command = store.getSnapshot().pending!
    expect(transport.send).toHaveBeenCalledTimes(1)
    expect(store.getSnapshot().pending).not.toBeNull()
    expect(store.getSnapshot().snapshot!.data.navigation.state).toBe('idle')
    await store.command('find', 'mug')
    expect(transport.send).toHaveBeenCalledTimes(1)
    snapshot.sequence++
    snapshot.data.lastCommand = {
      commandId: command.commandId,
      status: 'accepted',
      reason: null,
    }
    receive(structuredClone(snapshot))
    expect(store.getSnapshot().pending).toBeNull()
    stop()
  })
  it('keeps failed commands retryable with the same id, and handles a late acknowledgement', async () => {
    const { store, transport, receive, snapshot, stop } = harness()
    vi.mocked(transport.send).mockRejectedValueOnce(new Error('Network error'))
    await store.command('find', 'keys')
    const failed = store.getSnapshot().failed!
    expect(store.getSnapshot().error).toBe('Network error')
    await store.retry()
    expect(vi.mocked(transport.send).mock.calls[1][0].commandId).toBe(
      failed.commandId,
    )
    await vi.advanceTimersByTimeAsync(10000)
    expect(store.getSnapshot().pending).toBeNull()
    expect(store.getSnapshot().failed?.commandId).toBe(failed.commandId)
    snapshot.sequence++
    snapshot.data.lastCommand = {
      commandId: failed.commandId,
      status: 'accepted',
      reason: null,
    }
    receive(structuredClone(snapshot))
    expect(store.getSnapshot().failed).toBeNull()
    expect(store.getSnapshot().error).toBeNull()
    stop()
  })
  it('keeps a rejection visible across normal heartbeats', async () => {
    const { store, receive, connect, snapshot, stop } = harness()
    await store.command('stop')
    snapshot.sequence++
    connect('offline')
    snapshot.data.lastCommand = {
      commandId: store.getSnapshot().pending!.commandId,
      status: 'rejected',
      reason: 'Phone is busy',
    }
    receive(structuredClone(snapshot))
    connect('live')
    expect(store.getSnapshot().error).toBe('Phone is busy')
    expect(store.getSnapshot().pending).toBeNull()
    stop()
  })
  it('retains memory while offline and cancels pending timers on disposal', async () => {
    const { store, connect, stop } = harness()
    await store.command('stop')
    connect('offline')
    expect(store.getSnapshot().snapshot?.data.items).toHaveLength(4)
    stop()
    await vi.advanceTimersByTimeAsync(15000)
    expect(store.getSnapshot().error).toBeNull()
  })
  it.each(['deviceId', 'id'] as const)(
    'invalidates a failed request when session.%s changes',
    async (field) => {
      const { store, transport, receive, snapshot, stop } = harness()
      vi.mocked(transport.send).mockRejectedValueOnce(
        new Error('Network error'),
      )
      await store.command('find', 'keys')
      const original = store.getSnapshot().failed!
      snapshot.sequence++
      snapshot.data.session[field] = 'replacement'
      receive(structuredClone(snapshot))
      expect(store.getSnapshot().failed).toBeNull()
      expect(store.getSnapshot().error).toBeNull()
      await store.retry()
      expect(transport.send).toHaveBeenCalledTimes(1)
      await store.command('find', 'keys')
      const replacement = store.getSnapshot().pending!
      expect(replacement.deviceId).toBe(snapshot.data.session.deviceId)
      expect(replacement.commandId).not.toBe(original.commandId)
      stop()
    },
  )
  it.each(['deviceId', 'id'] as const)(
    'invalidates pending requests and ignores late results when session.%s changes',
    async (field) => {
      const { store, transport, receive, snapshot, stop } = harness()
      let rejectOriginal!: (error: Error) => void
      vi.mocked(transport.send).mockImplementationOnce(
        () =>
          new Promise((_, reject) => {
            rejectOriginal = reject
          }),
      )
      const originalSend = store.command('find', 'keys')
      const original = store.getSnapshot().pending!
      await vi.advanceTimersByTimeAsync(5000)
      snapshot.sequence++
      snapshot.data.session[field] = 'replacement'
      receive(structuredClone(snapshot))
      expect(store.getSnapshot().pending).toBeNull()
      expect(vi.getTimerCount()).toBe(0)
      await store.command('find', 'keys')
      const replacement = store.getSnapshot().pending!
      snapshot.sequence++
      snapshot.data.lastCommand = {
        commandId: original.commandId,
        status: 'accepted',
        reason: null,
      }
      receive(structuredClone(snapshot))
      rejectOriginal(new Error('Late error from old phone'))
      await originalSend
      await vi.advanceTimersByTimeAsync(5000)
      expect(store.getSnapshot().pending?.commandId).toBe(replacement.commandId)
      expect(store.getSnapshot().failed).toBeNull()
      expect(store.getSnapshot().error).toBeNull()
      stop()
    },
  )
  it('reuses an uncertain command for the same action within the same device/session, including stream reconnects', async () => {
    const { store, transport, receive, snapshot, stop } = harness()
    vi.mocked(transport.send).mockRejectedValueOnce(new Error('Network error'))
    await store.command('find', 'keys')
    const original = store.getSnapshot().failed!
    snapshot.streamId = 'reconnected-server'
    snapshot.sequence = 0
    receive(structuredClone(snapshot))
    await store.command('find', 'keys')
    expect(vi.mocked(transport.send).mock.calls[1][0].commandId).toBe(
      original.commandId,
    )
    stop()
  })
})
