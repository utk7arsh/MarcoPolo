import type { Command, Snapshot, Sound } from './schema'
import { hear, initialHearing } from './sound'
import type { Hearing } from './sound'
import type { Connection, Transport } from './transport'

export type DashboardState = {
  snapshot: Snapshot | null
  connection: Connection
  error: string | null
  connectionError: string | null
  pending: Command | null
  failed: Command | null
}

type CommandScope = { sessionId: string; deviceId: string }

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
  // What the wearer hears arrives up to 10 times a second: its listeners get each sound directly, outside the app
  // state, so the rest of the dashboard doesn't re-render for it.
  // The store folds every sound into `hearing`, so a view opened mid-sentence (or after a reconnect) starts from what
  // is audible now, not from silence.
  private soundListeners = new Set<(sound: Sound) => void>()
  private hearing: Hearing = initialHearing
  getHearing = () => this.hearing
  private timeout?: ReturnType<typeof setTimeout>
  private commandScope: CommandScope | null = null
  constructor(private transport: Transport) {}
  getSnapshot = () => this.state
  subscribe = (listener: () => void) => {
    this.listeners.add(listener)
    return () => {
      this.listeners.delete(listener)
    }
  }
  subscribeSound = (listener: (sound: Sound) => void) => {
    this.soundListeners.add(listener)
    return () => {
      this.soundListeners.delete(listener)
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
        const replaced =
          previous &&
          (previous.data.session.id !== snapshot.data.session.id ||
            previous.data.session.deviceId !== snapshot.data.session.deviceId)
        if (replaced) {
          clearTimeout(this.timeout)
          this.timeout = undefined
          this.commandScope = null
        }
        this.update({
          snapshot,
          ...(replaced ? { pending: null, failed: null, error: null } : {}),
        })
        const command = snapshot.data.lastCommand
        if (
          command &&
          (command.commandId === this.state.pending?.commandId ||
            command.commandId === this.state.failed?.commandId) &&
          command.status !== 'pending'
        ) {
          clearTimeout(this.timeout)
          this.timeout = undefined
          this.commandScope = null
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
      (sound) => {
        this.hearing = hear(this.hearing, sound, Date.now())
        this.soundListeners.forEach((listener) => listener(sound))
      },
    )
    return () => {
      stop()
      clearTimeout(this.timeout)
    }
  }
  dismissError = () =>
    this.update({ error: null, connectionError: null, failed: null })
  retry = async () => {
    if (this.state.failed && this.scopeIsCurrent(this.commandScope))
      await this.send(this.state.failed, this.commandScope!)
  }
  private scopeIsCurrent(scope: CommandScope | null) {
    const session = this.state.snapshot?.data.session
    return !!(
      scope &&
      session?.id === scope.sessionId &&
      session.deviceId === scope.deviceId
    )
  }
  async command(type: 'find' | 'stop', itemId?: string) {
    const session = this.state.snapshot?.data.session
    const deviceId = session?.deviceId
    if (!deviceId || this.state.pending || (type === 'find' && !itemId)) return
    const scope = { sessionId: session.id, deviceId }
    const failed = this.state.failed
    const same =
      this.scopeIsCurrent(this.commandScope) &&
      failed?.deviceId === deviceId &&
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
    await this.send(command, scope)
  }
  private async send(command: Command, scope: CommandScope) {
    if (
      this.state.pending ||
      command.deviceId !== scope.deviceId ||
      !this.scopeIsCurrent(scope)
    )
      return
    this.commandScope = scope
    this.update({ pending: command, failed: null, error: null })
    this.timeout = setTimeout(() => {
      if (
        !this.scopeIsCurrent(scope) ||
        this.state.pending?.commandId !== command.commandId
      )
        return
      this.update({
        pending: null,
        failed: command,
        error: 'The iPhone has not acknowledged this request.',
      })
    }, 10000)
    try {
      await this.transport.send(command)
    } catch (error) {
      if (
        !this.scopeIsCurrent(scope) ||
        this.getSnapshot().pending?.commandId !== command.commandId
      )
        return
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
