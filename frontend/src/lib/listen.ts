import type { Sound, SoundCue } from './schema'
import { mediaUrl } from './format'
import { apiUrl } from './transport'

// Listen in: this computer plays what the wearer hears, from the same directions. The beacon's sounds are the
// phone's own recipes (ios/Marco/Audio/SpatialAudio.swift, Tones), placed with Web Audio's HRTF panner the way
// AVAudioEnvironmentNode places them, so headphones on this computer give the wearer's 3D picture and speakers give
// at least left and right. Browser and Apple HRTFs differ: this mirrors the cues, not the exact headphone output.
// Marco's lines come from the server's POST /v1/speech, the same cached voice the phone
// plays (so they are placed too); in Demo mode, or if the server can't speak, this computer's own voice says them.
// A caretaker's voice memo plays as recorded.
// Opt-in only: the dashboard never makes a sound on its own (docs/frontend-backend-contract.md).

type Placed = { source: AudioBufferSourceNode; panner: PannerNode }
type ToneKind =
  | NonNullable<SoundCue['variant']>
  | 'beep'
  | 'muffled'
  | 'ding'
  | 'tone'
  | 'blip'
const HAND_SCALE = [587.33, 659.26, 739.99, 880, 987.77, 1174.66]

/** Missing detail means an older phone/demo; preserve its original recipe. */
export function cueTone(sound: SoundCue): ToneKind | null {
  switch (sound.cue) {
    case 'beep':
      if (
        sound.variant &&
        ['on_beam', 'off_beam', 'behind', 'here', 'hand_ping'].includes(
          sound.variant,
        )
      )
        return sound.variant
      return sound.muffled ? 'muffled' : 'beep'
    case 'ding':
      return sound.variant === 'arrive' ? 'arrive' : 'ding'
    case 'tone_on':
      return sound.variant === 'contact' ? 'contact' : 'tone'
    case 'blip':
      return 'blip'
    default:
      return null
  }
}

/** A head-relative direction as a Web Audio position: x right, y up, -z ahead (the listener's default). */
export function position(
  azimuthDeg: number,
  elevationDeg: number,
  distanceM: number,
) {
  const a = (azimuthDeg * Math.PI) / 180
  const e = (elevationDeg * Math.PI) / 180
  const d = Math.max(distanceM, 0.3)
  return {
    x: d * Math.cos(e) * Math.sin(a),
    y: d * Math.sin(e),
    z: -d * Math.cos(e) * Math.cos(a),
  }
}

/** The phone's current recipes (Tones in SpatialAudio.swift), plus the legacy beep/tone fallbacks.
 * Noise is independently generated, so noisy waveforms are equivalent recipes rather than identical samples. */
export function toneSamples(kind: ToneKind, rate: number, handStep = 0) {
  const make = (seconds: number, f: (t: number) => number) => {
    const out = new Float32Array(Math.round(seconds * rate))
    for (let i = 0; i < out.length; i++) out[i] = f(i / rate)
    return out
  }
  const beep = (freq: number, harmonics: number, ms: number, noise: number) => {
    const dur = ms / 1000
    return make(dur, (t) => {
      const env = Math.min(1, t / 0.004) * Math.exp(-t / (dur / 3))
      let s = 0
      for (let h = 1; h <= harmonics; h++)
        s += Math.sin(2 * Math.PI * freq * h * t) / h
      return 0.35 * env * s + (Math.random() * 2 - 1) * noise * env
    })
  }
  if (kind === 'beep') return beep(880, 6, 70, 0.12)
  if (kind === 'muffled') return beep(440, 2, 110, 0)
  if (kind === 'on_beam') return beep(1320, 7, 70, 0.2)
  if (kind === 'off_beam') return beep(880, 11, 110, 0.12)
  if (kind === 'behind') return beep(392, 2, 140, 0)
  if (kind === 'here' || kind === 'hand_ping') {
    const f =
      kind === 'here' ? 1046.5 : HAND_SCALE[Math.min(Math.max(handStep, 0), 5)]
    const amp = kind === 'here' ? 0.2 : 0.3
    return make(kind === 'here' ? 0.09 : 0.06, (t) => {
      const env = Math.min(1, t / 0.002) * Math.exp(-t / 0.018)
      const click = t < 0.003 ? (Math.random() - 0.5) * (1 - t / 0.003) : 0
      return (
        amp *
        (env *
          (Math.sin(2 * Math.PI * f * t) +
            0.25 * Math.sin(2 * Math.PI * 3 * f * t)) +
          click)
      )
    })
  }
  if (kind === 'arrive')
    return make(0.62, (t) => {
      let sum = 0
      for (const [f, t0] of [
        [1046.5, 0],
        [1318.5, 0.13],
        [1568, 0.26],
      ]) {
        if (t < t0) continue
        const u = t - t0
        sum +=
          Math.min(1, u / 0.003) *
          Math.exp(-u / 0.09) *
          (Math.sin(2 * Math.PI * f * u) +
            0.3 * Math.sin(2 * Math.PI * 2.76 * f * u))
      }
      return 0.3 * sum
    })
  if (kind === 'ding')
    return make(0.36, (t) => {
      const [f, t0] = t < 0.15 ? [1320, 0] : [1760, 0.18]
      const u = t - t0
      if (u < 0) return 0
      const env = Math.min(1, u / 0.003) * Math.exp(-u / 0.06)
      return (
        0.4 *
        env *
        (Math.sin(2 * Math.PI * f * u) +
          0.3 * Math.sin(2 * Math.PI * 2.76 * f * u))
      )
    })
  if (kind === 'tone' || kind === 'contact') {
    const f = kind === 'contact' ? Math.round(HAND_SCALE[5]) : 660
    return make(
      1,
      (t) =>
        0.22 *
        (Math.sin(2 * Math.PI * f * t) +
          0.4 * Math.sin(4 * Math.PI * f * t) +
          0.2 * Math.sin(6 * Math.PI * f * t)),
    )
  }
  return make(0.12, (t) => {
    const f = 520 + 1400 * t
    const env = Math.min(1, t / 0.01) * Math.exp(-t / 0.05)
    return (
      0.25 *
      env *
      (Math.sin(2 * Math.PI * f * t) + 0.3 * Math.sin(4 * Math.PI * f * t))
    )
  })
}

export class ListenIn {
  private context = new AudioContext()
  private buffers = new Map<string, AudioBuffer>()
  private tone?: Placed
  private label?: Placed
  private shots = new Map<Placed, SoundCue['source']>()
  private closed = false
  private voiceTurn = 0 // a newer line or silence drops an older line still loading

  constructor() {
    // Created from the Listen in button's click, so the browser lets it start.
    void this.context.resume()
  }

  play(sound: Sound) {
    if (this.closed) return
    if (sound.kind === 'field') {
      for (const [shot, source] of this.shots) {
        const at = source === 'beacon' ? sound.beacon : sound.voice
        if (at) this.place(shot.panner, at)
      }
      if (sound.beacon && this.tone) this.place(this.tone.panner, sound.beacon)
      if (sound.voice && this.label) this.place(this.label.panner, sound.voice)
      if (!sound.beacon) this.stopTone()
      return
    }
    switch (sound.cue) {
      case 'beep':
      case 'ding':
      case 'blip':
        // The phone's facing/arrival notes interrupt a beacon still ringing.
        if (sound.cue === 'ding') this.stopShots('beacon')
        this.oneShot(cueTone(sound)!, sound)
        break
      case 'tone_on':
        this.stopTone()
        this.tone = this.start(cueTone(sound)!, sound, true)
        break
      case 'tone_off':
        this.stopTone()
        break
      case 'say':
      case 'label':
        if (sound.audioUrl)
          void this.clip(this.memo(sound.audioUrl), sound, sound.text)
        else if (sound.text)
          void this.clip(this.marco(sound.text), sound, sound.text)
        break
      case 'silence':
        this.voiceTurn++
        this.stopShots()
        this.stopTone()
        this.stopLabel()
        window.speechSynthesis?.cancel()
        break
    }
  }

  close() {
    this.closed = true
    this.stopShots()
    this.stopTone()
    this.stopLabel()
    window.speechSynthesis?.cancel()
    void this.context.close()
  }

  private buffer(kind: ToneKind, handStep = 0) {
    const key = kind === 'hand_ping' ? `${kind}:${handStep}` : kind
    let b = this.buffers.get(key)
    if (!b) {
      const samples = toneSamples(kind, this.context.sampleRate, handStep)
      b = this.context.createBuffer(1, samples.length, this.context.sampleRate)
      b.copyToChannel(samples, 0)
      this.buffers.set(key, b)
    }
    return b
  }

  private panner(at: {
    azimuthDeg: number
    elevationDeg: number
    distanceM: number
  }) {
    const p = new PannerNode(this.context, {
      panningModel: 'HRTF',
      distanceModel: 'inverse',
      refDistance: 0.6,
      rolloffFactor: 0.35,
      maxDistance: 10,
    })
    this.place(p, at)
    p.connect(this.context.destination)
    return p
  }

  private place(
    p: PannerNode,
    at: { azimuthDeg: number; elevationDeg: number; distanceM: number },
  ) {
    const { x, y, z } = position(at.azimuthDeg, at.elevationDeg, at.distanceM)
    const t = this.context.currentTime
    p.positionX.setTargetAtTime(x, t, 0.03)
    p.positionY.setTargetAtTime(y, t, 0.03)
    p.positionZ.setTargetAtTime(z, t, 0.03)
  }

  private start(
    kind: Parameters<typeof toneSamples>[0],
    at: { azimuthDeg: number; elevationDeg: number; distanceM: number },
    loop = false,
    handStep = 0,
  ): Placed {
    const panner = this.panner(at)
    const source = new AudioBufferSourceNode(this.context, {
      buffer: this.buffer(kind, handStep),
      loop,
    })
    source.connect(panner)
    source.onended = () => panner.disconnect()
    source.start()
    return { source, panner }
  }

  private oneShot(
    kind: Parameters<typeof toneSamples>[0],
    at: Sound & { kind: 'cue' },
  ) {
    const shot = this.start(kind, at, false, at.handStep ?? 0)
    this.shots.set(shot, at.source)
    shot.source.onended = () => {
      shot.panner.disconnect()
      this.shots.delete(shot)
    }
  }

  private stopShots(source?: SoundCue['source']) {
    for (const [shot, playing] of this.shots) {
      if (source && source !== playing) continue
      shot.source.stop()
      this.shots.delete(shot)
    }
  }

  private stopTone() {
    this.tone?.source.stop()
    this.tone = undefined
  }

  private stopLabel() {
    this.label?.source.stop()
    this.label = undefined
  }

  private speak(text: string) {
    const synth = window.speechSynthesis
    if (!synth) return
    const line = new SpeechSynthesisUtterance(text)
    line.lang = 'en-US'
    synth.speak(line)
  }

  /** A caretaker's voice memo. */
  private async memo(url: string) {
    return fetch(mediaUrl(url) || url, { credentials: 'include' })
  }

  /** Marco's line in the wearer's voice: the server renders it once and caches it, so this is usually a cache hit. */
  private async marco(text: string) {
    if (import.meta.env.VITE_DATA_SOURCE !== 'api') throw new Error('demo')
    return fetch(
      apiUrl(import.meta.env.VITE_API_BASE_URL || '/api', '/v1/speech'),
      {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
        signal: AbortSignal.timeout(4000),
      },
    )
  }

  /** A voice clip from where the wearer hears it; this computer's voice if it can't be had. */
  private async clip(
    request: Promise<Response>,
    at: Sound & { kind: 'cue' },
    fallback: string | null,
  ) {
    const turn = ++this.voiceTurn
    try {
      const response = await request
      if (!response.ok) throw new Error(String(response.status))
      const audio = await this.context.decodeAudioData(
        await response.arrayBuffer(),
      )
      if (this.closed || turn !== this.voiceTurn) return
      this.stopLabel()
      const panner = this.panner(at)
      const source = new AudioBufferSourceNode(this.context, { buffer: audio })
      source.connect(panner)
      source.onended = () => panner.disconnect()
      source.start()
      this.label = { source, panner }
    } catch {
      if (fallback && !this.closed && turn === this.voiceTurn)
        this.speak(fallback)
    }
  }
}
