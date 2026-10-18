import { fromSide, onScreen } from '../lib/sound'
import type { Caption } from '../lib/sound'
import { earsLit, ripples } from '../lib/hearing'
import type { Heard } from '../lib/hearing'
import { Icon } from './Icon'

// What the wearer hears, woven into every view: the room map, the camera and the guidance panel each draw the same
// stream (the phone's dashboard.sound reports, folded by the store). Nothing is reconstructed in the browser.

/** The two ears, lit by how loud each hears the last sound; for any head drawn in the views. */
export function Ears({
  heard,
  x,
  size,
}: {
  heard: Heard
  x: number
  size: [number, number]
}) {
  const lit = earsLit(heard)
  return (
    <>
      {(['left', 'right'] as const).map((side) => (
        <rect
          key={`${side}-${heard.hearing.ears.at}`}
          className={`sound-ear ${lit ? 'flash' : ''} ${heard.speaking ? 'held' : ''}`}
          x={side === 'left' ? -x - size[0] : x}
          y={-size[1] / 2}
          width={size[0]}
          height={size[1]}
          rx={size[0] / 2}
          style={{
            ['--level' as string]: String(
              0.14 + 0.86 * heard.hearing.ears[side],
            ),
          }}
        />
      ))}
    </>
  )
}

/**
 * The guidance panel's direction, as the wearer hears it: their head from above, nose up, the sound on the rim,
 * a ripple into the head and the nearer ear lit with each beep. bearingDeg: the snapshot's, when no sound arrives.
 */
export function ListeningHead({
  heard,
  bearingDeg,
}: {
  heard: Heard
  bearingDeg: number | null
}) {
  const focus = heard.beacon || heard.voice
  const az = focus?.azimuthDeg ?? bearingDeg
  const rim = (r: number) => (az === null ? null : onScreen(az, r))
  const dot = rim(29)
  const muffled = !!heard.beacon?.muffled
  const facing = az !== null && Math.abs(az) <= 12
  return (
    <svg
      className="listening-head"
      viewBox="-41 -41 82 82"
      role="img"
      aria-label={
        az === null
          ? 'Direction unavailable'
          : `Sound at ${Math.round(az)} degrees from where the wearer faces`
      }
    >
      <path className="sound-behind" d="M -39 0 A 39 39 0 0 0 39 0 Z" />
      <circle className="sound-ring" r={39} />
      <path
        className={`sound-facing ${facing ? 'on' : ''}`}
        d="M 0 0 L -8.1 -38.1 A 39 39 0 0 1 8.1 -38.1 Z"
      />
      {dot && (
        <line className="sound-path" x1={0} y1={0} x2={dot.x} y2={dot.y} />
      )}
      {dot &&
        ripples(heard)
          .filter((r) => r.cue !== 'blip')
          .map((r) => (
            <g key={r.id} transform={`translate(${dot.x} ${dot.y})`}>
              <circle
                className={`sound-ripple ${r.muffled ? 'muffled' : ''} ${['say', 'label'].includes(r.cue) ? 'voice' : ''} ${r.cue}`}
                r={31}
              />
            </g>
          ))}
      {dot && (
        <g
          className={`sound-beacon ${muffled ? 'muffled' : ''}`}
          style={{ transform: `translate(${dot.x}px, ${dot.y}px)` }}
        >
          {heard.tone && <circle className="sound-tone" r={9} />}
          <circle className="sound-beacon-dot" r={4.5} />
        </g>
      )}
      <g className="sound-head">
        <Ears heard={heard} x={11.5} size={[3, 9]} />
        <circle className="sound-face" r={11} />
        <path className="sound-nose" d="M -3.5 -10.5 L 0 -15.5 L 3.5 -10.5" />
      </g>
    </svg>
  )
}

/** The line just spoken in the AirPods, with where it came from. */
export function SoundCaption({
  caption,
  speaking,
}: {
  caption: Caption | null
  speaking: boolean
}) {
  return (
    <figure
      className={`sound-caption ${caption ? (speaking ? 'speaking' : 'spoken') : 'empty'}`}
      aria-live="polite"
    >
      {caption && (
        <>
          <blockquote>{caption.text}</blockquote>
          <figcaption>
            {caption.cue === 'label' ? 'Voice label' : 'Marco'}
            {caption.anchor === 'ahead'
              ? ', in front of the face'
              : caption.from
                ? `, ${fromSide(caption.from.azimuthDeg)}`
                : ''}
          </figcaption>
        </>
      )}
    </figure>
  )
}

/** Away from Live: the line playing in the AirPods, briefly, so the people watching never miss what was said. */
export function SoundPill({ heard }: { heard: Heard }) {
  const caption = heard.caption
  if (!caption) return null
  return (
    <div
      className={`sound-pill ${heard.speaking ? 'speaking' : 'spoken'}`}
      role="status"
    >
      <Icon name="speaker" size={15} />
      <span>
        <span className="sound-pill-label">In the AirPods</span> “{caption.text}
        ”
      </span>
    </div>
  )
}

export function ListenButton({
  on,
  onToggle,
}: {
  on: boolean
  onToggle: () => void
}) {
  return (
    <button
      className="listen-button"
      aria-pressed={on}
      onClick={onToggle}
      title="Play what the wearer hears on this computer. Headphones give the 3D effect."
    >
      <Icon name="headphones" size={16} />
      Listen in
    </button>
  )
}
