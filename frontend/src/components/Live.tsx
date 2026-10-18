import { useState } from 'react'
import type { DashboardData } from '../lib/schema'
import {
  ago,
  direction,
  guidanceIssue,
  location,
  mapPositionIsLive,
} from '../lib/format'
import { Icon } from './Icon'
import { EmptyState, ItemImage } from './Shared'
import { MapView } from './MapView'
import { CameraView } from './CameraView'
import { ListenButton, ListeningHead, SoundCaption } from './Hearing'
import { captionOf, playing } from '../lib/hearing'
import type { Heard } from '../lib/hearing'

export function Live({
  now,
  data,
  online,
  pending,
  pendingTarget,
  onStop,
  onObjects,
  demo,
  heard,
  listen,
}: {
  now: number
  data: DashboardData
  online: boolean
  pending: boolean
  pendingTarget: string | null
  onStop: () => void
  onObjects: () => void
  demo: boolean
  heard: Heard
  listen: { on: boolean; onToggle: () => void }
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
  const mapLive = mapPositionIsLive(data, online, now)
  const audioActive =
    active &&
    data.devices.airpods.state === 'connected' &&
    nav.audioPattern !== 'off'
  // What the wearer hears runs through every view: the map, the camera and this panel draw the same stream.
  const caption = captionOf(heard, active ? nav.spokenInstruction : null)
  const nowPlaying = playing(heard, caption)
  const sound = (
    <div className="spoken-guidance">
      <div className="spoken-guidance-row">
        <span className="label">
          <Icon
            name="speaker"
            size={15}
            className={heard.speaking ? 'speaking' : ''}
          />
          {data.devices.airpods.state !== 'connected'
            ? 'AirPods disconnected'
            : nowPlaying
              ? `Playing in AirPods: ${nowPlaying}`
              : audioActive
                ? 'Playing in AirPods'
                : 'Nothing playing in AirPods'}
        </span>
        <ListenButton on={listen.on} onToggle={listen.onToggle} />
      </div>
      <SoundCaption caption={caption} speaking={heard.speaking} />
    </div>
  )
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
            <div className="view-switch" aria-label="Live view mode">
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
            <MapView
              data={data}
              live={mapLive}
              targetId={item?.id || null}
              heard={heard}
            />
          ) : (
            <CameraView
              now={now}
              data={data}
              online={online && data.devices.phone.state === 'connected'}
              targetId={item?.id || null}
              demo={demo}
              heard={heard}
            />
          )}
        </section>
        <aside className="guidance-panel" aria-label="Navigation guidance">
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
              <div
                className={`direction-display ${found ? 'found' : active ? 'guiding' : ''}`}
              >
                {found ? (
                  <>
                    <span className="direction-circle">
                      <Icon name="check" size={38} />
                    </span>
                    <h2>Found it.</h2>
                  </>
                ) : active ? (
                  <>
                    <span className="direction-circle listening">
                      <ListeningHead
                        heard={heard}
                        bearingDeg={nav.bearingDeg}
                      />
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
                          ? direction(nav.bearingDeg).replace(', ', ',\n')
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
              {(active || found || caption) && sound}
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
                    <Icon name="stop" size={16} />
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
              {caption && sound}
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
