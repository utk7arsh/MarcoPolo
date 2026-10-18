// Render the app's actual voice path through Apple's HRTF, without playing to a device.
import AVFAudio
import Foundation
import simd

let directory = FileManager.default.temporaryDirectory.appendingPathComponent("marco-spatial-\(UUID().uuidString)")
try FileManager.default.createDirectory(at: directory, withIntermediateDirectories: true)
defer { try? FileManager.default.removeItem(at: directory) }
let mono = AVAudioFormat(standardFormatWithSampleRate: 48_000, channels: 1)!
let stereo = AVAudioFormat(standardFormatWithSampleRate: 48_000, channels: 2)!
let fixture = directory.appendingPathComponent("voice-path.caf")
let input = AVAudioPCMBuffer(pcmFormat: mono, frameCapacity: 24_000)!
input.frameLength = input.frameCapacity
var seed: UInt64 = 42
for i in 0..<Int(input.frameLength) {
    seed = seed &* 6364136223846793005 &+ 1
    input.floatChannelData![0][i] = (Float(seed >> 40) / Float(1 << 24) - 0.5) * 0.2
}
do { let file = try AVAudioFile(forWriting: fixture, settings: mono.settings); try file.write(from: input) }

var passed = 0, failed = 0
func check(_ condition: Bool, _ name: String) {
    if condition { passed += 1 } else { failed += 1; print("FAIL: \(name)") }
}

func render(_ position: SIMD3<Float>, generalFirst: Bool = false, move: SIMD3<Float>? = nil) throws -> [[Float]] {
    let audio = SpatialAudio()
    try audio.engine.enableManualRenderingMode(.offline, format: stereo, maximumFrameCount: 512)
    try audio.start()
    defer { audio.stop() }
    audio.place(position)
    if generalFirst { try audio.playFile(fixture, atItem: false) }
    try audio.playFile(fixture, atItem: true)
    if let move { audio.place(move) }
    let output = AVAudioPCMBuffer(pcmFormat: stereo, frameCapacity: 512)!
    var channels = [[Float](), [Float]()]
    for _ in 0..<56 {
        let status = try audio.engine.renderOffline(512, to: output)
        guard status == .success else { throw NSError(domain: "OfflineRender", code: Int(status.rawValue)) }
        for c in 0..<2 { channels[c].append(contentsOf: UnsafeBufferPointer(start: output.floatChannelData![c], count: Int(output.frameLength))) }
    }
    return channels
}
func energy(_ samples: [Float]) -> Double { samples.reduce(0) { $0 + Double($1) * Double($1) } }
func bias(_ channels: [[Float]]) -> Double { 10 * log10(max(energy(channels[1]), 1e-20) / max(energy(channels[0]), 1e-20)) }

let right = try render(SIMD3(2, 0, 0))
let left = try render(SIMD3(-2, 0, 0))
let front = try render(SIMD3(0, 0, -2))
let back = try render(SIMD3(0, 0, 2))
for (name, channels) in [("right", right), ("left", left), ("front", front), ("back", back)] {
    check(channels.flatMap { $0 }.allSatisfy { $0.isFinite }, "\(name): finite samples")
    check(energy(channels[0]) + energy(channels[1]) > 0.0001, "\(name): audible rendered signal")
    print("\(name): right/left energy bias \(String(format: "%.2f", bias(channels))) dB")
}
check(bias(right) > 3, "item on right is louder in right ear immediately")
check(bias(left) < -3, "item on left is louder in left ear immediately")
check(abs(bias(front)) < 1, "front is centered")
check(abs(bias(back)) < 1, "back is centered")
let difference = zip(front[0], back[0]).reduce(0.0) { $0 + pow(Double($1.0 - $1.1), 2) }
check(difference > energy(front[0]) * 0.01, "front/back receive distinct HRTF filtering (not proof of perception)")
let afterGeneral = try render(SIMD3(2, 0, 0), generalFirst: true)
check(bias(afterGeneral) > 3, "item voice resets position after a general announcement")
let moved = try render(SIMD3(2, 0, 0), move: SIMD3(-2, 0, 0))
check(bias(moved) < -3, "moving target updates queued voice")
for (yaw, expectedRight) in [(90.0, false), (-90.0, true)] {
    let relative = Geo.listenerRelative(ear: .zero, headYawDeg: yaw, target: SIMD3(0, 0, -2))
    let rendered = try render(relative)
    check(expectedRight ? bias(rendered) > 3 : bias(rendered) < -3,
          "world-fixed front target shifts to opposite ear after head turn \(yaw)")
}
// A modest head turn must disambiguate opposite front/back sources in opposite ears.
for (name, target) in [("front", SIMD3<Float>(0, 0, -2)), ("back", SIMD3<Float>(0, 0, 2))] {
    for yaw in [-30.0, 30.0] {
        let relative = Geo.listenerRelative(ear: .zero, headYawDeg: yaw, target: target)
        let rendered = try render(relative)
        let expectedRight = name == "front" ? yaw < 0 : yaw > 0
        check(expectedRight ? bias(rendered) > 1 : bias(rendered) < -1,
              "\(name): head turn \(yaw) shifts rendered audio to the correct ear")
    }
}
print("\(passed) spatial render checks passed, \(failed) failed")
exit(failed == 0 ? 0 : 1)
