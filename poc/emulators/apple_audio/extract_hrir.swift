// Extracts head-related impulse responses (HRIRs) from Apple's own spatial-audio renderer
// (AVAudioEnvironmentNode, the engine an iOS app would use) by rendering a unit impulse
// offline from a grid of source directions.
//
// Coordinates follow AVAudioEnvironmentNode: right-handed, +x right, +y up, listener faces -z.
// Azimuth is clockwise from straight ahead (positive = right), elevation positive = up.
//
// Usage: extract_hrir <algorithm: hrtfhq|hrtf|auto|sphericalhead> <outdir> [distances csv]

import AVFoundation
import Foundation

let sampleRate = 48_000.0
let irLength = 8192
let preDelay = 1024
let stereo = AVAudioFormat(standardFormatWithSampleRate: sampleRate, channels: 2)!
let mono = AVAudioFormat(standardFormatWithSampleRate: sampleRate, channels: 1)!

enum ExtractError: Error { case render(String) }

func algorithm(named name: String) -> AVAudio3DMixingRenderingAlgorithm {
    switch name {
    case "hrtf": return .HRTF
    case "auto": return .auto
    case "sphericalhead": return .sphericalHead
    case "equalpower": return .equalPowerPanning
    default: return .HRTFHQ
    }
}

/// Renders `input` (mono) from one static source position; returns [left, right].
func render(_ input: [Float], algo: AVAudio3DMixingRenderingAlgorithm, position: AVAudio3DPoint,
            listenerYaw: Float = 0, extraFrames: Int = irLength) throws -> [[Float]] {
    let engine = AVAudioEngine()
    let player = AVAudioPlayerNode()
    let env = AVAudioEnvironmentNode()
    engine.attach(player)
    engine.attach(env)
    try engine.enableManualRenderingMode(.offline, format: stereo, maximumFrameCount: 4096)
    engine.connect(player, to: env, format: mono)
    engine.connect(env, to: engine.mainMixerNode, format: stereo)
    env.outputType = .headphones
    env.listenerPosition = AVAudio3DPoint(x: 0, y: 0, z: 0)
    env.listenerAngularOrientation = AVAudio3DAngularOrientation(yaw: listenerYaw, pitch: 0, roll: 0)
    env.reverbParameters.enable = false
    player.renderingAlgorithm = algo
    player.position = position
    player.reverbBlend = 0

    let buf = AVAudioPCMBuffer(pcmFormat: mono, frameCapacity: AVAudioFrameCount(input.count))!
    buf.frameLength = AVAudioFrameCount(input.count)
    let ch = buf.floatChannelData![0]
    for i in 0..<input.count { ch[i] = input[i] }

    try engine.start()
    player.scheduleBuffer(buf, at: nil, options: [], completionHandler: nil)
    player.play()
    let out = AVAudioPCMBuffer(pcmFormat: engine.manualRenderingFormat,
                               frameCapacity: engine.manualRenderingMaximumFrameCount)!
    var left = [Float](), right = [Float]()
    let total = input.count + extraFrames
    while left.count < total {
        let n = min(AVAudioFrameCount(total - left.count), engine.manualRenderingMaximumFrameCount)
        let status = try engine.renderOffline(n, to: out)
        guard status == .success else { throw ExtractError.render("status \(status.rawValue)") }
        let l = out.floatChannelData![0], r = out.floatChannelData![1]
        for i in 0..<Int(out.frameLength) { left.append(l[i]); right.append(r[i]) }
    }
    engine.stop()
    return [left, right]
}

func point(azDeg: Double, elDeg: Double, dist: Double) -> AVAudio3DPoint {
    let az = azDeg * .pi / 180, el = elDeg * .pi / 180
    return AVAudio3DPoint(x: Float(dist * cos(el) * sin(az)),
                          y: Float(dist * sin(el)),
                          z: Float(-dist * cos(el) * cos(az)))
}

let args = CommandLine.arguments
let algoName = args.count > 1 ? args[1] : "hrtfhq"
let outDir = args.count > 2 ? args[2] : "."
let distances = (args.count > 3 ? args[3] : "1.0").split(separator: ",").map { Double($0)! }
let algo = algorithm(named: algoName)

var impulse = [Float](repeating: 0, count: preDelay + 1)
impulse[preDelay] = 1.0

let azimuths = stride(from: -180.0, to: 180.0, by: 5.0).map { $0 }
let elevations: [Double] = [-60, -45, -30, -15, 0, 15, 30, 45, 60, 75, 90]

var meta: [[String: Any]] = []
var blob = Data()
let t0 = Date()
for dist in distances {
    for el in elevations {
        for az in azimuths {
            if el == 90 && az != 0 { continue }
            let lr = try render(impulse, algo: algo, position: point(azDeg: az, elDeg: el, dist: dist))
            for ch in lr {
                ch.withUnsafeBufferPointer { blob.append(Data(buffer: $0)) }
            }
            meta.append(["az": az, "el": el, "dist": dist, "frames": lr[0].count])
        }
    }
}

// Linearity and time-invariance checks on one direction.
let p = point(azDeg: 30, elDeg: 0, dist: 1)
var half = impulse; half[preDelay] = 0.5
var two = [Float](repeating: 0, count: preDelay + 4097); two[preDelay] = 1.0; two[preDelay + 4096] = 1.0
let a = try render(impulse, algo: algo, position: p)
let b = try render(half, algo: algo, position: p)
let c = try render(two, algo: algo, position: p)
var linErr: Float = 0, tiErr: Float = 0, peak: Float = 0
for i in 0..<irLength {
    linErr = max(linErr, abs(a[0][i] * 0.5 - b[0][i]))
    tiErr = max(tiErr, abs(c[0][i + 4096] - c[0][i] - (i >= 4096 ? 0 : 0)))
    peak = max(peak, abs(a[0][i]))
}

let info: [String: Any] = [
    "algorithm": algoName, "sampleRate": sampleRate, "preDelay": preDelay,
    "count": meta.count, "entries": meta,
    "checks": ["linearity_max_abs_err": linErr, "time_invariance_max_abs_err": tiErr, "peak": peak],
    "os": ProcessInfo.processInfo.operatingSystemVersionString,
    "seconds": Date().timeIntervalSince(t0),
]
try blob.write(to: URL(fileURLWithPath: "\(outDir)/hrir_\(algoName).f32"))
let json = try JSONSerialization.data(withJSONObject: info, options: [.prettyPrinted, .sortedKeys])
try json.write(to: URL(fileURLWithPath: "\(outDir)/hrir_\(algoName).json"))
print("done \(algoName): \(meta.count) directions in \(Date().timeIntervalSince(t0)) s; checks lin=\(linErr) ti=\(tiErr) peak=\(peak)")
