import ARKit
import Foundation

/// ARKit world tracking with LiDAR depth (docs/INTERFACES.md §2 and §3.4). Frames arrive on `queue` at 60 Hz, or 30 Hz
/// while the phone is hot or the developer switch asks for it (`setLowFrameRate`).
/// The ARWorldMap is saved every 30 s and on backgrounding; on launch the app relocalizes into it and starts a
/// fresh map if that hasn't worked after 30 s. Don't hold ARFrames for long: ARKit stalls when they pile up.
final class ARSessionManager: NSObject, ARSessionDelegate {
    let session = ARSession()
    let queue = DispatchQueue(label: "marco.arkit")
    private var lifecycle = WorldMapLifecycle()
    var mapId: String { lifecycle.mapId } // Read on the AR queue, like relocalizing.
    private(set) var relocalizing = false
    private var running = false
    private var relocalizeStarted: TimeInterval = 0
    private var lastSave: TimeInterval = 0
    private var mapping: ARFrame.WorldMappingStatus = .notAvailable
    /// Archiving a big ARWorldMap takes long enough to stall frame delivery, so it happens here, never on `queue`.
    /// Clearing the saved map goes through the same serial queue, so a late write can't outlive a fresh map.
    private let saveQueue = DispatchQueue(label: "marco.worldmap", qos: .utility)
    private var lowRate = false               // queue only: running the 30 fps format
    private var wantLowRate = false           // queue only: asked for (heat or the developer switch)
    private var lowRateBroken = false         // queue only: 30 fps gave no depth this session; stay at 60
    private var depthlessFrames = 0           // queue only
    private var restoredMap: ARWorldMap?      // queue only: kept while relocalizing, for a format fallback

    var onFrame: ((ARFrame) -> Void)?
    var onMapEvent: ((String, String) -> Void)?   // (relocalized | new_map | saved, map_id)
    var onTracking: ((String) -> Void)?
    var onLost: (() -> Void)?                     // the saved map wasn't found again; a fresh one started
    var onFailure: ((String) -> Void)?
    var onInterrupted: (() -> Void)?
    var onNote: ((String) -> Void)?               // one-line diagnostics for the developer log

    /// 1920x1440 (the contract's image) at 30 fps: half the camera, tracking and LiDAR work of the 60 fps default, and
    /// still 30 depth maps a second for 1 frame/s uploads, 10/s poses and hands at up to 15/s. Used only while the
    /// phone is hot or when asked; nil when the phone has no such format.
    static var lowRateFormat: ARConfiguration.VideoFormat? {
        ARWorldTrackingConfiguration.supportedVideoFormats.first {
            $0.imageResolution == CGSize(width: 1920, height: 1440) && $0.framesPerSecond == 30
                && $0.captureDeviceType == .builtInWideAngleCamera
        }
    }

    static var supported: Bool {
        ARWorldTrackingConfiguration.isSupported && ARWorldTrackingConfiguration.supportsFrameSemantics(.smoothedSceneDepth)
    }

    func start() {
        session.delegate = self
        session.delegateQueue = queue
        queue.async {
            let saved = WorldMapStore.load()
            self.lifecycle.begin(restoredMapId: saved?.1)
            self.running = true
            self.mapping = .notAvailable
            self.lastSave = 0
            self.relocalizing = saved != nil
            self.relocalizeStarted = saved == nil ? 0 : ProcessInfo.processInfo.systemUptime
            self.restoredMap = saved?.0
            self.run(initialMap: saved?.0)
            if saved == nil { self.onMapEvent?("new_map", self.mapId) }
        }
    }

    func pause() { queue.async { self.running = false; self.session.pause() } }

    private func configuration(initialMap: ARWorldMap?, lowRate: Bool) -> ARWorldTrackingConfiguration {
        let c = ARWorldTrackingConfiguration()
        c.worldAlignment = .gravity
        // No plane detection: nothing in the app reads plane anchors (the server names surfaces from depth).
        if ARWorldTrackingConfiguration.supportsFrameSemantics(.smoothedSceneDepth) {
            c.frameSemantics.insert(.smoothedSceneDepth)
        }
        if lowRate, let f = Self.lowRateFormat { c.videoFormat = f }
        c.initialWorldMap = initialMap
        return c
    }

    private func run(initialMap: ARWorldMap?) {
        lowRate = wantLowRate && !lowRateBroken && Self.lowRateFormat != nil
        depthlessFrames = 0
        let c = configuration(initialMap: initialMap, lowRate: lowRate)
        session.run(c, options: [.resetTracking, .removeExistingAnchors])
        let f = c.videoFormat
        onNote?("camera \(Int(f.imageResolution.width))x\(Int(f.imageResolution.height)) @ \(f.framesPerSecond) fps")
    }

    /// The 30 fps format gave no LiDAR depth for 3 s: go back to the default format. While relocalizing, start that
    /// again with the saved map; otherwise keep the current tracking (no reset), so the map's coordinates hold.
    private func fallBackToDefaultFormat() {
        lowRate = false
        lowRateBroken = true
        depthlessFrames = 0
        let c = configuration(initialMap: relocalizing ? restoredMap : nil, lowRate: false)
        session.run(c, options: relocalizing ? [.resetTracking, .removeExistingAnchors] : [])
        if relocalizing { relocalizeStarted = ProcessInfo.processInfo.systemUptime }
        onNote?("no LiDAR depth at 30 fps: back to \(c.videoFormat.framesPerSecond) fps")
    }

    /// 30 fps (hot phone, or the developer switch) or the default 60 fps. Switches a running session in place: no
    /// tracking reset, so the map's coordinates hold (while relocalizing it starts that again with the saved map).
    /// Before Start it only sets what Start will use. Any thread.
    func setLowFrameRate(_ low: Bool) {
        queue.async {
            self.wantLowRate = low
            guard self.running else { return }
            let target = low && !self.lowRateBroken && Self.lowRateFormat != nil
            guard target != self.lowRate else { return }
            self.lowRate = target
            self.depthlessFrames = 0
            let c = self.configuration(initialMap: self.relocalizing ? self.restoredMap : nil, lowRate: target)
            self.session.run(c, options: self.relocalizing ? [.resetTracking, .removeExistingAnchors] : [])
            if self.relocalizing { self.relocalizeStarted = ProcessInfo.processInfo.systemUptime }
            self.onNote?("camera now \(c.videoFormat.framesPerSecond) fps")
        }
    }

    /// Saved map couldn't be found again: new coordinates, so the server marks item positions stale.
    func startFreshMap() {
        queue.async { self.startFreshMapNow() }
    }

    private func startFreshMapNow() {
        lifecycle.begin()
        relocalizing = false
        relocalizeStarted = 0
        mapping = .notAvailable
        lastSave = 0
        restoredMap = nil
        saveQueue.async { WorldMapStore.clear() }
        if running { run(initialMap: nil) }
        onMapEvent?("new_map", mapId)
        onLost?()
    }

    /// Safe from any thread (the app calls it when going to the background).
    func saveMap() {
        queue.async { self.saveNow() }
    }

    private func saveNow() {
        guard running, !relocalizing, mapping == .mapped || mapping == .extending else { return }
        let ticket = lifecycle.prepareSave()
        session.getCurrentWorldMap { [weak self] map, _ in
            guard let self, let map else { return }
            self.queue.async {
                guard self.lifecycle.accepts(ticket) else { return }
                self.saveQueue.async {
                    guard (try? WorldMapStore.save(map, mapId: ticket.mapId)) != nil else { return }
                    self.queue.async { if self.lifecycle.accepts(ticket) { self.onMapEvent?("saved", ticket.mapId) } }
                }
            }
        }
    }

    // MARK: ARSessionDelegate (on `queue`)

    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        guard running else { return }
        if lowRate {
            depthlessFrames = frame.smoothedSceneDepth == nil ? depthlessFrames + 1 : 0
            if depthlessFrames > 90 { fallBackToDefaultFormat() }
        }
        mapping = frame.worldMappingStatus
        if relocalizing && frame.timestamp - relocalizeStarted > Config.relocalizeTimeoutS {
            startFreshMapNow()
            return
        }
        if !relocalizing && frame.timestamp - lastSave > Config.mapSaveIntervalS && (mapping == .mapped || mapping == .extending) {
            lastSave = frame.timestamp
            saveNow()
        }
        onFrame?(frame)
    }

    func session(_ session: ARSession, cameraDidChangeTrackingState camera: ARCamera) {
        guard running else { return }
        if relocalizing, case .normal = camera.trackingState {
            relocalizing = false
            restoredMap = nil                     // not needed once relocalized; it can be tens of MB
            onMapEvent?("relocalized", mapId)
        }
        onTracking?(Self.describe(camera.trackingState))
    }

    func session(_ session: ARSession, didFailWithError error: Error) {
        onTracking?("failed: \(error.localizedDescription)")
        onFailure?(error.localizedDescription)
    }

    func sessionWasInterrupted(_ session: ARSession) { onInterrupted?() }

    static func describe(_ s: ARCamera.TrackingState) -> String {
        switch s {
        case .normal: return "normal"
        case .notAvailable: return "not available"
        case .limited(let r):
            switch r {
            case .initializing: return "limited: initializing"
            case .relocalizing: return "limited: relocalizing"
            case .excessiveMotion: return "limited: moving too fast"
            case .insufficientFeatures: return "limited: too few features"
            @unknown default: return "limited"
            }
        }
    }
}

/// The ARWorldMap and its map_id, kept across launches (§3.4).
enum WorldMapStore {
    private static var url: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("marco.arworldmap")
    }

    static func save(_ map: ARWorldMap, mapId: String) throws {
        let data = try NSKeyedArchiver.archivedData(withRootObject: map, requiringSecureCoding: true)
        try data.write(to: url, options: .atomic)
        UserDefaults.standard.set(mapId, forKey: "mapId")
    }

    static func load() -> (ARWorldMap, String)? {
        guard let data = try? Data(contentsOf: url), let id = UserDefaults.standard.string(forKey: "mapId"),
              let map = try? NSKeyedUnarchiver.unarchivedObject(ofClass: ARWorldMap.self, from: data) else { return nil }
        return (map, id)
    }

    static func clear() {
        try? FileManager.default.removeItem(at: url)
        UserDefaults.standard.removeObject(forKey: "mapId")
    }
}
