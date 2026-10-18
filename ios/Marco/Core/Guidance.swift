import Foundation
import simd

/// What the user hears while being guided to an item (docs/INTERFACES.md §7). The phases are the contract's; the
/// sounds inside them are the phone's.
enum Phase: String {
    case behind      // |azimuth| > 110 (back in front under 100): low, muffled beeps
    case turning     // in front, off to one side: plain beeps at a steady searching pace
    case facing      // just locked onto the beam: double ding + haptic, once per lock
    case approach    // on the beam: bright pulses, faster as the distance shrinks; the stop notes at the item
    case reach       // fingertip within 45 cm (hand_proximity): rising pings, a held tone on contact
    case touched     // touch on the target: silence, then "Got it" or the label
    case off
}

/// The walking beacon. Which one plays says where the item is without relying on the HRTF alone: a generic HRTF
/// can't tell front from behind reliably (POC 5, Microsoft Soundscape), and the app knows the true angle, so it
/// says it with the sound itself.
enum Beacon: Equatable {
    case onBeam      // facing it: a bright pulse whose pace is the distance
    case offBeam     // in front but off to one side: a plain beep at a steady searching pace
    case behind      // behind the head: low, muffled, slower
    case here        // stopped within reach: a soft ping from the item, so the hand knows where to go
}

enum Cue: Equatable {
    case beacon(Beacon)
    case ding                        // locked on: two rising notes
    case arrive                      // stop walking: three rising notes
    case handPing(Int)               // reach: pitch step 0 (45 cm away) ... handSteps - 1 (almost touching)
    case haptic
    case steadyTone(Bool)            // the fingertip is on it
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
///
/// Beeps do the guiding; the only words are the opening "Polo!" line and "Got it" at the touch. One question per
/// stage, one meaning per sound:
/// - Which way? (behind, turning) The pace is fixed and fast enough to sample while the head turns (POC 5: a 0.4 s
///   beat reached 99% against 93% at 1 s); only the timbre moves: low and muffled behind, plain in front.
/// - How far? (facing, approach) On the beam the pulse turns bright and its pace is the distance, across the whole
///   room. Drifting off the beam swaps back to the plain beep at once, so a veering walker hears it.
/// - Stop. Three rising notes and a buzz, early enough for the walker's speed, then soft pings from the item until
///   the hand shows up.
/// - Where's my hand? (reach) The fingertip's distance as pings that rise in pitch and speed, then a held tone on
///   contact: a parking sensor for the hand.
/// The beam is a corridor, not a cone (Microsoft's Soundscape patent, Clew): its half-angle widens up close, 30 cm
/// either side of the item, so a walker who will reach it anyway isn't told to turn.
struct Guidance {
    static let facingDeg = 12.0          // the beam's half-angle far away ...
    static let beamHalfWidthM = 0.3      // ... and its half-width at the item up close
    static let lockHysteresisDeg = 8.0   // unlock this far outside the lock angle: one lock, one ding
    static let behindDeg = 110.0         // POC 5
    static let behindExitDeg = 100.0     // hysteresis, so the timbre doesn't flicker at the side
    static let facingHoldS = 0.8         // "facing" right after the lock, then "approach"
    static let searchIntervalS = 0.4     // the beat while turning (POC 5)
    static let behindIntervalS = 0.55
    static let hereIntervalS = 1.1
    static let withinReachM = 0.6        // stop walking: the stop notes (POC 5), torso to item ...
    static let stopLeadS = 0.5           // ... played this much earlier at the walker's speed (Bluetooth + reaction) ...
    static let stopLeadMaxM = 0.3        // ... but never more than this early
    static let closingTauS = 0.3         // smoothing of the walking speed
    static let rearmM = 1.1              // walked off again: the next arrival stops them again
    static let arriveS = 0.8             // the stop notes, then the soft pings
    static let handStartM = 0.45         // fingertip to item: the hand takes over
    static let handReleaseM = 0.55
    static let contactM = 0.05           // the held tone: the fingertip is on it
    static let contactReleaseM = 0.09
    static let handSteps = 6
    static let proximityFreshS = 0.5     // hand_proximity older than this no longer counts
    static let touchedHoldS = 1.5        // report "touched" this long, then off
    static let quietAfterSpeechS = 1.2   // no beeps over a spoken line

    /// The beam's half-angle at a distance: 12° far away, wider up close so it stays 30 cm either side of the item
    /// (17° at 1 m, 27° at 0.6 m).
    static func lockDeg(_ distanceM: Double) -> Double {
        max(facingDeg, atan2(beamHalfWidthM, max(distanceM, 0.01)) * 180 / .pi)
    }

    /// On the beam, the gap between pulses: 0.9 s at 4 m down to 0.3 s at 1 m and 0.2 s (5 a second) at the stop, on
    /// a log scale so equal ratios of distance are equal steps of pace (tempo is judged best at 0.3-0.8 s gaps).
    static func beepInterval(_ distanceM: Double) -> Double { min(max(0.3 * pow(max(distanceM, 0), 0.8), 0.2), 0.95) }

    /// Reach: the gap between pings (45 cm 0.3 s, 10 cm 0.13 s) ...
    static func handInterval(_ d: Double) -> Double { min(max(0.08 + 0.5 * d, 0.09), 0.3) }

    /// ... and their pitch step, 0 at 45 cm up to handSteps - 1 just before contact.
    static func handStep(_ d: Double) -> Int {
        let x = (handStartM - d) / (handStartM - contactM)
        return min(max(Int(x * Double(handSteps)), 0), handSteps - 1)
    }

    /// About how long a line takes to say (2.6 words a second), so the beacon waits for the opening line.
    static func speechS(_ text: String) -> Double { Double(text.split(separator: " ").count) / 2.6 + 0.3 }

    private(set) var target: GuidanceTarget?
    private(set) var phase: Phase = .off
    private(set) var relAzimuthDeg = 0.0
    private(set) var distanceM = 0.0
    private var locked = false
    private var lockedAt = -Double.infinity
    private var behind = false
    private var arrived = false
    private var holding = false          // the steady tone is on
    private var lastBeep = -Double.infinity
    private var quietUntil = -Double.infinity
    private var proximity: (d: Double, t: Double)?
    private var touchedAt: Double?
    private var lastDistance: (t: Double, d: Double)?
    private(set) var closingMS = 0.0     // walking speed toward the item

    /// Where the stop is called: 0.6 m, plus the distance the walker covers while the stop notes reach them.
    var stopAtM: Double { Self.withinReachM + min(max(closingMS, 0) * Self.stopLeadS, Self.stopLeadMaxM) }

    var active: Bool { target != nil }
    /// Stopped at the item or reaching for it: sounds should come from its true direction (BeaconWarp.fovea).
    var withinReach: Bool { arrived || phase == .reach }

    /// speechS: how long the opening line ("Polo! Behind you, ...") takes; the beacon waits for it.
    mutating func start(_ t: GuidanceTarget, now: Double, speechS: Double = Guidance.quietAfterSpeechS) {
        self = Guidance()
        target = t
        phase = .turning
        quietUntil = now + speechS
    }

    /// An `event moved` for the target (§7): head for its new position.
    mutating func retarget(itemId: String, position: SIMD3<Float>, surface: String?) {
        guard target?.itemId == itemId else { return }
        let moved = target?.position != position
        target?.position = position
        target?.surface = surface
        guard moved else { return }
        arrived = false
        proximity = nil
        locked = false
        lockedAt = -Double.infinity
        lastDistance = nil
        closingMS = 0
    }

    mutating func updateLabel(itemId: String, name: String?, text: String?, audioURL: String?) {
        guard target?.itemId == itemId else { return }
        if let name { target?.name = name }
        target?.labelText = text
        target?.labelAudioURL = audioURL
    }

    mutating func stop() -> [Cue] {
        let wasHolding = holding
        self = Guidance()
        return wasHolding ? [.steadyTone(false)] : []
    }

    mutating func handProximity(itemId: String, distanceM d: Double, t: Double) {
        guard itemId == target?.itemId else { return }
        proximity = (d, t)
    }

    /// A touch from the server. On the target: silence, then its label or "Got it."
    mutating func touched(itemId: String?, t: Double) -> [Cue] {
        guard let tg = target, phase != .touched, itemId == tg.itemId else { return [] }
        var cues: [Cue] = holding ? [.steadyTone(false)] : []
        holding = false
        phase = .touched
        touchedAt = t
        cues += [.silence, .haptic]
        if let url = tg.labelAudioURL {
            cues.append(.playLabel(url, fallback: tg.labelText ?? "Got it."))
        } else {
            cues.append(.say(tg.labelText ?? "Got it."))
        }
        return cues
    }

    /// One 60 Hz step. chest: the phone's position; ear: the listener's; headYawDeg: the fused listener yaw, best
    /// already advanced to when the sound will be heard (YawPredictor).
    mutating func tick(now: Double, chest: SIMD3<Float>, ear: SIMD3<Float>, headYawDeg: Double) -> [Cue] {
        guard let tg = target else { return [] }
        if phase == .touched {
            if let ta = touchedAt, now - ta >= Self.touchedHoldS { self = Guidance() }
            return []
        }
        relAzimuthDeg = Geo.relativeAzimuthDeg(from: ear, headingDeg: headYawDeg, to: tg.position)
        distanceM = Geo.horizontalDistance(chest, tg.position)
        if let p = lastDistance, now > p.t {
            let v = min(max((p.d - distanceM) / (now - p.t), -3), 3)     // a tracking jump isn't a sprint
            closingMS += (v - closingMS) * min(1, (now - p.t) / Self.closingTauS)
        }
        lastDistance = (now, distanceM)
        let az = abs(relAzimuthDeg)
        var cues: [Cue] = []

        // The hand: from 45 cm the fingertip's distance is all that plays.
        let handLimit = phase == .reach ? Self.handReleaseM : Self.handStartM
        if let p = proximity, now - p.t <= Self.proximityFreshS, p.d <= handLimit {
            if phase != .reach {
                phase = .reach
                lastBeep = -.infinity
            }
            let on = p.d <= (holding ? Self.contactReleaseM : Self.contactM)
            if on != holding {
                holding = on
                cues.append(.steadyTone(on))
            }
            if !holding && now - lastBeep >= Self.handInterval(p.d) {
                lastBeep = now
                cues.append(.handPing(Self.handStep(p.d)))
            }
            return cues
        }
        if holding {
            holding = false
            cues.append(.steadyTone(false))
        }

        let lock = Self.lockDeg(distanceM)
        if !locked && az <= lock {
            locked = true
            lockedAt = now
            lastBeep = now
            cues += [.ding, .haptic]
        } else if locked && az > lock + Self.lockHysteresisDeg {
            locked = false
            lastBeep = -.infinity                    // the plain beep at once: you've drifted off the beam
        }
        behind = az > (behind ? Self.behindExitDeg : Self.behindDeg)
        if locked {
            phase = now - lockedAt < Self.facingHoldS ? .facing : .approach
        } else {
            phase = behind ? .behind : .turning
        }

        if arrived && distanceM > Self.rearmM { arrived = false }
        if !arrived && distanceM <= stopAtM {
            arrived = true
            quietUntil = now + Self.arriveS
            lastBeep = now
            cues += [.arrive, .haptic]
        }

        if now >= quietUntil {
            let (sound, gap): (Beacon, Double) =
                arrived ? (.here, Self.hereIntervalS)
                : locked ? (.onBeam, Self.beepInterval(distanceM))
                : behind ? (.behind, Self.behindIntervalS)
                : (.offBeam, Self.searchIntervalS)
            if now - lastBeep >= gap {
                lastBeep = now
                cues.append(.beacon(sound))
            }
        }
        return cues
    }
}

/// Where the beacon plays, from where the item really is (both listener-relative, x right, -z ahead). Hearing is good
/// at left/right and poor at front/back, so the beacon is never played behind: while walking, errors up to 30° are
/// doubled (an "acoustic fovea", Shinn-Cunningham 1998: a 6° miss sounds like 12°), 30-90° are squeezed into 60-90°,
/// and anything further round is pinned at 90° on the shorter turning side, where the dull "behind" beep says the
/// rest. Following the sound is always the short way round, and facing it is still facing the item, because the lock
/// uses the true angle. Within reach the fovea is 1: the hand needs the true direction. Dead behind, the side holds
/// until the item is 20° clear of the other side, so it doesn't flip ear to ear.
struct BeaconWarp {
    var on = true
    var fovea = 2.0                      // gain on small errors; 1 within reach
    private var side = 1.0

    mutating func apply(_ p: SIMD3<Float>) -> SIMD3<Float> {
        let flat = Double((p.x * p.x + p.z * p.z).squareRoot())
        guard on, flat > 1e-4 else { return p }
        let az = atan2(Double(p.x), Double(-p.z)) * 180 / .pi
        let a = abs(az)
        if a < 160 { side = az < 0 ? -1 : 1 }
        let w = a <= 30 ? fovea * a : a <= 90 ? 30 * fovea + (a - 30) * (90 - 30 * fovea) / 60 : 90
        let r = side * w * .pi / 180
        return SIMD3(Float(flat * sin(r)), p.y, Float(-flat * cos(r)))
    }
}

/// Bluetooth makes the AirPods play a sound 0.1-0.25 s after the app renders it, so a sound placed with the head's
/// current yaw is heard where the head was, not where it is: during a turn the beacon smears and the ding lands past
/// the item. VR headsets have the same problem with photons; the fix is the same: render with the pose the head will
/// have when the output arrives, yaw + rate x latency. The rate is a least-squares slope over the last `windowS`,
/// which irons out the AirPods' ~35 Hz steps under the 60 Hz tick; slow drifts get no lead at all.
struct YawPredictor {
    var windowS = 0.12
    var deadbandDegS = 20.0
    var maxLeadDeg = 25.0
    var gapS = 0.3                       // a pause longer than this starts the slope over
    private var samples: [(t: Double, yaw: Double)] = []   // yaw unwrapped, so a slope can cross ±180
    private(set) var rateDegS = 0.0

    /// The yaw `aheadS` from now. t: the tick's time, on the uptime clock.
    mutating func predict(t: Double, yawDeg: Double, aheadS: Double) -> Double {
        if let last = samples.last, t - last.t > gapS || t < last.t { samples.removeAll() }
        let y = samples.last.map { $0.yaw + Geo.wrap180(yawDeg - $0.yaw) } ?? yawDeg
        if samples.last?.t != t { samples.append((t, y)) }
        samples.removeAll { t - $0.t > windowS }
        rateDegS = 0
        if samples.count >= 3, let first = samples.first, t - first.t >= 0.04 {
            let n = Double(samples.count)
            let mt = samples.reduce(0) { $0 + $1.t } / n
            let my = samples.reduce(0) { $0 + $1.yaw } / n
            let sty = samples.reduce(0) { $0 + ($1.t - mt) * ($1.yaw - my) }
            let stt = samples.reduce(0) { $0 + ($1.t - mt) * ($1.t - mt) }
            if stt > 0 { rateDegS = sty / stt }
        }
        guard abs(rateDegS) >= deadbandDegS, aheadS > 0 else { return Geo.wrap180(yawDeg) }
        return Geo.wrap180(yawDeg + min(max(rateDegS * aheadS, -maxLeadDeg), maxLeadDeg))
    }

    mutating func reset() {
        samples.removeAll()
        rateDegS = 0
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
