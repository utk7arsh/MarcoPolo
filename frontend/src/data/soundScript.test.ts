import { describe, expect, it } from 'vitest'
import { soundSchema } from '../lib/schema'
import { beepGap, guidingLoop, walkthrough } from './soundScript'

const valid = (sound: unknown) =>
  soundSchema.safeParse({
    type: 'dashboard.sound',
    schemaVersion: 1,
    streamId: 's',
    sentAt: '2026-10-18T01:00:00.000Z',
    sound,
  }).success

describe('Demo mode sounds follow the phone’s rules', () => {
  for (const [name, script] of [
    ['still frame', guidingLoop()],
    ['walkthrough', walkthrough('Your house keys.', '/audio/keys.wav')],
  ] as const) {
    it(`${name}: every message matches the contract, in time order`, () => {
      expect(script.steps.every((s) => valid(s.sound))).toBe(true)
      expect(
        script.steps.every((s, i, all) => i === 0 || all[i - 1].t <= s.t),
      ).toBe(true)
      expect(script.steps.at(-1)!.t).toBeLessThan(script.period)
    })
    it(`${name}: beeps are muffled exactly when the keys are behind the head`, () => {
      const beeps = script.steps.flatMap((s) =>
        s.sound.kind === 'cue' && s.sound.cue === 'beep' ? [s.sound] : [],
      )
      expect(beeps.length).toBeGreaterThan(5)
      expect(
        beeps.every((b) => b.muffled === Math.abs(b.azimuthDeg) > 90),
      ).toBe(true)
    })
  }
  it('the still frame beeps every clamp(0.15 + 0.35 d) seconds', () => {
    const times = guidingLoop()
      .steps.filter((s) => s.sound.kind === 'cue' && s.sound.cue === 'beep')
      .map((s) => s.t)
    expect(times[1] - times[0]).toBeCloseTo(beepGap(2.1) * 1000)
    expect(beepGap(0)).toBe(0.15)
    expect(beepGap(5)).toBe(1)
  })
  it('the walkthrough tells the whole story, in order', () => {
    const { steps } = walkthrough('Your house keys.', '/audio/keys.wav')
    const cues = steps.flatMap((s) =>
      s.sound.kind === 'cue' && s.sound.cue !== 'beep' ? [s.sound.cue] : [],
    )
    expect(cues).toEqual([
      'say',
      'ding',
      'say',
      'tone_on',
      'tone_off',
      'silence',
      'label',
    ])
    const ding = steps.find(
      (s) => s.sound.kind === 'cue' && s.sound.cue === 'ding',
    )!
    expect(
      ding.sound.kind === 'cue' && Math.abs(ding.sound.azimuthDeg),
    ).toBeLessThanOrEqual(12)
    const states = steps.flatMap((s) =>
      s.navigation?.state ? [s.navigation.state] : [],
    )
    expect([...new Set(states)]).toEqual(['guiding', 'within_reach', 'found'])
    const last = steps.at(-1)!.sound
    expect(
      last.kind === 'field' && last.beacon === null && last.voice === null,
    ).toBe(true)
  })
})
