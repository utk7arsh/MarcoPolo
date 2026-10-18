import Foundation
import simd

/// What the user hears while being guided to an item (docs/INTERFACES.md §7).
enum Phase: String {
    case behind      // |azimuth| > 90: muffled, lower beeps
    case turning     // off to the side
    case facing      // just locked on (|azimuth| <= 12): double ding + haptic, once per lock
    case approach    // walking: beeps faster as the distance shrinks
    case reach       // fingertip within 30 cm (hand_proximity): steady tone
    case touched     // touch on the target: silence, then "Got it" or the label
    case off
}

enum Cue: Equatable {
    case beep(muffled: Bool)
    case ding
    case haptic
    case steadyTone(Bool)
    case say(String)
    case playLabel(String, fallback: String) // cached audio, or current label text if unavailable
    case silence                     // stop everything that is playing
}

struct GuidanceTarget: Equatable {
    var itemId: String
    var name: String
    var position: SIMD3<Float>
    var surface: String?
    var labelText: String?
    var labelAudioURL: String?
}

/// The §7 loop as pure logic. The app ticks it at 60 Hz with the latest pose and head yaw, feeds it the server's
/// hand_proximity and touch messages, and plays the cues it returns. Angles are head-relative (what the user hears).
struct Guidance {
    static let facingDeg = 12.0
    static let unlockDeg = 20.0          // hysteresis: one lock, one ding
    static let behindDeg = 90.0
    static let facingHoldS = 0.8         // "facing" right after the lock, then "approach"
    static let reachProximityM = 0.30
    static let releaseProximityM = 0.40
    static let proximityFreshS = 0.5     // hand_proximity older than this no longer counts
    static let withinReachM = 0.6        // "Within reach" once, torso to item (POC 5)
    static let touchedHoldS = 1.5        // report "touched" this long, then off
    static let quietAfterSpeechS = 1.2   // no beeps over a spoken line

    /// §7 step 5: the gap between beeps.
    static func beepInterval(_ distanceM: Double) -> Double { min(max(0.15 + 0.35 * distanceM, 0.15), 1.0) }

    private(set) var target: GuidanceTarget?
    private(set) var phase: Phase = .off
    private(set) var relAzimuthDeg = 0.0
    private(set) var distanceM = 0.0
    private var locked = false
    private var lockedAt = -Double.infinity
    private var lastBeep = -Double.infinity
    private var quietUntil = -Double.infinity
    private var proximity: (d: Double, t: Double)?
    private var saidWithinReach = false
    private var touchedAt: Double?

    var active: Bool { target != nil }

    mutating func start(_ t: GuidanceTarget, now: Double) {
        self = Guidance()
        target = t
        phase = .turning
        quietUntil = now + Self.quietAfterSpeechS    // the "Polo!" line plays first
    }

    /// An `event moved` for the target (§7): head for its new position.
    mutating func retarget(itemId: String, position: SIMD3<Float>, surface: String?) {
        guard target?.itemId == itemId else { return }
        let moved = target?.position != position
        let changed = moved || target?.surface != surface
        target?.position = position
        target?.surface = surface
        guard changed else { return }
        saidWithinReach = false
        if moved {
            proximity = nil
            locked = false
            lockedAt = -Double.infinity
        }
    }

    mutating func updateLabel(itemId: String, name: String?, text: String?, audioURL: String?) {
        guard target?.itemId == itemId else { return }
        if let name { target?.name = name }
        target?.labelText = text
        target?.labelAudioURL = audioURL
    }

    mutating func stop() -> [Cue] {
        let wasReach = phase == .reach
        self = Guidance()
        return wasReach ? [.steadyTone(false)] : []
    }

    mutating func handProximity(itemId: String, distanceM d: Double, t: Double) {
        guard itemId == target?.itemId else { return }
        proximity = (d, t)
    }

    /// A touch from the server. On the target: silence, then its label or "Got it."
    mutating func touched(itemId: String?, t: Double) -> [Cue] {
        guard let tg = target, phase != .touched, itemId == tg.itemId else { return [] }
        let wasReach = phase == .reach
        phase = .touched
        touchedAt = t
        var cues: [Cue] = wasReach ? [.steadyTone(false)] : []
        cues += [.silence, .haptic]
        if let url = tg.labelAudioURL {
            cues.append(.playLabel(url, fallback: tg.labelText ?? "Got it."))
        } else {
            cues.append(.say(tg.labelText ?? "Got it."))
        }
        return cues
    }

    /// One 60 Hz step. chest: the phone's position; ear: the listener's; headYawDeg: the fused listener yaw.
    mutating func tick(now: Double, chest: SIMD3<Float>, ear: SIMD3<Float>, headYawDeg: Double) -> [Cue] {
        guard let tg = target else { return [] }
        if phase == .touched {
            if let ta = touchedAt, now - ta >= Self.touchedHoldS { self = Guidance() }
            return []
        }
        relAzimuthDeg = Geo.relativeAzimuthDeg(from: ear, headingDeg: headYawDeg, to: tg.position)
        distanceM = Geo.horizontalDistance(chest, tg.position)
        let az = abs(relAzimuthDeg)
        var cues: [Cue] = []

        let limit = phase == .reach ? Self.releaseProximityM : Self.reachProximityM
        if let p = proximity, now - p.t <= Self.proximityFreshS, p.d <= limit {
            if phase != .reach {
                phase = .reach
                cues.append(.steadyTone(true))
            }
            return cues
        }
        if phase == .reach { cues.append(.steadyTone(false)) }

        if !locked && az <= Self.facingDeg {
            locked = true
            lockedAt = now
            lastBeep = now
            cues += [.ding, .haptic]
        } else if locked && az > Self.unlockDeg {
            locked = false
        }
        if locked {
            phase = now - lockedAt < Self.facingHoldS ? .facing : .approach
        } else {
            phase = az > Self.behindDeg ? .behind : .turning
        }

        if !saidWithinReach && distanceM <= Self.withinReachM {
            saidWithinReach = true
            quietUntil = now + Self.quietAfterSpeechS
            cues.append(.say(tg.surface.map { "Within reach, on the \($0)." } ?? "Within reach."))
        }
        if now >= quietUntil && now - lastBeep >= Self.beepInterval(distanceM) {
            lastBeep = now
            cues.append(.beep(muffled: az > Self.behindDeg))
        }
        return cues
    }
}

/// Listener yaw in the world from the chest phone's ARKit heading and the AirPods' yaw (POC 4): AirPods yaw plus an
/// offset that is pulled toward the torso heading while the head is roughly forward and not turning fast. The
/// AirPods have no compass and drift; ARKit's torso heading doesn't. Without AirPods it is the torso heading
/// ("turn your body" mode).
///
/// Three additions for real AirPods, which the simulation didn't have:
/// - a Bluetooth gap shorter than `keepOffsetS` keeps the alignment (a longer one, e.g. a reconnect, starts over);
/// - a yaw jump faster than any head turn means the AirPods re-zeroed (they do on reconnect and when another app
///   starts spatial audio): re-align at once;
/// - a still head held more than the gate off the torso for `stuckS` means the alignment is wrong (it was made
///   while the head was turned), because nobody holds a turned head that long: re-align. If the user really was
///   looking sideways, the same rule heals it `stuckS` after they face forward again.
struct HeadFusion {
    var tau = 5.0                    // s; tuned in POC 4
    var gateRateDegS = 30.0
    var gateHeadOnTorsoDeg = 15.0
    var keepOffsetS = 2.0
    var jumpRateDegS = 1000.0
    var stuckS = 8.0
    private var offset: Double?
    private var prev: (yaw: Double, t: Double, torso: Double)?
    private var stuckSince: Double?
    private(set) var source = "phone"
    private(set) var realignments = 0
    /// Grows positive while AirPods and torso turn the same way during whole-body turns; negative means the AirPods
    /// yaw sign is flipped (use the debug screen's toggle).
    private(set) var signEvidence = 0.0

    /// airpodsDeg: the AirPods yaw already in heading convention (+ = right), nil when no fresh sample. t: the
    /// sample's time (or the frame's, when there is none), on the uptime clock.
    mutating func update(t: Double, torsoDeg: Double, airpodsDeg: Double?) -> Double {
        guard let ap = airpodsDeg else {
            if let p = prev, t - p.t > keepOffsetS {
                offset = nil
                prev = nil
                stuckSince = nil
            }
            source = "phone"
            return Geo.wrap180(torsoDeg)
        }
        var off: Double
        if let o = offset {
            off = o
        } else {
            off = Geo.wrap180(torsoDeg - ap)
            realignments += 1
        }
        if let p = prev, t > p.t {
            let dt = t - p.t
            let rate = Geo.wrap180(ap - p.yaw) / dt
            if abs(rate) > jumpRateDegS && dt < keepOffsetS {
                off = Geo.wrap180(torsoDeg - ap)
                realignments += 1
                stuckSince = nil
            } else {
                let dTorso = Geo.wrap180(torsoDeg - p.torso)
                if abs(dTorso) / dt > 20 { signEvidence += dTorso * Geo.wrap180(ap - p.yaw) }
                let headOnTorso = Geo.wrap180(ap + off - torsoDeg)
                let still = abs(rate) < gateRateDegS
                if still && abs(headOnTorso) < gateHeadOnTorsoDeg {
                    off += min(1, dt / tau) * Geo.wrap180(torsoDeg - (ap + off))
                    stuckSince = nil
                } else if still {
                    let since = stuckSince ?? t
                    stuckSince = since
                    if t - since > stuckS {
                        off = Geo.wrap180(torsoDeg - ap)
                        realignments += 1
                        stuckSince = nil
                    }
                } else {
                    stuckSince = nil
                }
            }
        }
        offset = Geo.wrap180(off)
        if prev == nil || t > prev!.t { prev = (ap, t, torsoDeg) }
        source = "fusion"
        return Geo.wrap180(ap + off)
    }
}
