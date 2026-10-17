import { useState } from 'react'
import type { DashboardData, Item } from '../lib/schema'
import { ago, guidanceIssue, location } from '../lib/format'
import { Icon } from './Icon'
import { EmptyState, ItemImage, VoiceLabel } from './Shared'

export function Objects({
  now,
  data,
  online,
  selectedId,
  onSelect,
  onFind,
  pending,
  onPhoton,
}: {
  now: number
  data: DashboardData
  online: boolean
  selectedId: string | null
  onSelect: (id: string) => void
  onFind: (item: Item) => void
  pending: boolean
  onPhoton: (id?: string) => void
}) {
  const [query, setQuery] = useState('')
  const items = data.items.filter((item) =>
    `${item.name} ${location(item)}`
      .toLowerCase()
      .includes(query.toLowerCase()),
  )
  const selected =
    data.items.find((item) => item.id === selectedId) || data.items[0]
  const requests = data.registrations.filter((r) => r.status !== 'saved')
  const issue = selected ? guidanceIssue(data, online, selected, now) : null
  return (
    <>
      <div className="page-heading">
        <div>
          <h1>Objects</h1>
          <p>
            {data.items.length} {data.items.length === 1 ? 'object' : 'objects'}
            <span className="middle-dot">·</span>
            {data.session.roomName}
          </p>
        </div>
        <button
          className="button secondary photon-button"
          onClick={() => onPhoton()}
        >
          Photon labels
          {requests.length > 0 && (
            <span className="count">{requests.length}</span>
          )}
        </button>
      </div>
      {data.items.length === 0 ? (
        <div className="panel library-empty">
          <EmptyState
            title="No objects yet"
            detail="Objects added through Photon will appear here."
          />
          <button className="button secondary" onClick={() => onPhoton()}>
            Photon labels
          </button>
        </div>
      ) : (
        <div className="objects-layout">
          <section className="panel object-library" aria-label="Object library">
            <div className="library-heading">
              <h2>
                All objects <span>· {data.items.length}</span>
              </h2>
              <label className="search">
                <Icon name="search" size={17} />
                <input
                  aria-label="Search objects"
                  placeholder="Search objects"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                />
                {query && (
                  <button
                    aria-label="Clear search"
                    className="icon-button"
                    onClick={() => setQuery('')}
                  >
                    <Icon name="close" size={15} />
                  </button>
                )}
              </label>
            </div>
            <div className="object-list">
              {items.map((item) => (
                <button
                  key={item.id}
                  className={`object-row ${selected?.id === item.id ? 'selected' : ''}`}
                  aria-pressed={selected?.id === item.id}
                  onClick={() => onSelect(item.id)}
                >
                  <ItemImage item={item} />
                  <span className="object-meta">
                    <strong>{item.name}</strong>
                    <span>{location(item)}</span>
                  </span>
                  <span className="row-time">
                    {item.lastSeen
                      ? ago(item.lastSeen.at, now)
                      : 'Not seen yet'}
                  </span>
                  <Icon name="chevron" size={15} />
                </button>
              ))}
              {items.length === 0 && (
                <EmptyState icon="search" title="No matches" />
              )}
            </div>
            {requests.length > 0 && (
              <div className="photon-summary">
                <div>
                  <span className="eyebrow">Photon labels</span>
                  <p>
                    <span className="dot blue" />
                    {data.items.find((i) => i.id === requests[0].itemId)
                      ?.name || 'New object'}{' '}
                    ·{' '}
                    {requests[0].status === 'waiting_for_label'
                      ? 'Awaiting label'
                      : requests[0].status === 'processing_label'
                        ? 'Processing label'
                        : requests[0].status === 'failed'
                          ? 'Label failed'
                          : requests[0].status === 'retake'
                            ? 'New photo needed'
                            : 'Photo received'}
                  </p>
                </div>
                <button
                  className="text-button"
                  onClick={() => onPhoton(requests[0].id)}
                >
                  View request <Icon name="chevron" size={14} />
                </button>
              </div>
            )}
          </section>
          {selected && (
            <aside
              className="panel object-detail"
              aria-label={`${selected.name} details`}
            >
              <div className="detail-title">
                <ItemImage item={selected} large />
                <h2>{selected.name}</h2>
              </div>
              <div className="last-seen">
                <span className="label">Last seen</span>
                <h3>{location(selected)}</h3>
                {selected.lastSeen && (
                  <p>
                    {selected.lastSeen.roomName}
                    <span className="middle-dot">·</span>
                    {ago(selected.lastSeen.at, now)}
                  </p>
                )}
              </div>
              <VoiceLabel item={selected} key={selected.id} />
              {data.recentMemory.some((m) => m.itemId === selected.id) && (
                <div className="history">
                  <h3 className="label">History</h3>
                  {data.recentMemory
                    .filter((m) => m.itemId === selected.id)
                    .sort((a, b) => Date.parse(b.at) - Date.parse(a.at))
                    .map((memory) => (
                      <div className="history-row" key={memory.id}>
                        <span>
                          {memory.kind === 'label_saved'
                            ? 'Label saved'
                            : memory.surface ||
                              selected.lastSeen?.roomName ||
                              'Seen'}
                          {memory.kind === 'moved' && (
                            <span className="moved-label">Moved</span>
                          )}
                        </span>
                        <time dateTime={memory.at}>{ago(memory.at, now)}</time>
                      </div>
                    ))}
                </div>
              )}
              <div className="find-action">
                <button
                  className="button primary"
                  disabled={pending || !!issue}
                  onClick={() => onFind(selected)}
                >
                  <Icon
                    name="arrow"
                    size={16}
                    style={{ transform: 'rotate(35deg)' }}
                  />
                  {pending
                    ? 'Requesting…'
                    : `Find ${selected.name.toLowerCase()}`}
                </button>
                {issue && <span className="action-reason">{issue}</span>}
              </div>
            </aside>
          )}
        </div>
      )}
    </>
  )
}
