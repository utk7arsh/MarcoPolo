import CoreMotion
import Foundation

/// AirPods head yaw from CMHeadphoneMotionManager (needs NSMotionUsageDescription), in our heading convention
/// (+ = turning right; Config.airpodsYawSign). HeadFusion turns it into the listener's world yaw.
final class HeadTracker: NSObject, CMHeadphoneMotionManagerDelegate {
    private let manager = CMHeadphoneMotionManager()
    private let queue: OperationQueue = {
        let q = OperationQueue()
        q.maxConcurrentOperationCount = 1
        return q
    }()
    private let lock = NSLock()
    private var latest: (t: Double, yawDeg: Double)?
    private(set) var connected = false

    var available: Bool { manager.isDeviceMotionAvailable }

    func start() {
        guard manager.isDeviceMotionAvailable else { return }
        manager.delegate = self
        manager.startDeviceMotionUpdates(to: queue) { [weak self] motion, _ in
            guard let self, let m = motion else { return }
            let yaw = Config.airpodsYawSign * m.attitude.yaw * 180 / .pi
            self.lock.lock()
            self.latest = (m.timestamp, yaw)
            self.lock.unlock()
        }
    }

    func stop() { manager.stopDeviceMotionUpdates() }

    /// The newest sample if it is at most maxAge old. `now` is on the uptime clock, like ARFrame.timestamp.
    func sample(now: Double, maxAge: Double = 0.5) -> (t: Double, yawDeg: Double)? {
        lock.lock()
        defer { lock.unlock() }
        guard let l = latest, now - l.t <= maxAge else { return nil }
        return l
    }

    func headphoneMotionManagerDidConnect(_ manager: CMHeadphoneMotionManager) { connected = true }

    func headphoneMotionManagerDidDisconnect(_ manager: CMHeadphoneMotionManager) {
        connected = false
        lock.lock()
        latest = nil
        lock.unlock()
    }
}
