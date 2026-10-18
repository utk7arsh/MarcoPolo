import { describe, expect, it } from 'vitest'
import { position, toneSamples } from './listen'

describe('listen in', () => {
  it('places sounds the way AVAudioEnvironmentNode does: x right, y up, -z ahead', () => {
    const ahead = position(0, 0, 2)
    expect(ahead.x).toBeCloseTo(0)
    expect(ahead.z).toBeCloseTo(-2)
    expect(position(90, 0, 1).x).toBeCloseTo(1)
    expect(position(180, 0, 1).z).toBeCloseTo(1)
    expect(position(0, -90, 1).y).toBeCloseTo(-1)
    expect(Math.hypot(...Object.values(position(0, 0, 0.05)))).toBeCloseTo(0.3) // never inside the head
  })
  it('makes the phone’s tones at their lengths, never clipping', () => {
    const rate = 48000
    expect(toneSamples('beep', rate)).toHaveLength(3360)
    expect(toneSamples('muffled', rate)).toHaveLength(5280)
    expect(toneSamples('ding', rate)).toHaveLength(17280)
    expect(toneSamples('tone', rate)).toHaveLength(48000)
    for (const kind of ['beep', 'muffled', 'ding', 'tone', 'blip'] as const)
      expect(Math.max(...toneSamples(kind, rate).map(Math.abs))).toBeLessThan(1)
  })
})
