import { useEffect, useState, useSyncExternalStore } from 'react'
import type { DashboardStore } from './lib/store'
import type { createDemoTransport, Scenario } from './data/demo'
import { scenarios } from './data/demo'
import { useNow } from './lib/useNow'
import { Objects } from './components/Objects'
import { Live } from './components/Live'
import { Icon } from './components/Icon'
import { Dialog } from './components/Dialog'
import { Photon } from './components/Photon'
import { EmptyState } from './components/Shared'

export function App({
  store,
  demo,
}: {
  store: DashboardStore
  demo?: ReturnType<typeof createDemoTransport>
}) {
  const now = useNow()
  const state = useSyncExternalStore(store.subscribe, store.getSnapshot)
  const [page, setPage] = useState(() =>
    window.location.hash === '#live' ? 'live' : 'objects',
  )
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [dialog, setDialog] = useState<'photon' | 'devices' | 'demo' | null>(
    null,
  )
  const [requestId, setRequestId] = useState<string | null>(null)
  const [scenario, setScenario] = useState<Scenario>('guiding')
  useEffect(() => store.start(), [store])
  useEffect(() => {
    const change = () =>
      setPage(window.location.hash === '#live' ? 'live' : 'objects')
    window.addEventListener('hashchange', change)
    return () => window.removeEventListener('hashchange', change)
  }, [])
  const navigate = (next: 'live' | 'objects') => {
    window.location.hash = next
    setPage(next)
  }
  const data = state.snapshot?.data
  const error = state.error || state.connectionError
  const online = state.connection === 'live'
  const connected =
    online &&
    data?.devices.phone.state === 'connected' &&
    data?.devices.airpods.state === 'connected'
  const deviceLabel = !online
    ? state.connection === 'connecting'
      ? 'Connecting'
      : 'Disconnected'
    : data?.devices.phone.state !== 'connected'
      ? 'iPhone disconnected'
      : data?.devices.airpods.state !== 'connected'
        ? 'AirPods disconnected'
        : 'iPhone + AirPods'
  const showPhoton = (id?: string) => {
    setRequestId(id || null)
    setDialog('photon')
  }
  return (
    <>
      <a
        href="#main-content"
        className="skip-link"
        onClick={(event) => {
          event.preventDefault()
          document.getElementById('main-content')?.focus()
        }}
      >
        Skip to content
      </a>
      <header className="app-header">
        <a href="#objects" className="brand" aria-label="Marco Polo home">
          <img src="/brand/marco-polo-mark.svg" width="32" height="32" alt="" />
          <span>Marco Polo</span>
        </a>
        <nav className="segmented main-nav" aria-label="Main navigation">
          <a
            href="#objects"
            aria-current={page === 'objects' ? 'page' : undefined}
          >
            Objects
          </a>
          <a href="#live" aria-current={page === 'live' ? 'page' : undefined}>
            Live
          </a>
        </nav>
        <div className="header-status">
          {demo && (
            <button className="demo-badge" onClick={() => setDialog('demo')}>
              Demo
            </button>
          )}
          <button
            className="device-button"
            onClick={() => setDialog('devices')}
            aria-label={`${deviceLabel}. Device status`}
          >
            <span className={`dot ${connected ? 'green' : 'gray'}`} />
            <span>{deviceLabel}</span>
            <Icon name="info" size={15} />
          </button>
        </div>
      </header>
      <main tabIndex={-1} id="main-content" className="main-content">
        {error && (
          <div className="error-banner" role="alert">
            <span>{error}</span>
            {state.failed && (
              <button
                className="text-button"
                onClick={() => void store.retry()}
              >
                Retry
              </button>
            )}
            <button
              className="icon-button"
              aria-label="Dismiss error"
              onClick={store.dismissError}
            >
              <Icon name="close" size={18} />
            </button>
          </div>
        )}
        {data ? (
          <>
            {!online && (
              <div className="connection-banner" role="status">
                <Icon name="signal" size={16} />
                Connection lost. Showing last-seen memory.
              </div>
            )}
            {page === 'objects' ? (
              <Objects
                now={now}
                data={data}
                online={online}
                selectedId={selectedId}
                onSelect={setSelectedId}
                pending={!!state.pending}
                onPhoton={showPhoton}
                onFind={(item) => {
                  setSelectedId(item.id)
                  void store.command('find', item.id)
                  navigate('live')
                }}
              />
            ) : (
              <Live
                now={now}
                data={data}
                online={online}
                demo={!!demo}
                pending={!!state.pending}
                pendingTarget={
                  state.pending?.type === 'find' ? state.pending.itemId : null
                }
                onStop={() => void store.command('stop')}
                onObjects={() => navigate('objects')}
              />
            )}
          </>
        ) : (
          <div className="panel initial-state">
            {state.connection === 'connecting' ? (
              <>
                <span className="loading-indicator" />
                <p>Connecting…</p>
              </>
            ) : (
              <EmptyState icon="signal" title="Waiting for the server" />
            )}
          </div>
        )}
      </main>
      {dialog === 'photon' && data && (
        <Photon
          now={now}
          data={data}
          initialId={requestId}
          onClose={() => setDialog(null)}
        />
      )}
      {dialog === 'devices' && (
        <Dialog title="Devices" onClose={() => setDialog(null)}>
          <dl className="device-list">
            <div>
              <dt>Dashboard</dt>
              <dd>
                {online
                  ? 'Connected'
                  : state.connection === 'connecting'
                    ? 'Connecting'
                    : 'Disconnected'}
              </dd>
            </div>
            <div>
              <dt>iPhone</dt>
              <dd>{data?.devices.phone.state || 'Unknown'}</dd>
            </div>
            <div>
              <dt>AirPods</dt>
              <dd>{data?.devices.airpods.state || 'Unknown'}</dd>
            </div>
            <div>
              <dt>Tracking</dt>
              <dd>{data?.devices.phone.tracking || 'Unknown'}</dd>
            </div>
          </dl>
        </Dialog>
      )}
      {dialog === 'demo' && demo && (
        <Dialog title="Demo scenarios" onClose={() => setDialog(null)}>
          <div className="scenario-list">
            {scenarios.map(([id, name]) => (
              <button
                key={id}
                className={`scenario-button ${id === scenario ? 'selected' : ''}`}
                onClick={() => {
                  demo.setScenario(id)
                  setScenario(id)
                  setDialog(null)
                }}
              >
                {name}
                {id === scenario && <Icon name="check" size={18} />}
              </button>
            ))}
          </div>
        </Dialog>
      )}
    </>
  )
}
