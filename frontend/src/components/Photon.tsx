import { useState } from 'react'
import type { DashboardData, Registration } from '../lib/schema'
import { ago } from '../lib/format'
import { Dialog } from './Dialog'
import { EmptyState, ItemImage, VoiceLabel } from './Shared'
import { Icon } from './Icon'

const status: Record<Registration['status'], string> = {
  photo_received: 'Photo received',
  waiting_for_label: 'Awaiting label',
  processing_label: 'Processing label',
  saved: 'Label saved',
  retake: 'New photo needed',
  failed: 'Label failed',
}
export function Photon({
  now,
  data,
  initialId,
  onClose,
}: {
  now: number
  data: DashboardData
  initialId: string | null
  onClose: () => void
}) {
  const [selectedId, setSelectedId] = useState(initialId)
  const request =
    data.registrations.find((r) => r.id === selectedId) || data.registrations[0]
  const item = data.items.find((i) => i.id === request?.itemId)
  return (
    <Dialog title="Photon labels" onClose={onClose} drawer>
      {data.registrations.length === 0 ? (
        <EmptyState icon="camera" title="No label requests" />
      ) : (
        <>
          {data.registrations.length > 1 && (
            <label className="field-label">
              Request
              <select
                value={request?.id}
                onChange={(e) => setSelectedId(e.target.value)}
              >
                {data.registrations.map((r) => (
                  <option value={r.id} key={r.id}>
                    {data.items.find((i) => i.id === r.itemId)?.name ||
                      'New object'}{' '}
                    · {status[r.status]}
                  </option>
                ))}
              </select>
            </label>
          )}
          {request && (
            <>
              <div className="photon-item">
                <ItemImage
                  item={{
                    name: item?.name || 'New object',
                    photoUrl: request.photoUrl || item?.photoUrl || null,
                  }}
                  large
                />
                <h3>{item?.name || 'New object'}</h3>
              </div>
              <div
                className={`request-state ${request.status === 'saved' ? 'saved' : ''}`}
              >
                <Icon
                  name={
                    request.status === 'saved'
                      ? 'check'
                      : request.status === 'failed' ||
                          request.status === 'retake'
                        ? 'info'
                        : 'signal'
                  }
                />
                <span>{status[request.status]}</span>
              </div>
              <dl className="request-data">
                {request.recipientName && (
                  <div>
                    <dt>Sent to</dt>
                    <dd>{request.recipientName}</dd>
                  </div>
                )}
                <div>
                  <dt>Updated</dt>
                  <dd>{ago(request.updatedAt, now)}</dd>
                </div>
              </dl>
              {request.message && (
                <p className="request-message">{request.message}</p>
              )}
              {request.label && (
                <VoiceLabel
                  key={request.id}
                  item={{
                    id: request.id,
                    name: item?.name || 'New object',
                    photoUrl: request.photoUrl,
                    voiceLabel: request.label,
                    lastSeen: null,
                  }}
                />
              )}
            </>
          )}
        </>
      )}
    </Dialog>
  )
}
