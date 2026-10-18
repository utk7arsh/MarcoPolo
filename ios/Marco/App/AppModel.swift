import ARKit
import Foundation
import SwiftUI
import UIKit

/// Wires the app together:
///   ARKit frames (60 Hz)  -> frames to the server at 1/s, poses at 10/s, the hand stream at 15/s
///   server messages       -> guidance, Marco's voice, labels
///   voice and buttons     -> queries
/// and runs the §7 guidance loop at 60 Hz on the main thread.
final class AppModel: ObservableObject {
    // The debug screen (main thread only).
    @Published var serverText = Config.serverURL?.absoluteString ?? ""
    @Published var running = false
    @Published var socketUp = false
    @Published var tracking = "not started"
    @Published var mapId = ""
    @Published var framesAccepted = 0
    @Published var lastUpload = ""
    @Published var headSource = "phone"
    @Published var headYaw = 0.0
    @Published var phase = Phase.off
    @Published var relAzimuth = 0.0
    @Published var distance = 0.0
    @Published var heard = ""
    @Published var micInfo = ""
    @Published var log: [String] = []
    @Published var recording = false
    @Published var recordInfo = "off"
    @Published var linkInfo = ""
    @Published var airpodsInfo = "not connected"
    @Published var signInfo = ""
    @Published var shareFile: ShareFile?

    let sessionId = UUID().uuidString

    private struct Live {
        var T: simd_float4x4?
        var headYaw = 0.0
        var headSource = "phone"
        var signEvidence = 0.0
        var realignments = 0
    }

    private let ar = ARSessionManager()
    private let encoder = FrameEncoder()
    private let hands = HandTracker()
    private let head = HeadTracker()
    private let audio = SpatialAudio()
    private let listener = Listener()
    private let haptic = UIImpactFeedbackGenerator(style: .heavy)
    private let live = Locked(Live())
    private let encodeQueue = DispatchQueue(label: "marco.encode")
    private let handQueue = DispatchQueue(label: "marco.hands")
    private let recorder = Recorder(root: Recorder.documents)
    private let poseRate = Locked(RateMeter())
    private let handRate = Locked(RateMeter())
    private var frameRate = RateMeter()                                // main thread
    private var uploader: Uploader?                                    // set once in start(), before ARKit runs
    private var socket: PhoneSocket?

    // ARKit queue only.
    private var fusion = HeadFusion()
    private var frameGate = Throttle(hz: Config.frameHz)
    private var poseGate = Throttle(hz: Config.poseHz)
    private var handGate = Throttle(hz: Config.handHz)
    private var frameId = 0
    private var handBusy = false

    // Main thread only.
    private var guidance = Guidance()
    private var guidanceGate = Throttle(hz: Config.guidanceMsgHz)
    private var uiGate = Throttle(hz: 10)
    private var timer: Timer?
    private var asked: [String: String] = [:]                          // find query_id -> the name asked for
    private var labels: [String: (text: String?, url: String?)] = [:]  // item_id -> its label
    private var audioCache: [String: URL] = [:]                        // label_audio_url -> local file
    private var vocabulary = ItemVocabulary()                          // registered item names, for the listener

    /// The clock of ARFrame.timestamp and CMDeviceMotion.timestamp.
    private var now: Double { ProcessInfo.processInfo.systemUptime }

    // MARK: - Start

    /// With a server URL: stream to it. With the field empty: record only (Record, then Export or Finder), for a
    /// walk with no server or network; the recording is in the server's own layout (Core/Recorder.swift).
    func start() {
        guard !running else { return }
        let text = serverText.trimmingCharacters(in: .whitespaces)
        var url: URL?
        if !text.isEmpty {
            guard let u = URL(string: text), let scheme = u.scheme, ["https", "http"].contains(scheme) else {
                return note("Server URL: https://<server-mac>.<tailnet>.ts.net, or leave it empty to record only.")
            }
            url = u
        }
        guard ARSessionManager.supported else { return note("This device has no LiDAR scene depth.") }
        if let url { Config.serverURL = url }
        running = true
        UIApplication.shared.isIdleTimerDisabled = true          // ARKit stops when the screen locks

        audio.onRoute = { [weak self] route in DispatchQueue.main.async { self?.micInfo = route } }
        do { try audio.start() } catch { note("audio: \(error.localizedDescription)") }
        micInfo = SpatialAudio.routeDescription()

        if let url {
            let up = Uploader(base: url)
            up.onResult = { [weak self] code, body, ms in DispatchQueue.main.async { self?.uploaded(code, body, ms) } }
            uploader = up
            refreshItems()

            let sock = PhoneSocket(base: url)
            sock.onMessage = { [weak self] m in DispatchQueue.main.async { self?.handle(m) } }
            sock.onState = { [weak self] isUp in
                DispatchQueue.main.async {
                    if isUp && self?.socketUp == false { self?.refreshItems() }   // items added while we were away
                    self?.socketUp = isUp
                }
            }
            sock.onUndecodable = { [weak self] s in DispatchQueue.main.async { self?.note("undecodable: \(s)") } }
            sock.connect()
            socket = sock
            ServerCheck.run(base: url) { [weak self] line in self?.note(line) }   // Tailscale off? not on the allow-list?
        } else {
            note("No server: recording only. Press Record, walk, then Export.")
        }

        head.start()
        listener.onIntent = { [weak self] intent, text in DispatchQueue.main.async { self?.act(intent, text) } }
        listener.onTranscript = { [weak self] text in DispatchQueue.main.async { self?.heard = text } }
        listener.onWake = { [weak self] in
            DispatchQueue.main.async {
                self?.heard = "Marco... (listening)"
                self?.audio.listening()
            }
        }
        listener.onError = { [weak self] e in DispatchQueue.main.async { self?.note("listener: \(e)") } }
        Listener.requestPermissions { [weak self] ok in
            DispatchQueue.main.async {
                guard let self else { return }
                guard ok else { return self.note("Speech or microphone permission denied: use the buttons.") }
                do { try self.listener.start() } catch { self.note("listener: \(error.localizedDescription)") }
            }
        }

        ar.onFrame = { [weak self] f in self?.onFrame(f) }
        ar.onTracking = { [weak self] s in DispatchQueue.main.async { self?.tracking = s } }
        ar.onMapEvent = { [weak self] e, id in self?.mapEvent(e, id) }
        ar.onLost = { [weak self] in DispatchQueue.main.async { self?.speak(Lines.bearings) } }
        ar.start()

        let t = Timer(timeInterval: 1.0 / 60, repeats: true) { [weak self] _ in self?.tick() }
        RunLoop.main.add(t, forMode: .common)
        timer = t
    }

    func saveMap() { ar.saveMap() }

    func newMap() { ar.startFreshMap() }

    func pushToTalk(_ down: Bool) { down ? listener.beginPushToTalk() : listener.endPushToTalk() }

    /// The debug screen's mic switch changed (Config.useIPhoneMic): re-route; both audio engines restart themselves.
    func micChanged() {
        do { try audio.applyRoute() } catch { note("mic route: \(error.localizedDescription)") }
        micInfo = SpatialAudio.routeDescription()
    }

    /// The registered items: their labels (audio cached now) and their names, which the listener matches speech to.
    private func refreshItems() {
        uploader?.items { [weak self] items in
            DispatchQueue.main.async {
                guard let self, let items else { return }
                for it in items where it.label_text != nil || it.label_audio_url != nil {
                    self.labels[it.item_id] = (Lines.spokenLabel(name: it.name, labelText: it.label_text), it.label_audio_url)
                    self.cache(it.label_audio_url)
                }
                self.learn(items.map(\.name))
            }
        }
    }

    /// Item names also arrive on server messages (an item registered over Photon after launch): no refetch needed.
    private func learn(_ names: [String?]) {
        var added = false
        for case let n? in names { added = vocabulary.add(n) || added }
        if added { listener.setItems(vocabulary.names) }
    }

    // MARK: - ARKit queue

    private func onFrame(_ frame: ARFrame) {
        let T = frame.camera.transform
        let t = frame.timestamp
        let torso = Geo.headingDeg(T)
        let yaw: Double
        if let s = head.sample(now: now) {
            yaw = fusion.update(t: s.t, torsoDeg: torso, airpodsDeg: s.yawDeg)
        } else {
            yaw = fusion.update(t: t, torsoDeg: torso, airpodsDeg: nil)
        }
        let source = fusion.source
        let evidence = fusion.signEvidence, realigned = fusion.realignments
        live.write {
            $0.T = T
            $0.headYaw = yaw
            $0.headSource = source
            $0.signEvidence = evidence
            $0.realignments = realigned
        }
        // §3.1: nothing goes out while tracking is limited or before relocalization finishes.
        guard case .normal = frame.camera.trackingState, !ar.relocalizing, socket != nil || recorder.isRecording else { return }
        let mapId = ar.mapId
        if poseGate.ready(t) {
            emit(PoseMsg(session_id: sessionId, map_id: mapId, t_device: t, camera_transform: Geo.flat(T),
                         head_yaw_deg: (yaw * 100).rounded() / 100, head_source: source))
            poseRate.write { $0.tick(t) }
        }
        if frameGate.ready(t) { upload(frame, mapId: mapId) }
        if handGate.ready(t) && !handBusy {
            handBusy = true
            handQueue.async {
                self.sendHand(frame, mapId: mapId)
                self.ar.queue.async { self.handBusy = false }
            }
        }
    }

    private func upload(_ frame: ARFrame, mapId: String) {
        guard let depth = frame.smoothedSceneDepth ?? frame.sceneDepth, let confMap = depth.confidenceMap,
              uploader != nil || recorder.isRecording else { return }
        frameId += 1
        let res = frame.camera.imageResolution
        let meta = FrameMeta(session_id: sessionId, map_id: mapId, frame_id: frameId, t_device: frame.timestamp,
                             t_wall: Clock.wall(), tracking: "normal", camera_transform: Geo.flat(frame.camera.transform),
                             intrinsics: Geo.flat(frame.camera.intrinsics), image_resolution: [Int(res.width), Int(res.height)],
                             jpeg_scale: Config.jpegScale)
        let image = frame.capturedImage
        let depthMap = depth.depthMap
        encodeQueue.async {
            guard let jpeg = self.encoder.jpeg(image) else { return }
            let d = FrameEncoder.plane(depthMap, as: Float32.self)
            let c = FrameEncoder.plane(confMap, as: UInt8.self)
            guard let dz = try? Wire.depthPayload(d.values), let cz = try? Wire.confidencePayload(c.values) else { return }
            if let m = try? JSONEncoder().encode(meta) {
                self.recorder.frame(meta: m, frameId: meta.frame_id, jpeg: jpeg, depth: dz, confidence: cz)
            }
            self.uploader?.submit(Uploader.Frame(meta: meta, jpeg: jpeg, depth: dz, confidence: cz))
        }
    }

    /// Every phone-to-server WebSocket message goes through here: encoded once, recorded if recording, sent if
    /// connected. hold: keep it until the socket is open (map events, queries) instead of dropping it.
    private func emit<T: Encodable>(_ msg: T, hold: Bool = false) {
        guard let data = try? JSONEncoder().encode(msg) else { return }
        recorder.message(data)
        if hold { socket?.sendWhenOpen(json: data) } else { socket?.send(json: data) }
    }

    /// Hand queue.
    private func sendHand(_ frame: ARFrame, mapId: String) {
        guard let depth = frame.smoothedSceneDepth ?? frame.sceneDepth, let confMap = depth.confidenceMap,
              let found = try? hands.detect(frame.capturedImage) else { return }      // nil: no hand in view
        let d = FrameEncoder.plane(depth.depthMap, as: Float32.self)
        let c = FrameEncoder.plane(confMap, as: UInt8.self)
        emit(HandMsg.make(sessionId: sessionId, mapId: mapId, t: frame.timestamp, transform: frame.camera.transform,
                          joints: found.joints, chirality: found.chirality, depth: d.values, conf: c.values,
                          width: d.width, height: d.height))
        handRate.write { $0.tick(frame.timestamp) }
    }

    private func mapEvent(_ event: String, _ id: String) {
        emit(MapMsg(session_id: sessionId, event: event, map_id: id), hold: true)
        DispatchQueue.main.async {
            self.mapId = id
            if event != "saved" { self.note("map \(event) \(id.prefix(8))") }
        }
    }

    // MARK: - Main thread

    private func tick() {
        let l = live.read { $0 }
        let t = now
        if let T = l.T, guidance.active {
            let chest = Geo.position(T)
            let ear = chest + SIMD3<Float>(0, Config.earAboveChestM, 0)
            play(guidance.tick(now: t, chest: chest, ear: ear, headYawDeg: l.headYaw))
            if let tg = guidance.target {
                audio.place(Geo.listenerRelative(ear: ear, headYawDeg: l.headYaw, target: tg.position))
            }
            if guidanceGate.ready(t) || !guidance.active { sendGuidance() }
        }
        if uiGate.ready(t) {
            headYaw = l.headYaw
            headSource = l.headSource
            phase = guidance.phase
            relAzimuth = guidance.relAzimuthDeg
            distance = guidance.distanceM
            refreshHealth(t, l)
        }
    }

    /// The debug screen's health rows (10/s): link, AirPods, recording.
    private func refreshHealth(_ t: Double, _ l: Live) {
        let poses = poseRate.read { m -> Double in var c = m; return c.rate(t) }
        let hands = handRate.read { m -> Double in var c = m; return c.rate(t) }
        linkInfo = String(format: "frames %.1f/s · poses %.0f/s · hands %.0f/s", frameRate.rate(t), poses, hands)
        let a = head.health
        airpodsInfo = a.samples == 0 ? "no samples (AirPods in? motion allowed?)"
            : String(format: "%.0f Hz · jitter %.0f ms · latency %.0f ms · raw yaw %.0f°", a.rateHz, a.jitterMs, a.latencyMs, a.yawDeg)
        if abs(l.signEvidence) < 50 {
            signInfo = "turn your whole body a few times to check · realigned \(l.realignments)×"
        } else {
            signInfo = (l.signEvidence > 0 ? "AirPods sign agrees with ARKit ✓" : "AirPods sign INVERTED: flip it")
                + " · realigned \(l.realignments)×"
        }
        if recording {
            let p = recorder.progress
            recordInfo = "● \(p.frames) frames · \(p.messages) messages · \(p.bytes / 1_000_000) MB"
        }
    }

    private func sendGuidance() {
        emit(GuidanceMsg(session_id: sessionId, item_id: guidance.target?.itemId, phase: guidance.phase.rawValue,
                         rel_azimuth_deg: (guidance.relAzimuthDeg * 10).rounded() / 10,
                         distance_m: (guidance.distanceM * 100).rounded() / 100))
    }

    private func handle(_ m: ServerMessage) {
        switch m {
        case .find(let a) where a.reason != "not_registered": learn([a.name])
        case .whatIsThis(let a): learn([a.name])
        case .touch(let tm): learn([tm.name])
        case .event(let e): learn([e.name])
        case .labelReady(let l): learn([l.name])
        default: break
        }
        switch m {
        case .find(let a): found(a)
        case .whatIsThis(let a): whatIsThis(a)
        case .setPlace(let a): if a.ok == true { speak(Lines.doorSet) }
        case .touch(let tm): touched(tm)
        case .touchEnd: break
        case .handProximity(let p): guidance.handProximity(itemId: p.item_id, distanceM: p.distance_m, t: now)
        case .event(let e): worldEvent(e)
        case .labelReady(let l):
            labels[l.item_id] = (Lines.spokenLabel(name: l.name, labelText: l.label_text), l.label_audio_url)
            cache(l.label_audio_url)
            speak(Lines.labelReady(l))
        case .error(let e): note("server: \(e.detail)")
        case .other(let type): note("unhandled \(type)")
        }
    }

    private func found(_ a: FindAnswer) {
        let asked = a.query_id.flatMap { self.asked.removeValue(forKey: $0) } ?? a.name ?? "thing"
        guard a.found, let id = a.item_id, let p = Geo.vec(a.position), let T = live.read({ $0.T }) else {
            return speak(Lines.notFound(a, asked: asked))
        }
        let chest = Geo.position(T)
        let yaw = live.read { $0.headYaw }
        let bodyAz = Geo.relativeAzimuthDeg(from: chest, headingDeg: Geo.headingDeg(T), to: p)   // "behind you" means the body
        let label = labels[id]
        play(guidance.stop())
        guidance.start(GuidanceTarget(itemId: id, name: a.name ?? asked, position: p, surface: a.surface,
                                      labelText: label?.text, labelAudioURL: label?.url), now: now)
        let ear = chest + SIMD3<Float>(0, Config.earAboveChestM, 0)
        audio.place(Geo.listenerRelative(ear: ear, headYawDeg: yaw, target: p))
        audio.say(Lines.polo(relAzimuthDeg: bodyAz, distanceM: Geo.horizontalDistance(chest, p), surface: a.surface), atItem: true)
        note("find \(asked): \(a.surface ?? "?"), \(Int(bodyAz)) deg, \(String(format: "%.1f", Geo.horizontalDistance(chest, p))) m")
    }

    private func whatIsThis(_ a: WhatAnswer) {
        if a.status == "known", let url = a.label_audio_url {
            if let file = audioCache[url], (try? audio.playFile(file, atItem: false)) != nil { return }
            cache(url)
        }
        if let line = Lines.whatIsThis(a) { speak(line) }
    }

    /// On the guided item: the end of guidance. Otherwise name what the hand is on (telling identical jars apart).
    private func touched(_ tm: TouchMsg) {
        let cues = guidance.touched(itemId: tm.item_id, t: now)
        if !cues.isEmpty { return play(cues) }
        guard let id = tm.item_id else { return }
        let label = labels[id]
        if let url = label?.url, let file = audioCache[url], (try? audio.playFile(file, atItem: false)) != nil { return }
        if let line = Lines.touchedKnown(name: tm.name, labelText: label?.text) { speak(line) }
    }

    private func worldEvent(_ e: WorldEventMsg) {
        switch e.kind {
        case "moved", "put_down", "seen":
            if let p = Geo.vec(e.position) { guidance.retarget(itemId: e.item_id, position: p) }
        case "left_behind":
            haptic.impactOccurred()
            speak(Lines.leftBehind(e))
        default:
            break
        }
    }

    private func play(_ cues: [Cue]) {
        for c in cues {
            switch c {
            case .haptic: haptic.impactOccurred()
            case .say(let s): audio.say(s, atItem: true)
            case .playLabel(let url):
                if let f = audioCache[url], (try? audio.playFile(f, atItem: true)) != nil { continue }
                audio.say("Got it.", atItem: true)
            default: audio.play(c)
            }
        }
    }

    /// Voice and the debug buttons both end up here.
    func act(_ intent: Intent?, _ text: String) {
        heard = text
        note("heard \"\(text)\" -> \(intent.map { String(describing: $0) } ?? "not understood")")
        guard let intent else { return speak(Lines.notUnderstood) }
        switch intent {
        case .find(let name): query("find", name: name)
        case .whatIsThis: query("what_is_this")
        case .setDoor: query("set_place", name: "door")
        case .stop: stopGuidance()
        }
    }

    func stopGuidance() {
        let was = guidance.active
        play(guidance.stop())
        audio.play(.silence)
        if was { sendGuidance() }
    }

    private func query(_ kind: String, name: String? = nil) {
        guard socket != nil, socketUp else { return speak(Lines.noServer) }
        let qid = UUID().uuidString
        if let name { asked[qid] = name }
        emit(QueryMsg(session_id: sessionId, query_id: qid, kind: kind, name: name), hold: true)
        note("-> \(kind) \(name ?? "")")
    }

    // MARK: - Recording (Core/Recorder.swift: the server's own layout, so server/tools read it as is)

    func toggleRecording() {
        if recorder.isRecording {
            recorder.stop()
            recording = false
            recordInfo = "stopped: Documents/sessions/\(Recorder.folderName(sessionId))"
        } else {
            let d = recorder.start(sessionId: sessionId)
            recording = true
            note("recording to Documents/sessions/\(d.lastPathComponent)")
        }
    }

    /// Zips this launch's recording for AirDrop (the Mac's Finder also shows Documents/sessions under Files).
    func exportRecording() {
        let dir = recorder.root.appendingPathComponent(Recorder.folderName(sessionId))
        guard FileManager.default.fileExists(atPath: dir.appendingPathComponent("frames.jsonl").path) else {
            return note("Nothing recorded in this launch yet.")
        }
        let rec = recorder
        DispatchQueue.global(qos: .userInitiated).async {
            rec.flush()
            var zipped: URL?
            var err: NSError?
            NSFileCoordinator().coordinate(readingItemAt: dir, options: [.forUploading], error: &err) { zip in
                let dest = FileManager.default.temporaryDirectory.appendingPathComponent("marco-\(dir.lastPathComponent).zip")
                try? FileManager.default.removeItem(at: dest)
                if (try? FileManager.default.copyItem(at: zip, to: dest)) != nil { zipped = dest }
            }
            DispatchQueue.main.async {
                if let zipped { self.shareFile = ShareFile(url: zipped) } else { self.note("export failed: \(err?.localizedDescription ?? "zip")") }
            }
        }
    }

    func register(name: String, photo: Data) {
        guard let up = uploader else { return note("Press Start first.") }
        up.register(name: name, photo: photo) { [weak self] result in
            DispatchQueue.main.async {
                switch result {
                case .success(let r):
                    if r.quality == "ok" { self?.learn([name]) }
                    self?.speak(Lines.registration(r, name: name))
                    self?.note("registered \(name): \(r.quality) \(r.reason ?? "")")
                case .failure(let e):
                    self?.note("register failed: \(e.localizedDescription)")
                }
            }
        }
    }

    /// The phone caches label audio, so touch playback never waits for the network (§4).
    private func cache(_ url: String?) {
        guard let url, audioCache[url] == nil, let up = uploader else { return }
        up.fetch(path: url) { [weak self] data, mime in
            guard let data else { return }
            let ext = ["audio/x-caf": "caf", "audio/mpeg": "mp3", "audio/wav": "wav"][mime ?? ""] ?? "m4a"
            let file = FileManager.default.temporaryDirectory.appendingPathComponent("label-\(UUID().uuidString).\(ext)")
            guard (try? data.write(to: file)) != nil else { return }
            DispatchQueue.main.async { self?.audioCache[url] = file }
        }
    }

    private func uploaded(_ code: Int, _ body: String, _ ms: Double) {
        if code == 202 {
            framesAccepted += 1
            frameRate.tick(now)
            lastUpload = String(format: "202 · %.0f ms round trip", ms)
        } else {
            lastUpload = "\(code): \(body.prefix(160))"
            note("frame upload \(code): \(body.prefix(240))")
        }
    }

    private func speak(_ line: String) {
        audio.say(line, atItem: false)
        note("says: \(line)")
    }

    private func note(_ s: String) {
        log.insert(s, at: 0)
        if log.count > 60 { log.removeLast(log.count - 60) }
    }
}

/// A file for the share sheet (the zipped recording).
struct ShareFile: Identifiable {
    let url: URL
    var id: String { url.path }
}
