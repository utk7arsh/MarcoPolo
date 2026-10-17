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
  close() {
    this.onclose?.()
  }
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
})
