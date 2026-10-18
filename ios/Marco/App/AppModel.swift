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
    @Published var micInfo = ""
    @Published var recording = false
    @Published var recordInfo = "off"
    @Published var linkInfo = ""
    @Published var airpodsInfo = "not connected"
    @Published var signInfo = ""
    @Published var shareFile: ShareFile?
    /// Where the server remembers each item, in this map's world frame, for the LiDAR view (LiDAR/LiDARScreen.swift).
    @Published private(set) var itemMarks: [ItemMark] = []
    @Published private(set) var guidanceTargetId: String?

    let sessionId = UUID().uuidString

    private struct Live {
        var generation: Int?
        var mapId: String?
        var revision = 0
        var pose: NavigationPose?
        var trackingNormal = false
        var headYaw = 0.0
        var headSource = "phone"
        var signEvidence = 0.0
        var realignments = 0

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
    private let recorder = Recorder(root: Recorder.documents)
    private let poseRate = Locked(RateMeter())
    private let handRate = Locked(RateMeter())
    private var uploader: Uploader?
    private var socket: PhoneSocket?

    // ARKit queue only.
    private var fusion = HeadFusion()
    private var frameGate = Throttle(hz: Config.frameHz)
    private var poseGate = Throttle(hz: Config.poseHz)
    private var handGate = HandRateGate()                              // 15/s near a hand, slower otherwise
    private var frameId = 0
    private var reportedFrameTicket: Int?
    private var handBusy = false

    // Main thread only.
    private var guidance = Guidance()
    private var guidanceGate = Throttle(hz: Config.guidanceMsgHz)
    private var uiGate = Throttle(hz: 10)
    private var timer: Timer?
    private var finds = FindRequests()
    private var lookout = Lookout()                                    // a find not seen yet: still watching for it
    private var voiceAnchor = SoundAnchor.ahead                        // where Marco's voice is coming from now
    private var lastTouch: (id: String, position: SIMD3<Float>)?       // the jar a "what is this" is about
    private var routeWatch = RouteWatch()                              // are the AirPods the output?
    private lazy var sounds = SoundReporter(sessionId: sessionId)      // what the wearer hears, for the dashboard
    private var beaconPoint: SIMD3<Float>?                             // the beacon, listener-relative, while guiding
    private var voicePlaced = SoundAnchor.aheadPoint                   // the voice, listener-relative
    private var guidanceScope: NavigationScope?
    private var commandGate = CommandGate()               // dashboard Find/Stop (docs/INTERFACES.md §4)
    private var labels: [String: (text: String?, url: String?)] = [:]  // item_id -> its label
    private var listenerStarted = false
    private var vocabulary = ItemVocabulary()                          // registered item names, for the listener
    private var frameRate = RateMeter()

    var arSession: ARSession { ar.session }

    /// How hard to work, by heat (Core/ResourcePolicy.swift). Read on the ARKit queue, set on the main thread.
    private let policy = Locked(ResourcePolicy())
    private var thermalObserver: NSObjectProtocol?
    /// The LiDAR view's redraw rate, lowered when the phone runs hot.
    @Published private(set) var lidarFPS = ResourcePolicy().lidarViewFPS
    /// True while Developer tools is on screen. The values only it shows are published only then: publishing them
    /// at 10 Hz otherwise re-renders the main panel ten times a second for nothing. Main thread.
    var diagnosticsVisible = false
    private var acceptedCount = 0                                      // main thread
    private var lastUploadText = ""                                    // main thread

    init() {
        if !ARSessionManager.supported { control.stop(reason: .unsupported) }
        thermalObserver = NotificationCenter.default.addObserver(forName: ProcessInfo.thermalStateDidChangeNotification,
                                                                 object: nil, queue: .main) { [weak self] _ in self?.thermalChanged() }
        thermalChanged()
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
        lookout.cancel()
        guidanceScope = nil
        live.write { $0 = Live(generation: ticket) }
        UIApplication.shared.isIdleTimerDisabled = true          // ARKit stops when the screen locks

        audio.onRoute = { [weak self] route in
            DispatchQueue.main.async {
                guard let self else { return }
                self.micInfo = route
                self.routeWatch.observe(SpatialAudio.outputRoute(), now: self.now)
            }
        }
        do { try audio.start() } catch {
            audioProblem = "Navigation audio could not start. Stop and restart the camera to try again."
            note("audio: \(error.localizedDescription)")
        }
        micInfo = SpatialAudio.routeDescription()
        routeWatch = RouteWatch()
        audio.setBeaconAudible(true)
        routeWatch.observe(SpatialAudio.outputRoute(), now: now)

        let up = Uploader(base: url)
        up.onResult = { [weak self] code, body, ms in DispatchQueue.main.async {
            guard let self, self.running, self.control.generation == ticket else { return }
            self.uploaded(code, body, ms)
        } }
        uploader = up
        audio.configureSpeech(base: url)
        refreshItems(ticket: ticket)                         // typed labels and names made before this launch

        let sock = PhoneSocket(base: url)
        sock.onMessage = { [weak self] m in DispatchQueue.main.async {
            guard let self, self.running, self.control.generation == ticket else { return }
            self.handle(m)
        } }
        sock.onState = { [weak self] isUp in DispatchQueue.main.async {
            guard let self, self.running, self.control.generation == ticket else { return }
            if isUp && !self.socketUp { self.refreshItems(ticket: ticket) }   // items added while we were away
            self.socketUp = isUp
        } }
        sock.onUndecodable = { [weak self] s in DispatchQueue.main.async { self?.note("undecodable: \(s)") } }
        sock.connect()
        socket = sock
        ServerCheck.run(base: url) { [weak self] line in                 // Tailscale off? not on the allow-list?
            guard let self, self.running, self.control.generation == ticket else { return }
            self.note(line)
        }

        head.start()
        listener.onIntent = { [weak self] intent, text in DispatchQueue.main.async {
            guard let self, self.running, self.control.generation == ticket else { return }
            self.act(intent, text)
        } }
        listener.onTranscript = { [weak self] text in DispatchQueue.main.async {
            guard let self, self.running, self.control.generation == ticket, self.diagnosticsVisible else { return }
            self.update(\.heard, text)        // every partial transcript of nearby chatter: developer screen only
        } }
        listener.onWake = { [weak self] in DispatchQueue.main.async {
            guard let self, self.running, self.control.generation == ticket else { return }
            self.heard = "Marco... (listening)"
            self.voiceAnchor = .ahead
            self.voicePlaced = SoundAnchor.aheadPoint
            self.audio.listening()
            self.report("blip", at: SoundAnchor.aheadPoint, anchor: "ahead", duration: 0.12)
        } }
        listener.onError = { [weak self] e in DispatchQueue.main.async { self?.note("listener: \(e)") } }
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
        ar.onNote = { [weak self] line in DispatchQueue.main.async { self?.note(line) } }
        ar.onLost = { [weak self] in DispatchQueue.main.async {
            guard let self, self.running, self.control.generation == ticket else { return }
            self.speak(Lines.bearings)
        } }
        ar.queue.async { self.fusion = HeadFusion() }
        updateCameraRate()                       // 60 fps unless hot or switched to 30
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
        if recorder.isRecording { toggleRecording() }
        finds.cancel()
        lookout.cancel()
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

    /// The debug screen's mic switch changed (Config.useIPhoneMic): re-route; both audio engines restart themselves.
    func micChanged() {
        do { try audio.applyRoute() } catch { note("mic route: \(error.localizedDescription)") }
        micInfo = SpatialAudio.routeDescription()
    }

    /// Typed labels and item names. Marco speaks every response through the same output voice.
    private func refreshItems(ticket: Int) {
        uploader?.items { [weak self] items in
            DispatchQueue.main.async {
                guard let self, self.running, self.control.generation == ticket, let items else { return }
                self.itemMarks = items.compactMap { it in
                    Geo.vec(it.position).map { ItemMark(id: it.item_id, name: it.name, position: $0, surface: it.surface, state: it.state) }
                }
                for it in items where it.label_text != nil || it.label_audio_url != nil {
                    self.labels[it.item_id] = (Lines.spokenLabel(name: it.name, labelText: it.label_text), nil)
                }
                self.learn(items.map(\.name))
            }
        }
    }

    /// The LiDAR view asks for fresh positions every few seconds while it's open.
    func refreshItemsNow() {
        guard running else { return }
        refreshItems(ticket: control.generation)
    }

    /// Item names also arrive on server messages (an item registered over Photon after launch): no refetch needed.
    private func learn(_ names: [String?]) {
        var added = false
        for case let n? in names { added = vocabulary.add(n) || added }
        if added { listener.setItems(vocabulary.names) }
    }

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
        let evidence = fusion.signEvidence, realigned = fusion.realignments
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
            $0.signEvidence = evidence
            $0.realignments = realigned
        }
        // §3.1: nothing goes out while tracking is limited or before relocalization finishes.
        guard normal, socket != nil else { return }
        if poseGate.ready(t) {
            emit(PoseMsg(session_id: sessionId, map_id: mapId, t_device: t, camera_transform: Geo.flat(T),
                         head_yaw_deg: (yaw * 100).rounded() / 100, head_source: source))
            poseRate.write { $0.tick(t) }
        }
        if frameGate.ready(t) { upload(frame, mapId: mapId, ticket: ticket) }
        if !handBusy, handGate.ready(t, policy: policy.read { $0 }) {
            handBusy = true
            handQueue.async {
                let found = self.sendHand(frame, mapId: mapId, ticket: ticket)
                self.ar.queue.async {
                    self.handBusy = false
                    if found { self.handGate.sawHand(at: t) }
                }
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
            if let m = try? JSONEncoder().encode(meta) {
                self.recorder.frame(meta: m, frameId: meta.frame_id, jpeg: jpeg, depth: dz, confidence: cz)
            }
            up.submit(Uploader.Frame(meta: meta, jpeg: jpeg, depth: dz, confidence: cz))
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
    /// Hand queue. True when Vision found a hand (the gate keeps the full rate while hands are around).
    private func sendHand(_ frame: ARFrame, mapId: String, ticket: Int) -> Bool {
        guard live.read({ $0.generation == ticket }),
              let depth = frame.smoothedSceneDepth ?? frame.sceneDepth, let confMap = depth.confidenceMap,
              let found = try? hands.detect(frame.capturedImage) else { return false }  // nil: no hand in view
        // Only the 21 9x9 windows are read from the depth buffers, not both whole maps.
        guard let patches = Wire.patches(depth: depth.depthMap, conf: confMap, joints: found.joints),
              live.read({ $0.generation == ticket }) else { return true }
        emit(HandMsg.make(sessionId: sessionId, mapId: mapId, t: frame.timestamp, transform: frame.camera.transform,
                          joints: found.joints, chirality: found.chirality, patches: patches))
        handRate.write { $0.tick(frame.timestamp) }
        return true
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
        emit(MapMsg(session_id: sessionId, event: event, map_id: id), hold: true)
        DispatchQueue.main.async {
            guard self.running, self.control.generation == ticket, self.live.read({ $0.scope == scope }) else { return }
            if event == "new_map" {                  // new coordinates: remembered positions no longer apply
                self.itemMarks = self.itemMarks.map { var m = $0; m.state = "stale"; return m }
            }
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
        watchForLookout(t, l)
        if let change = routeWatch.settle(now: t) { headphonesChanged(change) }
        // A line from a point in the room stays there while the head turns, guiding or not.
        if case .world = voiceAnchor, let pose = l.pose, pose.usable(now: t, in: l.scope) {
            let ear = Geo.position(pose.transform) + SIMD3<Float>(0, Config.earAboveChestM, 0)
            voicePlaced = voiceAnchor.listenerRelative(ear: ear, headYawDeg: l.headYaw)
            audio.moveVoice(voicePlaced)
        }
        if let pose = l.pose, pose.usable(now: t, in: guidanceScope), guidance.active {
            let T = pose.transform
            let chest = Geo.position(T)
            let ear = chest + SIMD3<Float>(0, Config.earAboveChestM, 0)
            play(guidance.tick(now: t, chest: chest, ear: ear, headYawDeg: l.headYaw))
            if let tg = guidance.target {
                beaconPoint = Geo.listenerRelative(ear: ear, headYawDeg: l.headYaw, target: tg.position)
                audio.place(beaconPoint!)
            }
            if guidanceGate.ready(t) || !guidance.active { sendGuidance() }
        }
        let beacon = guidance.active ? beaconPoint.map { ($0, muffled: guidance.phase == .behind) } : nil
        if let m = sounds.field(t: t, headYawDeg: l.headYaw, beacon: beacon, voice: (voicePlaced, anchor: anchorName(voiceAnchor))) {
            emit(m)
        }
        if uiGate.ready(t) {
            let target = guidance.active ? guidance.target?.itemId : nil
            if guidanceTargetId != target { guidanceTargetId = target }
            if diagnosticsVisible {
                update(\.headYaw, l.headYaw.rounded())
                update(\.headSource, l.headSource)
                update(\.phase, guidance.phase)
                update(\.relAzimuth, guidance.relAzimuthDeg.rounded())
                update(\.distance, (guidance.distanceM * 100).rounded() / 100)
                update(\.framesAccepted, acceptedCount)
                update(\.lastUpload, lastUploadText)
                refreshHealth(t, l)
            }
        }
    }

    /// The developer screen's health rows (10/s): link, AirPods, recording.
    private func refreshHealth(_ t: Double, _ l: Live) {
        let poses = poseRate.read { m -> Double in var c = m; return c.rate(t) }
        let hands = handRate.read { m -> Double in var c = m; return c.rate(t) }
        update(\.linkInfo, String(format: "frames %.1f/s · poses %.0f/s · hands %.0f/s · ", frameRate.rate(t), poses, hands)
                   + policy.read { $0 }.summary)
        let a = head.health
        update(\.airpodsInfo, a.samples == 0 ? "no samples (AirPods in? motion allowed?)"
            : String(format: "%.0f Hz · jitter %.0f ms · latency %.0f ms · raw yaw %.0f°", a.rateHz, a.jitterMs, a.latencyMs, a.yawDeg))
        if abs(l.signEvidence) < 50 {
            update(\.signInfo, "turn your whole body a few times to check · realigned \(l.realignments)×")
        } else {
            update(\.signInfo, (l.signEvidence > 0 ? "AirPods sign agrees with ARKit ✓" : "AirPods sign INVERTED: flip it")
                + " · realigned \(l.realignments)×")
        }
        if recording {
            let p = recorder.progress
            update(\.recordInfo, "● \(p.frames) frames · \(p.messages) messages · \(p.bytes / 1_000_000) MB")
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
            let text = Lines.spokenLabel(name: l.name, labelText: l.label_text)
            labels[l.item_id] = (text, nil)
            guidance.updateLabel(itemId: l.item_id, name: l.name, text: text, audioURL: nil)
            say(Lines.labelReady(l), from: anchor(item: l.item_id, touch: nil))
        case .error(let e): note("server: \(e.detail)")
        case .command(let c): command(c)
        case .other(let type): note("unhandled \(type)")
        }
    }

    private func found(_ a: FindAnswer) {
        let l = live.read { $0 }
        guard let request = finds.consume(id: a.query_id, in: l.scope), running else { return }
        guard let pose = l.pose, pose.usable(now: now, in: request.scope) else {
            return speak(Lines.positionUnavailable)
        }
        let name = a.name ?? request.name
        guard a.found, !["stale", "missing", "picked_up", "registered"].contains(a.state ?? ""),
              let id = a.item_id, let p = Geo.vec(a.position) else {
            // Not seen, or not trusted where it was: say so, and keep watching for its next sighting.
            if let id = a.item_id, a.reason != "not_registered" {
                lookout.watch(itemId: id, name: name, scope: request.scope, now: now)
            }
            return speak(Lines.notFound(a, asked: request.name))
        }
        guide(itemId: id, name: name, position: p, surface: a.surface, pose: pose, headYaw: l.headYaw, scope: request.scope)
    }

    /// Starts the §7 guidance and says where the item is, relative to the body: "Polo! Behind you, two steps, on
    /// the table." spotted: it was just seen after a not-found answer ("Polo! I see your keys. ...").
    private func guide(itemId id: String, name: String, position p: SIMD3<Float>, surface: String?, pose: NavigationPose,
                       headYaw yaw: Double, scope: NavigationScope, spotted: Bool = false) {
        let T = pose.transform
        let chest = Geo.position(T)
        let bodyAz = Geo.relativeAzimuthDeg(from: chest, headingDeg: Geo.headingDeg(T), to: p)   // "behind you" means the body
        let d = Geo.horizontalDistance(chest, p)
        let label = labels[id]
        play(guidance.stop())
        silence()
        guidanceScope = scope
        guidance.start(GuidanceTarget(itemId: id, name: name, position: p, surface: surface,
                                      labelText: label?.text, labelAudioURL: label?.url), now: now)
        let ear = chest + SIMD3<Float>(0, Config.earAboveChestM, 0)
        beaconPoint = Geo.listenerRelative(ear: ear, headYawDeg: yaw, target: p)
        audio.place(beaconPoint!)
        say(spotted ? Lines.spotted(name: name, relAzimuthDeg: bodyAz, distanceM: d, surface: surface)
                    : Lines.polo(relAzimuthDeg: bodyAz, distanceM: d, surface: surface), from: .world(p))
        note("\(spotted ? "spotted" : "find") \(name): \(surface ?? "?"), \(Int(bodyAz)) deg, \(String(format: "%.1f", d)) m")
    }

    /// Find or Stop from the dashboard: the exact item and position come from the server, no name lookup. Acks
    /// accepted, then applied (guidance started or stopped) or rejected with a reason. Stop leaves the camera on.
    private func command(_ c: CommandMsg) {
        let decision = commandGate.check(c, sessionId: sessionId)
        switch decision {
        case .duplicate:
            return
        case .reject(let reason):
            ack(c, "rejected", reason)
        case .stop:
            ack(c, "accepted", nil)
            stopGuidance()
            ack(c, "applied", nil)
            note("dashboard: stop")
        case .find(let id, let name, let p, let surface):
            let l = live.read { $0 }
            guard running, let scope = l.scope, let pose = l.pose, pose.usable(now: now, in: scope) else {
                return ack(c, "rejected", "position_unavailable: tracking isn't ready on the iPhone")
            }
            ack(c, "accepted", nil)
            finds.cancel()
            guide(itemId: id, name: name, position: p, surface: surface, pose: pose, headYaw: l.headYaw, scope: scope)
            ack(c, "applied", nil)
            note("dashboard: find \(name)")
        }
    }

    private func ack(_ c: CommandMsg, _ status: String, _ reason: String?) {
        emit(CommandAckMsg(session_id: sessionId, command_id: c.command_id, status: status, reason: reason), hold: true)
    }

    private func whatIsThis(_ a: WhatAnswer) {
        let from = anchor(item: a.item_id, touch: a.touch_id)          // the jar under the hand answers
        if let line = Lines.whatIsThis(a) { say(line, from: from, cue: a.status == "known" ? "label" : "say") }
    }

    /// On the guided item: the end of guidance. Otherwise name what the hand is on (telling identical jars apart).
    private func touched(_ tm: TouchMsg) {
        if let p = Geo.vec(tm.position) { lastTouch = (tm.touch_id, p) }
        let l = live.read { $0 }
        if guidance.active, l.pose?.usable(now: now, in: guidanceScope) != true || l.scope != guidanceScope {
            losePosition()
            return
        }
        let cues = guidance.touched(itemId: tm.item_id, t: now)
        if !cues.isEmpty { return play(cues) }
        guard let id = tm.item_id else { return }
        let label = labels[id]
        let from = SoundAnchor.at(tm.position)                         // the label comes from the jar itself
        if let line = Lines.touchedKnown(name: tm.name, labelText: label?.text) { say(line, from: from, cue: "label") }
    }

    private func worldEvent(_ e: WorldEventMsg) {
        markItem(e)
        lookout.sighted(e)
        switch e.kind {
        case "moved", "put_down", "seen":
            if let p = Geo.vec(e.position) { guidance.retarget(itemId: e.item_id, position: p, surface: e.surface) }
        case "left_behind":
            haptic.impactOccurred()
            say(Lines.leftBehind(e), from: .at(e.position))            // from where the keys still are
        default:
            break
        }
    }

    /// Keeps the LiDAR view's item positions live between refreshes.
    private func markItem(_ e: WorldEventMsg) {
        let i = itemMarks.firstIndex { $0.id == e.item_id }
        switch e.kind {
        case "seen", "moved", "put_down":
            guard let p = Geo.vec(e.position) else { return }
            let m = ItemMark(id: e.item_id, name: e.name, position: p, surface: e.surface ?? (i.map { itemMarks[$0].surface } ?? nil),
                             state: "present")
            if let i { itemMarks[i] = m } else { itemMarks.append(m) }
        case "picked_up", "missing":
            if let i { itemMarks[i].state = e.kind }
        default:
            break
        }
    }

    private func play(_ cues: [Cue]) {
        let guided = guidance.target.map { SoundAnchor.world($0.position) } ?? .ahead
        for c in cues {
            switch c {
            case .haptic: haptic.impactOccurred()
            case .say(let s): say(s, from: guided)
            case .playLabel(_, let fallback):
                say(fallback, from: guided, cue: "label")
            default:
                audio.play(c)
                reportBeacon(c)
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
        finds.cancel()
        lookout.cancel()
        guidanceScope = nil
        let was = guidance.active
        play(guidance.stop())
        silence()
        if was { sendGuidance() }
        phase = .off
    }

    /// Tracking recovery requires a fresh Find; old target coordinates never resume automatically.
    /// The item a find couldn't guide to was just seen: guide to it now. Or the watch ran out: say so.
    private func watchForLookout(_ t: Double, _ l: Live) {
        guard lookout.watching else { return }
        guard lookout.scope == l.scope else { return lookout.cancel() }        // a new capture run or map
        if lookout.spot != nil {
            guard let pose = l.pose, let scope = lookout.scope, pose.usable(now: t, in: scope), let s = lookout.take() else { return }
            guide(itemId: s.itemId, name: s.name, position: s.position, surface: s.surface, pose: pose,
                  headYaw: l.headYaw, scope: scope, spotted: true)
        } else if let name = lookout.expired(now: t) {
            speak(Lines.stillNotSeen(name))
        }
    }

    private func losePosition() {
        guard guidance.active || finds.pending != nil else { return }
        stopGuidance()
        speak(Lines.positionUnavailable)
    }

    private func query(_ kind: String, name: String? = nil) {
        guard socket != nil, socketUp else { return speak(Lines.noServer) }
        let qid = UUID().uuidString
        if kind == "find" {
            stopGuidance()
            let l = live.read { $0 }
            guard let scope = l.scope, l.pose?.usable(now: now, in: scope) == true else {
                return speak(Lines.positionUnavailable)
            }
            finds.begin(id: qid, name: name ?? "thing", scope: scope)
        }
        emit(QueryMsg(session_id: sessionId, query_id: qid, kind: kind, name: name), hold: true)
        note("-> \(kind) \(name ?? "")")
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

    private func uploaded(_ code: Int, _ body: String, _ ms: Double) {
        if code == 202 {
            acceptedCount += 1                  // published by the 10 Hz block while Developer tools is open
            frameRate.tick(now)
            lastUploadText = String(format: "202 · %.0f ms round trip", ms)
        } else {
            lastUploadText = "\(code): \(body.prefix(160))"
            note("frame upload \(code): \(body.prefix(240))")
        }
    }

    /// Publishes only real changes: every @Published write re-renders the screens that observe the model.
    private func update<T: Equatable>(_ key: ReferenceWritableKeyPath<AppModel, T>, _ value: T) {
        if self[keyPath: key] != value { self[keyPath: key] = value }
    }

    /// The phone's heat changed: slow the optional work (Core/ResourcePolicy.swift). Main thread.
    private func thermalChanged() {
        let p = ResourcePolicy(heat: .init(ProcessInfo.processInfo.thermalState))
        let before = policy.read { $0 }
        policy.write { $0 = p }
        update(\.lidarFPS, p.lidarViewFPS)
        updateCameraRate()
        if p.heat != before.heat, p.heat >= .serious || before.heat >= .serious { note(p.summary) }
    }

    /// 60 fps unless the phone is hot or the developer switch asks for 30. Switches a running camera in place.
    func updateCameraRate() {
        ar.setLowFrameRate(Config.lowFrameRate || policy.read { $0 }.lowCameraRate)
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

    /// Marco's own lines, from straight ahead.
    private func speak(_ line: String) { say(line, from: .ahead) }

    /// Every line Marco says goes through here, with where it comes from (Core/SoundScene.swift). A room point is
    /// placed now and kept current every tick; with no fresh pose to place it, the line comes from ahead.
    /// cue: "label" for an item's label (same voice, no memo), so the dashboard can still tell it apart.
    private func say(_ line: String, from anchor: SoundAnchor, cue: String = "say") {
        voiceAnchor = anchor
        let p = voicePoint()
        if let p { audio.say(line, at: p) } else { audio.say(line, atItem: false) }
        voicePlaced = p ?? SoundAnchor.aheadPoint
        report(cue, at: voicePlaced, anchor: p == nil ? "ahead" : anchorName(anchor), text: line,
               duration: SoundReporter.speechSeconds(line))
        note("says: \(line)")
    }

    /// Stop every sound (and tell the dashboard).
    private func silence() {
        audio.play(.silence)
        reportBeacon(.silence)
    }

    // MARK: - What the wearer hears, for the dashboard (docs/INTERFACES.md §3.2 sound, sound_field)

    private func report(_ cue: String, at p: SIMD3<Float>, anchor: String, muffled: Bool? = nil, text: String? = nil,
                        duration: Double? = nil) {
        emit(sounds.cue(cue, at: p, anchor: anchor, t: now, muffled: muffled, text: text, duration: duration))
    }

    /// The beacon's cues (the sound itself is SpatialAudio's).
    private func reportBeacon(_ c: Cue) {
        let at = beaconPoint ?? SoundAnchor.aheadPoint
        switch c {
        case .beep(let muffled): report("beep", at: at, anchor: "item", muffled: muffled)
        case .ding: report("ding", at: at, anchor: "item")
        case .steadyTone(let on): report(on ? "tone_on" : "tone_off", at: at, anchor: "item")
        case .silence: report("silence", at: at, anchor: "item")
        default: break
        }
    }

    private func anchorName(_ a: SoundAnchor) -> String {
        switch a {
        case .ahead: return "ahead"
        case .world(let p): return guidance.target?.position == p ? "item" : "room"
        }
    }

    private func voicePoint() -> SIMD3<Float>? {
        guard case .world = voiceAnchor else { return nil }
        let l = live.read { $0 }
        guard let pose = l.pose, pose.usable(now: now, in: l.scope) else { return nil }
        let ear = Geo.position(pose.transform) + SIMD3<Float>(0, Config.earAboveChestM, 0)
        return voiceAnchor.listenerRelative(ear: ear, headYawDeg: l.headYaw)
    }

    /// Where a line about an item comes from: the touch it answers, else where the item was last seen, else ahead.
    private func anchor(item itemId: String?, touch touchId: String?) -> SoundAnchor {
        if let t = lastTouch, let touchId, t.id == touchId { return .world(t.position) }
        if let itemId, let m = itemMarks.first(where: { $0.id == itemId }), m.shown { return .world(m.position) }
        return .ahead
    }

    /// The AirPods dropped, handed off, or came back (settled by RouteWatch). Without two ears the beacon can't point
    /// anywhere, so it goes quiet and Marco says so; speech carries on from the iPhone.
    private func headphonesChanged(_ c: RouteWatch.Change) {
        audio.setBeaconAudible(c.binaural)
        note("output: \(SpatialAudio.outputRoute().name), \(c.binaural ? "binaural" : "not binaural")")
        if !c.binaural { speak(Lines.headphonesLost) } else if c.was == false { speak(Lines.headphonesBack) }
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
