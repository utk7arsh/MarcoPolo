import type { Sound } from './schema'
import { mediaUrl } from './format'
import { apiUrl } from './transport'

// Listen in: this computer plays what the wearer hears, from the same directions. The beacon's sounds are the
// phone's own recipes (ios/Marco/Audio/SpatialAudio.swift, Tones), placed with Web Audio's HRTF panner the way
// AVAudioEnvironmentNode places them, so headphones on this computer give the wearer's 3D picture and speakers give
// at least left and right. Marco's lines come from the server's POST /v1/speech, the same cached voice the phone
// plays (so they are placed too); in Demo mode, or if the server can't speak, this computer's own voice says them.
// A caretaker's voice memo plays as recorded.
// Opt-in only: the dashboard never makes a sound on its own (docs/frontend-backend-contract.md).

type Placed = { source: AudioBufferSourceNode; panner: PannerNode }

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

/** The phone's tones, sample for sample (Tones in SpatialAudio.swift). */
export function toneSamples(
  kind: 'beep' | 'muffled' | 'ding' | 'tone' | 'blip',
  rate: number,
) {
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
  if (kind === 'tone')
    return make(
      1,
      (t) =>
        0.22 *
        (Math.sin(2 * Math.PI * 660 * t) +
          0.4 * Math.sin(4 * Math.PI * 660 * t) +
          0.2 * Math.sin(6 * Math.PI * 660 * t)),
    )
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
  private closed = false
  private voiceTurn = 0 // a newer line or silence drops an older line still loading

  constructor() {
    // Created from the Listen in button's click, so the browser lets it start.
    void this.context.resume()
  }

  play(sound: Sound) {
    if (this.closed) return
    if (sound.kind === 'field') {
      if (sound.beacon && this.tone) this.place(this.tone.panner, sound.beacon)
      if (sound.voice && this.label) this.place(this.label.panner, sound.voice)
      if (!sound.beacon) this.stopTone()
      return
    }
    switch (sound.cue) {
      case 'beep':
        this.oneShot(sound.muffled ? 'muffled' : 'beep', sound)
        break
      case 'ding':
      case 'blip':
        this.oneShot(sound.cue, sound)
        break
      case 'tone_on':
        this.stopTone()
        this.tone = this.start('tone', sound, true)
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
        this.stopTone()
        this.stopLabel()
        window.speechSynthesis?.cancel()
        break
    }
  }

  close() {
    this.closed = true
    this.stopTone()
    this.stopLabel()
    window.speechSynthesis?.cancel()
    void this.context.close()
  }

  private buffer(kind: Parameters<typeof toneSamples>[0]) {
    let b = this.buffers.get(kind)
    if (!b) {
      const samples = toneSamples(kind, this.context.sampleRate)
      b = this.context.createBuffer(1, samples.length, this.context.sampleRate)
      b.copyToChannel(samples, 0)
      this.buffers.set(kind, b)
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
      refDistance: 1,
      rolloffFactor: 0.5,
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
  ): Placed {
    const panner = this.panner(at)
    const source = new AudioBufferSourceNode(this.context, {
      buffer: this.buffer(kind),
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
    this.start(kind, at)
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
