import { useState } from 'react'
import type { DashboardData } from '../lib/schema'
import { mediaUrl } from '../lib/format'
import { EmptyState } from './Shared'

export function CameraView({
  now,
  data,
  targetId,
  online,
  demo,
}: {
  now: number
  data: DashboardData
  targetId: string | null
  online: boolean
  demo: boolean
}) {
  const [loaded, setLoaded] = useState<string | null>(null)
  const [failed, setFailed] = useState<string | null>(null)
  const camera = data.camera
  const src = mediaUrl(camera?.imageUrl)
  const id = camera
    ? `${data.session.id}-${camera.frameId}-${camera.widthPx}-${camera.heightPx}-${src}`
    : null
  const fresh = camera && (demo || now - Date.parse(camera.capturedAt) < 10000)
  const frameFailed = id !== null && failed === id
  if (!camera || !src || !online || !fresh || frameFailed)
    return (
      <div className="camera-absent">
        <EmptyState
          icon="camera"
          title={
            !online
              ? 'Camera disconnected'
              : frameFailed
                ? 'Frame unavailable'
                : 'Waiting for camera'
          }
        />
      </div>
    )
  const boxes = camera.boxes.filter(
    (box) =>
      box.itemId === targetId &&
      box.boxPx[2] > 0 &&
      box.boxPx[3] > 0 &&
      box.boxPx[0] < camera.widthPx &&
      box.boxPx[1] < camera.heightPx,
  )
  return (
    <div className="camera-canvas">
      <div
        className="camera-frame"
        style={{ aspectRatio: `${camera.widthPx} / ${camera.heightPx}` }}
      >
        <img
          key={id}
          src={src}
          alt="Chest camera preview"
          onLoad={(event) => {
            if (
              event.currentTarget.naturalWidth === camera.widthPx &&
              event.currentTarget.naturalHeight === camera.heightPx
            )
              setLoaded(id)
            else setFailed(id)
          }}
          onError={() => setFailed(id)}
        />
        {loaded === id && (
          <svg
            viewBox={`0 0 ${camera.widthPx} ${camera.heightPx}`}
            className="camera-overlay"
            aria-label={`${boxes.length} selected object detections`}
            role="img"
          >
            {boxes.map((box, i) => {
              const [x1, y1, x2, y2] = box.boxPx
              const name =
                data.items.find((item) => item.id === box.itemId)?.name ||
                'Object'
              return (
                <g key={`${id}-${i}`}>
                  <rect
                    data-testid="detection-box"
                    x={Math.max(0, x1)}
                    y={Math.max(0, y1)}
                    width={Math.min(camera.widthPx, x2) - Math.max(0, x1)}
                    height={Math.min(camera.heightPx, y2) - Math.max(0, y1)}
                    rx="12"
                    fill="none"
                    stroke="#70b7ff"
                    strokeWidth="4"
                  />
                  <rect
                    x={x1}
                    y={Math.max(0, y1 - 48)}
                    width={name.length * 17 + 32}
                    height="44"
                    rx="8"
                    fill="#1559d6"
                  />
                  <text
                    x={x1 + 16}
                    y={Math.max(31, y1 - 17)}
                    fill="white"
                    fontSize="28"
                  >
                    {name}
                  </text>
                </g>
              )
            })}
          </svg>
        )}
      </div>
      <span className="camera-caption">
        {demo ? 'Demo frame' : 'Chest camera'}
      </span>
    </div>
  )
}
