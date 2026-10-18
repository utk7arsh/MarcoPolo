import AVFAudio
import Foundation
import Speech

/// Speech in, from whichever mic the session routed (the AirPods' own, through Bluetooth high-quality recording, or
/// the iPhone's; see SpatialAudio.applyRoute). Listens all the time for "Marco, ..." with on-device recognition, and
/// does push-to-talk without the wake word. "Marco" alone, then a pause, makes the next words the command.
final class Listener {
    var onIntent: ((Intent?, String) -> Void)?   // nil intent: a command was heard but not understood
    var onTranscript: ((String) -> Void)?
    var onWake: (() -> Void)?                    // "Marco" alone: say the rest now
    var onError: ((String) -> Void)?

    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private let engine = AVAudioEngine()
    private let queue = DispatchQueue(label: "marco.listener")
    private let lock = NSLock()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var debounce: DispatchWorkItem?
    private var configObserver: NSObjectProtocol?
    // Listener queue only.
    private var generation = 0
    private var pushToTalk = false
    private var armedUntil = 0.0
    private var items = ItemVocabulary()
    static let pauseS = 0.9                      // silence after the last word that ends a command
    static let quickPauseS = 0.45                // ...when it already names a whole registered item
    static let armedS = 5.0                      // after "Marco" alone
    static let restartS = 50.0                   // server-side recognition stops after about a minute

    static func requestPermissions(_ done: @escaping (Bool) -> Void) {
        SFSpeechRecognizer.requestAuthorization { status in
            guard status == .authorized else { return done(false) }
            AVAudioApplication.requestRecordPermission { done($0) }
        }
    }

    /// The registered items: recognizer hints ("cumin", not "human"), and what "where are my ..." resolves to.
    func setItems(_ names: [String]) {
        queue.async { self.items = ItemVocabulary(names) }
    }

    func start() throws {
        try startEngine()
        // A route change (AirPods in or out, the mic switched) stops the engine and can change the input format.
        configObserver = NotificationCenter.default.addObserver(forName: .AVAudioEngineConfigurationChange, object: engine,
                                                                queue: nil) { [weak self] _ in
            self?.queue.async { self?.reconfigure(attempt: 0) }
        }
        queue.async { self.restart() }
    }

    func stop() {
        if let o = configObserver { NotificationCenter.default.removeObserver(o) }
        configObserver = nil
        engine.stop()
        engine.inputNode.removeTap(onBus: 0)
        queue.async {
            self.task?.cancel()
            self.task = nil
        }
    }

    /// Hold-to-talk: whatever is said until release is the command, no "Marco" needed.
    func beginPushToTalk() {
        queue.async {
            self.pushToTalk = true
            self.restart()
        }
    }

    func endPushToTalk() {
        queue.asyncAfter(deadline: .now() + Self.pauseS + 0.6) { self.pushToTalk = false }
    }

    /// The tap takes the input's format at this moment, which depends on the mic the route uses.
    private func startEngine() throws {
        let input = engine.inputNode
        let fmt = input.outputFormat(forBus: 0)
        guard fmt.sampleRate > 0, fmt.channelCount > 0 else {     // mid route change: no input yet
            throw NSError(domain: "Listener", code: 1, userInfo: [NSLocalizedDescriptionKey: "no microphone input"])
        }
        input.removeTap(onBus: 0)
        input.installTap(onBus: 0, bufferSize: 1024, format: fmt) { [weak self] buf, _ in
            guard let self else { return }
            self.lock.lock()
            let r = self.request
            self.lock.unlock()
            r?.append(buf)
        }
        engine.prepare()
        try engine.start()
    }

    private func reconfigure(attempt: Int) {
        do {
            engine.stop()
            try startEngine()
            restart()                                // a request is fed one format only
        } catch {
            guard attempt < 5 else {
                onError?("mic lost after a route change: \(error.localizedDescription)")
                return
            }
            queue.asyncAfter(deadline: .now() + 0.5) { self.reconfigure(attempt: attempt + 1) }
        }
    }

    private var now: Double { ProcessInfo.processInfo.systemUptime }

    private func restart() {
        generation += 1
        let gen = generation
        task?.cancel()
        debounce?.cancel()
        let req = SFSpeechAudioBufferRecognitionRequest()
        req.shouldReportPartialResults = true
        req.taskHint = .search
        req.contextualStrings = ["Marco"] + items.names
        if recognizer?.supportsOnDeviceRecognition == true { req.requiresOnDeviceRecognition = true }
        lock.lock()
        request = req
        lock.unlock()
        task = recognizer?.recognitionTask(with: req) { [weak self] result, error in
            guard let self else { return }
            self.queue.async {
                guard gen == self.generation else { return }
                if let r = result { self.heard(r.bestTranscription.formattedString, final: r.isFinal) }
                if error != nil || result?.isFinal == true {
                    self.queue.asyncAfter(deadline: .now() + 0.3) { if gen == self.generation { self.restart() } }
                }
            }
        }
        queue.asyncAfter(deadline: .now() + Self.restartS) { if gen == self.generation { self.restart() } }
    }

    /// What in a transcript is meant for Marco: all of it while holding to talk or just after "Marco", otherwise
    /// the words after the wake word. "" is the wake word alone; nil means it isn't for us.
    private func command(in text: String) -> String? {
        if pushToTalk || now < armedUntil { return Speech.command(after: text) ?? Speech.normalize(text) }
        return Speech.command(after: text)
    }

    private func heard(_ text: String, final: Bool) {
        onTranscript?(text)
        debounce?.cancel()
        let gen = generation
        let fire = DispatchWorkItem { [weak self] in
            guard let self, gen == self.generation else { return }
            self.finish(text)
        }
        debounce = fire
        let quick = command(in: text).map { Speech.isComplete($0, items: items) } ?? false
        queue.asyncAfter(deadline: .now() + (final ? 0 : quick ? Self.quickPauseS : Self.pauseS), execute: fire)
    }

    private func finish(_ text: String) {
        guard let command = command(in: text) else { return }    // no wake word: not for us
        if command.isEmpty {                                       // "Marco" ... : listen for the rest
            guard Speech.command(after: text) != nil else { return }   // an empty result, not the wake word
            armedUntil = now + Self.armedS
            onWake?()
            return restart()
        }
        armedUntil = 0
        onIntent?(Speech.intent(command, items: items), command)
        restart()                                                  // so the same words don't fire twice
    }
}
