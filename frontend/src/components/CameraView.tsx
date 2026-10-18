import { useState } from 'react'
import type { DashboardData } from '../lib/schema'
import { mediaUrl } from '../lib/format'
import { fromBody, headYaw } from '../lib/sound'
import { EmptyState } from './Shared'
import { ripples } from '../lib/hearing'
import type { Heard } from '../lib/hearing'

export function CameraView({
  now,
  data,
  targetId,
  online,
  demo,
  heard = null,
}: {
  now: number
  data: DashboardData
  targetId: string | null
  online: boolean
  demo: boolean
  heard?: Heard | null
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
  // What the wearer hears, in the picture: a sound from the item ripples on its box when the camera sees it, and
  // otherwise pulses on the edge it is beyond (the bottom edge for behind). The camera faces where the body does.
  const box = boxes[0]?.boxPx
  const yaw = heard ? headYaw(heard.hearing, heard.now, data.wearer) : null
  const heardHere = heard
    ? ripples(heard).filter((r) => r.anchor !== 'ahead' && r.cue !== 'blip')
    : []
  const edge = (azimuthDeg: number) => {
    const a = fromBody(azimuthDeg, yaw, data.wearer?.bodyYawDeg ?? null)
    return Math.abs(a) > 120
      ? 'behind'
      : a > 25
        ? 'right'
        : a < -25
          ? 'left'
          : null
  }
  return (
    <div className="camera-canvas">
      <div
        className="camera-frame"
        style={{ aspectRatio: `${camera.widthPx} / ${camera.heightPx}` }}
      >
        {heardHere.map((r) => {
          const side =
            box && r.anchor === 'item' ? null : edge(r.from.azimuthDeg)
          return side ? (
            <span
              key={r.id}
              className={`sound-edge ${side} ${r.muffled ? 'muffled' : ''}`}
              aria-hidden="true"
            />
          ) : null
        })}
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
            {box &&
              heardHere
                .filter((r) => r.anchor === 'item')
                .map((r) => (
                  <g
                    key={r.id}
                    transform={`translate(${(box[0] + box[2]) / 2} ${(box[1] + box[3]) / 2})`}
                  >
                    <circle
                      className={`sound-ripple camera ${r.muffled ? 'muffled' : ''} ${['say', 'label'].includes(r.cue) ? 'voice' : ''} ${r.cue}`}
                      r={Math.max(box[2] - box[0], box[3] - box[1]) * 0.9}
                    />
                  </g>
                ))}
          </svg>
        )}
      </div>
      <span className="camera-caption">
        {demo ? 'Demo frame' : 'Chest camera'}
      </span>
    </div>
  )
}
