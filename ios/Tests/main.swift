// Unit tests for the parts of the app that build on macOS (run: sh ios/check.sh). With --emit DIR it also writes
// what the app would send, for server/tests/test_ios_contract.py to feed to the real server.
import AVFAudio
import CoreVideo
import Foundation
import ImageIO
import Metal
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

// Control panel: permission cancellation, first-frame identity, interruption and server input.
var capture = CaptureControl()
check(capture.phase == .ready && capture.action == "Start camera", "initial camera action")
let firstStart = capture.begin(supported: true)!
check(capture.begin(supported: true) == nil, "duplicate start is ignored")
capture.stop()
check(!capture.permission(granted: true, ticket: firstStart), "stop invalidates pending permission")
capture.firstFrame(ticket: firstStart)
check(capture.phase == .ready, "old frame cannot revive stopped capture")
let deniedStart = capture.begin(supported: true)!
check(!capture.permission(granted: false, ticket: deniedStart), "permission denial never starts capture")
check(capture.phase == .denied && capture.action == "Open Settings", "permission recovery action")
let retry = capture.begin(supported: true)!
check(capture.permission(granted: true, ticket: retry), "retry after permission grant")
check(capture.phase == .starting && capture.action == "Cancel", "wait for actual first frame")
capture.firstFrame(ticket: firstStart)
check(capture.phase == .starting, "old session frame cannot finish new start")
capture.firstFrame(ticket: retry)
check(capture.phase == .running && capture.action == "Stop camera", "first current frame starts UI")
capture.stop(reason: .interrupted)
check(capture.phase == .interrupted && capture.needsAttention, "interruption exposes recovery")
capture.stop()
check(capture.begin(supported: false) == nil && capture.phase == .unsupported, "report unsupported depth")
for bad in ["", "localhost:8000", "ftp://server", "https://", "https://user:pass@server", "https://server?q=1", "https://server#part"] {
    check(ControlServerAddress.parse(bad) == nil, "reject invalid server: \(bad)")
}
check(ControlServerAddress.parse("  https://demo.example.ts.net/api\n")?.absoluteString == "https://demo.example.ts.net/api", "trim and retain base path")
check(ControlServerAddress.parse("http://127.0.0.1:8000") != nil, "accept local development server")
check(AudioRouteState(spatial: nil).spatialLabel == "Spatial audio unknown", "unknown spatial route")
check(AudioRouteState(spatial: false).spatialLabel == "Spatial audio off", "disabled spatial flag")
check(AudioRouteState(spatial: true).spatialLabel == "Spatial audio available", "enabled spatial flag")

// Spoken control-panel status: useful recovery instructions, meaningful changes only.
var statusReady = AccessibleControlStatus(serverConfigured: true,
    audio: AudioRouteState(name: "AirPods", external: true, spatial: true))
check(statusReady.summary.contains("Camera is off"), "spoken summary includes camera state")
check(statusReady.summary.contains("LiDAR available"), "spoken summary includes LiDAR")
check(statusReady.summary.contains("AirPods") && statusReady.summary.contains("Spatial audio available"), "spoken summary includes actual audio route")
check(statusReady.summary.contains("Start the camera to connect"), "idle connection is not reported as a failure")
check(statusReady.summary.contains("Voice commands: off"), "spoken summary includes voice status")
check(statusReady.announcement(since: statusReady) == nil, "identical status is silent")
var missingServer = statusReady
missingServer.serverConfigured = false
check(missingServer.summary.contains("Connection settings"), "missing server has recovery instructions")
var statusRunning = statusReady
statusRunning.phase = .running
statusRunning.tracking = "normal"
statusRunning.voice = .listening
check(statusRunning.waitingForServer, "running disconnected state enables connection reminder")
check(statusRunning.announcement(since: statusReady)?.contains("Camera running") == true, "announce successful first frame")
check(statusRunning.announcement(since: statusReady)?.contains("Server connecting") == true, "camera running does not imply server connected")
var connected = statusRunning
connected.serverConnected = true
check(!connected.waitingForServer, "connected state cancels connection reminder")
check(connected.announcement(since: statusRunning) == "Server connected.", "announce server recovery")
check(statusRunning.announcement(since: connected)?.contains("Server disconnected. Check Wi-Fi and Tailscale") == true, "announce lost server with action")
check(statusReady.announcement(since: connected) == "Camera stopped.", "intentional stop does not also announce server failure")
var denied = statusReady
denied.phase = .denied
check(denied.announcement(since: statusReady)?.contains("Open iPhone Settings") == true, "camera denial explains recovery")
check(denied.cameraActionHint.contains("Settings"), "denied primary action hint describes Settings")
denied.message = "Allow camera access in Settings."
check(denied.cameraDescription == "Camera access is off. Allow camera access in Settings.", "camera permission instructions are not duplicated")
var interrupted = connected
interrupted.phase = .interrupted
interrupted.message = "Camera interrupted. Start again when ready."
check(interrupted.cameraDescription == interrupted.message, "specific interruption reason is not duplicated")
check(statusReady.cameraActionHint.contains("Two-finger double-tap"), "start hint makes Magic Tap discoverable")
check(connected.cameraActionHint.contains("Stops capture"), "stop hint describes resource cleanup")
var failedCamera = connected
failedCamera.phase = .failed
failedCamera.message = "Camera is being used by another app."
check(failedCamera.announcement(since: connected)?.contains("another app") == true, "camera failure includes specific reason")
var unsupported = statusReady
unsupported.phase = .unsupported
unsupported.lidarAvailable = false
check(unsupported.summary.contains("LiDAR-capable iPhone is required"), "unsupported hardware has explanation")
var permission = statusReady
permission.phase = .permission
check(permission.announcement(since: statusReady) == nil, "system permission prompt owns speech")
var noHeadphones = connected
noHeadphones.audio = AudioRouteState(name: "iPhone", external: false, spatial: false)
check(noHeadphones.announcement(since: connected)?.contains("Headphones disconnected") == true, "announce unplugged headphones")
check(noHeadphones.summary.contains("Connect headphones for directional audio"), "speaker fallback is explicit")
var spatialOff = connected
spatialOff.audio.spatial = false
check(spatialOff.announcement(since: connected) == nil, "OS spatial flag is informational, not an HRTF failure")
var voiceDenied = connected
voiceDenied.voice = .permissionDenied
check(voiceDenied.announcement(since: connected)?.contains("microphone and speech recognition") == true, "voice permission failure is discoverable")
check(voiceDenied.summary.contains("restart the camera"), "voice recovery explains restart")
check(connected.announcement(since: voiceDenied) == "Voice commands are listening again.", "announce voice recovery")
var voiceUnavailable = connected
voiceUnavailable.voice = .unavailable
check(voiceUnavailable.announcement(since: connected)?.contains("unavailable") == true, "voice startup error has speech")
var audioFailed = connected
audioFailed.audioProblem = "Navigation audio could not start. Stop and restart the camera to try again."
check(audioFailed.announcement(since: connected) == audioFailed.audioProblem, "navigation audio startup error has speech")
var limited = connected
limited.tracking = "limited: moving too fast"
check(limited.announcement(since: connected)?.contains("more slowly") == true, "tracking loss has actionable instructions")
var stillLimited = limited
stillLimited.tracking = "limited: too few features"
check(stillLimited.announcement(since: limited) == nil, "changing limited reasons does not chatter")
check(connected.announcement(since: limited) == "Position tracking restored.", "announce restored positioning")
check(stillLimited.summary.contains("better light"), "read status includes latest tracking reason")
var initializing = connected
initializing.tracking = "limited: initializing"
check(connected.announcement(since: initializing) == nil, "normal startup tracking does not generate recovery chatter")
for state in [statusReady, statusRunning, connected, denied, failedCamera, unsupported, voiceDenied, noHeadphones] {
    check(!state.summary.contains("\n"), "spoken status has no visual line breaks")
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
    h.retarget(itemId: "mug", position: SIMD3(3, 1, 0), surface: nil)
    _ = h.tick(now: 0, chest: .zero, ear: SIMD3(0, 0.45, 0), headYawDeg: 0)
    check(near(h.relAzimuthDeg, 90, 0.01), "moved event retargets: \(h.relAzimuthDeg)")
    h.handProximity(itemId: "mug", distanceM: 0.2, t: 0)
    _ = h.tick(now: 0.9, chest: .zero, ear: SIMD3(0, 0.45, 0), headYawDeg: 0)
    check(h.phase != .reach, "stale proximity doesn't count")
    check(h.touched(itemId: "mug", t: 1) == [.silence, .haptic, .playLabel("/v1/audio/a", fallback: "Got it.")], "a labelled item plays its label")
}

// MARK: - Audit regressions: request cancellation, pose validity, map-save lifetime, live target metadata

do {
    let scope = NavigationScope(captureGeneration: 1, mapId: "room-a", revision: 1)
    let sample = NavigationPose(scope: scope, transform: matrix_identity_float4x4, timestamp: 10)
    check(sample.usable(now: 10.1, in: scope), "fresh current-map pose is usable")
    check(!sample.usable(now: 11, in: scope), "stalled camera invalidates directional guidance")
    check(!sample.usable(now: 9, in: scope), "future timestamp is unusable")
    check(!sample.usable(now: .infinity, in: scope), "non-finite clock is unusable")
    check(!sample.usable(now: 10.1, in: nil), "missing coordinate frame is unusable")
    let newMap = NavigationScope(captureGeneration: 1, mapId: "room-b", revision: 2)
    let restarted = NavigationScope(captureGeneration: 2, mapId: "room-a", revision: 1)
    let reset = NavigationScope(captureGeneration: 1, mapId: "room-a", revision: 2)
    for changed in [newMap, restarted, reset] {
        check(!sample.usable(now: 10.1, in: changed), "old pose cannot cross map/capture/reset: \(changed)")
    }
    var finds = FindRequests()
    finds.begin(id: "first", name: "keys", scope: scope)
    check(finds.consume(id: nil, in: scope) == nil && finds.pending?.id == "first", "uncorrelated Find cannot consume current request")
    check(finds.consume(id: "unknown", in: scope) == nil && finds.pending?.id == "first", "unknown Find answer is ignored")
    finds.cancel()
    check(finds.consume(id: "first", in: scope) == nil, "voice Stop cancels a delayed Find answer")
    finds.begin(id: "old", name: "keys", scope: scope)
    finds.begin(id: "new", name: "mug", scope: scope)
    check(finds.consume(id: "old", in: scope) == nil && finds.pending?.name == "mug", "superseded Find cannot replace newer search")
    check(finds.consume(id: "new", in: scope)?.name == "mug", "matching current Find is accepted")
    check(finds.consume(id: "new", in: scope) == nil, "duplicate Find answer cannot restart guidance")
    for changed in [newMap, restarted, reset] {
        finds.begin(id: "old-scope", name: "keys", scope: scope)
        check(finds.consume(id: "old-scope", in: changed) == nil, "old answer cannot cross map/capture/reset: \(changed)")
    }

    var maps = WorldMapLifecycle()
    maps.begin()
    let firstId = maps.mapId
    let discardedSave = maps.prepareSave()
    maps.begin() // resetTracking without a restored map
    check(maps.mapId != firstId, "unsaved capture restart allocates a new map ID")
    check(!maps.accepts(discardedSave), "save from discarded map cannot write or publish")
    let savedId = maps.mapId
    let beforeRestart = maps.prepareSave()
    maps.begin(restoredMapId: savedId)
    check(maps.mapId == savedId, "restoration retains the saved map identity")
    check(!maps.accepts(beforeRestart), "restoring same ID still invalidates previous capture's async save")
    let olderSave = maps.prepareSave()
    let newestSave = maps.prepareSave()
    check(!maps.accepts(olderSave) && maps.accepts(newestSave), "older overlapping save cannot overwrite the latest snapshot")
    maps.begin()
    check(!maps.accepts(newestSave), "manual or timeout fresh-map reset invalidates all pending saves")
    let currentSave = maps.prepareSave()
    check(maps.accepts(currentSave), "valid save after reset is accepted")

    var moving = Guidance()
    moving.start(GuidanceTarget(itemId: "keys", name: "keys", position: SIMD3(0, 1, -2), surface: "table", labelText: nil, labelAudioURL: nil), now: 0)
    moving.retarget(itemId: "keys", position: SIMD3(0, 1, -0.3), surface: "shelf")
    let reached = moving.tick(now: 2, chest: .zero, ear: .zero, headYawDeg: 0)
    check(reached.contains(.say("Within reach, on the shelf.")), "moved item speaks updated surface")
    moving.retarget(itemId: "keys", position: SIMD3(0, 1, -0.3), surface: "shelf")
    check(!moving.tick(now: 3, chest: .zero, ear: .zero, headYawDeg: 0).contains(.say("Within reach, on the shelf.")), "duplicate sighting does not repeat within-reach speech")
    moving.retarget(itemId: "keys", position: SIMD3(0, 1, -0.3), surface: nil)
    check(moving.tick(now: 4, chest: .zero, ear: .zero, headYawDeg: 0).contains(.say("Within reach.")), "unknown surface clears previous spoken surface")
    moving.handProximity(itemId: "keys", distanceM: 0.1, t: 4)
    check(moving.tick(now: 4.1, chest: .zero, ear: .zero, headYawDeg: 0).contains(.steadyTone(true)), "proximity starts steady tone before movement")
    moving.retarget(itemId: "keys", position: SIMD3(0, 1, -2), surface: "table")
    check(moving.tick(now: 4.2, chest: .zero, ear: .zero, headYawDeg: 0).contains(.steadyTone(false)), "moving target drops old proximity and stops steady tone")
    moving.retarget(itemId: "other", position: .zero, surface: nil)
    check(moving.target?.surface == "table", "other item's metadata does not overwrite target")

    var labelled = Guidance()
    let unlabelled = GuidanceTarget(itemId: "keys", name: "keys", position: SIMD3(0, 1, -2), surface: "table", labelText: nil, labelAudioURL: nil)
    labelled.start(unlabelled, now: 0)
    labelled.updateLabel(itemId: "keys", name: "front-door keys", text: "Your front-door keys.", audioURL: nil)
    check(labelled.touched(itemId: "keys", t: 1).contains(.say("Your front-door keys.")), "label arriving during guidance is spoken at touch")
    labelled.start(unlabelled, now: 2)
    labelled.updateLabel(itemId: "keys", name: nil, text: "New label", audioURL: "/v1/audio/old")
    labelled.updateLabel(itemId: "keys", name: nil, text: "Replacement label", audioURL: "/v1/audio/new")
    check(labelled.touched(itemId: "keys", t: 3).contains(.playLabel("/v1/audio/new", fallback: "Replacement label")), "replacement label uses latest audio and text fallback")
    labelled.start(unlabelled, now: 4)
    labelled.updateLabel(itemId: "other", name: "other", text: "Wrong label", audioURL: "/wrong")
    check(labelled.touched(itemId: "keys", t: 5).contains(.say("Got it.")), "label for another item is ignored by active guidance")
    labelled.start(unlabelled, now: 6)
    labelled.updateLabel(itemId: "keys", name: nil, text: "Text only", audioURL: "/old")
    labelled.updateLabel(itemId: "keys", name: nil, text: "Text only", audioURL: nil)
    check(labelled.touched(itemId: "keys", t: 7).contains(.say("Text only")), "text-only update clears obsolete audio URL")
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

    // Not found yet: say why, and that Marco keeps watching (Lookout).
    func answer(found: Bool, name: String, state: String? = nil, reason: String? = nil, surface: String? = nil) -> FindAnswer {
        FindAnswer(query_id: "q", found: found, item_id: "i", name: name, position: found ? [0, 0, -1] : nil, surface: surface,
                   seen_ago_s: nil, confidence: nil, state: state, reason: reason, last_position: nil)
    }
    let notYet: [(FindAnswer, String)] = [
        (answer(found: false, name: "keys", reason: "never_seen"),
         "I haven't seen your keys yet. Turn slowly and I'll tell you when I spot them."),
        (answer(found: false, name: "mug", reason: "not_where_last_seen", surface: "shelf"),
         "Your mug isn't where I last saw it, on the shelf. Turn slowly and I'll tell you when I spot it."),
        (answer(found: false, name: "keys", reason: "not_where_last_seen"),
         "Your keys aren't where I last saw them. Turn slowly and I'll tell you when I spot them."),
        (answer(found: true, name: "wallet", state: "stale"),
         "I haven't seen your wallet since I got my bearings again. Turn slowly and I'll tell you when I spot it."),
        (answer(found: true, name: "glasses", state: "picked_up"),
         "I last saw your glasses when you picked them up. Turn slowly and I'll tell you when I spot them."),
        (answer(found: false, name: "cat", reason: "not_registered"), "I don't know your cat yet. Send me a photo of it."),
        (answer(found: false, name: "keys", reason: "not_registered"), "I don't know your keys yet. Send me a photo of them.")]
    for (a, want) in notYet { check(Lines.notFound(a, asked: "thing") == want, "notFound: \(Lines.notFound(a, asked: "thing"))") }
    check(Lines.spotted(name: "keys", relAzimuthDeg: 60, distanceM: 3.0, surface: "table")
          == "Polo! I see your keys. At two o'clock, four steps, on the table.", "spotted")
    check(Lines.stillNotSeen("keys") == "I still haven't spotted your keys. Ask me again any time.", "the watch ran out")
    check(Lines.isPlural("keys") && Lines.isPlural("Glasses") && !Lines.isPlural("glasses case") && !Lines.isPlural("cumin")
          && !Lines.isPlural("bus") && !Lines.isPlural("glass"), "them or it")
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

// MARK: - Lookout: a find that hasn't been seen yet keeps watching

do {
    let scope = NavigationScope(captureGeneration: 1, mapId: "m", revision: 0)
    func ev(_ kind: String, _ id: String = "keys-1", at p: [Float]? = [1, 0.8, -2]) -> WorldEventMsg {
        WorldEventMsg(kind: kind, item_id: id, name: "keys", position: p, from_position: nil, surface: "table", t_wall: nil)
    }
    var w = Lookout()
    check(!w.watching && w.expired(now: 1e9) == nil, "idle")
    w.watch(itemId: "keys-1", name: "keys", scope: scope, now: 100)
    w.sighted(ev("seen", "wallet-1"))
    w.sighted(ev("missing"))
    w.sighted(ev("seen", at: nil))
    check(w.watching && w.spot == nil, "another item, a missing event or no position: still watching")
    check(w.expired(now: 100 + Lookout.windowS - 1) == nil, "not yet expired")
    w.sighted(ev("seen"))
    check(w.spot == Lookout.Spot(itemId: "keys-1", name: "keys", position: SIMD3(1, 0.8, -2), surface: "table"), "seen: spot kept")
    check(w.expired(now: 1e9) == nil, "a spot waiting for a pose never expires")
    check(w.take()?.itemId == "keys-1" && !w.watching && w.take() == nil, "taken once, then the watch is over")
    w.watch(itemId: "keys-1", name: "keys", scope: scope, now: 0)
    w.sighted(ev("put_down"))
    check(w.spot != nil, "put_down counts")
    w.watch(itemId: "keys-1", name: "keys", scope: scope, now: 0)
    check(w.spot == nil, "a new watch starts empty")
    check(w.expired(now: Lookout.windowS) == "keys" && !w.watching && w.expired(now: 1e9) == nil, "expires once")
    w.watch(itemId: "keys-1", name: "keys", scope: scope, now: 0)
    w.cancel()
    w.sighted(ev("seen"))
    check(!w.watching && w.spot == nil, "cancelled: a later sighting does nothing")
}

// MARK: - Sound scene: where each sound comes from, and whether it reaches two ears

do {
    let ear = SIMD3<Float>(0, 1.6, 0)
    check(SoundAnchor.ahead.listenerRelative(ear: ear, headYawDeg: 75) == SIMD3(0, 0, -1), "ahead is fixed to the head")
    let jar = SoundAnchor.world(SIMD3(1, 0.9, -1))
    check(jar.listenerRelative(ear: ear, headYawDeg: 30) == Geo.listenerRelative(ear: ear, headYawDeg: 30, target: SIMD3(1, 0.9, -1)),
          "a room point uses the server's geometry")
    let facing = jar.listenerRelative(ear: ear, headYawDeg: 0), turned = jar.listenerRelative(ear: ear, headYawDeg: 90)
    check(facing.x > 0 && facing.z < 0 && turned.x < 0 && turned.z < 0,
          "front-right; after a 90 degree right turn, front-left: \(facing) \(turned)")
    check(abs(turned.y - (0.9 - 1.6)) < 1e-6, "height below the ear is kept")
    check(SoundAnchor.at(nil) == .ahead && SoundAnchor.at([1, 2]) == .ahead && SoundAnchor.at([1, 2, 3]) == .world(SIMD3(1, 2, 3)),
          "a message position, or ahead")

    let airpods = OutputRoute(name: "AirPods Pro", headphones: true, channels: 2)
    let speaker = OutputRoute(name: "Speaker", headphones: false, channels: 2)
    let mono = OutputRoute(name: "AirPods Pro", headphones: true, channels: 1)
    check(airpods.binaural && !speaker.binaural && !mono.binaural, "two ears: headphones with 2 channels")
    var w = RouteWatch()
    w.observe(airpods, now: 0)
    check(w.settle(now: 1) == nil, "not settled yet")
    check(w.settle(now: 1.5) == RouteWatch.Change(was: nil, binaural: true) && w.binaural == true, "first state")
    w.observe(speaker, now: 10)
    w.observe(airpods, now: 10.5)
    check(w.settle(now: 20) == nil && w.binaural == true, "a flap shorter than settleS is ignored")
    w.observe(speaker, now: 30)
    w.observe(speaker, now: 31)
    check(w.settle(now: 31.4) == nil, "the clock runs from the first sighting of the change")
    check(w.settle(now: 31.5) == RouteWatch.Change(was: true, binaural: false), "lost")
    check(w.settle(now: 40) == nil, "reported once")
    w.observe(airpods, now: 50)
    check(w.settle(now: 52) == RouteWatch.Change(was: false, binaural: true), "back")
    check(!Lines.headphonesLost.lowercased().contains("marco") && !Lines.headphonesBack.lowercased().contains("marco"),
          "no wake word in the new lines")
}

// MARK: - What the wearer hears, for the dashboard (§3.2 sound, sound_field)

do {
    let ahead = HeardDirection(SoundAnchor.aheadPoint), right = HeardDirection(SIMD3(2, 0, 0))
    let behind = HeardDirection(SIMD3(0, 0, 1.5)), low = HeardDirection(SIMD3(0, -0.8, -0.8))
    check(ahead.azDeg == 0 && ahead.elDeg == 0 && ahead.distanceM == 1, "ahead: \(ahead)")
    check(right.azDeg == 90 && right.distanceM == 2 && abs(behind.azDeg) == 180, "right and behind: \(right) \(behind)")
    check(low.elDeg == -45 && low.distanceM == 1.13, "below the ear: \(low)")
    check(HeardDirection(SIMD3(-1, 0, -1)).azDeg == -45, "front-left is negative")

    var r = SoundReporter(sessionId: "s")
    let beep = r.cue("beep", at: SIMD3(1, 0, 1), anchor: "item", t: 10, muffled: true)
    check(beep.source == "beacon" && beep.az_deg == 135 && beep.muffled == true && beep.text == nil, "beep: \(beep)")
    let say = r.cue("say", at: SIMD3(0, 0, -1), anchor: "ahead", t: 10, text: "Polo!", duration: 1.04)
    check(say.source == "voice" && say.duration_s == 1 && say.text == "Polo!", "say: \(say)")
    if let json = try? JSONEncoder().encode(beep), let o = try? JSONSerialization.jsonObject(with: json) as? [String: Any] {
        check(o["type"] as? String == "sound" && o["cue"] as? String == "beep" && o["az_deg"] as? Double == 135
              && o["text"] == nil && o["session_id"] as? String == "s", "sound encodes the contract's keys: \(o)")
    } else { check(false, "sound encodes") }

    // The field: 10/s while anything is audible, once more when it goes quiet, then nothing.
    var f = SoundReporter(sessionId: "s")
    let v = (SoundAnchor.aheadPoint, anchor: "ahead")
    check(f.field(t: 0, headYawDeg: 0, beacon: nil, voice: v) == nil, "quiet: no field")
    let b = (SIMD3<Float>(0, -0.8, 1.6), muffled: true)
    var sent = 0
    for i in 0..<60 where f.field(t: Double(i) / 60, headYawDeg: 12.34, beacon: b, voice: v) != nil { sent += 1 }
    check((9...11).contains(sent), "10/s while guiding: \(sent)")
    let one = f.field(t: 1.2, headYawDeg: 12.34, beacon: b, voice: v)
    check(one?.beacon?.muffled == true && one?.voice == nil && one?.head_yaw_deg == 12.3, "beacon only: \(String(describing: one))")
    let quiet = f.field(t: 1.21, headYawDeg: 0, beacon: nil, voice: v)
    check(quiet != nil && quiet?.beacon == nil && quiet?.voice == nil, "going quiet goes out at once")
    check(f.field(t: 1.5, headYawDeg: 0, beacon: nil, voice: v) == nil, "then nothing")
    _ = f.cue("say", at: SoundAnchor.aheadPoint, anchor: "ahead", t: 2, text: "Got it.", duration: 1)
    check(f.field(t: 2.2, headYawDeg: 0, beacon: nil, voice: v)?.voice?.anchor == "ahead", "the voice while it speaks")
    check(f.field(t: 3.05, headYawDeg: 0, beacon: nil, voice: v)?.voice == nil, "and the last field after it ends")
    _ = f.cue("say", at: SoundAnchor.aheadPoint, anchor: "ahead", t: 4, text: "Got it.", duration: 5)
    _ = f.cue("silence", at: SoundAnchor.aheadPoint, anchor: "item", t: 4.5)
    check(f.field(t: 4.6, headYawDeg: 0, beacon: nil, voice: v)?.voice == nil, "silence ends the voice")
    check(abs(SoundReporter.speechSeconds("Polo! Behind you, two steps, on the table.") - (8 / 2.6 + 0.3)) < 1e-9, "speech length")
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
    if case .command(let c)? = decode(#"{"type":"command","command_id":"c-1","session_id":"s1","action":"find","item_id":"fake-keys","name":"keys","position":[1,0.75,-2],"surface":"table","expires_wall":"2026-10-17T22:00:10.000Z"}"#) {
        check(c.action == "find" && c.item_id == "fake-keys" && c.position == [1, 0.75, -2], "dashboard command decodes")
    } else { check(false, "dashboard command decodes") }
}

// MARK: - Dashboard Find/Stop (docs/INTERFACES.md §4 command, §3.2 command_ack)

do {
    func cmd(_ id: String, _ action: String, session: String = "s1", expires: String? = "2026-10-17T22:00:10.000Z",
             item: String? = "k", position: [Float]? = [1, 0, -2]) -> CommandMsg {
        CommandMsg(command_id: id, session_id: session, action: action, item_id: item, name: "keys", position: position,
                   surface: "table", expires_wall: expires)
    }
    let t = CommandGate.wall("2026-10-17T22:00:05.000Z")!
    var g = CommandGate()
    check(g.check(cmd("a", "find"), sessionId: "s1", now: t) == .find(itemId: "k", name: "keys", position: SIMD3(1, 0, -2), surface: "table"),
          "find hands back the exact item and its position")
    check(g.check(cmd("a", "find"), sessionId: "s1", now: t) == .duplicate, "a repeated command is dropped")
    check(g.check(cmd("b", "stop", item: nil, position: nil), sessionId: "s1", now: t) == .stop, "stop")
    if case .reject(let r) = g.check(cmd("c", "find", session: "s0"), sessionId: "s1", now: t) {
        check(r.hasPrefix("session_mismatch"), "another session's command is refused")
    } else { check(false, "another session's command is refused") }
    let late = CommandGate.wall("2026-10-17T22:00:13.000Z")!
    if case .reject(let r) = g.check(cmd("d", "find"), sessionId: "s1", now: late) {
        check(r.hasPrefix("expired"), "a late command is refused, never started")
    } else { check(false, "a late command is refused") }
    check(g.check(cmd("e", "find"), sessionId: "s1", now: CommandGate.wall("2026-10-17T22:00:11.500Z")!) != .reject("expired: the command arrived too late"),
          "two seconds of clock slack")
    if case .reject(let r) = g.check(cmd("f", "find", position: nil), sessionId: "s1", now: t) {
        check(r.hasPrefix("invalid"), "find without a position is refused")
    } else { check(false, "find without a position is refused") }
    let ack = try! JSONSerialization.jsonObject(with: JSONEncoder().encode(CommandAckMsg(session_id: "s1", command_id: "a", status: "applied", reason: nil))) as! [String: Any]
    check(ack["type"] as? String == "command_ack" && ack["command_id"] as? String == "a" && ack["status"] as? String == "applied",
          "command_ack wire keys")
}

// MARK: - Speech output: private requests, caching, fallback and late-reply cancellation

do {
    let base = URL(string: "https://marco.test")!
    let request = SpeechOutputClient.request(base: base, text: "Polo! On your left.")
    check(request.url?.absoluteString == "https://marco.test/v1/speech" && request.httpMethod == "POST", "speech uses the private server route")
    check(request.value(forHTTPHeaderField: "xi-api-key") == nil, "no provider key leaves the phone")
    let body = try! JSONSerialization.jsonObject(with: request.httpBody!) as! [String: String]
    check(body == ["text": "Polo! On your left."], "speech request sends only the already-decided line")
    let response = HTTPURLResponse(url: base, statusCode: 200, httpVersion: nil, headerFields: ["Content-Type": "audio/wav"])!
    // An actual PCM WAV: one signed 16-bit mono sample at 24 kHz.
    let wav = Data([
        0x52, 0x49, 0x46, 0x46, 38, 0, 0, 0, 0x57, 0x41, 0x56, 0x45,
        0x66, 0x6d, 0x74, 0x20, 16, 0, 0, 0, 1, 0, 1, 0,
        0xc0, 0x5d, 0, 0, 0x80, 0xbb, 0, 0, 2, 0, 16, 0,
        0x64, 0x61, 0x74, 0x61, 2, 0, 0, 0, 1, 0,
    ])
    check(SpeechOutputClient.validAudio(wav, response: response), "WAV response accepted")
    check(!SpeechOutputClient.validAudio(Data("not audio".utf8), response: response), "invalid audio refused")
    check(!SpeechOutputClient.validAudio(Data(repeating: 0, count: 1_000_001), response: response), "oversized audio refused")
    var signatureOnly = Data(repeating: 0, count: 46)
    signatureOnly.replaceSubrange(0..<4, with: Data("RIFF".utf8))
    signatureOnly.replaceSubrange(8..<12, with: Data("WAVE".utf8))
    check(!SpeechOutputClient.validAudio(signatureOnly, response: response), "RIFF signature alone cannot poison the speech cache")
    for (offset, byte, name) in [(4, 0xff, "RIFF length"), (22, 2, "stereo"), (24, 0, "sample rate"),
                                 (28, 0, "byte rate"), (32, 1, "block alignment"), (34, 8, "sample width"),
                                 (36, 0, "data chunk"), (40, 4, "truncated sample data")] {
        var invalid = wav
        invalid[offset] = UInt8(byte)
        check(!SpeechOutputClient.validAudio(invalid, response: response), "invalid speech WAV rejected: \(name)")
    }
    do {
        var requests = 0
        var time = 0.0
        var finish: ((Data?, URLResponse?, Error?) -> Void)?
        let recovering = SpeechOutputClient(clock: { time }, load: { _, done in
            requests += 1; finish = done; return {}
        })
        recovering.configure(base: base)
        var result: Data?
        recovering.audio(for: "same phrase") { result = $0 }
        finish?(signatureOnly, response, nil)
        RunLoop.current.run(until: Date().addingTimeInterval(0.025))
        check(result == nil, "malformed WAV selects fallback before being cached")
        time = 16
        recovering.audio(for: "same phrase") { result = $0 }
        check(requests == 2, "malformed audio does not prevent a later provider retry")
        finish?(wav, response, nil)
        RunLoop.current.run(until: Date().addingTimeInterval(0.025))
        check(result == wav, "same phrase recovers with valid provider audio")
    }
    var loads = 0, cancels = 0
    var completions: [(Data?, URLResponse?, Error?) -> Void] = []
    var time = 100.0
    let client = SpeechOutputClient(maxEntries: 1, clock: { time }, load: { _, done in
        loads += 1
        completions.append(done)
        return { cancels += 1 }
    })
    func drainSpeechCallbacks() { RunLoop.current.run(until: Date().addingTimeInterval(0.025)) }
    var results: [Data?] = []
    client.audio(for: "No server") { results.append($0) }
    check(results.count == 1 && results[0] == nil && loads == 0, "unconfigured speech falls back without a request")
    results.removeAll()
    client.configure(base: base)
    client.audio(for: "old") { results.append($0) }
    client.audio(for: "new") { results.append($0) }
    completions[0](wav, response, nil)
    drainSpeechCallbacks()
    check(results.isEmpty && cancels == 1, "new speech cancels and ignores the older response")
    completions[1](wav, response, nil)
    drainSpeechCallbacks()
    check(results.count == 1 && results[0] == wav, "current response completes")
    client.audio(for: "new") { results.append($0) }
    check(loads == 2 && results.count == 2, "a repeated phrase uses cached audio")
    client.audio(for: "stopped") { results.append($0) }
    client.cancel()
    completions[2](wav, response, nil)
    drainSpeechCallbacks()
    check(results.count == 2, "Stop suppresses late audio and fallback callbacks")
    client.audio(for: "failure") { results.append($0) }
    completions[3](nil, nil, URLError(.timedOut))
    drainSpeechCallbacks()
    check(results.count == 3 && results.last! == nil, "network failure chooses Apple speech")
    client.audio(for: "another line") { results.append($0) }
    check(loads == 4 && results.last! == nil, "provider cooldown avoids repeated timeout waits")
    client.audio(for: "new") { results.append($0) }
    check(results.last! == wav, "cached speech is available during an outage")
    time += 16
    client.audio(for: "recovered") { results.append($0) }
    completions[4](wav, response, nil)
    drainSpeechCallbacks()
    check(results.last! == wav && loads == 5, "speech retries after the short cooldown")
    client.audio(for: "new") { results.append($0) }
    check(loads == 6, "bounded phrase cache evicts the oldest entry")
    client.configure(base: URL(string: "https://other.test"))
    completions[5](wav, response, nil)
    let before = results.count
    drainSpeechCallbacks()
    check(results.count == before, "changing servers invalidates the previous response")
    client.audio(for: "recovered") { results.append($0) }
    check(loads == 7, "a new server does not reuse the old server's voice cache")
    client.cancel()
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

// MARK: - Resource policy (Core/ResourcePolicy.swift) and the lighter hand path

do {
    // Frames and poses never change; hands run at full rate only near a hand, and slow down with heat.
    let cool = ResourcePolicy(heat: .nominal), hot = ResourcePolicy(heat: .serious), burning = ResourcePolicy(heat: .critical)
    check(cool.handHz(sinceLastHand: 0.5) == 15 && cool.handHz(sinceLastHand: 5) == 5, "nominal: 15/s near a hand, 5/s otherwise")
    check(hot.handHz(sinceLastHand: 0) == 10 && hot.handHz(sinceLastHand: 9) == 2, "serious: 10/2")
    check(burning.handHz(sinceLastHand: 0) == 5 && burning.handHz(sinceLastHand: 9) == 1, "critical: 5/1")
    check(ResourcePolicy.Heat.allCases.map { ResourcePolicy(heat: $0).lidarViewFPS } == [60, 60, 30, 15], "LiDAR view fps by heat")
    check(!cool.lowCameraRate && !ResourcePolicy(heat: .fair).lowCameraRate && hot.lowCameraRate && burning.lowCameraRate,
          "camera stays at 60 fps until the phone is seriously hot")
    check(ResourcePolicy.Heat(ProcessInfo.ThermalState.serious) == .serious && ResourcePolicy.Heat.fair < .critical, "heat mapping")
    check(cool.summary == "heat nominal · camera 60 fps · hands 15/s near a hand, 5/s otherwise", cool.summary)
    check(hot.summary == "heat serious · camera 30 fps · hands 10/s near a hand, 2/s otherwise", hot.summary)

    // The gate: 5/s while no hand is around, 15/s for 1.5 s after one was seen (60 fps frames).
    var gate = HandRateGate()
    var fired = 0
    for i in 0..<60 where gate.ready(Double(i) / 60, policy: cool) { fired += 1 }
    check(fired == 5, "no hand: 5 detections in a second, got \(fired)")
    gate.sawHand(at: 1.0)
    fired = 0
    for i in 60..<120 where gate.ready(Double(i) / 60, policy: cool) { fired += 1 }
    check(fired == 15, "hand seen: 15 detections in the next second, got \(fired)")
    fired = 0
    for i in 180..<240 where gate.ready(Double(i) / 60, policy: cool) { fired += 1 }   // 2-3 s after: hand gone
    check(fired == 5, "hand gone for 2 s: back to 5/s, got \(fired)")

    // Hand patches read straight from padded buffers are byte-identical to the contract-tested array version.
    let (d, c) = syntheticMaps()
    let dpb = padded(d, 256, 192, format: kCVPixelFormatType_DepthFloat32)
    let cpb = padded(c, 256, 192, format: kCVPixelFormatType_OneComponent8)
    var js = HandJoints.names.enumerated().map { j, n in Joint(name: n, x: 0.2 + 0.03 * Double(j), y: 0.15 + 0.035 * Double(j), conf: 0.9) }
    js[0] = Joint(name: "wrist", x: 0.001, y: 0.999, conf: 0.8)       // top-left corner: padded patch
    js[3] = Joint(name: "thumbIP", x: 0, y: 0, conf: 0)               // missing joint, as the phone sends it
    js[20] = Joint(name: "littleTip", x: 0.9999, y: 0.0001, conf: 0.7) // bottom-right corner
    let ref = Wire.patches(depth: d, conf: c, width: 256, height: 192, joints: js)
    if let fast = Wire.patches(depth: dpb, conf: cpb, joints: js) {
        let same = fast.depth.count == ref.depth.count && zip(fast.depth, ref.depth).allSatisfy { $0.bitPattern == $1.bitPattern }
        check(same && fast.conf == ref.conf, "buffer patches match the array patches byte for byte")
        let a = HandMsg.make(sessionId: "s", mapId: "m", t: 1, transform: matrix_identity_float4x4, joints: js, chirality: "right",
                             depth: d, conf: c, width: 256, height: 192)
        let b = HandMsg.make(sessionId: "s", mapId: "m", t: 1, transform: matrix_identity_float4x4, joints: js, chirality: "right",
                             patches: fast)
        check(a == b, "the hand message is the same either way")
    } else {
        check(false, "buffer patches returned nil")
    }
    check(Wire.patches(depth: cpb, conf: cpb, joints: js) == nil, "wrong depth format: nil")
}

// MARK: - LiDAR view (Core/DepthVision.swift)

do {
    // Colour: near warm, far cool, always a valid colour.
    let warm = DepthPalette.color(depthM: 0.2), cool = DepthPalette.color(depthM: 4.2), mid = DepthPalette.color(depthM: 2.0)
    check(warm.x > warm.z && warm.x > 0.4, "near is warm: \(warm)")
    check(cool.z > cool.x, "far is cool: \(cool)")
    check([warm, cool, mid].allSatisfy { simd_reduce_min($0) >= 0 && simd_reduce_max($0) <= 1 }, "colours in 0...1")
    check(DepthPalette.normalized(-1) == 0 && DepthPalette.normalized(99) == 1 && DepthPalette.normalized(.nan) == 1, "normalized clamps")

    // Depth under a point: median of confident pixels; a flying pixel and low confidence don't count.
    var d = [Float](repeating: 2.0, count: 16 * 12), c = [UInt8](repeating: 2, count: 16 * 12)
    d[6 * 16 + 8] = 0.3                                     // one flying pixel right under the probe
    d[5 * 16 + 8] = .nan
    for i in 0..<16 { c[7 * 16 + i] = 0; d[7 * 16 + i] = 9 }  // a low-confidence row
    check(DepthProbe.median(depth: d, confidence: c, width: 16, height: 12, u: 8, v: 6) == 2.0, "probe ignores outliers")
    check(DepthProbe.median(depth: d, confidence: c, width: 16, height: 12, u: 99, v: 6) == nil, "probe outside the map")
    let allLow = [UInt8](repeating: 0, count: 16 * 12)
    check(DepthProbe.median(depth: d, confidence: allLow, width: 16, height: 12, u: 8, v: 6) == nil, "no confident pixels: nil")
    // Straight from padded CVPixelBuffers, as ARKit hands them over.
    var ramp = [Float](repeating: 0, count: 256 * 192)
    for v in 0..<192 { for u in 0..<256 { ramp[v * 256 + u] = 0.5 + Float(u) / 100 } }
    let dpb = padded(ramp, 256, 192, format: kCVPixelFormatType_DepthFloat32)
    let cpb = padded([UInt8](repeating: 2, count: 256 * 192), 256, 192, format: kCVPixelFormatType_OneComponent8)
    let probed = DepthProbe.median(depth: dpb, confidence: cpb, at: CGPoint(x: 0.5, y: 0.5)) ?? -1
    check(abs(probed - (0.5 + 128.0 / 100)) < 1e-4, "probe from a padded buffer: \(probed)")

    // Stats.
    let st = DepthStats.of(depth: [1, 2, 3, .nan, 9, 0], confidence: [2, 2, 1, 2, 2, 2], step: 1)
    check(near(st.validFraction, 0.5) && near(st.highFraction, 2.0 / 6) && st.medianM == 2, "depth stats: \(st)")

    // Pinhole round trip, in the server's conventions: the principal point at 2 m is 2 m down the optical axis.
    let K = simd_float3x3(columns: (SIMD3(1450, 0, 0), SIMD3(0, 1450, 0), SIMD3(960, 720, 1)))
    let size = CGSize(width: 1920, height: 1440)
    let T = pose(yawLeftDeg: 35, pitchDeg: -25, at: SIMD3(0.4, 1.3, -0.2))
    let center = CameraMath.unproject(CGPoint(x: 960.0 / 1920, y: 720.0 / 1440), depthM: 2, intrinsics: K, imageSize: size, cameraToWorld: T)
    let axis = T * SIMD4<Float>(0, 0, -2, 1)
    check(simd_distance(center, SIMD3(axis.x, axis.y, axis.z)) < 1e-4, "principal point unprojects along -z")
    let p0 = CGPoint(x: 0.21, y: 0.77)
    let w = CameraMath.unproject(p0, depthM: 1.7, intrinsics: K, imageSize: size, cameraToWorld: T)
    if let back = CameraMath.project(w, intrinsics: K, imageSize: size, cameraToWorld: T) {
        check(abs(back.point.x - p0.x) < 1e-4 && abs(back.point.y - p0.y) < 1e-4 && abs(back.depthM - 1.7) < 1e-4, "project inverts unproject")
    } else { check(false, "project returned nil for a point in front") }
    let behind = T * SIMD4<Float>(0, 0, 2, 1)
    check(CameraMath.project(SIMD3(behind.x, behind.y, behind.z), intrinsics: K, imageSize: size, cameraToWorld: T) == nil, "behind: nil")

    // Portrait display transform (ARKit's for a 4:3 sensor image on a 3:4 view): the sensor's top-left corner shows
    // at the view's top-right, as in the server's upright rotation.
    let portrait = CGAffineTransform(a: 0, b: 1, c: -1, d: 0, tx: 1, ty: 0)
    let view = CGSize(width: 390, height: 520)
    let tl = ViewMapping.viewPoint(fromImage: .zero, viewSize: view, displayTransform: portrait)
    check(abs(tl.x - 390) < 1e-6 && abs(tl.y) < 1e-6, "sensor top-left at view top-right: \(tl)")
    let img = ViewMapping.imagePoint(fromView: CGPoint(x: 100, y: 300), viewSize: view, displayTransform: portrait)
    let again = ViewMapping.viewPoint(fromImage: img, viewSize: view, displayTransform: portrait)
    check(abs(again.x - 100) < 1e-6 && abs(again.y - 300) < 1e-6, "view to image and back")

    // Remembered items: in front and on screen are labelled (target first), behind and stale are not.
    let I = matrix_identity_float4x4                         // camera at the origin looking down -z
    let marks = [ItemMark(id: "k", name: "keys", position: SIMD3(0, 0, -2), surface: "table", state: "present"),
                 ItemMark(id: "m", name: "mug", position: SIMD3(0.1, 0, -1), surface: nil, state: nil),
                 ItemMark(id: "w", name: "wallet", position: SIMD3(0, 0, 2), surface: nil, state: nil),
                 ItemMark(id: "s", name: "bottle", position: SIMD3(0, 0, -1.5), surface: nil, state: "stale")]
    let r = ItemOverlay.place(marks, cameraToWorld: I, intrinsics: K, imageSize: size, viewSize: view,
                              displayTransform: portrait, targetId: "k")
    check(r.shown.map(\.id) == ["k", "m"] && r.outOfView == 1, "placed: \(r.shown.map(\.id)), out \(r.outOfView)")
    check(r.shown.first?.text == "keys · 2.0 m · table" && r.shown.first?.isTarget == true, "label: \(r.shown.first?.text ?? "")")
    let said = ItemOverlay.spoken(centerM: 1.42, items: r.shown, outOfView: r.outOfView, viewWidth: view.width)
    check(said.hasPrefix("Straight ahead, 1.4 meters.") && said.contains("Keys, 2.0 meters") && said.hasSuffix("1 more item out of view."), said)

    // The point cloud grows only when the camera moves or turns.
    var gate = PointAccumulationGate()
    check(gate.shouldAdd(I) && !gate.shouldAdd(I), "first frame adds, the same pose doesn't")
    var moved = I
    moved.columns.3 = SIMD4(0.03, 0, 0, 1)
    check(gate.shouldAdd(moved), "3 cm move adds")
    check(gate.shouldAdd(pose(yawLeftDeg: 3, at: SIMD3(0.03, 0, 0))), "3 deg turn adds")

    // The Swift mirrors of the shader structs match Metal's layout byte for byte.
    typealias QU = LiDARQuadUniforms
    typealias UU = LiDARUnprojectUniforms
    check(MemoryLayout<QU>.offset(of: \.viewToImageT) == 16 && MemoryLayout<QU>.offset(of: \.overlay) == 24
          && MemoryLayout<QU>.offset(of: \.cameraBrightness) == 40 && MemoryLayout<QU>.stride == 48, "quad uniforms layout")
    check(MemoryLayout<UU>.offset(of: \.intrinsics) == 64 && MemoryLayout<UU>.offset(of: \.imageSize) == 80
          && MemoryLayout<UU>.offset(of: \.gridW) == 88 && MemoryLayout<UU>.offset(of: \.capacity) == 100
          && MemoryLayout<UU>.offset(of: \.minConfidence) == 112 && MemoryLayout<UU>.stride == 128, "unproject uniforms layout")
    check(MemoryLayout<LiDARParticle>.stride == 32, "particle is 32 bytes")
}

// MARK: - LiDAR shaders on this Mac's GPU (the phone compiles the same source at runtime)

if let dev = MTLCreateSystemDefaultDevice(), let queue = dev.makeCommandQueue() {
    do {
        let lib = try dev.makeLibrary(source: LiDARShaderSource.source, options: nil)
        let missing = LiDARShaderSource.functions.filter { lib.makeFunction(name: $0) == nil }
        check(missing.isEmpty, "shader functions missing: \(missing)")

        func texture<T>(_ fmt: MTLPixelFormat, _ w: Int, _ h: Int, _ values: [T]) -> MTLTexture {
            let d = MTLTextureDescriptor.texture2DDescriptor(pixelFormat: fmt, width: w, height: h, mipmapped: false)
            d.storageMode = .shared
            d.usage = [.shaderRead]
            let t = dev.makeTexture(descriptor: d)!
            values.withUnsafeBytes { t.replace(region: MTLRegionMake2D(0, 0, w, h), mipmapLevel: 0, withBytes: $0.baseAddress!,
                                                bytesPerRow: $0.count / h) }
            return t
        }
        // A grey camera image, a depth ramp (1 m + u/256 + v/1000) and confidence 0 on the left eighth of the map.
        let yTex = texture(.r8Unorm, 16, 12, [UInt8](repeating: 128, count: 16 * 12))
        let cTex = texture(.rg8Unorm, 8, 6, [UInt8](repeating: 128, count: 8 * 6 * 2))
        var ramp = [Float](repeating: 0, count: 256 * 192), conf = [UInt8](repeating: 2, count: 256 * 192)
        for v in 0..<192 { for u in 0..<256 { ramp[v * 256 + u] = 1 + Float(u) / 256 + Float(v) / 1000; if u < 32 { conf[v * 256 + u] = 0 } } }
        let dTex = texture(.r32Float, 256, 192, ramp), kTex = texture(.r8Uint, 256, 192, conf)

        // lidarUnproject puts each grid point where CameraMath.unproject (the server's convention) does.
        let K = simd_float3x3(columns: (SIMD3(1450, 0, 0), SIMD3(0, 1450, 0), SIMD3(960, 720, 1)))
        let T = pose(yawLeftDeg: -40, pitchDeg: -30, at: SIMD3(0.5, 1.3, -1))
        let gw = 8, gh = 6
        var uu = LiDARUnprojectUniforms(cameraToWorld: T, intrinsics: SIMD4(1450, 1450, 960, 720), imageSize: SIMD2(1920, 1440),
                                        gridW: UInt32(gw), gridH: UInt32(gh), base: 0, capacity: UInt32(gw * gh),
                                        nearM: 0.1, farM: 5, minConfidence: 1)
        let buf = dev.makeBuffer(length: gw * gh * MemoryLayout<LiDARParticle>.stride, options: .storageModeShared)!
        let pso = try dev.makeComputePipelineState(function: lib.makeFunction(name: "lidarUnproject")!)
        let cmd = queue.makeCommandBuffer()!, enc = cmd.makeComputeCommandEncoder()!
        enc.setComputePipelineState(pso)
        enc.setBytes(&uu, length: MemoryLayout<LiDARUnprojectUniforms>.stride, index: 0)
        enc.setBuffer(buf, offset: 0, index: 1)
        enc.setTextures([yTex, cTex, dTex, kTex], range: 0..<4)
        enc.dispatchThreads(MTLSize(width: gw, height: gh, depth: 1), threadsPerThreadgroup: MTLSize(width: gw, height: gh, depth: 1))
        enc.endEncoding()
        cmd.commit()
        cmd.waitUntilCompleted()
        let ps = buf.contents().bindMemory(to: LiDARParticle.self, capacity: gw * gh)
        var worst: Float = 0, empty = 0, grey = true
        for gy in 0..<gh {
            for gx in 0..<gw {
                let p = ps[gy * gw + gx]
                let uv = CGPoint(x: (Double(gx) + 0.5) / Double(gw), y: (Double(gy) + 0.5) / Double(gh))
                let u = Int(uv.x * 256), v = Int(uv.y * 192)
                if u < 32 { empty += p.position.w == 0 ? 1 : 0; continue }
                let want = CameraMath.unproject(uv, depthM: 1 + Float(u) / 256 + Float(v) / 1000, intrinsics: K,
                                                imageSize: CGSize(width: 1920, height: 1440), cameraToWorld: T)
                worst = max(worst, simd_distance(SIMD3(p.position.x, p.position.y, p.position.z), want))
                grey = grey && abs(p.color.x - 0.5) < 0.02 && abs(p.color.y - 0.5) < 0.02 && abs(p.color.z - 0.5) < 0.02
            }
        }
        check(worst < 1e-3, "GPU unproject matches CameraMath: worst \(worst) m")
        check(empty == gh, "low-confidence samples are empty slots: \(empty) of \(gh)")
        check(grey, "point colours come from the camera image (grey)")

        // lidarQuadFragment paints depth with DepthPalette's colour (overlay 1, identity view-to-image map).
        let rp = MTLRenderPipelineDescriptor()
        rp.vertexFunction = lib.makeFunction(name: "lidarQuadVertex")
        rp.fragmentFunction = lib.makeFunction(name: "lidarQuadFragment")
        rp.colorAttachments[0].pixelFormat = .rgba8Unorm
        let rps = try dev.makeRenderPipelineState(descriptor: rp)
        let od = MTLTextureDescriptor.texture2DDescriptor(pixelFormat: .rgba8Unorm, width: 32, height: 24, mipmapped: false)
        od.storageMode = .shared
        od.usage = [.renderTarget]
        let out = dev.makeTexture(descriptor: od)!
        let pass = MTLRenderPassDescriptor()
        pass.colorAttachments[0].texture = out
        pass.colorAttachments[0].loadAction = .clear
        pass.colorAttachments[0].storeAction = .store
        var qu = LiDARQuadUniforms(viewToImage: SIMD4(1, 0, 0, 1), viewToImageT: SIMD2(0, 0), overlay: 1, minConfidence: 1,
                                   nearM: DepthPalette.nearM, farM: DepthPalette.farM, cameraBrightness: 1)
        let cmd2 = queue.makeCommandBuffer()!, re = cmd2.makeRenderCommandEncoder(descriptor: pass)!
        re.setRenderPipelineState(rps)
        re.setFragmentBytes(&qu, length: MemoryLayout<LiDARQuadUniforms>.stride, index: 0)
        re.setFragmentTextures([yTex, cTex, dTex, kTex], range: 0..<4)
        re.drawPrimitives(type: .triangleStrip, vertexStart: 0, vertexCount: 4)
        re.endEncoding()
        cmd2.commit()
        cmd2.waitUntilCompleted()
        var px = [UInt8](repeating: 0, count: 4)
        out.getBytes(&px, bytesPerRow: 32 * 4, from: MTLRegionMake2D(24, 12, 1, 1), mipmapLevel: 0)   // view = image here
        let uvx = (24.0 + 0.5) / 32, uvy = (12.0 + 0.5) / 24
        let want = DepthPalette.color(depthM: 1 + Float(Int(uvx * 256)) / 256 + Float(Int(uvy * 192)) / 1000) * 255
        let got = SIMD3<Float>(Float(px[0]), Float(px[1]), Float(px[2]))
        check(simd_reduce_max(simd_abs(got - want)) <= 3, "GPU heat map matches DepthPalette: \(got) vs \(want)")
    } catch {
        check(false, "LiDAR shaders: \(error)")
    }
} else {
    print("note: no Metal device here, LiDAR shader checks skipped")
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
        json(CommandAckMsg(session_id: sid, command_id: "no-such-command", status: "applied", reason: nil)),
    ]
    write("phone.jsonl", lines.reduce(into: Data()) { $0.append($1); $0.append(0x0A) })
    lines.removeAll()

    // What the wearer hears (§3.2), made by the app's own SoundReporter, for the server and the dashboard schema.
    var heard = SoundReporter(sessionId: sid)
    let behind = SIMD3<Float>(0.9, -0.8, 1.6), jar = SIMD3<Float>(0.2, -0.45, -0.35)
    var sounds: [Data] = [
        json(heard.cue("say", at: behind, anchor: "item", t: 1001.0, text: "Polo! Behind you, two steps, on the table.",
                       duration: SoundReporter.speechSeconds("Polo! Behind you, two steps, on the table."))),
        json(heard.cue("beep", at: behind, anchor: "item", t: 1004.0, muffled: true)),
        json(heard.cue("ding", at: SIMD3(0, -0.8, -1.2), anchor: "item", t: 1006.0)),
        json(heard.cue("tone_on", at: SIMD3(0, -0.6, -0.3), anchor: "item", t: 1010.0)),
        json(heard.cue("label", at: jar, anchor: "room", t: 1012.0, text: "That's the cumin, love", duration: 1.8,
                       audioURL: "/v1/audio/abc123")),
        json(heard.cue("blip", at: SoundAnchor.aheadPoint, anchor: "ahead", t: 1013.0, duration: 0.12)),
        json(heard.cue("silence", at: behind, anchor: "item", t: 1014.0)),
    ]
    var fields = SoundReporter(sessionId: sid)
    _ = fields.cue("say", at: SoundAnchor.aheadPoint, anchor: "ahead", t: 1020.0, text: "Got it.", duration: 1)
    if let f = fields.field(t: 1020.1, headYawDeg: 12.34, beacon: (behind, muffled: true), voice: (SoundAnchor.aheadPoint, anchor: "ahead")) {
        sounds.append(json(f))
    }
    if let quiet = fields.field(t: 1022.0, headYawDeg: 0, beacon: nil, voice: (SoundAnchor.aheadPoint, anchor: "ahead")) {
        sounds.append(json(quiet))
    }
    write("sound.jsonl", sounds.reduce(into: Data()) { $0.append($1); $0.append(0x0A) })

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
