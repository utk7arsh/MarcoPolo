import Foundation
import simd

// How Marco's sound gets to the ears. The AirPods take no commands: the server sends meaning (items, positions,
// touches) to the phone, the phone renders every sound binaurally with Apple's HRTF (Audio/SpatialAudio.swift), and
// the AirPods receive finished stereo over Bluetooth. So on the phone each server message becomes a sound plus where
// it comes from (a SoundAnchor). Room points are re-projected through the fused head yaw at 60 Hz, so a sound stays
// put in the room while the head turns. RouteWatch says whether that stereo is reaching two ears at all.

/// Where a sound comes from.
enum SoundAnchor: Equatable {
    case ahead                       // fixed to the head, 1 m in front: Marco's own lines ("Sorry, I didn't catch that")
    case world(SIMD3<Float>)         // a point in the room (ARKit world, metres): an item, a touched jar

    static let aheadPoint = SIMD3<Float>(0, 0, -1)

    /// A position from a server message, or ahead when it has none.
    static func at(_ position: [Float]?) -> SoundAnchor { Geo.vec(position).map(SoundAnchor.world) ?? .ahead }

    /// Listener-relative (x right, y up, -z ahead), as AVAudioEnvironmentNode takes it.
    func listenerRelative(ear: SIMD3<Float>, headYawDeg: Double) -> SIMD3<Float> {
        switch self {
        case .ahead: return Self.aheadPoint
        case .world(let p): return Geo.listenerRelative(ear: ear, headYawDeg: headYawDeg, target: p)
        }
    }
}

/// The audio output as the session reports it.
struct OutputRoute: Equatable {
    var name: String                 // "AirPods Pro", "Speaker"
    var headphones: Bool             // every output port is a headphone one (wired, Bluetooth A2DP, LE or HFP)
    var channels: Int

    /// HRTF needs a headphone in each ear. The iPhone's speaker, AirPlay, or a mono Bluetooth link can't place a sound.
    var binaural: Bool { headphones && channels >= 2 }
}

/// Whether spatial sound reaches two ears, settled: a route change counts once it has held for `settleS`, because
/// routes flap (the AirPods' mic mode switching, a reconnect, a handoff to another device and back).
struct RouteWatch {
    static let settleS = 1.5
    struct Change: Equatable {
        var was: Bool?               // nil: the first settled state since start
        var binaural: Bool
    }
    private(set) var binaural: Bool?
    private var pending: (value: Bool, since: Double)?

    mutating func observe(_ r: OutputRoute, now: Double) {
        if r.binaural == binaural { pending = nil; return }       // a flap that came back
        if pending?.value != r.binaural { pending = (r.binaural, now) }
    }

    /// The new settled state, once, after it has held for `settleS`.
    mutating func settle(now: Double) -> Change? {
        guard let p = pending, now - p.since >= Self.settleS else { return nil }
        pending = nil
        let c = Change(was: binaural, binaural: p.value)
        binaural = p.value
        return c
    }
}
