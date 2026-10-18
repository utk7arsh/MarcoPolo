import type { Sound, SoundCue } from './schema'

// What the wearer is hearing, folded from the phone's `dashboard.sound` stream (docs/INTERFACES.md §6). The phone
// renders every sound, so this is the real thing: where the beacon and Marco's voice are relative to the wearer's
// head, which cue just played, and the words just spoken. Times are browser milliseconds (Date.now()).

export type Direction = {
  azimuthDeg: number
  elevationDeg: number
  distanceM: number
}
export type Anchor = 'item' | 'room' | 'ahead'
export type Ripple = {
  id: number
  cue: SoundCue['cue']
  anchor: Anchor
  at: number
  from: Direction
  muffled: boolean
}
export type Caption = {
  text: string
  cue: 'say' | 'label'
  anchor: Anchor
  from: Direction | null // null: a line this browser didn't hear start (the snapshot's), from where unknown
  at: number
  until: number
}
export type Hearing = {
  beacon: (Direction & { muffled: boolean; at: number }) | null
  voice: (Direction & { anchor: Anchor; at: number }) | null
  tone: boolean
  caption: Caption | null
  ripples: Ripple[]
  ears: { left: number; right: number; at: number }
  head: { yawDeg: number; at: number } | null // the listener's world yaw, from the field
  lastAt: number
}

export const STALE_MS = 1500 // a source not refreshed for this long is no longer drawn
export const RIPPLE_MS = 1400 // how long a cue's ripple lives
export const CAPTION_HOLD_MS = 4000 // a finished line stays (dimmed) this long

export const initialHearing: Hearing = {
  beacon: null,
  voice: null,
  tone: false,
  caption: null,
  ripples: [],
  ears: { left: 0, right: 0, at: 0 },
  head: null,
  lastAt: 0,
}

let rippleId = 0

/** One sound from the phone, folded into what's audible now. */
export function hear(state: Hearing, sound: Sound, now: number): Hearing {
  const ripples = state.ripples.filter((r) => now - r.at < RIPPLE_MS)
  if (sound.kind === 'field') {
    return {
      ...state,
      ripples,
      lastAt: now,
      beacon: sound.beacon
        ? {
            ...direction(sound.beacon),
            muffled: !!sound.beacon.muffled,
            at: now,
          }
        : null,
      voice: sound.voice
        ? { ...direction(sound.voice), anchor: sound.voice.anchor, at: now }
        : null,
      head:
        sound.headYawDeg === null
          ? state.head
          : { yawDeg: sound.headYawDeg, at: now },
    }
  }
  const from = direction(sound)
  const muffled = !!sound.muffled
  const next: Hearing = { ...state, ripples, lastAt: now }
  if (sound.cue === 'silence') {
    return {
      ...next,
      tone: false,
      voice: null,
      caption: state.caption && {
        ...state.caption,
        until: Math.min(state.caption.until, now),
      },
    }
  }
  if (sound.cue === 'tone_off') return { ...next, tone: false }
  next.ripples = [
    ...ripples,
    {
      id: ++rippleId,
      cue: sound.cue,
      anchor: sound.anchor,
      at: now,
      from,
      muffled,
    },
  ]
  next.ears = { ...earLevels(from.azimuthDeg, muffled), at: now }
  if (sound.source === 'beacon') next.beacon = { ...from, muffled, at: now }
  if (sound.cue === 'tone_on') next.tone = true
  if (sound.cue === 'say' || sound.cue === 'label') {
    next.voice = { ...from, anchor: sound.anchor, at: now }
    next.caption = {
      text: sound.text || 'A voice label',
      cue: sound.cue,
      anchor: sound.anchor,
      from,
      at: now,
      until: now + (sound.durationS ?? 2) * 1000,
    }
  }
  return next
}

function direction(d: Direction): Direction {
  return {
    azimuthDeg: d.azimuthDeg,
    elevationDeg: d.elevationDeg,
    distanceM: d.distanceM,
  }
}

/** The sources still worth drawing at `now`. */
export function audible(state: Hearing, now: number) {
  const beacon =
    state.beacon && now - state.beacon.at <= STALE_MS ? state.beacon : null
  const speaking = !!state.caption && now < state.caption.until
  const voice =
    state.voice && (speaking || now - state.voice.at <= STALE_MS)
      ? state.voice
      : null
  const caption =
    state.caption && now - state.caption.until <= CAPTION_HOLD_MS
      ? state.caption
      : null
  return { beacon, voice, speaking, caption, tone: state.tone && !!beacon }
}

/** The clock hour of a head-relative azimuth: 12 ahead, 3 right, 6 behind, 9 left. */
export function clockHour(azimuthDeg: number) {
  const hour = Math.round((((azimuthDeg % 360) + 360) % 360) / 30)
  return hour === 0 ? 12 : hour
}

/** How loud each ear hears a source, 0 to 1 (a level difference only; enough to show which ear leads). */
export function earLevels(azimuthDeg: number, muffled = false) {
  const right = 0.5 + 0.5 * Math.sin((azimuthDeg * Math.PI) / 180)
  const scale = muffled ? 0.55 : 1
  return { left: (1 - right) * scale, right: right * scale }
}

/** Distance to a fraction of the ring's radius: compressed, so 30 cm and 4 m both read clearly. */
export function ringFraction(distanceM: number) {
  return Math.min(1, Math.max(0.16, Math.log1p(distanceM) / Math.log1p(4)))
}

/** A head-relative direction on screen, unit radius: x right, y down (SVG), the nose up. */
export function onScreen(azimuthDeg: number, fraction: number) {
  const a = (azimuthDeg * Math.PI) / 180
  return { x: Math.sin(a) * fraction, y: -Math.cos(a) * fraction }
}

export function meters(distanceM: number) {
  return `${distanceM.toFixed(distanceM < 1 ? 2 : 1)} m`
}

/** Distance across the floor, as the top-down view and the guidance panel show it (the phone reports ear to source). */
export function flatMeters(d: Direction) {
  return d.distanceM * Math.cos((d.elevationDeg * Math.PI) / 180)
}

export const FACING_DEG = 12 // the phone's lock: a double ding (docs/INTERFACES.md §7)

/** The words beside the compass: the clock hour, where that is, and what is playing. */
export function readout(
  beacon: (Direction & { muffled: boolean }) | null,
  voice: (Direction & { anchor: Anchor }) | null,
  {
    itemName,
    tone,
    label,
  }: { itemName: string | null; tone: boolean; label: boolean },
) {
  const focus = beacon || voice
  if (!focus) return null
  const facing = Math.abs(focus.azimuthDeg) <= FACING_DEG
  if (!beacon && voice?.anchor === 'ahead')
    return {
      hour: 'Ahead',
      where: 'Marco’s voice',
      detail: 'In front of the face',
    }
  const hour = facing ? 'Ahead' : `${clockHour(focus.azimuthDeg)} o’clock`
  if (beacon) {
    const thing = itemName ? `the ${itemName.toLowerCase()}` : 'it'
    return {
      hour,
      where: facing ? `Facing ${thing}` : sideOf(beacon.azimuthDeg),
      detail: [
        itemName && itemName[0].toUpperCase() + itemName.slice(1),
        meters(flatMeters(beacon)),
        tone ? 'steady tone' : beacon.muffled ? 'muffled' : null,
      ]
        .filter(Boolean)
        .join(', '),
    }
  }
  return {
    hour,
    where: sideOf(focus.azimuthDeg),
    detail: `${label ? 'Voice label' : 'Marco’s voice'}, ${meters(flatMeters(focus))}`,
  }
}

/** The dashboard's own direction words (format.ts direction), relative to the head. */
export function sideOf(azimuthDeg: number) {
  const angle = (((azimuthDeg % 360) + 540) % 360) - 180
  if (Math.abs(angle) < 22.5) return 'Ahead of you'
  if (Math.abs(angle) > 157.5) return 'Behind you'
  const side = angle > 0 ? 'right' : 'left'
  if (Math.abs(angle) < 67.5) return `Ahead, to your ${side}`
  if (Math.abs(angle) > 112.5) return `Behind you, to your ${side}`
  return `To your ${side}`
}

/** Where a line came from, after "Marco, …": "from behind, on the right". */
export function fromSide(azimuthDeg: number) {
  const angle = (((azimuthDeg % 360) + 540) % 360) - 180
  const side = angle > 0 ? 'right' : 'left'
  if (Math.abs(angle) < 22.5) return 'from ahead'
  if (Math.abs(angle) > 157.5) return 'from behind'
  if (Math.abs(angle) < 67.5) return `from ahead, on the ${side}`
  if (Math.abs(angle) > 112.5) return `from behind, on the ${side}`
  return `from the ${side}`
}

/** The listener's world yaw now: the 10 Hz field's if fresh, else the snapshot's head, else the body's. */
export function headYaw(
  state: Hearing,
  now: number,
  wearer: { headYawDeg: number | null; bodyYawDeg: number } | null,
) {
  if (state.head && now - state.head.at <= STALE_MS) return state.head.yawDeg
  return wearer?.headYawDeg ?? wearer?.bodyYawDeg ?? null
}

/** A head-relative direction as a point on the room map (x right, z down; yaw clockwise from -Z). */
export function inRoom(
  from: Direction,
  wearer: { x: number; z: number },
  headYawDeg: number,
) {
  const a = ((headYawDeg + from.azimuthDeg) * Math.PI) / 180
  const d = flatMeters(from)
  return { x: wearer.x + d * Math.sin(a), z: wearer.z - d * Math.cos(a) }
}

/** A head-relative azimuth relative to the chest camera, which faces where the body does. */
export function fromBody(
  azimuthDeg: number,
  headYawDeg: number | null,
  bodyYawDeg: number | null,
) {
  const turn =
    headYawDeg !== null && bodyYawDeg !== null ? headYawDeg - bodyYawDeg : 0
  return ((((azimuthDeg + turn) % 360) + 540) % 360) - 180
}
