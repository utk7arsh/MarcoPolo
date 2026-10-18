import AVFAudio
import Foundation
import simd

/// Spatial audio for guidance (docs/INTERFACES.md §7): beeps, dings, the steady tone, Marco's voice and label
/// playback, all placed at the item and rendered with Apple's HRTF. Positions are listener-relative (x right, y up,
/// -z ahead; Geo.listenerRelative with the fused head yaw), so the listener node itself never turns and there is no
/// AVAudio yaw-sign convention to get wrong.
final class SpatialAudio {
    let engine = AVAudioEngine()
    private let environment = AVAudioEnvironmentNode()
    private let beacon = AVAudioPlayerNode()     // beeps and dings
    private let tone = AVAudioPlayerNode()       // steady tone in the last 30 cm
    private let voice = AVAudioPlayerNode()      // speech and labels
    private let format = AVAudioFormat(standardFormatWithSampleRate: 48_000, channels: 1)!
    private lazy var beep = Tones.beep(format, freq: 880, harmonics: 6, ms: 70, noise: 0.12)
    private lazy var beepMuffled = Tones.beep(format, freq: 440, harmonics: 2, ms: 110, noise: 0)
    private lazy var ding = Tones.ding(format)
    private lazy var steady = Tones.loop(format, freq: 660)
    private let synth = AVSpeechSynthesizer()
    private var speechConverter: AVAudioConverter?
    private var voiceAtItem = false
    private static let ahead = AVAudio3DPoint(x: 0, y: 0, z: -1)

    init() {
        engine.attach(environment)
        for n in [beacon, tone, voice] {
            engine.attach(n)
            engine.connect(n, to: environment, format: format)
            n.renderingAlgorithm = .HRTFHQ
            n.sourceMode = .pointSource
        }
        let out = engine.outputNode.outputFormat(forBus: 0)
        let stereo = AVAudioFormat(standardFormatWithSampleRate: out.sampleRate > 0 ? out.sampleRate : 48_000, channels: 2)
        engine.connect(environment, to: engine.mainMixerNode, format: stereo)
        environment.outputType = .headphones
        environment.listenerPosition = AVAudio3DPoint(x: 0, y: 0, z: 0)
        environment.listenerAngularOrientation = AVAudio3DAngularOrientation(yaw: 0, pitch: 0, roll: 0)
        let att = environment.distanceAttenuationParameters
        att.distanceAttenuationModel = .inverse
        att.referenceDistance = 1.0          // no change inside 1 m; about -9.5 dB at 5 m
        att.rolloffFactor = 0.5
        att.maximumDistance = 10
        environment.reverbParameters.enable = false
    }

    /// Call once, before Listener.start(): the session keeps the AirPods in A2DP (stereo, so spatial audio works)
    /// and records from the iPhone's own mic. Bluetooth HFP would turn the AirPods into a mono headset.
    func start() throws {
        #if os(iOS)
        let s = AVAudioSession.sharedInstance()
        try s.setCategory(.playAndRecord, mode: .default, options: [.allowBluetoothA2DP, .defaultToSpeaker])
        try s.setActive(true)
        #endif
        engine.prepare()
        try engine.start()
        for n in [beacon, tone, voice] { n.play() }
    }

    /// Where the guided item is now, listener-relative. Call every tick while guiding.
    func place(_ p: SIMD3<Float>) {
        let pt = AVAudio3DPoint(x: p.x, y: p.y, z: p.z)
        beacon.position = pt
        tone.position = pt
        voice.position = voiceAtItem ? pt : Self.ahead
    }

    /// Sound cues. .say, .playLabel and .haptic are routed by the app (speech needs a place, labels the cache).
    func play(_ cue: Cue) {
        switch cue {
        case .beep(let muffled):
            beacon.scheduleBuffer(muffled ? beepMuffled : beep, at: nil, options: [], completionHandler: nil)
        case .ding:
            beacon.scheduleBuffer(ding, at: nil, options: [.interrupts], completionHandler: nil)
        case .steadyTone(let on):
            if on {
                tone.scheduleBuffer(steady, at: nil, options: [.loops, .interrupts], completionHandler: nil)
            } else {
                tone.stop()
                tone.play()
            }
        case .silence:
            synth.stopSpeaking(at: .immediate)
            for n in [beacon, tone, voice] {
                n.stop()
                n.play()
            }
        case .say, .playLabel, .haptic:
            break
        }
    }

    /// Marco's voice, rendered in 3D: at the guided item ("Polo!") or straight ahead.
    func say(_ text: String, atItem: Bool) {
        voiceAtItem = atItem
        if !atItem { voice.position = Self.ahead }
        let u = AVSpeechUtterance(string: text)
        u.voice = AVSpeechSynthesisVoice(language: "en-US")
        synth.write(u) { [weak self] buffer in
            guard let self, let pcm = buffer as? AVAudioPCMBuffer, pcm.frameLength > 0 else { return }
            if self.speechConverter?.inputFormat != pcm.format {
                self.speechConverter = AVAudioConverter(from: pcm.format, to: self.format)
            }
            guard let conv = self.speechConverter, let mono = Self.convert(pcm, with: conv, to: self.format, endOfStream: false) else { return }
            self.voice.scheduleBuffer(mono, completionHandler: nil)
        }
    }

    /// A label voice memo (any format AVAudioFile reads, such as the server's m4a), at the item or ahead.
    func playFile(_ url: URL, atItem: Bool) throws {
        let file = try AVAudioFile(forReading: url)
        guard let pcm = AVAudioPCMBuffer(pcmFormat: file.processingFormat, frameCapacity: AVAudioFrameCount(file.length)) else { return }
        try file.read(into: pcm)
        guard let conv = AVAudioConverter(from: pcm.format, to: format),
              let mono = Self.convert(pcm, with: conv, to: format, endOfStream: true) else { return }
        voiceAtItem = atItem
        if !atItem { voice.position = Self.ahead }
        voice.scheduleBuffer(mono, at: nil, options: [.interrupts], completionHandler: nil)
    }

    /// Any PCM buffer -> mono 48 kHz float, the format the 3D sources are connected with.
    static func convert(_ input: AVAudioPCMBuffer, with conv: AVAudioConverter, to format: AVAudioFormat, endOfStream: Bool) -> AVAudioPCMBuffer? {
        conv.downmix = true
        let ratio = format.sampleRate / input.format.sampleRate
        let cap = AVAudioFrameCount(Double(input.frameLength) * ratio) + 4096
        guard let out = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: cap) else { return nil }
        var fed = false
        var error: NSError?
        let status = conv.convert(to: out, error: &error) { _, inputStatus in
            if fed {
                inputStatus.pointee = endOfStream ? .endOfStream : .noDataNow
                return nil
            }
            fed = true
            inputStatus.pointee = .haveData
            return input
        }
        return status == .error || out.frameLength == 0 ? nil : out
    }
}

/// The guidance sounds, synthesised so nothing has to be bundled. Broadband content (harmonics, a little noise)
/// gives the HRTF something to work with; pure sines localise badly.
enum Tones {
    static func buffer(_ format: AVAudioFormat, seconds: Double, _ f: (Double) -> Float) -> AVAudioPCMBuffer {
        let n = AVAudioFrameCount(seconds * format.sampleRate)
        let b = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: n)!
        b.frameLength = n
        let ch = b.floatChannelData![0]
        for i in 0..<Int(n) { ch[i] = f(Double(i) / format.sampleRate) }
        return b
    }

    static func beep(_ format: AVAudioFormat, freq: Double, harmonics: Int, ms: Double, noise: Float) -> AVAudioPCMBuffer {
        var rng = SystemRandomNumberGenerator()
        let dur = ms / 1000
        return buffer(format, seconds: dur) { t in
            let env = min(1, t / 0.004) * exp(-t / (dur / 3))
            var s = 0.0
            for h in 1...harmonics { s += sin(2 * .pi * freq * Double(h) * t) / Double(h) }
            return Float(0.35 * env * s) + Float.random(in: -1...1, using: &rng) * noise * Float(env)
        }
    }

    /// Facing it: two rising bell notes.
    static func ding(_ format: AVAudioFormat) -> AVAudioPCMBuffer {
        buffer(format, seconds: 0.36) { t in
            let (f, t0) = t < 0.15 ? (1320.0, 0.0) : (1760.0, 0.18)
            let u = t - t0
            guard u >= 0 else { return 0 }
            let env = min(1, u / 0.003) * exp(-u / 0.06)
            return Float(0.4 * env * (sin(2 * .pi * f * u) + 0.3 * sin(2 * .pi * 2.76 * f * u)))
        }
    }

    /// One second of a soft tone; whole cycles, so it loops without a click.
    static func loop(_ format: AVAudioFormat, freq: Double) -> AVAudioPCMBuffer {
        buffer(format, seconds: 1.0) { t in
            Float(0.22 * (sin(2 * .pi * freq * t) + 0.4 * sin(4 * .pi * freq * t) + 0.2 * sin(6 * .pi * freq * t)))
        }
    }
}
