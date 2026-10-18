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

/// Where a sound is, as the wearer hears it, from a listener-relative point (x right, y up, -z ahead): azimuth 0
/// ahead, +90 right, ±180 behind; elevation + up; distance ear to source. Rounded as the contract sends it.
struct HeardDirection: Equatable {
    var azDeg: Double
    var elDeg: Double
    var distanceM: Double

    init(_ p: SIMD3<Float>) {
        let x = Double(p.x), y = Double(p.y), z = Double(p.z)
        let flat = (x * x + z * z).squareRoot()
        azDeg = (atan2(x, -z) * 1800 / .pi).rounded() / 10
        elDeg = (atan2(y, flat) * 1800 / .pi).rounded() / 10
        distanceM = ((flat * flat + y * y).squareRoot() * 100).rounded() / 100
    }
}

/// What the wearer is hearing, told to the dashboard (docs/INTERFACES.md §3.2 `sound` and `sound_field`). Only the
/// phone knows: every sound is rendered here, at the point each source was placed, so the judges' view is the real
/// thing, not a reconstruction.
struct SoundReporter {
    static let fieldHz = 10.0
    let sessionId: String
    private var gate = Throttle(hz: SoundReporter.fieldHz)
    private var voiceUntil = -Double.infinity
    private var audible = false

    init(sessionId: String) { self.sessionId = sessionId }

    /// One sound, the moment it starts. `p`: where it comes from, listener-relative.
    mutating func cue(_ cue: String, at p: SIMD3<Float>, anchor: String, t: Double, muffled: Bool? = nil,
                      text: String? = nil, duration: Double? = nil, audioURL: String? = nil) -> SoundMsg {
        let voice = ["say", "label", "blip"].contains(cue)
        if cue == "silence" { voiceUntil = -Double.infinity }
        if voice, let duration { voiceUntil = max(voiceUntil, t + duration) }
        let d = HeardDirection(p)
        return SoundMsg(session_id: sessionId, t_device: t, cue: cue, source: voice ? "voice" : "beacon", anchor: anchor,
                        az_deg: d.azDeg, el_deg: d.elDeg, distance_m: d.distanceM, muffled: muffled, text: text,
                        duration_s: duration.map { ($0 * 10).rounded() / 10 }, audio_url: audioURL)
    }

    /// The field at 10/s while the beacon is placed or the voice is speaking, then once more when it goes quiet; nil
    /// otherwise. beacon: its point and whether it's muffled; voice: its point and anchor.
    mutating func field(t: Double, headYawDeg: Double, beacon: (SIMD3<Float>, muffled: Bool)?,
                        voice: (SIMD3<Float>, anchor: String)) -> SoundFieldMsg? {
        let speaking = t < voiceUntil
        let now = beacon != nil || speaking
        guard now || audible else { return nil }                 // quiet, and already said so
        guard !now || gate.ready(t) else { return nil }          // going quiet goes out at once
        audible = now
        func source(_ p: SIMD3<Float>, muffled: Bool? = nil, anchor: String? = nil) -> SoundFieldMsg.Source {
            let d = HeardDirection(p)
            return .init(az_deg: d.azDeg, el_deg: d.elDeg, distance_m: d.distanceM, muffled: muffled, anchor: anchor)
        }
        return SoundFieldMsg(session_id: sessionId, t_device: t, head_yaw_deg: (headYawDeg * 10).rounded() / 10,
                             beacon: beacon.map { source($0.0, muffled: $0.muffled) },
                             voice: speaking ? source(voice.0, anchor: voice.anchor) : nil)
    }

    /// How long a spoken line takes at AVSpeechUtterance's default rate: about 2.6 words a second.
    static func speechSeconds(_ text: String) -> Double {
        let words = text.split(whereSeparator: { $0 == " " }).count
        return (Double(words) / 2.6 + 0.3)
    }
}
