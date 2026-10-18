import type { DashboardData, Sound, SoundCue } from '../lib/schema'

// Demo mode's sounds: what the phone would report (dashboard.sound) for the demo room, following the phone's own
// rules (docs/INTERFACES.md §7): a beep every clamp(0.15 + 0.35 x distance, 0.15, 1.0) s, muffled while the keys are
// behind the head, a ding within 12 degrees, "Within reach" at 0.6 m, the steady tone at 30 cm. Simulated, like the
// rest of Demo mode: the live view never uses it.

export type Step = {
  t: number // ms from the start of the loop
  sound: Sound
  navigation?: Partial<DashboardData['navigation']>
  // where the wearer stands and faces on the map (x right, z down; yaw clockwise from -Z)
  wearer?: { x: number; z: number; headYawDeg: number; bodyYawDeg: number }
}

const EAR_ABOVE_TABLE = 0.8 // m: the keys are on a coffee table

export const beepGap = (distanceM: number) =>
  Math.min(Math.max(0.15 + 0.35 * distanceM, 0.15), 1.0)

function heard(azimuthDeg: number, flatM: number) {
  return {
    azimuthDeg: Math.round(azimuthDeg * 10) / 10,
    elevationDeg:
      Math.round(((Math.atan2(-EAR_ABOVE_TABLE, flatM) * 180) / Math.PI) * 10) /
      10,
    distanceM: Math.round(Math.hypot(flatM, EAR_ABOVE_TABLE) * 100) / 100,
  }
}

function cue(
  t: number,
  name: SoundCue['cue'],
  azimuthDeg: number,
  flatM: number,
  extra: Partial<SoundCue> = {},
): Sound {
  const voice = name === 'say' || name === 'label' || name === 'blip'
  return {
    kind: 'cue',
    tDevice: t / 1000,
    cue: name,
    source: voice ? 'voice' : 'beacon',
    anchor: 'item',
    ...heard(azimuthDeg, flatM),
    muffled: name === 'beep' ? Math.abs(azimuthDeg) > 90 : null,
    text: null,
    durationS: null,
    audioUrl: null,
    ...extra,
  }
}

function field(
  t: number,
  beacon: { azimuthDeg: number; flatM: number } | null,
  voice: { azimuthDeg: number; flatM: number } | null,
  headYawDeg = 0,
): Sound {
  return {
    kind: 'field',
    tDevice: t / 1000,
    headYawDeg,
    beacon: beacon
      ? {
          ...heard(beacon.azimuthDeg, beacon.flatM),
          muffled: Math.abs(beacon.azimuthDeg) > 90,
        }
      : null,
    voice: voice
      ? { ...heard(voice.azimuthDeg, voice.flatM), anchor: 'item' }
      : null,
  }
}

/** The "Finding keys" still frame: the keys stay 2.1 m away at 145 degrees, behind and to the right. */
export function guidingLoop(): { period: number; steps: Step[] } {
  const az = 145
  const d = 2.1
  const period = 9500
  const line = 'Turn right. Your keys are behind you.'
  const speech = 2600
  const steps: Step[] = [
    {
      t: 300,
      sound: cue(300, 'say', az, d, { text: line, durationS: speech / 1000 }),
    },
  ]
  for (let t = 300 + speech + 400; t < period - 200; t += beepGap(d) * 1000)
    steps.push({ t, sound: cue(t, 'beep', az, d) })
  for (let t = 0; t < period; t += 100)
    steps.push({
      t,
      sound: field(
        t,
        { azimuthDeg: az, flatM: d },
        t >= 300 && t < 300 + speech ? { azimuthDeg: az, flatM: d } : null,
      ),
    })
  return { period, steps: steps.sort((a, b) => a.t - b.t) }
}

/**
 * The whole find, about 22 s: "Polo!", the wearer turns to the keys, walks up, reaches, touches. from and keys: map
 * positions; the wearer starts facing -Z, and every step's sound, guidance and position agree with them.
 */
export function walkthrough(
  labelText: string | null,
  labelUrl: string | null,
  {
    from,
    keys,
  }: { from: { x: number; z: number }; keys: { x: number; z: number } } = {
    from: { x: 0, z: 0 },
    keys: { x: 1, z: Math.sqrt(3) }, // 2 m away, 150 degrees: behind, to the right
  },
): { period: number; steps: Step[] } {
  const steps: Step[] = []
  const add = (
    t: number,
    sound: Sound,
    navigation?: Step['navigation'],
    wearer?: Step['wearer'],
  ) => steps.push({ t: Math.round(t), sound, navigation, wearer })
  const start = Math.hypot(keys.x - from.x, keys.z - from.z)
  const bearing =
    (Math.atan2(keys.x - from.x, -(keys.z - from.z)) * 180) / Math.PI
  const unit = { x: (keys.x - from.x) / start, z: (keys.z - from.z) / start }
  // Where the keys are, relative to the head, over time: turning to them in 3.5-6.5 s, then walking in.
  const at = (t: number) => {
    const turn = Math.min(1, Math.max(0, (t - 3500) / 3000))
    const eased = turn * turn * (3 - 2 * turn)
    const walk = Math.min(1, Math.max(0, (t - 7000) / 6500))
    const flatM = start - (start - 0.25) * walk
    const headYawDeg =
      bearing * eased + (walk > 0 ? 5 * Math.sin(t / 700) * (1 - walk) : 0)
    const azimuthDeg = bearing - headYawDeg
    const wearer = {
      x: keys.x - unit.x * flatM,
      z: keys.z - unit.z * flatM,
      headYawDeg: Math.round(headYawDeg * 10) / 10,
      bodyYawDeg: Math.round(bearing * eased * 10) / 10,
    }
    return { azimuthDeg, flatM, headYawDeg, wearer }
  }
  const polo = 'Polo! Behind you, two steps, on the table.'
  const reach = 'Within reach, on the table.'
  let speakingUntil = 500 + 2900 // the "Polo!" line
  let saidReach = false
  let dinged = false
  let toneAt: number | null = null
  const end = 15000
  add(
    0,
    field(0, null, null),
    { state: 'guiding', audioPattern: 'beacon', spokenInstruction: null },
    at(0).wearer,
  )
  add(500, cue(500, 'say', bearing, start, { text: polo, durationS: 2.9 }), {
    spokenInstruction: polo,
  })
  let nextBeep = 3500
  // The snapshot's spoken line, as the server keeps it: while the line plays and for 3 s after.
  let spoken: string | null = polo
  let spokenUntil = 500 + 2900 + 3000
  for (let t = 0; t <= end; t += 50) {
    const p = at(t)
    if (t % 100 === 0)
      add(
        t,
        field(
          t,
          t >= 500 ? p : null,
          t < speakingUntil && t >= 500 ? p : null,
          p.headYawDeg,
        ),
        t >= 500
          ? {
              distanceM: Math.round(p.flatM * 100) / 100,
              bearingDeg: Math.round(p.azimuthDeg),
              state: toneAt !== null ? 'within_reach' : 'guiding',
              audioPattern: toneAt !== null ? 'steady' : 'beacon',
              spokenInstruction: t < spokenUntil ? spoken : null,
            }
          : undefined,
        p.wearer,
      )
    if (!dinged && t > 3500 && Math.abs(p.azimuthDeg) <= 12) {
      dinged = true
      add(t, cue(t, 'ding', p.azimuthDeg, p.flatM))
      nextBeep = t + 800
    }
    if (!saidReach && p.flatM <= 0.6) {
      saidReach = true
      add(
        t,
        cue(t, 'say', p.azimuthDeg, p.flatM, { text: reach, durationS: 1.6 }),
        { spokenInstruction: reach },
      )
      speakingUntil = t + 1600
      spoken = reach
      spokenUntil = t + 1600 + 3000
    }
    if (toneAt === null && p.flatM <= 0.3) {
      toneAt = t
      add(t, cue(t, 'tone_on', p.azimuthDeg, p.flatM))
    }
    // No beeps over Marco's voice; otherwise one every beepGap.
    if (toneAt === null && t >= 3500 && t >= speakingUntil && t >= nextBeep) {
      add(t, cue(t, 'beep', p.azimuthDeg, p.flatM))
      nextBeep = t + beepGap(p.flatM) * 1000
    }
  }
  const touch = end + 400
  const last = at(end)
  add(touch, cue(touch, 'tone_off', last.azimuthDeg, last.flatM))
  add(touch, cue(touch, 'silence', last.azimuthDeg, last.flatM))
  const words = labelText || 'Got it.'
  add(
    touch + 50,
    cue(touch + 50, labelUrl ? 'label' : 'say', last.azimuthDeg, last.flatM, {
      text: words,
      durationS: 1.6,
      audioUrl: labelUrl,
    }),
    {
      state: 'found',
      audioPattern: 'confirmation',
      spokenInstruction: words,
      distanceM: null,
      bearingDeg: null,
    },
  )
  for (let t = touch + 100; t <= touch + 1700; t += 100)
    add(t, field(t, null, last))
  add(touch + 1800, field(touch + 1800, null, null))
  return { period: touch + 6500, steps: steps.sort((a, b) => a.t - b.t) }
}
