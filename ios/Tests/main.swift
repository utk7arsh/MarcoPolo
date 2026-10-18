// Unit tests for the parts of the app that build on macOS (run: sh ios/check.sh). With --emit DIR it also writes
// what the app would send, for server/tests/test_ios_contract.py to feed to the real server.
import AVFAudio
import CoreVideo
import Foundation
import ImageIO
import simd

var passed = 0
var failed = 0

func check(_ ok: Bool, _ what: @autoclosure () -> String, line: Int = #line) {
    if ok {
        passed += 1
    } else {
        failed += 1
        print("FAIL main.swift:\(line): \(what())")
    }
}

func near(_ a: Double, _ b: Double, _ tol: Double = 1e-4) -> Bool { abs(a - b) <= tol }

/// Rotation about +y (right-handed: positive turns -z toward -x, i.e. to the left), with a translation.
func pose(yawLeftDeg: Float, pitchDeg: Float = 0, at p: SIMD3<Float> = .zero) -> simd_float4x4 {
    let a = yawLeftDeg * .pi / 180, b = pitchDeg * .pi / 180
    let ry = simd_float4x4(columns: (SIMD4(cos(a), 0, -sin(a), 0), SIMD4(0, 1, 0, 0), SIMD4(sin(a), 0, cos(a), 0), SIMD4(0, 0, 0, 1)))
    let rx = simd_float4x4(columns: (SIMD4(1, 0, 0, 0), SIMD4(0, cos(b), sin(b), 0), SIMD4(0, -sin(b), cos(b), 0), SIMD4(0, 0, 0, 1)))
    var T = ry * rx
    T.columns.3 = SIMD4(p.x, p.y, p.z, 1)
    return T
}

struct SplitMix: RandomNumberGenerator {
    var state: UInt64
    mutating func next() -> UInt64 {
        state &+= 0x9E37_79B9_7F4A_7C15
        var z = state
        z = (z ^ (z >> 30)) &* 0xBF58_476D_1CE4_E5B9
        z = (z ^ (z >> 27)) &* 0x94D0_49BB_1331_11EB
        return z ^ (z >> 31)
    }
}

// MARK: - Geometry (server/marco/geometry.py conventions)

do {
    let T = pose(yawLeftDeg: -90, at: SIMD3(1, 2, 3))
    let f = Geo.flat(T)
    check(f.count == 16 && Array(f[12...14]) == [1, 2, 3] && f[15] == 1, "column-major puts the translation at 12..14: \(f)")
    check(Array(f[0...3]) == [T.columns.0.x, T.columns.0.y, T.columns.0.z, T.columns.0.w], "column 0 first")
    let K = simd_float3x3(columns: (SIMD3(1450, 0, 0), SIMD3(0, 1450, 0), SIMD3(960, 720, 1)))
    check(Geo.flat(K) == [1450, 0, 0, 0, 1450, 0, 960, 720, 1], "intrinsics column-major: \(Geo.flat(K))")
    check(near(Geo.headingDeg(pose(yawLeftDeg: 0)), 0), "facing -z is heading 0")
    check(near(Geo.headingDeg(pose(yawLeftDeg: -90)), 90), "turned right to +x is +90")
    check(near(Geo.headingDeg(pose(yawLeftDeg: 30, pitchDeg: -35)), -30), "pitch doesn't change heading")
    let o = SIMD3<Float>(0, 0, 0)
    check(near(Geo.relativeAzimuthDeg(from: o, headingDeg: 0, to: SIMD3(0, 0, -2)), 0), "ahead is 0")
    check(near(Geo.relativeAzimuthDeg(from: o, headingDeg: 0, to: SIMD3(2, 0, 0)), 90), "right is +90")
    check(near(Geo.relativeAzimuthDeg(from: o, headingDeg: 0, to: SIMD3(-1, 0, 0)), -90), "left is -90")
    check(near(abs(Geo.relativeAzimuthDeg(from: o, headingDeg: 0, to: SIMD3(0, 0, 2))), 180), "behind is 180")
    check(near(Geo.relativeAzimuthDeg(from: o, headingDeg: 90, to: SIMD3(2, 0, 0)), 0), "facing +x, +x is ahead")
    check(near(Geo.wrap180(190), -170) && near(Geo.wrap180(-190), 170) && near(Geo.wrap180(180), -180), "wrap180 like Python")
    let clocks: [(Double, Int)] = [(0, 12), (90, 3), (-90, 9), (180, 6), (-180, 6), (45, 2), (15, 12), (75, 2), (-15, 12), (-45, 10), (100, 3)]
    for (az, c) in clocks { check(Geo.clockPosition(az) == c, "clock(\(az)) = \(Geo.clockPosition(az)), want \(c)") }
    let steps: [(Double, Int)] = [(1.05, 2), (1.75, 2), (0.2, 1), (2.1, 3), (0.0, 1)]
    for (d, n) in steps { check(Geo.steps(d) == n, "steps(\(d)) = \(Geo.steps(d)), want \(n)") }
    let ahead = Geo.listenerRelative(ear: o, headYawDeg: 90, target: SIMD3(1, 0, 0))
    check(simd_distance(ahead, SIMD3(0, 0, -1)) < 1e-5, "facing +x, +x is ahead (-z): \(ahead)")
    let right = Geo.listenerRelative(ear: o, headYawDeg: 90, target: SIMD3(0, -0.5, 1))
    check(simd_distance(right, SIMD3(1, -0.5, 0)) < 1e-5, "facing +x, +z is to the right, below: \(right)")
}

// MARK: - Wire formats

do {
    let bytes = [UInt8](Wire.float16LE([1, -2, .nan, 0.5]))
    check(bytes == [0x00, 0x3C, 0x00, 0xC0, 0x00, 0x7E, 0x00, 0x38], "float16 little-endian: \(bytes)")
    let depth = (0..<(256 * 192)).map { Float($0 % 977) * 0.01 }
    let z = try! Wire.depthPayload(depth)
    let back = try! Wire.inflate(z)
    check(back == Wire.float16LE(depth) && z.count < back.count, "deflate round trip and it compresses")

    var d = [Float](repeating: 0, count: 256 * 192)
    var c = [UInt8](repeating: 0, count: 256 * 192)
    for v in 0..<192 { for u in 0..<256 { d[v * 256 + u] = Float(v * 256 + u); c[v * 256 + u] = UInt8((u + v) % 3) } }
    let centre = Joint(name: "indexTip", x: 10.5 / 256, y: 1 - 20.5 / 192, conf: 1)
    let corner = Joint(name: "wrist", x: 0, y: 1, conf: 1)
    let p = Wire.patches(depth: d, conf: c, width: 256, height: 192, joints: [centre, corner])
    check(p.depth.count == 2 * 81 && p.conf.count == 2 * 81, "two 9x9 patches")
    check(p.depth[40] == Float(20 * 256 + 10), "patch centre is pixel (u 10, v 20): \(p.depth[40])")
    check(p.depth[0] == Float(16 * 256 + 6), "patch row 0 is v - 4, column 0 is u - 4")
    check(p.depth[81].isNaN && p.conf[81] == 0, "outside the map: NaN and 0")
    check(p.depth[81 + 40] == 0 && p.depth[81 + 80] == Float(4 * 256 + 4), "corner joint centred on pixel (0, 0)")

    let body = Wire.multipart(boundary: "B", fields: [("meta", "{}")],
                              files: [.init(field: "image", filename: "f.jpg", contentType: "image/jpeg", data: Data([1, 2, 3]))])
    let s = String(decoding: body, as: UTF8.self)
    check(s.hasPrefix("--B\r\nContent-Disposition: form-data; name=\"meta\"\r\n\r\n{}\r\n") && s.hasSuffix("--B--\r\n"), "multipart layout")
}

// MARK: - Rates and the upload queue

do {
    var g = LatestWins<Int>()
    check(g.offer(1) == 1, "first upload starts at once")
    check(g.offer(2) == nil && g.offer(3) == nil && g.dropped == 1, "newer frames wait; only the newest is kept")
    check(g.finished() == 3 && g.inFlight, "the newest waiting frame goes next")
    check(g.finished() == nil && !g.inFlight, "then idle")

    var rng = SplitMix(state: 7)
    var gates = [Throttle(hz: 1), Throttle(hz: 10), Throttle(hz: 15)]
    var counts = [0, 0, 0]
    for i in 0..<600 {                                   // 10 s of ARKit at 60 Hz with +-2 ms jitter
        let t = Double(i) / 60 + Double.random(in: -0.002...0.002, using: &rng)
        for k in 0..<3 where gates[k].ready(t) { counts[k] += 1 }
    }
    check(counts[0] == 10 && (99...101).contains(counts[1]) && (148...151).contains(counts[2]), "1/10/15 Hz from 60 Hz: \(counts)")
}

// MARK: - Head fusion (POC 4)

do {
    var f = HeadFusion()
    check(f.update(t: 0, torsoDeg: 30, airpodsDeg: nil) == 30 && f.source == "phone", "no AirPods: the torso heading")
    // Head forward, AirPods drifting 1 deg/s: the fused yaw stays on the torso heading.
    var worst = 0.0
    for i in 0..<(60 * 25) {
        let t = Double(i) / 25
        let y = f.update(t: t, torsoDeg: 30, airpodsDeg: Geo.wrap180(-50 + 1.0 * t))
        if t > 20 { worst = max(worst, abs(Geo.wrap180(y - 30))) }
    }
    check(worst < 6 && f.source == "fusion", "drift is pulled out: worst \(worst) deg")
    // A quick head turn to 60 deg (torso still) is followed, not pulled back.
    var g = HeadFusion()
    var y = 0.0
    for i in 0..<100 {
        let t = Double(i) / 25
        let head = min(60, max(0, (t - 1) * 120))       // turns at 120 deg/s after 1 s
        y = g.update(t: t, torsoDeg: 0, airpodsDeg: head + 17)
    }
    check(near(y, 60, 1.0), "fused yaw follows the head turn: \(y)")
}

// MARK: - Head fusion on real AirPods: Bluetooth gaps, re-zeroing, a bad start, the sign check

do {
    func aligned() -> HeadFusion {                        // torso 10, AirPods -70: offset 80
        var f = HeadFusion()
        for i in 0..<50 { _ = f.update(t: Double(i) / 25, torsoDeg: 10, airpodsDeg: -70) }
        return f
    }
    // A 1 s gap (frames pass nil) keeps the alignment: the head turned 30 deg right meanwhile and reads 40.
    var f = aligned()
    for i in 0..<25 { _ = f.update(t: 2 + Double(i) / 25, torsoDeg: 10, airpodsDeg: nil) }
    let y = f.update(t: 3.0, torsoDeg: 10, airpodsDeg: -40)
    check(near(y, 40, 0.5) && f.realignments == 1, "a 1 s Bluetooth gap keeps the alignment: \(y), \(f.realignments)")
    // A 3 s gap is a reconnect: the AirPods restart from a new zero, so re-align to the torso.
    var g = aligned()
    for i in 0..<75 { _ = g.update(t: 2 + Double(i) / 25, torsoDeg: 10, airpodsDeg: nil) }
    let z = g.update(t: 5.0, torsoDeg: 10, airpodsDeg: 123)
    check(near(z, 10, 0.01) && g.realignments == 2, "a 3 s gap re-aligns: \(z), \(g.realignments)")
    // 120 deg in 40 ms is no head turn: the AirPods re-zeroed (another app's spatial audio), re-align at once.
    var h = aligned()
    let j = h.update(t: 2.0, torsoDeg: 10, airpodsDeg: 50)
    check(near(j, 10, 0.01) && h.realignments == 2, "a re-zero jump re-aligns: \(j)")
    // Aligned while the head was turned 40 deg left. The head comes back to face forward (AirPods +40 at
    // 40 deg/s) and the fusion reads 40 deg off; the 15 deg gate blocks the slow pull. After 8 s still: re-align.
    var k = HeadFusion()
    _ = k.update(t: 0, torsoDeg: 0, airpodsDeg: 0)
    var s = 0.0
    for i in 1...25 { s = k.update(t: Double(i) * 0.04, torsoDeg: 0, airpodsDeg: 1.6 * Double(i)) }
    check(near(s, 40, 0.5), "a bad start reads 40 deg off: \(s)")
    for i in 26...(26 + 9 * 25) { s = k.update(t: Double(i) * 0.04, torsoDeg: 0, airpodsDeg: 40) }
    check(abs(s) < 1 && k.realignments == 2, "...and is re-aligned after 8 s still: \(s), \(k.realignments)")
    // Whole-body turns (head fixed on the torso) show whether the AirPods yaw sign matches ARKit's.
    var good = HeadFusion(), bad = HeadFusion()
    for i in 0..<100 {
        let t = Double(i) * 0.04, torso = Geo.wrap180(Double(i) * 2.4)     // 60 deg/s
        _ = good.update(t: t, torsoDeg: torso, airpodsDeg: Geo.wrap180(torso + 33))
        _ = bad.update(t: t, torsoDeg: torso, airpodsDeg: Geo.wrap180(-torso + 33))
    }
    check(good.signEvidence > 50 && bad.signEvidence < -50, "sign check: \(good.signEvidence) / \(bad.signEvidence)")
}

// MARK: - Health readouts (hour-one test 2)

do {
    var m = MotionStats()
    for i in 0..<60 { m.add(t: 100 + Double(i) * 0.04, arrival: 100.03 + Double(i) * 0.04, yawDeg: 5) }
    check(near(m.rateHz, 25, 0.01) && m.jitterMs < 0.01 && near(m.latencyMs, 30, 0.01) && m.samples == 60,
          "AirPods stats: \(m.rateHz) Hz, \(m.jitterMs) ms jitter, \(m.latencyMs) ms latency")
    var r = RateMeter(window: 2)
    for i in 0..<100 { r.tick(Double(i) * 0.1) }
    check(near(r.rate(9.9), 10, 0.6), "rate meter: \(r.rate(9.9))/s")
    check(r.rate(30) == 0, "rate meter forgets old events")
}

// MARK: - Recording on the phone, in the server's layout (server/marco/recorder.py)

do {
    check(Recorder.folderName("a/../b c") == "abc" && Recorder.folderName("") == "unknown", "folder names match the server's")
    check(Recorder.stamped(Data(#"{"a":1}"#.utf8), wall: 1.5) == Data(#"{"a":1,"received_wall":1.5}"#.utf8), "stamp adds received_wall")
    check(Recorder.stamped(Data("{}".utf8), wall: 2) == Data(#"{"received_wall":2.0}"#.utf8), "stamp on an empty object")
    let root = FileManager.default.temporaryDirectory.appendingPathComponent("marco-rec-\(UUID().uuidString)")
    let rec = Recorder(root: root)
    rec.message(Data("{}".utf8))                                   // not recording yet: ignored
    let dir = rec.start(sessionId: "rec-test")
    let meta = FrameMeta(session_id: "rec-test", map_id: "m", frame_id: 7, t_device: 5, t_wall: Clock.wall(), tracking: "normal",
                         camera_transform: Geo.flat(matrix_identity_float4x4), intrinsics: Geo.flat(matrix_identity_float3x3),
                         image_resolution: [1920, 1440], jpeg_scale: 0.5)
    rec.frame(meta: try! JSONEncoder().encode(meta), frameId: 7, jpeg: Data([1, 2, 3]), depth: Data([4]), confidence: Data([5]))
    rec.message(try! JSONEncoder().encode(PoseMsg(session_id: "rec-test", map_id: "m", t_device: 5.1,
                                                  camera_transform: Geo.flat(matrix_identity_float4x4), head_yaw_deg: 0, head_source: "phone")))
    rec.stop()
    rec.message(Data("{}".utf8))                                   // stopped: ignored
    rec.flush()
    let read = { (name: String) in (try? String(contentsOf: dir.appendingPathComponent(name), encoding: .utf8)) ?? "" }
    let frames = read("frames.jsonl").split(separator: "\n"), phone = read("phone.jsonl").split(separator: "\n")
    let f0 = (try? JSONSerialization.jsonObject(with: Data((frames.first ?? "").utf8))) as? [String: Any] ?? [:]
    let p0 = (try? JSONSerialization.jsonObject(with: Data((phone.first ?? "").utf8))) as? [String: Any] ?? [:]
    check(frames.count == 1 && f0["frame_id"] as? Int == 7 && f0["received_wall"] as? Double != nil, "frames.jsonl: \(frames)")
    check(phone.count == 1 && p0["type"] as? String == "pose" && p0["received_wall"] as? Double != nil, "phone.jsonl: \(phone)")
    let fm = FileManager.default, fdir = dir.appendingPathComponent("frames")
    check(fm.contents(atPath: fdir.appendingPathComponent("000007.jpg").path) == Data([1, 2, 3])
          && fm.contents(atPath: fdir.appendingPathComponent("000007.depth").path) == Data([4])
          && fm.contents(atPath: fdir.appendingPathComponent("000007.conf").path) == Data([5]), "frame files are the bytes as sent")
    check(rec.progress.frames == 1 && rec.progress.messages == 1, "recorder counts: \(rec.progress)")
    try? fm.removeItem(at: root)
}

// MARK: - Guidance (INTERFACES.md §7)

do {
    check(near(Guidance.beepInterval(0), 0.15) && near(Guidance.beepInterval(1), 0.5) && near(Guidance.beepInterval(3), 1.0), "beep gap formula")
    var g = Guidance()
    let target = GuidanceTarget(itemId: "keys", name: "keys", position: SIMD3(0, 0.9, 2), surface: "counter", labelText: nil, labelAudioURL: nil)
    g.start(target, now: 0)
    var cues: [Cue] = []
    var t = 0.0
    func run(_ seconds: Double, chest: SIMD3<Float>, yaw: Double) {
        let end = t + seconds
        while t < end {
            cues += g.tick(now: t, chest: chest, ear: chest + SIMD3(0, 0.45, 0), headYawDeg: yaw)
            t += 1.0 / 60
        }
    }
    run(3, chest: .zero, yaw: 0)                                       // the keys are behind
    let beeps = cues.filter { if case .beep = $0 { return true } else { return false } }
    check(g.phase == .behind && !beeps.isEmpty && beeps.allSatisfy { $0 == .beep(muffled: true) }, "behind: muffled beeps (\(beeps.count))")
    check(!cues.contains(.ding), "no ding while behind")
    cues = []
    run(0.3, chest: .zero, yaw: 179)                                   // turns around
    check(cues.filter { $0 == .ding }.count == 1 && cues.contains(.haptic) && g.phase == .facing, "facing: one ding + haptic")
    cues = []
    run(1.0, chest: .zero, yaw: 175)
    check(g.phase == .approach && !cues.contains(.ding), "then approach, no second ding")
    run(0.2, chest: .zero, yaw: 140)                                   // drifts off by 39 deg: unlocks
    check(g.phase == .turning, "unlocked when 20+ deg off: \(g.phase)")
    cues = []
    run(0.2, chest: .zero, yaw: 180)
    check(cues.filter { $0 == .ding }.count == 1, "a new lock dings again")
    cues = []
    run(2, chest: SIMD3(0, 0, 1.5), yaw: 180)                          // walks up to it
    check(near(g.distanceM, 0.5, 1e-3) && cues.contains(.say("Within reach, on the counter.")), "within reach, said once")
    g.handProximity(itemId: "keys", distanceM: 0.25, t: t)
    cues = []
    run(0.1, chest: SIMD3(0, 0, 1.5), yaw: 180)
    check(g.phase == .reach && cues == [.steadyTone(true)], "steady tone within 30 cm: \(cues)")
    g.handProximity(itemId: "wallet", distanceM: 0.05, t: t)           // another item's proximity is ignored
    check(g.touched(itemId: "wallet", t: t).isEmpty, "a touch on another item doesn't end guidance")
    let touch = g.touched(itemId: "keys", t: t)
    check(touch == [.steadyTone(false), .silence, .haptic, .say("Got it.")] && g.phase == .touched, "touch: silence then Got it: \(touch)")
    run(1.6, chest: SIMD3(0, 0, 1.5), yaw: 180)
    check(!g.active && g.phase == .off, "off after the touched hold")

    var h = Guidance()
    h.start(GuidanceTarget(itemId: "mug", name: "mug", position: SIMD3(0, 1, -3), surface: nil, labelText: nil, labelAudioURL: "/v1/audio/a"), now: 0)
    h.retarget(itemId: "mug", position: SIMD3(3, 1, 0))
    _ = h.tick(now: 0, chest: .zero, ear: SIMD3(0, 0.45, 0), headYawDeg: 0)
    check(near(h.relAzimuthDeg, 90, 0.01), "moved event retargets: \(h.relAzimuthDeg)")
    h.handProximity(itemId: "mug", distanceM: 0.2, t: 0)
    _ = h.tick(now: 0.9, chest: .zero, ear: SIMD3(0, 0.45, 0), headYawDeg: 0)
    check(h.phase != .reach, "stale proximity doesn't count")
    check(h.touched(itemId: "mug", t: 1) == [.silence, .haptic, .playLabel("/v1/audio/a")], "a labelled item plays its label")
}

// MARK: - What Marco says, and what it hears

do {
    check(Lines.polo(relAzimuthDeg: 180, distanceM: 1.4, surface: "table") == "Polo! Behind you, two steps, on the table.", Lines.polo(relAzimuthDeg: 180, distanceM: 1.4, surface: "table"))
    check(Lines.polo(relAzimuthDeg: 90, distanceM: 0.7, surface: nil) == "Polo! On your right, one step.", "one step on the right")
    check(Lines.polo(relAzimuthDeg: 60, distanceM: 3.0, surface: "shelf") == "Polo! At two o'clock, four steps, on the shelf.", "clock words")
    check(Lines.polo(relAzimuthDeg: 0, distanceM: 0.5, surface: "counter") == "Polo! Within reach, straight ahead, on the counter.", "within reach")
    let nf = FindAnswer(query_id: "q", found: false, item_id: nil, name: "cat", position: nil, surface: nil, seen_ago_s: nil,
                        confidence: nil, state: nil, reason: "not_registered", last_position: nil)
    check(Lines.notFound(nf, asked: "cat") == "I don't know your cat yet. Send me a photo of it.", "not registered")
    check(!Lines.bearings.lowercased().contains("marco"), "Marco never says its own wake word")
    check(Lines.spokenLabel(name: "turmeric", labelText: "Turmeric") == "That's the turmeric.", "a bare name gets a sentence")
    check(Lines.spokenLabel(name: "cumin", labelText: "That's the cumin, love") == "That's the cumin, love", "the caretaker's words")
    check(Lines.spokenLabel(name: "mug", labelText: nil) == "That's the mug.", "no label text")
    if let items = try? JSONDecoder().decode([ItemInfo].self, from: Data(#"[{"item_id":"a","name":"keys","position":null,"surface":null,"state":"registered","last_seen_wall":null,"label_text":null,"label_audio_url":null,"size_m":0.1}]"#.utf8)) {
        check(items.count == 1 && items[0].name == "keys", "GET /v1/items decodes")
    } else { check(false, "GET /v1/items decodes") }

    check(Speech.command(after: "Marco, where are my keys?") == "where are my keys", "wake word stripped")
    check(Speech.command(after: "hello there") == nil, "no wake word, no command")
    check(Speech.command(after: "marco blah. Marko what is this") == "what is this", "the last wake word wins")
    let intents: [(String, Intent?)] = [
        ("where are my keys", .find("keys")), ("Where did I leave the wallet?", .find("wallet")),
        ("find my water bottle please", .find("water bottle")), ("where's my mug", .find("mug")),
        ("where is the remote", .find("remote")), ("what is this", .whatIsThis), ("what am I touching", .whatIsThis),
        ("this is the door", .setDoor), ("stop", .stop), ("never mind", .stop), ("tell me a joke", nil)]
    for (text, want) in intents { check(Speech.intent(text) == want, "intent(\(text)) = \(String(describing: Speech.intent(text)))") }

    // The wake word as the recognizer writes it, and "Marco" alone.
    check(Speech.command(after: "Hey Marco, where's my wallet") == "where's my wallet", "hey Marco")
    check(Speech.command(after: "Mark oh where are my keys") == "where are my keys", "Mark oh")
    check(Speech.command(after: "Marco") == "", "the wake word alone is an empty command")
    check(Speech.command(after: "Marcos Polo was a traveller") == nil, "Marcos is not the wake word")

    // How people ask, with no registered items: the thing, as said.
    let asks: [(String, Intent?)] = [
        ("do you know where my keys are", .find("keys")), ("where did my wallet go", .find("wallet")),
        ("where my keys at", .find("keys")), ("have you seen my glasses", .find("glasses")),
        ("can you help me find my phone", .find("phone")), ("I can't find my charger", .find("charger")),
        ("polo where are my keys", .find("keys")), ("okay could you find the remote for me", .find("remote")),
        ("I'm looking for my cane", .find("cane")), ("where did I put the cumin", .find("cumin")),
        ("where is it", nil), ("where", nil), ("keys", nil), ("please stop", .stop)]
    for (text, want) in asks { check(Speech.intent(text) == want, "intent(\(text)) = \(String(describing: Speech.intent(text)))") }

    // With registered items: the item's own name.
    let v = ItemVocabulary(["keys", "Wallet", "blue water bottle", "coffee mug", "cumin jar", "paprika jar",
                            "glasses case", "TV remote", "wallet"])
    check(v.names.count == 8, "names are kept once, ignoring case: \(v.names)")
    let resolved: [(String, String?)] = [
        ("keys", "keys"), ("key", "keys"), ("my car keys", "keys"), ("keyring", "keys"), ("wallets", "Wallet"),
        ("walet", "Wallet"), ("billfold", "Wallet"), ("the water bottle", "blue water bottle"), ("bottle", "blue water bottle"),
        ("mug", "coffee mug"), ("cup", "coffee mug"), ("red mug", "coffee mug"), ("specs", "glasses case"),
        ("remote", "TV remote"), ("clicker", "TV remote"), ("cumin", "cumin jar"), ("kumin", "cumin jar"),
        ("jar", nil), ("passport", nil), ("cake", nil), ("water glass", nil), ("", nil)]
    for (said, want) in resolved {
        check(v.resolve(said)?.name == want, "resolve(\(said)) = \(String(describing: v.resolve(said)?.name)), want \(String(describing: want))")
    }
    check(v.resolve("keys")?.how == .exact && v.resolve("billfold")?.how == .synonym && v.resolve("walet")?.how == .spelling
          && v.resolve("car keys")?.how == .partial, "how each matched")
    let both = ItemVocabulary(["keys", "car keys"])
    check(both.resolve("car keys")?.name == "car keys" && both.resolve("spare car keys")?.name == "car keys"
          && both.resolve("keys")?.name == "keys", "the more specific name wins")

    let withItems: [(String, Intent?)] = [
        ("where are my car keys", .find("keys")), ("I can't find my specs", .find("glasses case")),
        ("where's the thing", nil), ("where is my walet", .find("Wallet")), ("where are my keys and my wallet", .find("keys")),
        ("where's my passport", .find("passport")), ("keys", .find("keys")), ("my coffee mug", .find("coffee mug")),
        ("bottle", nil), ("tell me a joke", nil), ("what is this", .whatIsThis)]
    for (text, want) in withItems {
        check(Speech.intent(text, items: v) == want, "intent(\(text), items) = \(String(describing: Speech.intent(text, items: v)))")
    }

    // Answer sooner when nothing more is needed; wait when the name is still coming.
    check(Speech.isComplete("where are my keys", items: v), "a whole registered name is complete")
    check(!Speech.isComplete("where are my", items: v) && !Speech.isComplete("where's my water", items: v),
          "half a name is not")
    check(!Speech.isComplete("where are my car keys", items: v), "more words than the name: wait for the rest")
    check(Speech.isComplete("stop", items: v) && !Speech.isComplete("tell me", items: v), "stop is complete")
    check(Words.editDistance("cumin", "kumin") == 1 && Words.editDistance("", "abc") == 3 && Words.editDistance("abc", "abc") == 0,
          "edit distance")
    check(Words.content("My Mom's glasses") == ["mom", "glass"] && Words.stem("batteries") == "battery", "stems")
}

// MARK: - Server messages (§4), as the server sends them

do {
    func decode(_ s: String) -> ServerMessage? { try? ServerMessage.decode(Data(s.utf8)) }
    if case .find(let a)? = decode(#"{"type":"answer","query_id":"q1","kind":"find","found":true,"item_id":"fake-keys","name":"keys","position":[1.0,0.75,-2.0],"surface":"table","seen_ago_s":null,"confidence":0.8,"state":"present"}"#) {
        check(a.found && a.position == [1, 0.75, -2] && a.seen_ago_s == nil, "find answer")
    } else { check(false, "find answer decodes") }
    if case .find(let a)? = decode(#"{"type":"answer","query_id":"q2","kind":"find","found":false,"reason":"not_where_last_seen","item_id":"i","name":"mug","last_position":[0,1,0],"surface":"shelf"}"#) {
        check(!a.found && a.reason == "not_where_last_seen" && a.last_position == [0, 1, 0], "not found answer")
    } else { check(false, "not found decodes") }
    check(decode(#"{"type":"answer","query_id":"q3","kind":"what_is_this","status":"unknown","touch_id":"t1"}"#)
          == .whatIsThis(WhatAnswer(query_id: "q3", status: "unknown", item_id: nil, name: nil, label_text: nil, label_audio_url: nil, touch_id: "t1")), "what is this")
    check(decode(#"{"type":"answer","query_id":"q4","kind":"set_place","name":"door","ok":true}"#)
          == .setPlace(SetPlaceAnswer(query_id: "q4", name: "door", ok: true)), "set_place")
    check(decode(#"{"type":"touch","touch_id":"t1","item_id":null,"name":null,"position":[0,1,0],"t_device":null}"#)
          == .touch(TouchMsg(touch_id: "t1", item_id: nil, name: nil, position: [0, 1, 0], t_device: nil)), "touch of an unknown thing")
    check(decode(#"{"type":"touch_end","touch_id":"t1"}"#) == .touchEnd(TouchEndMsg(touch_id: "t1")), "touch_end")
    check(decode(#"{"type":"hand_proximity","item_id":"k","distance_m":0.27}"#) == .handProximity(HandProximityMsg(item_id: "k", distance_m: 0.27)), "proximity")
    if case .event(let e)? = decode(#"{"type":"event","kind":"moved","item_id":"i","name":"mug","position":[1,0.9,0],"from_position":[0,0.9,0],"surface":"counter","t_wall":"x"}"#) {
        check(e.kind == "moved" && e.from_position == [0, 0.9, 0], "moved event")
    } else { check(false, "event decodes") }
    check(decode(#"{"type":"label_ready","item_id":"i","name":"cumin","label_text":"That's the cumin, love","label_audio_url":"/v1/audio/a"}"#)
          == .labelReady(LabelReadyMsg(item_id: "i", name: "cumin", label_text: "That's the cumin, love", label_audio_url: "/v1/audio/a")), "label_ready")
    check(decode(#"{"type":"error","detail":"bad","for_type":"hand"}"#) == .error(ServerErrorMsg(detail: "bad", for_type: "hand")), "error")
    check(decode(#"{"type":"frame","jpeg_b64":"..."}"#) == .other("frame"), "unknown types don't throw")
}

// MARK: - Frame encoding (CoreImage, CoreVideo)

func ycbcr(_ w: Int, _ h: Int) -> CVPixelBuffer {
    var out: CVPixelBuffer?
    let attrs = [kCVPixelBufferIOSurfacePropertiesKey as String: [String: Any]()] as CFDictionary
    CVPixelBufferCreate(nil, w, h, kCVPixelFormatType_420YpCbCr8BiPlanarFullRange, attrs, &out)
    let pb = out!
    CVPixelBufferLockBaseAddress(pb, [])
    let y = CVPixelBufferGetBaseAddressOfPlane(pb, 0)!.assumingMemoryBound(to: UInt8.self)
    let yRow = CVPixelBufferGetBytesPerRowOfPlane(pb, 0)
    for r in 0..<h { for c in 0..<w { y[r * yRow + c] = UInt8((c * 255) / w) } }
    let uv = CVPixelBufferGetBaseAddressOfPlane(pb, 1)!.assumingMemoryBound(to: UInt8.self)
    let uvRow = CVPixelBufferGetBytesPerRowOfPlane(pb, 1)
    for r in 0..<(h / 2) { for c in 0..<(w / 2) { uv[r * uvRow + 2 * c] = 128; uv[r * uvRow + 2 * c + 1] = UInt8((r * 255) / (h / 2)) } }
    CVPixelBufferUnlockBaseAddress(pb, [])
    return pb
}

/// A one-plane buffer with padded rows, like ARKit's depth and confidence maps can have.
func padded<T>(_ values: [T], _ w: Int, _ h: Int, format: OSType, pad: Int = 64) -> CVPixelBuffer {
    let row = w * MemoryLayout<T>.stride + pad
    let mem = UnsafeMutableRawPointer.allocate(byteCount: row * h, alignment: 64)
    for y in 0..<h { for x in 0..<w { (mem + y * row).assumingMemoryBound(to: T.self)[x] = values[y * w + x] } }
    var out: CVPixelBuffer?
    let st = CVPixelBufferCreateWithBytes(nil, w, h, format, mem, row, { _, base in UnsafeMutableRawPointer(mutating: base)?.deallocate() }, nil, nil, &out)
    precondition(st == kCVReturnSuccess, "CVPixelBufferCreateWithBytes \(st)")
    return out!
}

func jpegInfo(_ data: Data) -> (w: Int, h: Int, orientation: Int?) {
    let src = CGImageSourceCreateWithData(data as CFData, nil)!
    let p = CGImageSourceCopyPropertiesAtIndex(src, 0, nil) as! [CFString: Any]
    return (p[kCGImagePropertyPixelWidth] as! Int, p[kCGImagePropertyPixelHeight] as! Int, p[kCGImagePropertyOrientation] as? Int)
}

func syntheticMaps() -> (depth: [Float], conf: [UInt8]) {
    var d = [Float](), c = [UInt8]()
    for v in 0..<192 {
        for u in 0..<256 {
            let z: Float = 1.0 + 0.002 * Float(u) + 0.003 * Float(v)
            d.append(z)
            c.append(UInt8((u + v) % 3))
        }
    }
    return (d, c)
}
let (syntheticDepth, syntheticConf) = syntheticMaps()
let sensorImage = ycbcr(1920, 1440)
let encoder = FrameEncoder()
let jpeg = encoder.jpeg(sensorImage)!

do {
    let info = jpegInfo(jpeg)
    check(info.w == 960 && info.h == 720, "JPEG is the sensor image scaled 0.5: \(info.w)x\(info.h)")
    check(info.orientation == nil || info.orientation == 1, "no EXIF rotation: \(String(describing: info.orientation))")
    let d = FrameEncoder.plane(padded(syntheticDepth, 256, 192, format: kCVPixelFormatType_DepthFloat32), as: Float32.self)
    check(d.width == 256 && d.height == 192 && d.values == syntheticDepth, "depth rows copied past the padding")
    let c = FrameEncoder.plane(padded(syntheticConf, 256, 192, format: kCVPixelFormatType_OneComponent8), as: UInt8.self)
    check(c.values == syntheticConf, "confidence rows copied past the padding")
    let fmt = AVAudioFormat(standardFormatWithSampleRate: 48_000, channels: 1)!
    let loop = Tones.loop(fmt, freq: 660)
    let s = loop.floatChannelData![0]
    check(loop.frameLength == 48_000 && abs(s[0]) < 1e-6 && abs(s[47_999] - s[0]) < 0.06, "steady tone loops without a click")
    check(Tones.beep(fmt, freq: 880, harmonics: 6, ms: 70, noise: 0.1).frameLength == 3360, "70 ms beep")
}

// MARK: - Connecting to the server (venue Mac or the Vultr box, over the tailnet)

do {
    let h = "marco-gpu.example.ts.net"
    let ok = ServerCheck.describe(host: h, status: 200, error: nil, ms: 61, items: 3)
    check(ok.hasPrefix("Server OK") && ok.contains("3 items") && ok.contains("61 ms"), ok)
    check(ServerCheck.describe(host: h, status: 200, error: nil, ms: 5, items: 1).contains("1 item registered"), "singular")
    check(ServerCheck.describe(host: h, status: 403, error: nil, ms: 0, items: nil).contains("TAILSCALE_ALLOWED_LOGINS"), "403 names the allow-list")
    check(ServerCheck.describe(host: h, status: nil, error: .cannotFindHost, ms: 0, items: nil).contains("Tailscale app"), "DNS failure: Tailscale off")
    check(ServerCheck.describe(host: h, status: nil, error: .timedOut, ms: 0, items: nil).contains("marco-vultr.sh status"), "timeout: is the box up")
    check(ServerCheck.describe(host: h, status: nil, error: .appTransportSecurityRequiresSecureConnection, ms: 0, items: nil).contains("https"), "plain http")
}

// MARK: - Contract fixtures for the server

if let i = CommandLine.arguments.firstIndex(of: "--emit"), i + 1 < CommandLine.arguments.count {
    let dir = URL(fileURLWithPath: CommandLine.arguments[i + 1], isDirectory: true)
    try! FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
    func write(_ name: String, _ data: Data) { try! data.write(to: dir.appendingPathComponent(name)) }
    let enc = JSONEncoder()
    func json<T: Encodable>(_ v: T) -> Data { try! enc.encode(v) }

    let sid = "ios-contract", mid = "ios-map"
    let T = pose(yawLeftDeg: 30, pitchDeg: -20, at: SIMD3(0.5, 1.2, -0.3))
    let K = simd_float3x3(columns: (SIMD3(1450, 0, 0), SIMD3(0, 1450, 0), SIMD3(960, 720, 1)))
    write("depth_truth.f32", syntheticDepth.withUnsafeBytes { Data($0) })
    write("conf_truth.u8", Data(syntheticConf))

    let meta = FrameMeta(session_id: sid, map_id: mid, frame_id: 1, t_device: 1000.0, t_wall: Clock.wall(), tracking: "normal",
                         camera_transform: Geo.flat(T), intrinsics: Geo.flat(K), image_resolution: [1920, 1440], jpeg_scale: 0.5)
    let frame = Uploader.Frame(meta: meta, jpeg: jpeg, depth: try! Wire.depthPayload(syntheticDepth),
                               confidence: try! Wire.confidencePayload(syntheticConf))
    let (req, body) = try! Uploader.frameRequest(base: URL(string: "https://server.example.ts.net")!, frame)
    write("frame_multipart.bin", body)
    write("frame_content_type.txt", Data(req.value(forHTTPHeaderField: "Content-Type")!.utf8))
    write("frame_url.txt", Data(req.url!.absoluteString.utf8))

    var joints = HandJoints.names.enumerated().map { j, n in Joint(name: n, x: 0.30 + 0.01 * Double(j), y: 0.40 + 0.012 * Double(j), conf: 0.9) }
    joints[0] = Joint(name: "wrist", x: 0.001, y: 0.999, conf: 0.8)           // at the map's corner: padded patch
    joints[8] = Joint(name: "indexTip", x: 0.5, y: 0.5, conf: 0.95)
    let hand = HandMsg.make(sessionId: sid, mapId: mid, t: 1000.05, transform: T, joints: joints, chirality: "right",
                            depth: syntheticDepth, conf: syntheticConf, width: 256, height: 192)
    var lines: [Data] = [
        json(PoseMsg(session_id: sid, map_id: mid, t_device: 1000.02, camera_transform: Geo.flat(T), head_yaw_deg: 12.5, head_source: "fusion")),
        json(hand),
        json(MapMsg(session_id: sid, event: "relocalized", map_id: mid)),
        json(QueryMsg(session_id: sid, query_id: "q-find", kind: "find", name: "keys")),
        json(QueryMsg(session_id: sid, query_id: "q-what", kind: "what_is_this", name: nil)),
        json(QueryMsg(session_id: sid, query_id: "q-door", kind: "set_place", name: "door")),
        json(GuidanceMsg(session_id: sid, item_id: "fake-keys", phase: "turning", rel_azimuth_deg: -140, distance_m: 1.6)),
        json(GuidanceMsg(session_id: sid, item_id: nil, phase: "off", rel_azimuth_deg: 0, distance_m: 0)),
    ]
    write("phone.jsonl", lines.reduce(into: Data()) { $0.append($1); $0.append(0x0A) })
    lines.removeAll()

    // A short walk recorded on the phone (Core/Recorder.swift), for server/tools/check_recording.py and
    // marco.session.Session: 3 frames at 1/s, 21 poses at 10/s, a hand and a map event.
    let rec = Recorder(root: dir.appendingPathComponent("recorded"))
    rec.start(sessionId: sid)
    rec.message(json(MapMsg(session_id: sid, event: "new_map", map_id: mid)))
    for k in 0..<3 {
        var m = meta
        m.frame_id = k + 1
        m.t_device = 1000.0 + Double(k)
        rec.frame(meta: json(m), frameId: m.frame_id, jpeg: jpeg, depth: frame.depth, confidence: frame.confidence)
    }
    for k in 0...20 {
        rec.message(json(PoseMsg(session_id: sid, map_id: mid, t_device: 1000.0 + Double(k) * 0.1, camera_transform: Geo.flat(T),
                                 head_yaw_deg: 12.5, head_source: "fusion")))
    }
    rec.message(json(hand))
    rec.stop()
    rec.flush()

    var rng = SplitMix(state: 42)
    var headings: [[String: [Double]]] = []
    for _ in 0..<50 {
        let M = pose(yawLeftDeg: Float.random(in: -180...180, using: &rng), pitchDeg: Float.random(in: -60...20, using: &rng),
                     at: SIMD3(Float.random(in: -3...3, using: &rng), 1.2, Float.random(in: -3...3, using: &rng)))
        headings.append(["T": Geo.flat(M).map(Double.init), "heading": [Geo.headingDeg(M)]])
    }
    var azimuths: [[String: [Double]]] = []
    for _ in 0..<200 {
        let u = SIMD3<Float>(Float.random(in: -4...4, using: &rng), 1.2, Float.random(in: -4...4, using: &rng))
        let tg = SIMD3<Float>(Float.random(in: -4...4, using: &rng), Float.random(in: 0...1.5, using: &rng), Float.random(in: -4...4, using: &rng))
        let h = Double.random(in: -180...180, using: &rng)
        let az = Geo.relativeAzimuthDeg(from: u, headingDeg: h, to: tg)
        let hd = Geo.horizontalDistance(u, tg)
        let l = Geo.listenerRelative(ear: u, headYawDeg: h, target: tg)
        azimuths.append(["user": [u.x, u.y, u.z].map(Double.init), "heading": [h], "target": [tg.x, tg.y, tg.z].map(Double.init),
                         "rel_az": [az], "clock": [Double(Geo.clockPosition(az))], "hdist": [hd], "steps": [Double(Geo.steps(hd))],
                         "listener": [l.x, l.y, l.z].map(Double.init)])
    }
    write("geometry.json", json(["heading": headings, "azimuth": azimuths]))
    print("fixtures written to \(dir.path)")
}

print("\(passed) passed, \(failed) failed")
exit(failed == 0 ? 0 : 1)
