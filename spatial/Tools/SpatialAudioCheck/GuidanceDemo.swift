import Foundation
import simd

/// Test-only trajectory. Only head yaw comes from hardware; body/hand movement is simulated.
struct GuidanceDemo {
    enum Stage: String { case intro, turn, aligned, approach, reachIntro, reach, touched, finished }
    enum Event: Equatable { case narration(String), cue(Cue) }
    struct Frame {
        let stage: Stage
        let chest: SIMD3<Float>
        let ear: SIMD3<Float>
        let target: SIMD3<Float>
        let distance: Double
        let events: [Event]
    }
    private(set) var stage = Stage.intro
    private(set) var alignmentConfirmed = false
    private var stageStart: Double?
    private var alignedSince: Double?
    private var saidTwo = false, saidOne = false
    private var guidance = Guidance()
    private let ray = SIMD3<Float>(0.5, 0, -0.8660254)
    private var target: SIMD3<Float> { ray * 3 + SIMD3(0, Config.earAboveChestM, 0) }

    mutating func tick(now: Double, headYaw: Double) -> Frame {
        var events: [Event] = []
        if stageStart == nil {
            stageStart = now
            events.append(.narration("Stay seated. This is a simulated approach. Only your head turns are tracked."))
        }
        let elapsed = now - stageStart!
        var distance = 3.0
        if stage == .approach { distance = max(0.5, 3 - elapsed / 18 * 2.5) }
        if [.reachIntro, .reach, .touched, .finished].contains(stage) { distance = 0.5 }
        let chest = ray * Float(3 - distance)
        let ear = chest + SIMD3<Float>(0, Config.earAboveChestM, 0)
        func append(_ cues: [Cue]) { events += cues.map { .cue($0) } }
        switch stage {
        case .intro:
            if elapsed >= 8 {
                guidance.start(GuidanceTarget(itemId: "demo-keys", name: "keys", position: target,
                                             surface: "table", labelText: nil, labelAudioURL: nil), now: now)
                stage = .turn; stageStart = now
                events.append(.narration("Keys are three meters ahead and to your right. Slowly turn your head right toward the beeps. Listen for the double ding."))
            }
        case .turn:
            // Let the instruction finish before starting the actual guidance cues.
            if elapsed >= 7 {
                append(guidance.tick(now: now, chest: chest, ear: ear, headYawDeg: headYaw))
                if abs(guidance.relAzimuthDeg) <= Guidance.facingDeg {
                    if alignedSince == nil { alignedSince = now }
                    if now - alignedSince! >= 0.6 {
                        alignmentConfirmed = true
                        stage = .aligned; stageStart = now
                        events.append(.narration("Head aligned. Stay seated. I will now simulate moving closer. Faster beeps mean closer."))
                    }
                } else { alignedSince = nil }
            }
            if elapsed >= 25 && stage == .turn {
                stage = .aligned; stageStart = now
                events.append(.narration("Head alignment was not confirmed. Stay seated. I will continue with a simulated distance demonstration."))
            }
        case .aligned:
            if elapsed >= 6 { stage = .approach; stageStart = now }
        case .approach:
            append(guidance.tick(now: now, chest: chest, ear: ear, headYawDeg: headYaw))
            if distance <= 2 && !saidTwo { saidTwo = true; events.append(.narration("Two meters.")) }
            if distance <= 1 && !saidOne { saidOne = true; events.append(.narration("One meter.")) }
            if elapsed >= 18 {
                stage = .reachIntro; stageStart = now
                events.append(.narration("Approach complete. Now simulating your hand reaching. A steady tone means your hand is close."))
            }
        case .reachIntro:
            if elapsed >= 6 { stage = .reach; stageStart = now }
        case .reach:
            let handDistance = max(0.05, 0.5 - elapsed / 7 * 0.45)
            guidance.handProximity(itemId: "demo-keys", distanceM: handDistance, t: now)
            append(guidance.tick(now: now, chest: chest, ear: ear, headYawDeg: headYaw))
            if elapsed >= 7 {
                append(guidance.touched(itemId: "demo-keys", t: now))
                stage = .touched; stageStart = now
            }
        case .touched:
            if elapsed >= 4 { stage = .finished; stageStart = now }
        case .finished: break
        }
        return Frame(stage: stage, chest: chest, ear: ear, target: target, distance: distance, events: events)
    }
}

/// Uses production audio and motion classes with the test-only trajectory above.
func runGuidanceDemo(audio: SpatialAudio, tracker: HeadTracker, referenceYaw: Double) {
    var demo = GuidanceDemo()
    var activeTime = 0.0
    var lastWall = ProcessInfo.processInfo.systemUptime
    let deadline = lastWall + 110
    var lost = false, speechUntil = 0.0
    var priorStage: GuidanceDemo.Stage?
    var samples = 0, missingTicks = 0, beeps = 0, dings = 0, steady = 0
    var lastSampleTime: Double?
    while ProcessInfo.processInfo.systemUptime < deadline {
        let now = ProcessInfo.processInfo.systemUptime
        let dt = min(0.1, now - lastWall)
        lastWall = now
        guard let sample = tracker.sample(now: now) else {
            if !lost { audio.play(.silence); print("Motion lost: pausing guidance AND simulated movement.") }
            lost = true; missingTicks += 1
            RunLoop.current.run(until: Date(timeIntervalSinceNow: 1.0 / 60)); continue
        }
        if sample.t != lastSampleTime { samples += 1; lastSampleTime = sample.t }
        if lost { print("Motion recovered: resuming simulated movement.") }
        lost = false
        activeTime += dt
        let yaw = Geo.wrap180(sample.yawDeg - referenceYaw)
        let frame = demo.tick(now: activeTime, headYaw: yaw)
        audio.place(Geo.listenerRelative(ear: frame.ear, headYawDeg: yaw, target: frame.target))
        if frame.stage != priorStage {
            print("SIMULATION stage=\(frame.stage.rawValue) distance=\(String(format: "%.2f", frame.distance)) m headAlignmentConfirmed=\(demo.alignmentConfirmed)")
            priorStage = frame.stage
        }
        // Narration is test instruction; .say cues are the production item's speech.
        for event in frame.events {
            if case .narration(let text) = event {
                audio.say(text, atItem: false)
                speechUntil = activeTime + max(1.2, Double(text.split(separator: " ").count) * 0.36)
            }
        }
        for event in frame.events {
            guard case .cue(let cue) = event else { continue }
            switch cue {
            case .beep:
                if activeTime >= speechUntil { audio.play(cue); beeps += 1 }
            case .say(let text):
                audio.say(text, atItem: true)
                speechUntil = activeTime + max(1.2, Double(text.split(separator: " ").count) * 0.36)
            case .ding: audio.play(cue); dings += 1
            case .steadyTone(let on): audio.play(cue); if on { steady += 1 }
            case .haptic: break // Mac helper has no phone haptic actuator.
            case .playLabel: break // Synthetic demo has no remote label.
            case .silence: audio.play(cue)
            }
        }
        if frame.stage == .finished { break }
        RunLoop.current.run(until: Date(timeIntervalSinceNow: 1.0 / 60))
    }
    print("GUIDANCE DEMO completed=\(demo.stage == .finished) headAlignmentConfirmed=\(demo.alignmentConfirmed) samples=\(samples) missingTicks=\(missingTicks) beeps=\(beeps) dings=\(dings) steadyEntries=\(steady)")
}
