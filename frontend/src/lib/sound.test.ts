import { describe, expect, it } from 'vitest'
import type { Sound, SoundCue } from './schema'
import {
  RIPPLE_MS,
  STALE_MS,
  audible,
  clockHour,
  earLevels,
  flatMeters,
  hear,
  initialHearing,
  onScreen,
  readout,
  ringFraction,
  fromBody,
  fromSide,
  headYaw,
  inRoom,
  sideOf,
} from './sound'

const cue = (name: SoundCue['cue'], extra: Partial<SoundCue> = {}): Sound => ({
  kind: 'cue',
  tDevice: 1,
  cue: name,
  source: ['say', 'label', 'blip'].includes(name) ? 'voice' : 'beacon',
  anchor: 'item',
  azimuthDeg: 145,
  elevationDeg: -20,
  distanceM: 2.2,
  muffled: name === 'beep' ? true : null,
  text: null,
  durationS: null,
  audioUrl: null,
  ...extra,
})

describe('the hearing model', () => {
  it('places the beacon from a beep, ripples it, and lights the nearer ear', () => {
    const h = hear(initialHearing, cue('beep'), 1000)
    expect(h.beacon).toMatchObject({ azimuthDeg: 145, muffled: true, at: 1000 })
    expect(h.ripples).toHaveLength(1)
    expect(h.ears.right).toBeGreaterThan(h.ears.left)
    expect(h.ears.right).toBeLessThan(0.6) // muffled: quieter
  })
  it('keeps the spoken line, then lets it fade; silence ends it at once', () => {
    let h = hear(initialHearing, cue('say', { text: 'Polo!', durationS: 2 }), 0)
    expect(audible(h, 1000)).toMatchObject({
      speaking: true,
      caption: { text: 'Polo!' },
    })
    expect(audible(h, 2500).speaking).toBe(false)
    expect(audible(h, 2500).caption?.text).toBe('Polo!') // dimmed, still on screen
    expect(audible(h, 7000).caption).toBeNull()
    h = hear(h, cue('silence'), 1200)
    expect(audible(h, 1300)).toMatchObject({ speaking: false, voice: null })
  })
  it('follows the field, and forgets sources that stop being refreshed', () => {
    const field: Sound = {
      kind: 'field',
      tDevice: 2,
      headYawDeg: 30,
      beacon: {
        azimuthDeg: -40,
        elevationDeg: -10,
        distanceM: 1.5,
        muffled: false,
      },
      voice: null,
    }
    const h = hear(initialHearing, field, 5000)
    expect(audible(h, 5000 + STALE_MS).beacon?.azimuthDeg).toBe(-40)
    expect(audible(h, 5001 + STALE_MS).beacon).toBeNull()
    expect(hear(h, { ...field, beacon: null }, 5100).beacon).toBeNull()
  })
  it('turns the steady tone on and off, and prunes old ripples', () => {
    let h = hear(initialHearing, cue('tone_on'), 0)
    expect(audible(h, 10).tone).toBe(true)
    h = hear(h, cue('tone_off'), 20)
    expect(h.tone).toBe(false)
    h = hear(h, cue('ding'), RIPPLE_MS + 100)
    expect(h.ripples.map((r) => r.cue)).toEqual(['ding'])
  })
})

describe('the compass geometry and words', () => {
  it('reads azimuths as clock hours, 12 ahead and 3 on the right', () => {
    expect([0, 14, 16, 90, 145, 180, -180, -90, -30].map(clockHour)).toEqual([
      12, 12, 1, 3, 5, 6, 6, 9, 11,
    ])
  })
  it('levels each ear by the side the sound is on', () => {
    expect(earLevels(90)).toEqual({ left: 0, right: 1 })
    expect(earLevels(-90).left).toBe(1)
    expect(earLevels(0).left).toBeCloseTo(0.5)
  })
  it('puts the nose up and right on the right, and compresses distance', () => {
    expect(onScreen(0, 1).y).toBeCloseTo(-1)
    expect(onScreen(90, 1).x).toBeCloseTo(1)
    expect(onScreen(180, 0.5).y).toBeCloseTo(0.5)
    expect(ringFraction(0.05)).toBe(0.16)
    expect(ringFraction(4)).toBe(1)
    expect(ringFraction(1)).toBeGreaterThan(0.4)
  })
  it('shows the distance across the floor, as the guidance panel does', () => {
    expect(
      flatMeters({ azimuthDeg: 0, elevationDeg: -60, distanceM: 1 }),
    ).toBeCloseTo(0.5)
  })
  it('says where the sound is, and does not repeat itself when facing', () => {
    expect(
      readout(
        { azimuthDeg: 0, elevationDeg: 0, distanceM: 1, muffled: false },
        null,
        { itemName: 'keys', tone: false, label: false },
      )?.detail,
    ).toBe('Keys, 1.0 m')
    const beacon = {
      azimuthDeg: 145,
      elevationDeg: 0,
      distanceM: 2.1,
      muffled: true,
    }
    expect(
      readout(beacon, null, { itemName: 'Keys', tone: false, label: false }),
    ).toEqual({
      hour: '5 o’clock',
      where: 'Behind you, to your right',
      detail: 'Keys, 2.1 m, muffled',
    })
    expect(
      readout(
        { ...beacon, azimuthDeg: 8, distanceM: 0.25, muffled: false },
        null,
        { itemName: 'Keys', tone: true, label: false },
      ),
    ).toEqual({
      hour: 'Ahead',
      where: 'Facing the keys',
      detail: 'Keys, 0.25 m, steady tone',
    })
    expect(
      readout(
        null,
        { azimuthDeg: 0, elevationDeg: 0, distanceM: 1, anchor: 'ahead' },
        { itemName: null, tone: false, label: false },
      )?.where,
    ).toBe('Marco’s voice')
    expect(
      readout(
        null,
        { azimuthDeg: -100, elevationDeg: -40, distanceM: 0.6, anchor: 'room' },
        { itemName: null, tone: false, label: true },
      )?.detail,
    ).toBe('Voice label, 0.46 m')
    expect(
      readout(null, null, { itemName: null, tone: false, label: false }),
    ).toBeNull()
    expect(sideOf(-120)).toBe('Behind you, to your left')
    expect([0, 180, 45, -150, 90].map(fromSide)).toEqual([
      'from ahead',
      'from behind',
      'from ahead, on the right',
      'from behind, on the left',
      'from the right',
    ])
  })
})

describe('placing what the wearer hears in the room and the picture', () => {
  it('turns a head-relative direction into a point on the room map', () => {
    const p = inRoom(
      { azimuthDeg: 90, elevationDeg: 0, distanceM: 2 },
      { x: 1, z: 1 },
      0,
    )
    expect(p.x).toBeCloseTo(3)
    expect(p.z).toBeCloseTo(1)
    const behind = inRoom(
      { azimuthDeg: 180, elevationDeg: 0, distanceM: 1 },
      { x: 0, z: 0 },
      90,
    )
    expect(behind.x).toBeCloseTo(-1) // facing +x, behind is -x
  })
  it('uses the freshest head yaw it has', () => {
    const field: Sound = {
      kind: 'field',
      tDevice: 1,
      headYawDeg: 33,
      beacon: null,
      voice: null,
    }
    const h = hear(initialHearing, field, 1000)
    expect(headYaw(h, 1100, { headYawDeg: 10, bodyYawDeg: 5 })).toBe(33)
    expect(
      headYaw(h, 1000 + STALE_MS + 1, { headYawDeg: 10, bodyYawDeg: 5 }),
    ).toBe(10)
    expect(
      headYaw(initialHearing, 0, { headYawDeg: null, bodyYawDeg: 5 }),
    ).toBe(5)
    expect(headYaw(initialHearing, 0, null)).toBeNull()
  })
  it('sees a sound relative to the chest camera, which faces where the body does', () => {
    expect(fromBody(10, 40, 0)).toBe(50) // head turned 40 right: 10 from the head is 50 from the body
    expect(fromBody(170, 20, 0)).toBe(-170)
    expect(fromBody(30, null, 0)).toBe(30)
  })
})
