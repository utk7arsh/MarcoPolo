import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { demoSnapshot } from '../data/demo'
import { apiUrl, createApiTransport } from './transport'

class Socket {
  static instances: Socket[] = []
  onmessage?: (event: { data: string }) => void
  onclose?: () => void
  onerror?: () => void
  constructor(readonly url: string) {
    Socket.instances.push(this)
  }
  close = vi.fn(() => {
    this.onclose?.()
  })
  receive(value: unknown) {
    this.onmessage?.({ data: JSON.stringify(value) })
  }
}
beforeEach(() => {
  vi.useFakeTimers()
  Socket.instances = []
  vi.stubGlobal('window', { location: { origin: 'https://dashboard.test' } })
  vi.stubGlobal('WebSocket', Socket)
  vi.stubGlobal(
    'fetch',
    vi.fn(
      async () => new Response(JSON.stringify(demoSnapshot()), { status: 200 }),
    ),
  )
})
afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
})
describe('FastAPI transport', () => {
  it('joins same-origin and remote bases and converts the websocket scheme', async () => {
    expect(apiUrl('/api', '/events')).toBe('https://dashboard.test/api/events')
    expect(apiUrl('http://localhost:8000/', '/dashboard/snapshot')).toBe(
      'http://localhost:8000/dashboard/snapshot',
    )
    const stop = createApiTransport('/api').start(vi.fn(), vi.fn())
    await vi.advanceTimersByTimeAsync(0)
    expect(String(Socket.instances[0].url)).toBe(
      'wss://dashboard.test/api/events',
    )
    stop()
  })
  it('validates snapshots, ignores older sequences and marks silent streams stale', async () => {
    const receive = vi.fn(),
      connection = vi.fn()
    const stop = createApiTransport('/api').start(receive, connection)
    await vi.advanceTimersByTimeAsync(0)
    const socket = Socket.instances[0]
    socket.receive(demoSnapshot())
    expect(receive).toHaveBeenCalledTimes(1)
    socket.receive({ type: 'other.event' })
    expect(receive).toHaveBeenCalledTimes(1)
    socket.receive({ type: 'dashboard.snapshot' })
    expect(connection).toHaveBeenLastCalledWith(
      'stale',
      expect.stringContaining('contract'),
    )
    const newer = demoSnapshot()
    newer.sequence = 2
    socket.receive(newer)
    expect(receive).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(3500)
    expect(connection).toHaveBeenLastCalledWith('stale')
    stop()
  })
  it('fetches a fresh snapshot on reconnect and stops after disposal', async () => {
    const stop = createApiTransport('/api').start(vi.fn(), vi.fn())
    await vi.advanceTimersByTimeAsync(0)
    Socket.instances[0].close()
    await vi.advanceTimersByTimeAsync(500)
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(Socket.instances).toHaveLength(2)
    stop()
    await vi.advanceTimersByTimeAsync(10000)
    expect(fetch).toHaveBeenCalledTimes(2)
  })
  it('does not retry an authorization failure or connect an unauthorized socket', async () => {
    vi.mocked(fetch).mockResolvedValue(new Response('{}', { status: 403 }))
    const connection = vi.fn()
    const stop = createApiTransport('/api').start(vi.fn(), connection)
    await vi.advanceTimersByTimeAsync(10000)
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(Socket.instances).toHaveLength(0)
    expect(connection).toHaveBeenLastCalledWith(
      'offline',
      expect.stringContaining('access denied'),
    )
    stop()
  })
  it('sends JSON commands with credentials and surfaces structured server errors', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify({ commandId: 'cmd-1', status: 'pending' }), {
        status: 202,
      }),
    )
    const transport = createApiTransport('/api')
    await transport.send({
      commandId: 'cmd-1',
      deviceId: 'phone',
      type: 'stop',
    })
    expect(fetch).toHaveBeenCalledWith(
      'https://dashboard.test/api/dashboard/commands',
      expect.objectContaining({ method: 'POST', credentials: 'include' }),
    )
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(
        JSON.stringify({
          error: {
            code: 'phone_disconnected',
            message: 'iPhone is disconnected.',
          },
        }),
        { status: 409 },
      ),
    )
    await expect(
      transport.send({ commandId: 'cmd-2', deviceId: 'phone', type: 'stop' }),
    ).rejects.toThrow('iPhone is disconnected.')
  })
  it('recovers a silent open socket, refetches and ignores messages from the detached socket', async () => {
    vi.setSystemTime(0)
    const receive = vi.fn(),
      connection = vi.fn()
    const stop = createApiTransport('/api').start(receive, connection)
    await vi.advanceTimersByTimeAsync(15000)
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(Socket.instances).toHaveLength(2)
    expect(Socket.instances[0].close).toHaveBeenCalledTimes(1)
    const old = demoSnapshot()
    old.sequence = 99
    Socket.instances[0].receive(old)
    expect(receive).toHaveBeenCalledTimes(1)
    const fresh = demoSnapshot()
    fresh.sequence = 2
    Socket.instances[1].receive(fresh)
    expect(receive).toHaveBeenLastCalledWith(fresh)
    expect(connection).toHaveBeenLastCalledWith('live')
    stop()
  })
  it('bounds a socket that never supplies a first valid snapshot', async () => {
    vi.mocked(fetch).mockResolvedValueOnce(new Response('{}', { status: 503 }))
    const receive = vi.fn()
    const stop = createApiTransport('/api').start(receive, vi.fn())
    await vi.advanceTimersByTimeAsync(10000)
    expect(receive).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1500)
    expect(Socket.instances[0].close).toHaveBeenCalledTimes(1)
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(receive).toHaveBeenCalledTimes(1)
    stop()
  })
  it('restores live state from the watchdog HTTP refetch before a new socket sends data', async () => {
    const initial = demoSnapshot()
    const recovered = structuredClone(initial)
    recovered.sequence++
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify(initial)))
      .mockResolvedValueOnce(new Response(JSON.stringify(recovered)))
    const receive = vi.fn(),
      connection = vi.fn()
    const stop = createApiTransport('/api').start(receive, connection)
    await vi.advanceTimersByTimeAsync(3500)
    expect(connection).toHaveBeenLastCalledWith('stale')
    await vi.advanceTimersByTimeAsync(7500)
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(receive).toHaveBeenLastCalledWith(recovered)
    expect(connection).toHaveBeenLastCalledWith('live')
    expect(Socket.instances).toHaveLength(2)
    stop()
  })
  it('schedules only one reconnect when error, close and heartbeat coincide', async () => {
    const stop = createApiTransport('/api').start(vi.fn(), vi.fn())
    await vi.advanceTimersByTimeAsync(0)
    const socket = Socket.instances[0]
    socket.onerror?.()
    socket.onclose?.()
    socket.onerror?.()
    await vi.advanceTimersByTimeAsync(500)
    expect(socket.close).toHaveBeenCalledTimes(1)
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(Socket.instances).toHaveLength(2)
    stop()
  })
  it('cancels a watchdog reconnect on disposal', async () => {
    const stop = createApiTransport('/api').start(vi.fn(), vi.fn())
    await vi.advanceTimersByTimeAsync(10500)
    expect(Socket.instances[0].close).toHaveBeenCalledTimes(1)
    stop()
    await vi.advanceTimersByTimeAsync(30000)
    expect(fetch).toHaveBeenCalledTimes(1)
    expect(Socket.instances).toHaveLength(1)
  })
  it('does not deliver a snapshot whose response body finishes after disposal', async () => {
    let finish!: (value: unknown) => void
    const response = new Response('{}')
    vi.spyOn(response, 'json').mockImplementation(
      () =>
        new Promise((resolve) => {
          finish = resolve
        }),
    )
    vi.mocked(fetch).mockResolvedValueOnce(response)
    const receive = vi.fn()
    const stop = createApiTransport('/api').start(receive, vi.fn())
    await vi.advanceTimersByTimeAsync(0)
    stop()
    finish(demoSnapshot())
    await vi.advanceTimersByTimeAsync(0)
    expect(receive).not.toHaveBeenCalled()
    expect(Socket.instances).toHaveLength(0)
  })
  it('stops watchdog recovery when a refetch denies authorization', async () => {
    vi.mocked(fetch)
      .mockResolvedValueOnce(new Response(JSON.stringify(demoSnapshot())))
      .mockResolvedValueOnce(new Response('{}', { status: 401 }))
    const connection = vi.fn()
    const stop = createApiTransport('/api').start(vi.fn(), connection)
    await vi.advanceTimersByTimeAsync(30000)
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(Socket.instances).toHaveLength(1)
    expect(connection).toHaveBeenLastCalledWith(
      'offline',
      expect.stringContaining('access denied'),
    )
    stop()
  })
  it('retries a websocket construction failure through the same backoff', async () => {
    let first = true
    vi.stubGlobal(
      'WebSocket',
      class extends Socket {
        constructor(url: string) {
          if (first) {
            first = false
            throw new Error('Socket unavailable')
          }
          super(url)
        }
      },
    )
    const stop = createApiTransport('/api').start(vi.fn(), vi.fn())
    await vi.advanceTimersByTimeAsync(500)
    expect(fetch).toHaveBeenCalledTimes(2)
    expect(Socket.instances).toHaveLength(1)
    stop()
  })
})

describe('what the wearer hears on /events', () => {
  const beep = (streamId: string, extra = {}) => ({
    type: 'dashboard.sound',
    schemaVersion: 1,
    streamId,
    sentAt: '2026-10-18T01:00:00.000Z',
    sound: {
      kind: 'cue',
      tDevice: 812.4,
      cue: 'beep',
      source: 'beacon',
      anchor: 'item',
      azimuthDeg: 145,
      elevationDeg: -20,
      distanceM: 2.2,
      muffled: true,
      text: null,
      durationS: null,
      audioUrl: null,
      ...extra,
    },
  })
  it('passes sounds of the current stream on, apart from snapshots, and drops the rest quietly', async () => {
    const snapshots = vi.fn(),
      connection = vi.fn(),
      sounds = vi.fn()
    const stop = createApiTransport('/api').start(snapshots, connection, sounds)
    await vi.advanceTimersByTimeAsync(0)
    const socket = Socket.instances[0]
    const stream = demoSnapshot().streamId
    socket.receive(beep(stream))
    expect(sounds).toHaveBeenCalledTimes(1)
    expect(sounds.mock.calls[0][0]).toMatchObject({
      cue: 'beep',
      azimuthDeg: 145,
      muffled: true,
    })
    socket.receive(beep('another-server'))
    socket.receive(beep(stream, { cue: 'whistle' }))
    socket.receive(beep(stream, { azimuthDeg: 400 }))
    expect(sounds).toHaveBeenCalledTimes(1)
    expect(snapshots).toHaveBeenCalledTimes(1) // the GET snapshot only: a sound is never a snapshot
    expect(connection).not.toHaveBeenCalledWith('stale', expect.anything())
    stop()
  })
  it('does not count sounds as snapshot progress', async () => {
    const connection = vi.fn()
    const stop = createApiTransport('/api').start(vi.fn(), connection, vi.fn())
    await vi.advanceTimersByTimeAsync(0)
    const socket = Socket.instances[0]
    for (let i = 0; i < 8; i++) {
      socket.receive(beep(demoSnapshot().streamId))
      await vi.advanceTimersByTimeAsync(500)
    }
    expect(connection).toHaveBeenLastCalledWith('stale')
    stop()
  })
})
