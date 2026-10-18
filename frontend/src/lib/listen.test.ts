import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ListenIn, cueTone, position, toneSamples } from './listen'
import { soundSchema } from './schema'
import type { SoundCue } from './schema'

const cue = (
  name: SoundCue['cue'],
  extra: Partial<SoundCue> = {},
): SoundCue => ({
  kind: 'cue',
  tDevice: 1,
  cue: name,
  source: 'beacon',
  anchor: 'item',
  azimuthDeg: 45,
  elevationDeg: -20,
  distanceM: 2,
  muffled: false,
  text: null,
  durationS: null,
  audioUrl: null,
  ...extra,
})

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

  it('keeps all current phone variants and all six reach pitches distinct', () => {
    const variants = [
      'on_beam',
      'off_beam',
      'behind',
      'here',
      'hand_ping',
      'arrive',
      'contact',
    ] as const
    expect(
      variants.map((variant) =>
        cueTone(
          cue(
            variant === 'arrive'
              ? 'ding'
              : variant === 'contact'
                ? 'tone_on'
                : 'beep',
            { variant, handStep: variant === 'hand_ping' ? 3 : undefined },
          ),
        ),
      ),
    ).toEqual(variants)
    expect(cueTone(cue('beep', { muffled: true }))).toBe('muffled')
    expect(cueTone(cue('beep'))).toBe('beep')
    expect(cueTone(cue('ding'))).toBe('ding')
    expect(cueTone(cue('tone_on'))).toBe('tone')
    expect(cueTone(cue('tone_off'))).toBeNull()
    const lengths = variants.map((v) => toneSamples(v, 48000).length)
    expect(lengths).toEqual([3360, 5280, 6720, 4320, 2880, 29760, 48000])
    for (const v of variants)
      expect(Math.max(...toneSamples(v, 48000).map(Math.abs))).toBeLessThan(1)
    const pitches = Array.from({ length: 6 }, (_, step) =>
      toneSamples('hand_ping', 48000, step),
    )
    expect(new Set(pitches.map((samples) => samples[500])).size).toBe(6)
  })

  it('renders the reach scale and contact frequency from the phone’s recipes', () => {
    // Disable just the random click, and compare samples after it has ended.
    vi.spyOn(Math, 'random').mockReturnValue(0.5)
    for (const [step, f] of [
      587.33, 659.26, 739.99, 880, 987.77, 1174.66,
    ].entries()) {
      const samples = toneSamples('hand_ping', 48000, step)
      for (const i of [200, 501, 1200]) {
        const t = i / 48000
        const expected =
          0.3 *
          Math.exp(-t / 0.018) *
          (Math.sin(2 * Math.PI * f * t) +
            0.25 * Math.sin(2 * Math.PI * 3 * f * t))
        expect(samples[i]).toBeCloseTo(expected, 6)
      }
    }
    const samples = toneSamples('contact', 48000)
    const t = 501 / 48000,
      f = 1175
    expect(samples[501]).toBeCloseTo(
      0.22 *
        (Math.sin(2 * Math.PI * f * t) +
          0.4 * Math.sin(4 * Math.PI * f * t) +
          0.2 * Math.sin(6 * Math.PI * f * t)),
      6,
    )
    vi.restoreAllMocks()
  })

  it('accepts old/new relay messages and rejects corrupt variants or pitch steps', () => {
    const envelope = (sound: unknown) => ({
      type: 'dashboard.sound',
      schemaVersion: 1,
      streamId: 's',
      sentAt: '2026-10-18T01:00:00.000Z',
      sound,
    })
    expect(soundSchema.parse(envelope(cue('beep'))).sound).not.toHaveProperty(
      'variant',
    )
    expect(
      soundSchema.parse(
        envelope(cue('beep', { variant: 'hand_ping', handStep: 5 })),
      ).sound,
    ).toMatchObject({ variant: 'hand_ping', handStep: 5 })
    for (const extra of [
      { variant: 'bad' },
      { handStep: -1 },
      { handStep: 6 },
      { handStep: true },
      { handStep: 2.5 },
    ])
      expect(
        soundSchema.safeParse(envelope({ ...cue('beep'), ...extra })).success,
      ).toBe(false)
  })
})

// Verify the playback routing/cache and cancellation as well as the sample-generating helpers.
class BufferStub {
  samples: Float32Array = new Float32Array()
  copyToChannel(samples: Float32Array) {
    this.samples = samples
  }
}
class ContextStub {
  sampleRate = 48000
  currentTime = 0
  destination = {}
  resume = vi.fn()
  close = vi.fn()
  createBuffer() {
    return new BufferStub()
  }
}
class PannerStub {
  static all: PannerStub[] = []
  positionX = { setTargetAtTime: vi.fn() }
  positionY = { setTargetAtTime: vi.fn() }
  positionZ = { setTargetAtTime: vi.fn() }
  connect = vi.fn()
  disconnect = vi.fn()
  constructor(
    _ctx: unknown,
    readonly options: PannerOptions,
  ) {
    PannerStub.all.push(this)
  }
}
class SourceStub {
  static all: SourceStub[] = []
  onended?: () => void
  connect = vi.fn()
  start = vi.fn()
  stop = vi.fn(() => this.onended?.())
  constructor(
    _ctx: unknown,
    readonly options: { buffer: BufferStub; loop?: boolean },
  ) {
    SourceStub.all.push(this)
  }
}
describe('ListenIn playback', () => {
  beforeEach(() => {
    SourceStub.all = []
    PannerStub.all = []
    vi.stubGlobal('AudioContext', ContextStub)
    vi.stubGlobal('AudioBufferSourceNode', SourceStub)
    vi.stubGlobal('PannerNode', PannerStub)
    vi.stubGlobal('window', { speechSynthesis: { cancel: vi.fn() } })
  })
  afterEach(() => {
    vi.unstubAllGlobals()
    vi.restoreAllMocks()
  })

  it('caches each reach pitch separately and uses the current distance attenuation', () => {
    const player = new ListenIn()
    player.play(cue('beep', { variant: 'hand_ping', handStep: 0 }))
    player.play(cue('beep', { variant: 'hand_ping', handStep: 5 }))
    player.play(cue('beep', { variant: 'hand_ping', handStep: 0 }))
    expect(SourceStub.all[0].options.buffer).not.toBe(
      SourceStub.all[1].options.buffer,
    )
    expect(SourceStub.all[0].options.buffer).toBe(
      SourceStub.all[2].options.buffer,
    )
    expect(PannerStub.all[0].options).toMatchObject({
      refDistance: 0.6,
      rolloffFactor: 0.35,
    })
    player.close()
    expect(SourceStub.all.every((s) => s.stop.mock.calls.length === 1)).toBe(
      true,
    )
  })

  it('plays three arrival notes, interrupts the old beacon and silences running sounds', () => {
    const player = new ListenIn()
    player.play(cue('beep', { variant: 'on_beam' }))
    player.play(cue('ding', { variant: 'arrive' }))
    expect(SourceStub.all[0].stop).toHaveBeenCalledOnce()
    expect(SourceStub.all[1].options.buffer.samples.length).toBe(29760)
    player.play(cue('tone_on', { variant: 'contact' }))
    expect(SourceStub.all[2].options.loop).toBe(true)
    player.play(cue('silence'))
    expect(SourceStub.all.every((s) => s.stop.mock.calls.length === 1)).toBe(
      true,
    )
    player.close()
  })

  it('moves a ringing cue with the head-relative field, and stops the held tone when quiet', () => {
    const player = new ListenIn()
    player.play(cue('ding', { variant: 'arrive' }))
    player.play(cue('tone_on', { variant: 'contact' }))
    player.play({
      kind: 'field',
      tDevice: 2,
      headYawDeg: 40,
      beacon: {
        azimuthDeg: -90,
        elevationDeg: 0,
        distanceM: 1,
        muffled: false,
      },
      voice: null,
    })
    expect(
      PannerStub.all[0].positionX.setTargetAtTime,
    ).toHaveBeenLastCalledWith(-1, 0, 0.03)
    player.play({
      kind: 'field',
      tDevice: 3,
      headYawDeg: 40,
      beacon: null,
      voice: null,
    })
    expect(SourceStub.all[1].stop).toHaveBeenCalledOnce()
    player.close()
    player.play(cue('beep'))
    expect(SourceStub.all).toHaveLength(2)
  })
})
