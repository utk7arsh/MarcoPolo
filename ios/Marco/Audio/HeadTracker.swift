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
    private var stats = MotionStats()
    private(set) var connected = false

    var available: Bool { manager.isDeviceMotionAvailable }

    /// Hour-one test 2 (REQUIREMENTS §9): rate (expect 25 Hz), jitter, sensor-to-app latency, raw yaw.
    var health: MotionStats { lock.lock(); defer { lock.unlock() }; return stats }

    func start() {
        guard manager.isDeviceMotionAvailable else { return }
        manager.delegate = self
        manager.startDeviceMotionUpdates(to: queue) { [weak self] motion, _ in
            guard let self, let m = motion else { return }
            let arrival = ProcessInfo.processInfo.systemUptime
            // Both should be the uptime clock; if they ever disagree, arrival time keeps the fusion working.
            let t = abs(arrival - m.timestamp) < 1 ? m.timestamp : arrival
            let raw = m.attitude.yaw * 180 / .pi
            self.lock.lock()
            self.latest = (t, Config.airpodsYawSign * raw)
            self.stats.add(t: t, arrival: arrival, yawDeg: raw)
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
