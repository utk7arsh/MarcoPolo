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
