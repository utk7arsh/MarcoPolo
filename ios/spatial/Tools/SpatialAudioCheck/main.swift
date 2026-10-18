// macOS hardware check using the same HeadTracker and SpatialAudio as the iPhone app.
// Run through ios/spatial/check-airpods.sh. No microphone capture or network access.
import CoreMotion
import CoreAudio
import AVFAudio
import Foundation
import simd
import Darwin

setbuf(stdout, nil) // Keep live diagnostics visible even when launched into a log file.

if CommandLine.arguments.contains("--guidance") {
    print("Automatic --guidance demo withdrawn. Real walking needs iPhone ARKit; scripted playback is explicitly --simulate-approach.")
    exit(2)
}
let focused = CommandLine.arguments.contains("--front-back")
let guided = CommandLine.arguments.contains("--simulate-approach")
let tracker = HeadTracker()
print("Headphone motion available: \(tracker.available); authorization: \(CMHeadphoneMotionManager.authorizationStatus().rawValue)")
tracker.start()
defer { tracker.stop() }
let listening = CommandLine.arguments.contains("--listen") || focused || guided
if listening {
    var address = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyDefaultOutputDevice,
                                            mScope: kAudioObjectPropertyScopeGlobal,
                                            mElement: kAudioObjectPropertyElementMain)
    var device = AudioDeviceID(0), size = UInt32(MemoryLayout<AudioDeviceID>.size)
    let deviceStatus = AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &address, 0, nil, &size, &device)
    address.mSelector = kAudioDevicePropertyTransportType
    var transport: UInt32 = 0
    size = UInt32(MemoryLayout<UInt32>.size)
    let transportStatus = AudioObjectGetPropertyData(device, &address, 0, nil, &size, &transport)
    guard deviceStatus == noErr, transportStatus == noErr,
          [kAudioDeviceTransportTypeBluetooth, kAudioDeviceTransportTypeBluetoothLE].contains(transport) else {
        print("Select Bluetooth headphones as the Mac output before running a listening test. No audio played.")
        exit(1)
    }
}
// In focused mode, A/B use identical un-muffled beacons to test spatial perception.
// The last stage separately demonstrates the production spoken/muffled rear cue.
let duration = focused ? 46.0 : listening ? 28.0 : 12.0
let audio = listening ? SpatialAudio() : nil
try audio?.start()
audio?.engine.mainMixerNode.outputVolume = 0.35
defer { audio?.stop() }
let audioStarted = ProcessInfo.processInfo.systemUptime
if focused || guided {
    audio?.place(SIMD3(0, 0, -1))
    audio?.play(.ding)
    audio?.say("Preparing test. Waiting for head tracking.", atItem: false)
    print("Audio started; waiting up to 30 seconds for a fresh motion sample.")
}
var referenceYaw: Double?
if focused || guided {
    let deadline = ProcessInfo.processInfo.systemUptime + 30
    while referenceYaw == nil && ProcessInfo.processInfo.systemUptime < deadline {
        referenceYaw = tracker.sample(now: ProcessInfo.processInfo.systemUptime)?.yawDeg
        RunLoop.current.run(until: Date(timeIntervalSinceNow: 1.0 / 60))
    }
    guard referenceYaw != nil else {
        print("No fresh headphone motion; guidance not started. Authorization=\(CMHeadphoneMotionManager.authorizationStatus().rawValue), available=\(tracker.available), connected=\(tracker.connected)")
        audio?.say("Head tracking did not start. Check motion permission and wear both earbuds.", atItem: false)
        RunLoop.current.run(until: Date(timeIntervalSinceNow: 5))
        audio?.stop(); tracker.stop(); exit(2)
    }
    while ProcessInfo.processInfo.systemUptime - audioStarted < 3.5 {
        RunLoop.current.run(until: Date(timeIntervalSinceNow: 1.0 / 60))
    }
    print("Motion ready; starting listening sequence.")
}
if guided, let audio, let referenceYaw {
    runGuidanceDemo(audio: audio, tracker: tracker, referenceYaw: referenceYaw)
    audio.stop()
    tracker.stop()
    exit(0)
}
let start = ProcessInfo.processInfo.systemUptime
var lastTimestamp: Double?, firstTimestamp: Double?, minimum = Double.infinity, maximum = -Double.infinity
var samples = 0, announced = -1
let tour: [(Double, SIMD3<Float>, String)] = focused ? [
    (0, SIMD3(-2, 0, 0), "Left check. Polo. Your keys are here."),
    (5, SIMD3(2, 0, 0), "Right check. Polo. Your keys are here."),
    (10, SIMD3(0, 0, 2), "Test A. Polo. Your keys are here. Slowly turn your head."),
    (22, SIMD3(0, 0, -2), "Test B. Polo. Your keys are here. Slowly turn your head."),
    (34, SIMD3(0, 0, 2), Lines.polo(relAzimuthDeg: 180, distanceM: 2, surface: nil))
] : [
    (0, SIMD3(-2, 0, 0), "Polo. Your keys are here."),
    (5, SIMD3(2, 0, 0), "Polo. Your keys are here."),
    (10, SIMD3(0, 0, -2), "Polo. Your keys are here."),
    (15, SIMD3(0, 0, 2), "Polo. Your keys are here."),
    (20, SIMD3(0, 0, -2), "Polo. Turn your head. The keys stay in the same place.")
]
var lastBeep = -Double.infinity
var trackingLost = false
var trackedTicks = 0, missingTicks = 0
var stageYawMin = Double.infinity, stageYawMax = -Double.infinity
while ProcessInfo.processInfo.systemUptime - start < duration {
    let now = ProcessInfo.processInfo.systemUptime
    let sample = tracker.sample(now: now)
    if let sample, sample.t != lastTimestamp {
        if firstTimestamp == nil { firstTimestamp = sample.t; if referenceYaw == nil { referenceYaw = sample.yawDeg } }
        lastTimestamp = sample.t
        samples += 1
        minimum = min(minimum, sample.yawDeg)
        maximum = max(maximum, sample.yawDeg)
    }
    if listening {
        let elapsed = now - start
        let index = tour.lastIndex { elapsed >= $0.0 } ?? 0
        if focused && sample == nil {
            missingTicks += 1
            if !trackingLost { audio?.play(.silence); print("Motion lost; audio paused.") }
            trackingLost = true
            RunLoop.current.run(until: Date(timeIntervalSinceNow: 1.0 / 60))
            continue
        }
        trackingLost = false
        if focused { trackedTicks += 1 }
        let yaw = (focused || index == 4) ? Geo.wrap180((sample?.yawDeg ?? referenceYaw ?? 0) - (referenceYaw ?? 0)) : 0
        audio?.place(Geo.listenerRelative(ear: .zero, headYawDeg: yaw, target: tour[index].1))
        if index != announced {
            if focused && announced >= 0 { print("Stage \(announced + 1) relative yaw range: \(stageYawMin)...\(stageYawMax)") }
            stageYawMin = yaw; stageYawMax = yaw
            announced = index
            print("Voice position \(index + 1): \(tour[index].1); head tracking: \(sample != nil)")
            audio?.say(tour[index].2, atItem: true)
        }
        stageYawMin = min(stageYawMin, yaw); stageYawMax = max(stageYawMax, yaw)
        if focused && elapsed >= tour[index].0 + 3.5 && now - lastBeep >= 0.65 {
            let azimuth = Geo.relativeAzimuthDeg(from: .zero, headingDeg: yaw, to: tour[index].1)
            audio?.play(.beep(muffled: index == 4 && abs(azimuth) > 90))
            lastBeep = now
        }
    }
    RunLoop.current.run(until: Date(timeIntervalSinceNow: 1.0 / 60))
}
let span = (lastTimestamp ?? 0) - (firstTimestamp ?? 0)
let rate = span > 0 ? Double(max(0, samples - 1)) / span : 0
print("Motion samples: \(samples); observed rate: \(String(format: "%.1f", rate)) Hz; yaw span: \(samples > 0 ? maximum - minimum : 0) degrees")
if samples == 0 { print("No motion stream verified. A stereo audio connection alone does not establish head tracking.") }
if focused {
    print("Stage \(announced + 1) relative yaw range: \(stageYawMin)...\(stageYawMax)")
    print("Focused tracked ticks: \(trackedTicks); missing-motion ticks: \(missingTicks)")
}
