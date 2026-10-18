import ARKit
import Foundation

/// ARKit world tracking with LiDAR depth (docs/INTERFACES.md §2 and §3.4). Frames arrive on `queue` (60 Hz).
/// The ARWorldMap is saved every 30 s and on backgrounding; on launch the app relocalizes into it and starts a
/// fresh map if that hasn't worked after 30 s. Don't hold ARFrames for long: ARKit stalls when they pile up.
final class ARSessionManager: NSObject, ARSessionDelegate {
    let session = ARSession()
    let queue = DispatchQueue(label: "marco.arkit")
    private(set) var mapId = UUID().uuidString
    private(set) var relocalizing = false
    private var relocalizeStarted: TimeInterval = 0
    private var lastSave: TimeInterval = 0
    private var mapping: ARFrame.WorldMappingStatus = .notAvailable

    var onFrame: ((ARFrame) -> Void)?
    var onMapEvent: ((String, String) -> Void)?   // (relocalized | new_map | saved, map_id)
    var onTracking: ((String) -> Void)?
    var onLost: (() -> Void)?                     // the saved map wasn't found again; a fresh one started

    static var supported: Bool {
        ARWorldTrackingConfiguration.isSupported && ARWorldTrackingConfiguration.supportsFrameSemantics(.smoothedSceneDepth)
    }

    func start() {
        session.delegate = self
        session.delegateQueue = queue
        queue.async {
            if let (map, id) = WorldMapStore.load() {
                self.mapId = id
                self.relocalizing = true
                self.relocalizeStarted = ProcessInfo.processInfo.systemUptime
                self.run(initialMap: map)
            } else {
                self.run(initialMap: nil)
                self.onMapEvent?("new_map", self.mapId)
            }
        }
    }

    func pause() { session.pause() }

    private func run(initialMap: ARWorldMap?) {
        let c = ARWorldTrackingConfiguration()
        c.worldAlignment = .gravity
        c.planeDetection = [.horizontal]
        if ARWorldTrackingConfiguration.supportsFrameSemantics(.smoothedSceneDepth) {
            c.frameSemantics.insert(.smoothedSceneDepth)
        }
        c.initialWorldMap = initialMap
        session.run(c, options: [.resetTracking, .removeExistingAnchors])
    }

    /// Saved map couldn't be found again: new coordinates, so the server marks item positions stale.
    func startFreshMap() {
        queue.async {
            self.relocalizing = false
            self.mapId = UUID().uuidString
            WorldMapStore.clear()
            self.run(initialMap: nil)
            self.onMapEvent?("new_map", self.mapId)
            self.onLost?()
        }
    }

    /// Safe from any thread (the app calls it when going to the background).
    func saveMap() {
        queue.async { self.saveNow() }
    }

    private func saveNow() {
        guard !relocalizing, mapping == .mapped || mapping == .extending else { return }
        let id = mapId
        session.getCurrentWorldMap { [weak self] map, _ in
            guard let map, (try? WorldMapStore.save(map, mapId: id)) != nil else { return }
            self?.onMapEvent?("saved", id)
        }
    }

    // MARK: ARSessionDelegate (on `queue`)

    func session(_ session: ARSession, didUpdate frame: ARFrame) {
        mapping = frame.worldMappingStatus
        if relocalizing && frame.timestamp - relocalizeStarted > Config.relocalizeTimeoutS {
            startFreshMap()
            return
        }
        if !relocalizing && frame.timestamp - lastSave > Config.mapSaveIntervalS && (mapping == .mapped || mapping == .extending) {
            lastSave = frame.timestamp
            saveNow()
        }
        onFrame?(frame)
    }

    func session(_ session: ARSession, cameraDidChangeTrackingState camera: ARCamera) {
        if relocalizing, case .normal = camera.trackingState {
            relocalizing = false
            onMapEvent?("relocalized", mapId)
        }
        onTracking?(Self.describe(camera.trackingState))
    }

    func session(_ session: ARSession, didFailWithError error: Error) {
        onTracking?("failed: \(error.localizedDescription)")
    }

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
