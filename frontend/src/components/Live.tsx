import { useState } from 'react'
import type { DashboardData } from '../lib/schema'
import { ago, direction, guidanceIssue, location } from '../lib/format'
import { Icon } from './Icon'
import { EmptyState, ItemImage } from './Shared'
import { MapView } from './MapView'
import { CameraView } from './CameraView'

export function Live({
  now,
  data,
  online,
  pending,
  pendingTarget,
  onStop,
  onObjects,
  demo,
}: {
  now: number
  data: DashboardData
  online: boolean
  pending: boolean
  pendingTarget: string | null
  onStop: () => void
  onObjects: () => void
  demo: boolean
}) {
  const [view, setView] = useState<'map' | 'camera'>('map')
  const nav = data.navigation
  const item = data.items.find(
    (i) => i.id === (pendingTarget || nav.targetItemId),
  )
  const issue = guidanceIssue(data, online, item, now)
  const staleNavigation = now - Date.parse(nav.updatedAt) > 5000
  const active =
    !pendingTarget &&
    (nav.state === 'guiding' || nav.state === 'within_reach') &&
    !issue &&
    !staleNavigation
  const found = !pendingTarget && nav.state === 'found' && !issue
  const title = !online
    ? 'Connection lost'
    : pendingTarget
      ? `Finding ${item?.name.toLowerCase() || 'object'}`
      : found
        ? 'Got it.'
        : nav.state === 'within_reach'
          ? 'Within reach'
          : item
            ? `Finding ${item.name.toLowerCase()}`
            : 'Live'
  const status = !online
    ? 'Reconnecting'
    : pending
      ? 'Request pending'
      : issue && item
        ? issue
        : found
          ? 'Object found'
          : active
            ? 'Guidance active'
            : nav.state === 'paused'
              ? 'Guidance paused'
              : 'Ready'
  const mapLive =
    online &&
    data.devices.phone.state === 'connected' &&
    data.devices.phone.tracking === 'normal' &&
    !!data.devices.phone.lastMessageAt &&
    now - Date.parse(data.devices.phone.lastMessageAt) < 5000 &&
    !!data.wearer &&
    now - Date.parse(data.wearer.at) < 5000
  const audioActive =
    active &&
    data.devices.airpods.state === 'connected' &&
    nav.audioPattern !== 'off'
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>{title}</h1>
          <p>{data.session.roomName}</p>
        </div>
        <span
          className={`status-pill ${active ? 'active' : found ? 'success' : ''}`}
          role="status"
        >
          <span
            className={`dot ${active ? 'blue' : found ? 'green' : 'gray'}`}
          />
          {status}
        </span>
      </div>
      <div className="live-layout">
        <section className="panel live-viewport" aria-label="Live view">
          <div className="viewport-toolbar">
            <div className="segmented small" aria-label="Live view mode">
              <button
                aria-pressed={view === 'map'}
                onClick={() => setView('map')}
              >
                Map
              </button>
              <button
                aria-pressed={view === 'camera'}
                onClick={() => setView('camera')}
              >
                Camera
              </button>
            </div>
            <span className="position-status">
              <span className={`dot ${mapLive ? 'green' : 'gray'}`} />
              {mapLive ? 'Live position' : 'Position unavailable'}
            </span>
          </div>
          {view === 'map' ? (
            <MapView data={data} live={mapLive} targetId={item?.id || null} />
          ) : (
            <CameraView
              now={now}
              data={data}
              online={online && data.devices.phone.state === 'connected'}
              targetId={item?.id || null}
              demo={demo}
            />
          )}
        </section>
        <aside
          className="panel guidance-panel"
          aria-label="Navigation guidance"
        >
          {item ? (
            <>
              <div className="guidance-item">
                <ItemImage item={item} />
                <div>
                  <h2>{item.name}</h2>
                  <p>
                    {location(item)}
                    {item.lastSeen && (
                      <>
                        <span className="middle-dot">·</span>Seen{' '}
                        {ago(item.lastSeen.at, now).toLowerCase()}
                      </>
                    )}
                  </p>
                </div>
              </div>
              <div className={`direction-display ${found ? 'found' : ''}`}>
                {found ? (
                  <>
                    <span className="direction-circle">
                      <Icon name="check" size={38} />
                    </span>
                    <h2>Found it.</h2>
                  </>
                ) : active ? (
                  <>
                    <span className="direction-circle">
                      {nav.bearingDeg !== null ? (
                        <Icon
                          name="arrow"
                          size={48}
                          style={{ transform: `rotate(${nav.bearingDeg}deg)` }}
                        />
                      ) : (
                        <Icon name="recenter" size={40} />
                      )}
                    </span>
                    {nav.distanceM !== null && (
                      <div
                        className="distance"
                        aria-label={`${nav.distanceM.toFixed(nav.distanceM < 1 ? 2 : 1)} meters`}
                      >
                        <span>
                          {nav.distanceM.toFixed(nav.distanceM < 1 ? 2 : 1)}
                        </span>
                        <span className="distance-unit">m</span>
                      </div>
                    )}
                    <p>
                      {nav.state === 'within_reach'
                        ? 'Within reach'
                        : nav.bearingDeg !== null
                          ? direction(nav.bearingDeg)
                          : 'Direction unavailable'}
                    </p>
                  </>
                ) : (
                  <>
                    <span className="direction-circle muted">
                      <Icon name={pending ? 'signal' : 'phone'} size={32} />
                    </span>
                    <h2>
                      {pending
                        ? 'Waiting for iPhone'
                        : issue ||
                          (staleNavigation
                            ? 'Waiting for guidance'
                            : nav.state === 'paused'
                              ? 'Guidance paused'
                              : 'Location unavailable')}
                    </h2>
                  </>
                )}
              </div>
              {active && (
                <div className="spoken-guidance">
                  <span className="label">
                    <Icon name="speaker" size={15} />
                    {audioActive
                      ? 'Playing in AirPods'
                      : data.devices.airpods.state !== 'connected'
                        ? 'AirPods disconnected'
                        : 'Audio paused'}
                  </span>
                  {nav.spokenInstruction && <p>{nav.spokenInstruction}</p>}
                </div>
              )}
              <div className="guidance-actions">
                {found ? (
                  <button className="button secondary" onClick={onObjects}>
                    Back to objects
                  </button>
                ) : (
                  <button
                    className="button secondary"
                    disabled={
                      pending ||
                      !online ||
                      data.devices.phone.state !== 'connected'
                    }
                    onClick={onStop}
                  >
                    {pending ? 'Requesting…' : 'Stop finding'}
                  </button>
                )}
              </div>
            </>
          ) : (
            <div className="idle-guidance">
              <EmptyState icon="key" title="Ready when you are" />
              <button className="button primary" onClick={onObjects}>
                Choose an object
              </button>
            </div>
          )}
        </aside>
      </div>
      <details className="session-details">
        <summary>
          Session details <Icon name="chevron" size={14} />
        </summary>
        <dl>
          <div>
            <dt>Room</dt>
            <dd>{data.session.roomName}</dd>
          </div>
          <div>
            <dt>Tracking</dt>
            <dd>{data.devices.phone.tracking}</dd>
          </div>
          <div>
            <dt>Audio</dt>
            <dd>{data.devices.airpods.state}</dd>
          </div>
          <div>
            <dt>Session</dt>
            <dd>{data.session.id}</dd>
          </div>
        </dl>
      </details>
    </>
  )
}
