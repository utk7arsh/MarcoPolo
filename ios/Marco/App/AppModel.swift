import ARKit
import AVFoundation
import Foundation
import SwiftUI
import UIKit

/// Wires the app together:
///   ARKit frames (60 Hz)  -> frames to the server at 1/s, poses at 10/s, the hand stream at 15/s
///   server messages       -> guidance, Marco's voice, labels
///   voice and buttons     -> queries
/// and runs the §7 guidance loop at 60 Hz on the main thread.
final class AppModel: ObservableObject {
    // UI state is published on the main thread. Sensor processing stays on its existing queues.
    @Published private(set) var control = CaptureControl()
    @Published private(set) var controlMessage: String?
    @Published private(set) var voiceStatus: VoiceInputStatus = .off
    @Published private(set) var audioProblem: String?
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
    @Published var log: [String] = []

    let sessionId = UUID().uuidString

    private struct Live {
        var generation: Int?
        var mapId: String?
        var revision = 0
        var pose: NavigationPose?
        var trackingNormal = false
        var headYaw = 0.0
        var headSource = "phone"

        var scope: NavigationScope? {
            guard let generation, let mapId else { return nil }
            return NavigationScope(captureGeneration: generation, mapId: mapId, revision: revision)
        }
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
    private var uploader: Uploader?
    private var socket: PhoneSocket?

    // ARKit queue only.
    private var fusion = HeadFusion()
    private var frameGate = Throttle(hz: Config.frameHz)
    private var poseGate = Throttle(hz: Config.poseHz)
    private var handGate = Throttle(hz: Config.handHz)
    private var frameId = 0
    private var reportedFrameTicket: Int?
    private var handBusy = false

    // Main thread only.
    private var guidance = Guidance()
    private var guidanceGate = Throttle(hz: Config.guidanceMsgHz)
    private var uiGate = Throttle(hz: 10)
    private var timer: Timer?
    private var finds = FindRequests()
    private var guidanceScope: NavigationScope?
    private var labels: [String: (text: String?, url: String?)] = [:]  // item_id -> its label
    private var audioCache: [String: URL] = [:]                        // label_audio_url -> local file
    private var listenerStarted = false

    var arSession: ARSession { ar.session }

    init() {
        if !ARSessionManager.supported { control.stop(reason: .unsupported) }
    }

    /// The clock of ARFrame.timestamp and CMDeviceMotion.timestamp.
    private var now: Double { ProcessInfo.processInfo.systemUptime }

    // MARK: - Start

    func start() {
        guard !running else { return }
        guard let url = ControlServerAddress.parse(serverText) else {
            controlMessage = "Set the server address in Connection settings."
            return
        }
        guard let ticket = control.begin(supported: ARSessionManager.supported) else { return }
        controlMessage = nil
        let permitted: (Bool) -> Void = { [weak self] granted in
            DispatchQueue.main.async {
                guard let self else { return }
                guard self.control.permission(granted: granted, ticket: ticket) else {
                    if self.control.phase == .denied { self.controlMessage = "Allow camera access in Settings." }
                    return
                }
                self.beginCapture(url: url, ticket: ticket)
            }
        }
        switch AVCaptureDevice.authorizationStatus(for: .video) {
        case .authorized: permitted(true)
        case .notDetermined: AVCaptureDevice.requestAccess(for: .video, completionHandler: permitted)
        default:
            _ = control.permission(granted: false, ticket: ticket)
            controlMessage = "Allow camera access in Settings."
        }
    }

    private func beginCapture(url: URL, ticket: Int) {
        Config.serverURL = url
        running = true
        voiceStatus = .starting
        audioProblem = nil
        finds.cancel()
        guidanceScope = nil
        live.write { $0 = Live(generation: ticket) }
        UIApplication.shared.isIdleTimerDisabled = true          // ARKit stops when the screen locks

        do { try audio.start() } catch {
            audioProblem = "Navigation audio could not start. Stop and restart the camera to try again."
            note("audio: \(error.localizedDescription)")
        }

        let up = Uploader(base: url)
        up.onResult = { [weak self] code, body in DispatchQueue.main.async {
            guard let self, self.running, self.control.generation == ticket else { return }
            self.uploaded(code, body)
        } }
        uploader = up
        up.items { [weak self] items in                      // labels made before this launch, audio cached now
            DispatchQueue.main.async {
                guard let self, self.running, self.control.generation == ticket else { return }
                for it in items ?? [] where it.label_text != nil || it.label_audio_url != nil {
                    self.labels[it.item_id] = (Lines.spokenLabel(name: it.name, labelText: it.label_text), it.label_audio_url)
                    self.cache(it.label_audio_url)
                }
            }
        }

        let sock = PhoneSocket(base: url)
        sock.onMessage = { [weak self] m in DispatchQueue.main.async {
            guard let self, self.running, self.control.generation == ticket else { return }
            self.handle(m)
        } }
        sock.onState = { [weak self] isUp in DispatchQueue.main.async {
            guard let self, self.running, self.control.generation == ticket else { return }
            self.socketUp = isUp
        } }
        sock.onUndecodable = { [weak self] s in DispatchQueue.main.async { self?.note("undecodable: \(s)") } }
        sock.connect()
        socket = sock

        head.start()
        listener.onIntent = { [weak self] intent, text in DispatchQueue.main.async {
            guard let self, self.running, self.control.generation == ticket else { return }
            self.act(intent, text)
        } }
        listener.onTranscript = { [weak self] text in DispatchQueue.main.async {
            guard let self, self.running, self.control.generation == ticket else { return }
            self.heard = text
        } }
        Listener.requestPermissions { [weak self] ok in
            DispatchQueue.main.async {
                guard let self, self.running, self.control.generation == ticket else { return }
                guard ok else {
                    self.voiceStatus = .permissionDenied
                    return self.note("Speech or microphone permission denied.")
                }
                do {
                    try self.listener.start()
                    self.listenerStarted = true
                    self.voiceStatus = .listening
                } catch {
                    self.voiceStatus = .unavailable
                    self.note("listener: \(error.localizedDescription)")
                }
            }
        }

        ar.onFrame = { [weak self] f in self?.onFrame(f, ticket: ticket) }
        ar.onTracking = { [weak self] s in
            guard let self else { return }
            if s != "normal" {
                self.live.write {
                    guard $0.generation == ticket else { return }
                    if $0.trackingNormal { $0.revision += 1 }
                    $0.trackingNormal = false
                    $0.pose = nil
                }
            }
            DispatchQueue.main.async {
                guard self.running, self.control.generation == ticket else { return }
                self.tracking = s
                if s != "normal" { self.losePosition() }
            }
        }
        ar.onFailure = { [weak self] message in DispatchQueue.main.async {
            guard let self, self.running, self.control.generation == ticket else { return }
            self.stop(reason: .failed, message: message)
        } }
        ar.onInterrupted = { [weak self] in DispatchQueue.main.async {
            guard let self, self.running, self.control.generation == ticket else { return }
            self.stop(reason: .interrupted, message: "Camera interrupted. Start again when ready.")
        } }
        ar.onMapEvent = { [weak self] e, id in
            guard let self, self.live.read({ $0.generation == ticket }) else { return }
            self.mapEvent(e, id, ticket: ticket)
        }
        ar.onLost = { [weak self] in DispatchQueue.main.async {
            guard let self, self.running, self.control.generation == ticket else { return }
            self.speak(Lines.bearings)
        } }
        ar.queue.async { self.fusion = HeadFusion() }
        ar.start()

        let t = Timer(timeInterval: 1.0 / 60, repeats: true) { [weak self] _ in self?.tick() }
        RunLoop.main.add(t, forMode: .common)
        timer = t
    }

    func stop(reason: CaptureControl.Phase = .ready, message: String? = nil) {
        let finalReason: CaptureControl.Phase = reason == .ready && !ARSessionManager.supported ? .unsupported : reason
        control.stop(reason: finalReason) // Invalidates permission callbacks, including before start.
        controlMessage = message
        let wasRunning = running
        running = false
        voiceStatus = .off
        audioProblem = nil
        live.write { $0.generation = nil; $0.pose = nil }
        finds.cancel()
        timer?.invalidate(); timer = nil
        UIApplication.shared.isIdleTimerDisabled = false
        guard wasRunning else { return }
        ar.saveMap()
        ar.pause()
        stopGuidance()
        if listenerStarted { listener.stop(); listenerStarted = false }
        head.stop()
        audio.stop()
        socket?.close(); socket = nil
        uploader = nil
        socketUp = false
        tracking = "not started"
    }

    func refreshCameraAccess() {
        if control.phase == .denied, AVCaptureDevice.authorizationStatus(for: .video) == .authorized {
            control.stop()
            controlMessage = nil
        }
    }

    func saveMap() { ar.saveMap() }

    func newMap() { ar.startFreshMap() }

    func pushToTalk(_ down: Bool) { down ? listener.beginPushToTalk() : listener.endPushToTalk() }

    // MARK: - ARKit queue

    private func onFrame(_ frame: ARFrame, ticket: Int) {
        guard live.read({ $0.generation == ticket }) else { return }
        if reportedFrameTicket != ticket {
            reportedFrameTicket = ticket
            DispatchQueue.main.async { [weak self] in self?.control.firstFrame(ticket: ticket) }
        }
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
        let normal: Bool
        if case .normal = frame.camera.trackingState { normal = !ar.relocalizing } else { normal = false }
        let mapId = ar.mapId
        live.write {
            guard $0.generation == ticket else { return }
            if $0.mapId != mapId {
                $0.mapId = mapId
                $0.revision += 1
            }
            if !normal && $0.trackingNormal { $0.revision += 1 }
            $0.trackingNormal = normal
            $0.pose = normal ? $0.scope.map { NavigationPose(scope: $0, transform: T, timestamp: t) } : nil
            $0.headYaw = yaw
            $0.headSource = source
        }
        // §3.1: nothing goes out while tracking is limited or before relocalization finishes.
        guard normal, let socket else { return }
        if poseGate.ready(t) {
            socket.send(PoseMsg(session_id: sessionId, map_id: mapId, t_device: t, camera_transform: Geo.flat(T),
                                head_yaw_deg: (yaw * 100).rounded() / 100, head_source: source))
        }
        if frameGate.ready(t) { upload(frame, mapId: mapId, ticket: ticket) }
        if handGate.ready(t) && !handBusy {
            handBusy = true
            handQueue.async {
                self.sendHand(frame, mapId: mapId, socket: socket, ticket: ticket)
                self.ar.queue.async { self.handBusy = false }
            }
        }
    }

    private func upload(_ frame: ARFrame, mapId: String, ticket: Int) {
        guard let depth = frame.smoothedSceneDepth ?? frame.sceneDepth, let confMap = depth.confidenceMap,
              let up = uploader else { return }
        frameId += 1
        let res = frame.camera.imageResolution
        let meta = FrameMeta(session_id: sessionId, map_id: mapId, frame_id: frameId, t_device: frame.timestamp,
                             t_wall: Clock.wall(), tracking: "normal", camera_transform: Geo.flat(frame.camera.transform),
                             intrinsics: Geo.flat(frame.camera.intrinsics), image_resolution: [Int(res.width), Int(res.height)],
                             jpeg_scale: Config.jpegScale)
        let image = frame.capturedImage
        let depthMap = depth.depthMap
        encodeQueue.async {
            guard self.live.read({ $0.generation == ticket }) else { return }
            guard let jpeg = self.encoder.jpeg(image) else { return }
            let d = FrameEncoder.plane(depthMap, as: Float32.self)
            let c = FrameEncoder.plane(confMap, as: UInt8.self)
            guard let dz = try? Wire.depthPayload(d.values), let cz = try? Wire.confidencePayload(c.values) else { return }
            up.submit(Uploader.Frame(meta: meta, jpeg: jpeg, depth: dz, confidence: cz))
        }
    }

    /// Hand queue.
    private func sendHand(_ frame: ARFrame, mapId: String, socket: PhoneSocket, ticket: Int) {
        guard live.read({ $0.generation == ticket }),
              let depth = frame.smoothedSceneDepth ?? frame.sceneDepth, let confMap = depth.confidenceMap,
              let found = try? hands.detect(frame.capturedImage) else { return }      // nil: no hand in view
        let d = FrameEncoder.plane(depth.depthMap, as: Float32.self)
        let c = FrameEncoder.plane(confMap, as: UInt8.self)
        guard live.read({ $0.generation == ticket }) else { return }
        socket.send(HandMsg.make(sessionId: sessionId, mapId: mapId, t: frame.timestamp, transform: frame.camera.transform,
                                  joints: found.joints, chirality: found.chirality, depth: d.values, conf: c.values,
                                  width: d.width, height: d.height))
    }

    private func mapEvent(_ event: String, _ id: String, ticket: Int) {
        live.write {
            guard $0.generation == ticket else { return }
            if event == "new_map" || $0.mapId != id {
                $0.mapId = id
                $0.revision += 1
                $0.pose = nil
                $0.trackingNormal = false
            }
        }
        let scope = live.read { $0.scope }
        socket?.sendWhenOpen(MapMsg(session_id: sessionId, event: event, map_id: id))
        DispatchQueue.main.async {
            guard self.running, self.control.generation == ticket, self.live.read({ $0.scope == scope }) else { return }
            if (self.guidance.active && self.guidanceScope != scope) ||
                (self.finds.pending != nil && self.finds.pending?.scope != scope) {
                self.losePosition()
            }
            self.mapId = id
            if event != "saved" { self.note("map \(event) \(id.prefix(8))") }
        }
    }

    // MARK: - Main thread

    private func tick() {
        let l = live.read { $0 }
        let t = now
        if (guidance.active || finds.pending != nil), l.pose?.usable(now: t, in: l.scope) != true {
            losePosition()
        }
        if guidance.active, guidanceScope != l.scope { losePosition() }
        if let pose = l.pose, pose.usable(now: t, in: guidanceScope), guidance.active {
            let T = pose.transform
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
        }
    }

    private func sendGuidance() {
        socket?.send(GuidanceMsg(session_id: sessionId, item_id: guidance.target?.itemId, phase: guidance.phase.rawValue,
                                 rel_azimuth_deg: (guidance.relAzimuthDeg * 10).rounded() / 10,
                                 distance_m: (guidance.distanceM * 100).rounded() / 100))
    }

    private func handle(_ m: ServerMessage) {
        switch m {
        case .find(let a): found(a)
        case .whatIsThis(let a): whatIsThis(a)
        case .setPlace(let a): if a.ok == true { speak(Lines.doorSet) }
        case .touch(let tm): touched(tm)
        case .touchEnd: break
        case .handProximity(let p): guidance.handProximity(itemId: p.item_id, distanceM: p.distance_m, t: now)
        case .event(let e): worldEvent(e)
        case .labelReady(let l):
            let text = Lines.spokenLabel(name: l.name, labelText: l.label_text)
            labels[l.item_id] = (text, l.label_audio_url)
            guidance.updateLabel(itemId: l.item_id, name: l.name, text: text, audioURL: l.label_audio_url)
            cache(l.label_audio_url)
            speak(Lines.labelReady(l))
        case .error(let e): note("server: \(e.detail)")
        case .other(let type): note("unhandled \(type)")
        }
    }

    private func found(_ a: FindAnswer) {
        let l = live.read { $0 }
        guard let request = finds.consume(id: a.query_id, in: l.scope), running else { return }
        guard let pose = l.pose, pose.usable(now: now, in: request.scope) else {
            return speak(Lines.positionUnavailable)
        }
        guard a.found, let id = a.item_id, let p = Geo.vec(a.position) else {
            return speak(Lines.notFound(a, asked: request.name))
        }
        guard !["stale", "missing", "picked_up", "registered"].contains(a.state ?? "") else {
            return speak(Lines.positionUnavailable)
        }
        let T = pose.transform
        let chest = Geo.position(T)
        let yaw = l.headYaw
        let bodyAz = Geo.relativeAzimuthDeg(from: chest, headingDeg: Geo.headingDeg(T), to: p)   // "behind you" means the body
        let label = labels[id]
        play(guidance.stop())
        audio.play(.silence)
        guidanceScope = request.scope
        guidance.start(GuidanceTarget(itemId: id, name: a.name ?? request.name, position: p, surface: a.surface,
                                      labelText: label?.text, labelAudioURL: label?.url), now: now)
        let ear = chest + SIMD3<Float>(0, Config.earAboveChestM, 0)
        audio.place(Geo.listenerRelative(ear: ear, headYawDeg: yaw, target: p))
        audio.say(Lines.polo(relAzimuthDeg: bodyAz, distanceM: Geo.horizontalDistance(chest, p), surface: a.surface), atItem: true)
        note("find \(request.name): \(a.surface ?? "?"), \(Int(bodyAz)) deg, \(String(format: "%.1f", Geo.horizontalDistance(chest, p))) m")
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
        let l = live.read { $0 }
        if guidance.active, l.pose?.usable(now: now, in: guidanceScope) != true || l.scope != guidanceScope {
            losePosition()
            return
        }
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
            if let p = Geo.vec(e.position) { guidance.retarget(itemId: e.item_id, position: p, surface: e.surface) }
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
            case .playLabel(let url, let fallback):
                if let f = audioCache[url], (try? audio.playFile(f, atItem: true)) != nil { continue }
                audio.say(fallback, atItem: true)
            default: audio.play(c)
            }
        }
    }

    /// Voice and the debug buttons both end up here.
    func act(_ intent: Intent?, _ text: String) {
        heard = text
        guard let intent else { return speak(Lines.notUnderstood) }
        switch intent {
        case .find(let name): query("find", name: name)
        case .whatIsThis: query("what_is_this")
        case .setDoor: query("set_place", name: "door")
        case .stop: stopGuidance()
        }
    }

    func stopGuidance() {
        finds.cancel()
        guidanceScope = nil
        let was = guidance.active
        play(guidance.stop())
        audio.play(.silence)
        if was { sendGuidance() }
        phase = .off
    }

    /// Tracking recovery requires a fresh Find; old target coordinates never resume automatically.
    private func losePosition() {
        guard guidance.active || finds.pending != nil else { return }
        stopGuidance()
        speak(Lines.positionUnavailable)
    }

    private func query(_ kind: String, name: String? = nil) {
        guard let socket, socketUp else { return speak(Lines.noServer) }
        let qid = UUID().uuidString
        if kind == "find" {
            stopGuidance()
            let l = live.read { $0 }
            guard let scope = l.scope, l.pose?.usable(now: now, in: scope) == true else {
                return speak(Lines.positionUnavailable)
            }
            finds.begin(id: qid, name: name ?? "thing", scope: scope)
        }
        socket.sendWhenOpen(QueryMsg(session_id: sessionId, query_id: qid, kind: kind, name: name))
        note("-> \(kind) \(name ?? "")")
    }

    func register(name: String, photo: Data) {
        guard let up = uploader else { return note("Press Start first.") }
        up.register(name: name, photo: photo) { [weak self] result in
            DispatchQueue.main.async {
                switch result {
                case .success(let r):
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

    private func uploaded(_ code: Int, _ body: String) {
        if code == 202 {
            framesAccepted += 1
            lastUpload = "202"
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
