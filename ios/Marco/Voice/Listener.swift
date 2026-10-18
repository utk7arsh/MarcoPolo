import AVFAudio
import Foundation
import Speech

/// Speech in, from the iPhone's mic (the AirPods stay in A2DP for spatial audio; see SpatialAudio.start). Listens
/// all the time for "Marco, ..." with on-device recognition, and does push-to-talk without the wake word.
final class Listener {
    var onIntent: ((Intent?, String) -> Void)?   // nil intent: a command was heard but not understood
    var onTranscript: ((String) -> Void)?

    private let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US"))
    private let engine = AVAudioEngine()
    private let queue = DispatchQueue(label: "marco.listener")
    private let lock = NSLock()
    private var request: SFSpeechAudioBufferRecognitionRequest?
    private var task: SFSpeechRecognitionTask?
    private var debounce: DispatchWorkItem?
    private var generation = 0
    private var pushToTalk = false
    static let pauseS = 0.9                      // silence after the last word that ends a command
    static let restartS = 50.0                   // server-side recognition stops after about a minute

    private enum StartError: Error { case recognitionUnavailable }

    static func requestPermissions(_ done: @escaping (Bool) -> Void) {
        SFSpeechRecognizer.requestAuthorization { status in
            guard status == .authorized else { return done(false) }
            AVAudioApplication.requestRecordPermission { done($0) }
        }
    }

    func start() throws {
        guard recognizer?.isAvailable == true else { throw StartError.recognitionUnavailable }
        let input = engine.inputNode
        let fmt = input.outputFormat(forBus: 0)
        input.removeTap(onBus: 0)
        input.installTap(onBus: 0, bufferSize: 1024, format: fmt) { [weak self] buf, _ in
            guard let self else { return }
            self.lock.lock()
            let r = self.request
            self.lock.unlock()
            r?.append(buf)
        }
        engine.prepare()
        do { try engine.start() } catch {
            input.removeTap(onBus: 0)
            throw error
        }
        queue.async { self.restart() }
    }

    func stop() {
        engine.stop()
        engine.inputNode.removeTap(onBus: 0)
        queue.async {
            self.generation += 1
            self.debounce?.cancel()
            self.debounce = nil
            self.pushToTalk = false
            self.task?.cancel()
            self.task = nil
            self.lock.lock()
            self.request = nil
            self.lock.unlock()
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

    private func restart() {
        generation += 1
        let gen = generation
        task?.cancel()
        debounce?.cancel()
        let req = SFSpeechAudioBufferRecognitionRequest()
        req.shouldReportPartialResults = true
        req.taskHint = .search
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

    private func heard(_ text: String, final: Bool) {
        onTranscript?(text)
        debounce?.cancel()
        let gen = generation
        let fire = DispatchWorkItem { [weak self] in
            guard let self, gen == self.generation else { return }
            self.finish(text)
        }
        debounce = fire
        queue.asyncAfter(deadline: .now() + (final ? 0 : Self.pauseS), execute: fire)
    }

    private func finish(_ text: String) {
        let command = pushToTalk ? Speech.normalize(text) : Speech.command(after: text)
        guard let command, !command.isEmpty else { return }      // no wake word: not for us
        onIntent?(Speech.intent(command), command)
        restart()                                                // so the same words don't fire twice
    }
}
