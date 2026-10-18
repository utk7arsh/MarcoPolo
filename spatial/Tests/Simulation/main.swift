import Foundation
import simd

var passed = 0, failed = 0
func check(_ condition: Bool, _ message: String) {
    if condition { passed += 1 } else { failed += 1; print("FAIL: \(message)") }
}
var demo = GuidanceDemo()
var events: [(Double, GuidanceDemo.Stage, GuidanceDemo.Event)] = []
var approachDistances: [Double] = []
var priorStage: GuidanceDemo.Stage?
var stages: [GuidanceDemo.Stage] = []
var target: SIMD3<Float>?
var fixedTarget = true
var finished = false
for i in 0..<5400 {
    let t = Double(i) / 60
    let frame = demo.tick(now: t, headYaw: 30)
    if target == nil { target = frame.target }
    fixedTarget = fixedTarget && simd_distance(target!, frame.target) < 1e-5
    if frame.stage != priorStage { stages.append(frame.stage); priorStage = frame.stage }
    for event in frame.events { events.append((t, frame.stage, event)) }
    if frame.stage == .approach { approachDistances.append(frame.distance) }
    if frame.stage == .finished { finished = true; break }
}
check(finished, "demo finishes with aligned head")
check(demo.alignmentConfirmed, "actual head alignment is recorded")
check(stages == [.intro, .turn, .aligned, .approach, .reachIntro, .reach, .touched, .finished], "turn/approach/reach sequence")
check(fixedTarget, "object stays fixed in world coordinates during simulated body motion")
check(zip(approachDistances, approachDistances.dropFirst()).allSatisfy { $0 >= $1 }, "approach distance decreases monotonically")
check((approachDistances.first ?? 0) > 2.9 && (approachDistances.last ?? 3) < 0.51, "approach covers 3 m to half a meter")
check(events.contains { $0.2 == .cue(.ding) }, "production facing ding is used")
check(events.contains { $0.2 == .narration("Two meters.") }, "two-meter narration")
check(events.contains { $0.2 == .narration("One meter.") }, "one-meter narration")
check(events.contains { $0.2 == .cue(.say("Within reach, on the table.")) }, "production within-reach speech")
check(events.contains { $0.2 == .cue(.steadyTone(true)) && $0.1 == .reach }, "hand proximity starts steady tone")
check(events.contains { $0.2 == .cue(.steadyTone(false)) }, "touch stops steady tone")
check(events.contains { $0.2 == .cue(.silence) }, "touch silences beacon")
check(events.contains { $0.2 == .cue(.say("Got it.")) }, "production touch confirmation")
check(!events.contains { $0.1 == .intro && $0.2 == .cue(.beep(muffled: false)) }, "intro does not emit beacon")
let approachBeeps = events.filter { $0.1 == .approach && $0.2 == .cue(.beep(muffled: false)) }.map { $0.0 }
let gaps = zip(approachBeeps, approachBeeps.dropFirst()).map { $1 - $0 }
check(gaps.count > 10 && gaps.first! > gaps.last!, "actual Guidance emits progressively faster approach beeps")
var noTurn = GuidanceDemo()
var disclosedTimeout = false
for i in 0..<5400 {
    let frame = noTurn.tick(now: Double(i) / 60, headYaw: 0)
    disclosedTimeout = disclosedTimeout || frame.events.contains {
        if case .narration(let text) = $0 { return text.contains("not confirmed") }; return false
    }
    if frame.stage == .finished { break }
}
check(!noTurn.alignmentConfirmed, "timeout cannot claim head alignment")
check(disclosedTimeout && noTurn.stage == .finished, "timeout is spoken before distance-only demo proceeds")
print("\(passed) guidance-demo checks passed, \(failed) failed")
exit(failed == 0 ? 0 : 1)
