import Foundation

/// AirPods stream health for the debug screen (hour-one test 2: rate, jitter, latency, drift). The research has no
/// measured numbers for these (poc/research/airpods_facts.md), so the phone reports them.
struct MotionStats: Equatable {
    private(set) var samples = 0
    private(set) var rateHz = 0.0
    private(set) var jitterMs = 0.0          // standard deviation of the sample interval
    private(set) var latencyMs = 0.0         // median of arrival minus sample timestamp
    private(set) var yawDeg = 0.0            // raw CoreMotion yaw (arbitrary zero), to watch drift with the head still
    private var intervals: [Double] = []
    private var latencies: [Double] = []
    private var lastT: Double?
    static let window = 100

    mutating func add(t: Double, arrival: Double, yawDeg: Double) {
        samples += 1
        self.yawDeg = yawDeg
        if let l = lastT, t > l { intervals.append(t - l) }
        lastT = t
        latencies.append(arrival - t)
        if intervals.count > Self.window { intervals.removeFirst(intervals.count - Self.window) }
        if latencies.count > Self.window { latencies.removeFirst(latencies.count - Self.window) }
        if !intervals.isEmpty {
            let mean = intervals.reduce(0, +) / Double(intervals.count)
            let varSum = intervals.reduce(0) { $0 + ($1 - mean) * ($1 - mean) }
            rateHz = mean > 0 ? 1 / mean : 0
            jitterMs = (varSum / Double(intervals.count)).squareRoot() * 1000
        }
        latencyMs = latencies.sorted()[latencies.count / 2] * 1000
    }
}

/// Events per second over the last `window` seconds (frames accepted, poses, hands), for the debug screen.
struct RateMeter {
    let window: Double
    private var times: [Double] = []

    init(window: Double = 3) { self.window = window }

    mutating func tick(_ t: Double) {
        times.append(t)
        trim(t)
    }

    mutating func rate(_ now: Double) -> Double {
        trim(now)
        return Double(times.count) / window
    }

    private mutating func trim(_ now: Double) {
        if let i = times.firstIndex(where: { $0 > now - window }) {
            if i > 0 { times.removeFirst(i) }
        } else {
            times.removeAll()
        }
    }
}
