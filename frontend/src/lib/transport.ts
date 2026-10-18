import { commandResponseSchema, snapshotSchema } from './schema'
import type { Command, Snapshot } from './schema'

export type Connection = 'connecting' | 'live' | 'stale' | 'offline'
export interface Transport {
  start: (
    snapshot: (value: Snapshot) => void,
    connection: (value: Connection, error?: string) => void,
  ) => () => void
  send: (command: Command) => Promise<void>
}

export function apiUrl(
  base: string,
  path: string,
  origin = window.location.origin,
) {
  return new URL(`${base.replace(/\/$/, '')}${path}`, origin).toString()
}

export function createApiTransport(base: string): Transport {
  return {
    start(onSnapshot, onConnection) {
      let stopped = false
      let socket: WebSocket | undefined
      let retry: ReturnType<typeof setTimeout> | undefined
      let abort: AbortController | undefined
      let attempts = 0
      let lastProgress = Date.now()
      let current: Snapshot | undefined
      let authFailed = false
      const receive = (raw: unknown) => {
        if (stopped || authFailed) return
        if (
          typeof raw === 'object' &&
          raw &&
          'type' in raw &&
          raw.type !== 'dashboard.snapshot'
        )
          return
        const parsed = snapshotSchema.safeParse(raw)
        if (!parsed.success) {
          onConnection(
            'stale',
            'Server data does not match the dashboard contract.',
          )
          return
        }
        const value = parsed.data
        if (
          current?.streamId === value.streamId &&
          current.sequence >= value.sequence
        )
          return
        current = value
        lastProgress = Date.now()
        attempts = 0
        onSnapshot(value)
        onConnection('live')
      }
      const schedule = () => {
        if (!stopped && !authFailed && retry === undefined)
          retry = setTimeout(
            () => {
              retry = undefined
              void connect()
            },
            Math.min(500 * 2 ** attempts++, 5000),
          )
      }
      const disconnect = (closed: WebSocket, close = true) => {
        if (stopped || authFailed || socket !== closed) return
        // Detach first: error, close and heartbeat may all report the same dead socket.
        socket = undefined
        if (close) closed.close()
        onConnection('offline')
        schedule()
      }
      const connect = async () => {
        if (stopped || authFailed) return
        lastProgress = Date.now() // Also bounds the wait for a first valid snapshot.
        const controller = new AbortController()
        abort = controller
        const timeout = setTimeout(() => controller.abort(), 5000)
        try {
          const response = await fetch(apiUrl(base, '/dashboard/snapshot'), {
            credentials: 'include',
            signal: controller.signal,
          })
          if (stopped) return
          if (response.status === 401 || response.status === 403) {
            authFailed = true
            onConnection(
              'offline',
              'Dashboard access denied. Check the server session.',
            )
            return
          }
          if (!response.ok) throw new Error('Could not load the dashboard.')
          receive(await response.json())
        } catch {
          if (!stopped)
            onConnection('offline', 'Cannot reach the server. Reconnecting…')
        } finally {
          clearTimeout(timeout)
        }
        if (stopped || authFailed) return
        const url = new URL(apiUrl(base, '/events'))
        url.protocol = url.protocol === 'https:' ? 'wss:' : 'ws:'
        try {
          const connected = new WebSocket(url)
          socket = connected
          connected.onmessage = (event) => {
            if (stopped || socket !== connected) return
            try {
              receive(JSON.parse(String(event.data)))
            } catch {
              onConnection('stale', 'Could not read a server update.')
            }
          }
          connected.onclose = () => disconnect(connected, false)
          connected.onerror = () => disconnect(connected)
        } catch {
          onConnection(
            'offline',
            'Cannot open the live connection. Reconnecting…',
          )
          schedule()
        }
      }
      const heartbeat = setInterval(() => {
        if (stopped || authFailed || retry !== undefined) return
        const silence = Date.now() - lastProgress
        if (silence > 10000 && socket) disconnect(socket)
        else if (silence > 3000) onConnection('stale')
      }, 500)
      void connect()
      return () => {
        stopped = true
        clearInterval(heartbeat)
        clearTimeout(retry)
        abort?.abort()
        socket?.close()
      }
    },
    async send(command) {
      const response = await fetch(apiUrl(base, '/dashboard/commands'), {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(command),
        signal: AbortSignal.timeout(8000),
      })
      if (!response.ok) {
        const body = await response.json().catch(() => null)
        throw new Error(
          body?.error?.message || `Command failed (${response.status}).`,
        )
      }
      const result = commandResponseSchema.parse(await response.json())
      if (response.status !== 202 || result.commandId !== command.commandId)
        throw new Error('Unexpected command acknowledgement.')
    },
  }
}
