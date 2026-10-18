import Foundation

/// How hard the phone works, by heat and by need. INTERFACES.md's rates are ceilings. Frames stay at 1/s and poses at
/// 10/s whatever happens, because the server's memory and the dashboard radar are built from them. The camera runs at
/// 60 fps and drops to 30 only when the phone is hot; hand detection and the LiDAR view give way first.
struct ResourcePolicy: Equatable {
    enum Heat: Int, Comparable, CaseIterable {
        case nominal, fair, serious, critical

        init(_ s: ProcessInfo.ThermalState) {
            switch s {
            case .nominal: self = .nominal
            case .fair: self = .fair
            case .serious: self = .serious
            case .critical: self = .critical
            @unknown default: self = .serious
            }
        }

        static func < (a: Heat, b: Heat) -> Bool { a.rawValue < b.rawValue }
        var label: String { ["nominal", "fair", "serious", "critical"][rawValue] }
    }

    var heat: Heat = .nominal

    /// The full hand rate holds this long after Vision last saw a hand.
    static let handHoldS = 1.5

    /// Vision hand detection: the full rate while a hand is around (the server's touch vote wants about 15 a second),
    /// a slow look-for-a-hand rate otherwise. Most of the time no hand is in view, so this is most of the saving.
    func handHz(sinceLastHand s: Double) -> Double {
        let active = s <= Self.handHoldS
        switch heat {
        case .nominal, .fair: return active ? Config.handHz : 5
        case .serious: return active ? 10 : 2
        case .critical: return active ? 5 : 1
        }
    }

    /// Camera at 30 fps instead of 60: half the camera, tracking and LiDAR work, only once the phone is hot.
    var lowCameraRate: Bool { heat >= .serious }

    /// The LiDAR view's redraw rate: the camera's rate, then lower as the phone heats up.
    var lidarViewFPS: Int { [60, 60, 30, 15][heat.rawValue] }

    /// "heat fair · camera 60 fps · hands 15/s near a hand, 5/s otherwise", for the developer screen.
    var summary: String {
        String(format: "heat %@ · camera %ld fps · hands %.0f/s near a hand, %.0f/s otherwise", heat.label,
               lowCameraRate ? 30 : 60, handHz(sinceLastHand: 0), handHz(sinceLastHand: .infinity))
    }
}

/// Picks hand-detection frames at the policy's rate, which depends on how recently a hand was seen.
struct HandRateGate {
    private(set) var lastRun = -Double.infinity
    private(set) var lastSeen = -Double.infinity

    /// slack: accept a frame this early, so a 60 fps source with jitter still gives the full rate.
    mutating func ready(_ now: Double, policy: ResourcePolicy, slack: Double = 0.004) -> Bool {
        let hz = policy.handHz(sinceLastHand: now - lastSeen)
        guard now - lastRun >= 1 / hz - slack else { return false }
        lastRun = now
        return true
    }

    /// Vision found a hand in the frame taken at `t`.
    mutating func sawHand(at t: Double) { lastSeen = max(lastSeen, t) }
}
