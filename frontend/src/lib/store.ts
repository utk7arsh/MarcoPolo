import type { Command, Snapshot } from './schema'
import type { Connection, Transport } from './transport'

export type DashboardState = {
  snapshot: Snapshot | null
  connection: Connection
  error: string | null
  connectionError: string | null
  pending: Command | null
  failed: Command | null
}

export class DashboardStore {
  private state: DashboardState = {
    snapshot: null,
    connection: 'connecting',
    error: null,
    connectionError: null,
    pending: null,
    failed: null,
  }
  private listeners = new Set<() => void>()
  private timeout?: ReturnType<typeof setTimeout>
  constructor(private transport: Transport) {}
  getSnapshot = () => this.state
  subscribe = (listener: () => void) => {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }
  private update(change: Partial<DashboardState>) {
    this.state = { ...this.state, ...change }
    this.listeners.forEach((listener) => listener())
  }
  start = () => {
    const stop = this.transport.start(
      (snapshot) => {
        const previous = this.state.snapshot
        if (
          previous?.streamId === snapshot.streamId &&
          snapshot.sequence <= previous.sequence
        )
          return
        this.update({ snapshot })
        const command = snapshot.data.lastCommand
        if (
          command &&
          (command.commandId === this.state.pending?.commandId ||
            command.commandId === this.state.failed?.commandId) &&
          command.status !== 'pending'
        ) {
          clearTimeout(this.timeout)
          this.update({
            pending: null,
            failed: null,
            error:
              command.status === 'rejected'
                ? command.reason || 'The iPhone could not start this request.'
                : null,
          })
        }
      },
      (connection, error) =>
        this.update({
          connection,
          connectionError:
            error ||
            (connection === 'live' ? null : this.state.connectionError),
        }),
    )
    return () => {
      stop()
      clearTimeout(this.timeout)
    }
  }
  dismissError = () =>
    this.update({ error: null, connectionError: null, failed: null })
  retry = async () => {
    if (this.state.failed) await this.send(this.state.failed)
  }
  async command(type: 'find' | 'stop', itemId?: string) {
    const deviceId = this.state.snapshot?.data.session.deviceId
    if (!deviceId || this.state.pending || (type === 'find' && !itemId)) return
    const failed = this.state.failed
    const same =
      failed?.type === type &&
      (failed.type === 'stop' || failed.itemId === itemId)
    const command = same
      ? failed
      : type === 'find'
        ? {
            commandId: crypto.randomUUID(),
            deviceId,
            type: 'find' as const,
            itemId: itemId!,
          }
        : { commandId: crypto.randomUUID(), deviceId, type: 'stop' as const }
    await this.send(command)
  }
  private async send(command: Command) {
    if (this.state.pending) return
    this.update({ pending: command, failed: null, error: null })
    this.timeout = setTimeout(() => {
      this.update({
        pending: null,
        failed: command,
        error: 'The iPhone has not acknowledged this request.',
      })
    }, 10000)
    try {
      await this.transport.send(command)
    } catch (error) {
      if (this.getSnapshot().pending?.commandId !== command.commandId) return
      clearTimeout(this.timeout)
      this.update({
        pending: null,
        failed: command,
        error:
          error instanceof Error
            ? error.message
            : 'Could not send the request.',
      })
    }
  }
}
