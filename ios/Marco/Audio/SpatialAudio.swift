import AVFAudio
import Foundation
import simd

/// Spatial audio for guidance (docs/INTERFACES.md §7): beeps, dings, the steady tone, Marco's voice and label
/// playback, rendered with Apple's HRTF into the stereo the AirPods play (Core/SoundScene.swift). Positions are
/// listener-relative (x right, y up, -z ahead; Geo.listenerRelative with the fused head yaw), so the listener node
/// itself never turns and there is no AVAudio yaw-sign convention to get wrong.
///
/// Two places: the guided item (`place`, every tick: the beacon, the tone, and the voice when `atItem`), and the
/// voice's own point (`say(_:at:)`, then `moveVoice` every tick), for a line from somewhere else
/// in the room, such as a touched jar.
final class SpatialAudio {
    enum PlaybackError: Error { case unreadableAudio }
    let engine = AVAudioEngine()
    private let environment = AVAudioEnvironmentNode()
    private let beacon = AVAudioPlayerNode()     // beeps, dings and the hand's pings
    private let tone = AVAudioPlayerNode()       // the held tone when the fingertip is on the item
    private let voice = AVAudioPlayerNode()      // speech and labels
    private let format = AVAudioFormat(standardFormatWithSampleRate: 48_000, channels: 1)!
    // One family, ordered by pitch: low and dull behind, plain in front, bright on the beam (Core/Guidance.swift).
    // In front they reach ~10 kHz and last 100 ms or more while the head is turning: the pinna cues live above 4 kHz,
    // and a head turn only helps a sound that lasts through it.
    private lazy var beamPulse = Tones.beep(format, freq: 1320, harmonics: 7, ms: 70, noise: 0.2)
    private lazy var beep = Tones.beep(format, freq: 880, harmonics: 11, ms: 110, noise: 0.12)
    private lazy var beepMuffled = Tones.beep(format, freq: 392, harmonics: 2, ms: 140, noise: 0)
    private lazy var herePing = Tones.ping(format, freq: 1046.5, amp: 0.2, ms: 90)
    private lazy var handPings = Tones.handScale.map { Tones.ping(format, freq: $0) }
    private lazy var ding = Tones.ding(format)
    private lazy var arrive = Tones.arrive(format)
    private lazy var steady = Tones.loop(format, freq: Tones.handScale.last!.rounded())
    private let synth = AVSpeechSynthesizer()
    private let speechOutput = SpeechOutputClient()
    private var speechGeneration = 0
    private var speechConverter: AVAudioConverter?
    private lazy var blip = Tones.blip(format)
    private enum VoiceSpot { case ahead, item, point }
    private var voiceSpot = VoiceSpot.ahead
    private var observers: [NSObjectProtocol] = []
    private static let ahead = AVAudio3DPoint(x: 0, y: 0, z: -1)
    private var itemPosition = SpatialAudio.ahead

    /// The route changed (AirPods in or out, the mic switched): its description, for the debug screen. Any thread.
    var onRoute: ((String) -> Void)?

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
        att.referenceDistance = 0.6          // louder all the way in to the stop: -3.5 dB at 2 m, -9 dB at 6 m. Gentle,
        att.rolloffFactor = 0.35             // so it's heard across the room; the pace carries the distance
        att.maximumDistance = 10
        environment.reverbParameters.enable = false
    }

    /// Call once, before Listener.start().
    func start() throws {
        #if os(iOS)
        try applyRoute()
        try AVAudioSession.sharedInstance().setActive(true)
        observers.append(NotificationCenter.default.addObserver(forName: AVAudioSession.routeChangeNotification,
                                                                object: nil, queue: nil) { [weak self] n in
            // AirPods put in after Start: route again so their mic is picked up, not just their speakers.
            let raw = n.userInfo?[AVAudioSessionRouteChangeReasonKey] as? UInt
            if raw.flatMap(AVAudioSession.RouteChangeReason.init) == .newDeviceAvailable { try? self?.applyRoute() }
            self?.onRoute?(Self.routeDescription())
        })
        #endif
        // A route change stops the engine; start it again so the beacon and Marco's voice don't go quiet for good.
        observers.append(NotificationCenter.default.addObserver(forName: .AVAudioEngineConfigurationChange, object: engine,
                                                                queue: .main) { [weak self] _ in
            guard let self else { return }
            self.engine.prepare()
            try? self.engine.start()
            for n in [self.beacon, self.tone, self.voice] { n.play() }
        })
        engine.prepare()
        try engine.start()
        for n in [beacon, tone, voice] { n.play() }
    }

    #if os(iOS)
    /// Output to the AirPods stays full-bandwidth stereo (A2DP), which HRTF needs. Speech in comes from the AirPods'
    /// own mic when the route supports Bluetooth high-quality recording (iOS 26; AirPods Pro 3): that mode keeps the
    /// output full-bandwidth too. Otherwise, or with the debug screen's switch, from the iPhone's mic. Never HFP: it
    /// would make the AirPods a mono 16 kHz headset. Call again after changing Config.useIPhoneMic.
    func applyRoute() throws {
        let s = AVAudioSession.sharedInstance()
        let base: AVAudioSession.CategoryOptions = [.allowBluetoothA2DP, .defaultToSpeaker]
        try? s.setPrefersNoInterruptionsFromSystemAlerts(true)     // no ringtone cutting into guidance
        if #available(iOS 26.0, *), !Config.useIPhoneMic {
            if (try? s.setCategory(.playAndRecord, mode: .default, options: base.union(.bluetoothHighQualityRecording))) != nil {
                let airpods = s.availableInputs?.first { $0.bluetoothMicrophoneExtension?.highQualityRecording.isSupported == true }
                try? s.setPreferredInput(airpods)                      // nil: the system's choice
                return
            }
        }
        try s.setCategory(.playAndRecord, mode: .default, options: base)
        try? s.setPreferredInput(s.availableInputs?.first { $0.portType == .builtInMic })
    }

    /// "mic AirPods Pro (BluetoothHFP, high quality), 48 kHz · out AirPods Pro, 2 ch". Hour-one: the AirPods mic
    /// with "high quality", and the output still 2 channels.
    static func routeDescription() -> String {
        let s = AVAudioSession.sharedInstance()
        let mic = s.currentRoute.inputs.first.map { p -> String in
            var hq = ""
            if #available(iOS 26.0, *), let ext = p.bluetoothMicrophoneExtension {
                hq = ext.highQualityRecording.isEnabled ? ", high quality" : ext.highQualityRecording.isSupported ? ", HQ off" : ", no HQ"
            }
            return "\(p.portName) (\(p.portType.rawValue)\(hq)), \(Int(s.sampleRate / 1000)) kHz"
        } ?? "none"
        let out = s.currentRoute.outputs.first.map { "\($0.portName), \(s.outputNumberOfChannels) ch" } ?? "none"
        return "mic \(mic) · out \(out)"
    }
    #endif

    /// "Marco" alone was heard: a soft blip ahead, then say the rest.
    func listening() {
        cancelVoice()
        aim(.ahead)
        voice.scheduleBuffer(blip, at: nil, options: [], completionHandler: nil)
    }

    /// No headphones (Core/RouteWatch): beeps and the tone from the chest speaker can't point anywhere and only
    /// startle, so they go quiet. Marco keeps talking.
    func setBeaconAudible(_ on: Bool) {
        beacon.volume = on ? 1 : 0
        tone.volume = on ? 1 : 0
    }

    #if os(iOS)
    static func outputRoute() -> OutputRoute {
        let s = AVAudioSession.sharedInstance()
        let outs = s.currentRoute.outputs
        let phones: Set<AVAudioSession.Port> = [.headphones, .bluetoothA2DP, .bluetoothLE, .bluetoothHFP]
        return OutputRoute(name: outs.map(\.portName).joined(separator: ", "),
                           headphones: !outs.isEmpty && outs.allSatisfy { phones.contains($0.portType) },
                           channels: s.outputNumberOfChannels)
    }
    #endif

    func stop() {
        cancelVoice()
        for node in [beacon, tone, voice] { node.stop() }
        engine.stop()
        #if os(iOS)
        try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation)
        #endif
    }

    /// Where the guided item is now, listener-relative. Call every tick while guiding.
    func place(_ p: SIMD3<Float>) {
        let pt = AVAudio3DPoint(x: p.x, y: p.y, z: p.z)
        itemPosition = pt
        beacon.position = pt
        tone.position = pt
        if voiceSpot == .item { voice.position = pt }
    }

    /// Where the voice's own point is now, listener-relative. Call every tick after `say(_:at:)`.
    func moveVoice(_ p: SIMD3<Float>) {
        guard voiceSpot == .point else { return }
        voice.position = AVAudio3DPoint(x: p.x, y: p.y, z: p.z)
    }

    /// How long after rendering a sound reaches the ears: the route's output latency (most of it Bluetooth, for
    /// AirPods), one I/O buffer, and the AirPods' motion report on the way in. YawPredictor leads the head by this.
    var audioLagS: Double {
        #if os(iOS)
        let s = AVAudioSession.sharedInstance()
        return min(max(s.outputLatency + s.ioBufferDuration + 0.03, 0.03), 0.25)
        #else
        return 0.05
        #endif
    }

    private func aim(_ spot: VoiceSpot, _ p: SIMD3<Float>? = nil) {
        voiceSpot = spot
        switch spot {
        case .ahead: voice.position = Self.ahead
        case .item: voice.position = itemPosition
        case .point: if let p { voice.position = AVAudio3DPoint(x: p.x, y: p.y, z: p.z) }
        }
    }

    /// Sound cues. .say, .playLabel and .haptic are routed by the app (speech needs a place).
    func play(_ cue: Cue) {
        switch cue {
        case .beacon(let b):
            let buffer: AVAudioPCMBuffer
            switch b {
            case .onBeam: buffer = beamPulse
            case .offBeam: buffer = beep
            case .behind: buffer = beepMuffled
            case .here: buffer = herePing
            }
            beacon.scheduleBuffer(buffer, at: nil, options: [], completionHandler: nil)
        case .ding:
            beacon.scheduleBuffer(ding, at: nil, options: [.interrupts], completionHandler: nil)
        case .arrive:
            beacon.scheduleBuffer(arrive, at: nil, options: [.interrupts], completionHandler: nil)
        case .handPing(let step):
            beacon.scheduleBuffer(handPings[min(max(step, 0), handPings.count - 1)], at: nil, options: [], completionHandler: nil)
        case .steadyTone(let on):
            if on {
                tone.scheduleBuffer(steady, at: nil, options: [.loops, .interrupts], completionHandler: nil)
            } else {
                tone.stop()
                tone.play()
            }
        case .silence:
            cancelVoice()
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
        aim(atItem ? .item : .ahead)
        speak(text)
    }

    /// Marco's voice from a point in the room (listener-relative now; keep it current with `moveVoice`).
    func say(_ text: String, at p: SIMD3<Float>) {
        aim(.point, p)
        speak(text)
    }

    private func speak(_ text: String) {
        cancelVoice()
        let ticket = speechGeneration
        speechOutput.audio(for: text) { [weak self] data in
            guard let self, self.speechGeneration == ticket, self.engine.isRunning else { return }
            if let data, let mono = try? self.speechBuffer(data) {
                self.voice.scheduleBuffer(mono, at: nil, options: [.interrupts], completionHandler: nil)
            } else {
                self.appleSpeech(text, ticket: ticket)
            }
        }
    }

    func configureSpeech(base: URL?) { speechOutput.configure(base: base) }

    /// Invalidate network replies and Apple callbacks as well as the sound already playing.
    private func cancelVoice() {
        speechGeneration += 1
        speechOutput.cancel()
        synth.stopSpeaking(at: .immediate)
        voice.stop()
        if engine.isRunning { voice.play() }
    }

    private func speechBuffer(_ data: Data) throws -> AVAudioPCMBuffer {
        let url = FileManager.default.temporaryDirectory.appendingPathComponent("speech-\(UUID().uuidString).wav")
        defer { try? FileManager.default.removeItem(at: url) }
        try data.write(to: url, options: .atomic)
        return try monoBuffer(url)
    }

    private func appleSpeech(_ text: String, ticket: Int) {
        let u = AVSpeechUtterance(string: text)
        u.voice = AVSpeechSynthesisVoice(language: "en-US")
        synth.write(u) { [weak self] buffer in
            guard let pcm = buffer as? AVAudioPCMBuffer, pcm.frameLength > 0 else { return }
            DispatchQueue.main.async {
                guard let self, self.speechGeneration == ticket, self.engine.isRunning else { return }
                if self.speechConverter?.inputFormat != pcm.format {
                    self.speechConverter = AVAudioConverter(from: pcm.format, to: self.format)
                }
                guard let conv = self.speechConverter, let mono = Self.convert(pcm, with: conv, to: self.format, endOfStream: false) else { return }
                self.voice.scheduleBuffer(mono, completionHandler: nil)
            }
        }
    }

    private func monoBuffer(_ url: URL) throws -> AVAudioPCMBuffer {
        let file = try AVAudioFile(forReading: url)
        guard let pcm = AVAudioPCMBuffer(pcmFormat: file.processingFormat, frameCapacity: AVAudioFrameCount(file.length)) else {
            throw PlaybackError.unreadableAudio
        }
        try file.read(into: pcm)
        guard let conv = AVAudioConverter(from: pcm.format, to: format),
              let mono = Self.convert(pcm, with: conv, to: format, endOfStream: true) else {
            throw PlaybackError.unreadableAudio
        }
        return mono
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

    /// Listening: one short, quiet rising note, unlike any guidance sound.
    static func blip(_ format: AVAudioFormat) -> AVAudioPCMBuffer {
        buffer(format, seconds: 0.12) { t in
            let f = 520 + 1400 * t                  // a glide up
            let env = min(1, t / 0.01) * exp(-t / 0.05)
            return Float(0.25 * env * (sin(2 * .pi * f * t) + 0.3 * sin(4 * .pi * f * t)))
        }
    }

    /// Stop walking: three rising bell notes (a major triad), unlike the facing ding's two.
    static func arrive(_ format: AVAudioFormat) -> AVAudioPCMBuffer {
        let notes = [(1046.5, 0.0), (1318.5, 0.13), (1568.0, 0.26)]
        return buffer(format, seconds: 0.62) { t in
            var s = 0.0
            for (f, t0) in notes where t >= t0 {
                let u = t - t0
                s += min(1, u / 0.003) * exp(-u / 0.09) * (sin(2 * .pi * f * u) + 0.3 * sin(2 * .pi * 2.76 * f * u))
            }
            return Float(0.3 * s)
        }
    }

    /// The hand's pitches, rising as the fingertip closes in (D major pentatonic, D5 to D6). The held tone on
    /// contact is the top note, so the ladder ends on it.
    static let handScale = [587.33, 659.26, 739.99, 880.0, 987.77, 1174.66]

    /// A short pitched ping with a click on its front: the click is the transient the HRTF places.
    static func ping(_ format: AVAudioFormat, freq: Double, amp: Double = 0.3, ms: Double = 60) -> AVAudioPCMBuffer {
        var rng = SystemRandomNumberGenerator()
        return buffer(format, seconds: ms / 1000) { t in
            let env = min(1, t / 0.002) * exp(-t / 0.018)
            let click = t < 0.003 ? Double.random(in: -0.5...0.5, using: &rng) * (1 - t / 0.003) : 0
            return Float(amp * (env * (sin(2 * .pi * freq * t) + 0.25 * sin(2 * .pi * 3 * freq * t)) + click))
        }
    }

    /// One second of a soft tone; whole cycles, so it loops without a click.
    static func loop(_ format: AVAudioFormat, freq: Double) -> AVAudioPCMBuffer {
        buffer(format, seconds: 1.0) { t in
            Float(0.22 * (sin(2 * .pi * freq * t) + 0.4 * sin(4 * .pi * freq * t) + 0.2 * sin(6 * .pi * freq * t)))
        }
    }
}
