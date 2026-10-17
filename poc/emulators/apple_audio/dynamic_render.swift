// Renders a world-fixed source through Apple's AVAudioEnvironmentNode while the listener's
// orientation is updated over time (the "manual head tracking" path an app would use with
// CMHeadphoneMotionManager). Writes a stereo float32 file for analysis.
//
// Usage: dynamic_render <yaw_trajectory.f32 (one yaw per block, degrees)> <block_frames> <out.f32>
//        [source_az_deg=0] [dist=2] [signal=noise|chime] [mode=listener|source]
// mode=listener: rotate listenerAngularOrientation; mode=source: keep listener fixed and move the source.

import AVFoundation
import Foundation

let fs = 48_000.0
let stereo = AVAudioFormat(standardFormatWithSampleRate: fs, channels: 2)!
let mono = AVAudioFormat(standardFormatWithSampleRate: fs, channels: 1)!
let a = CommandLine.arguments
let yawData = try Data(contentsOf: URL(fileURLWithPath: a[1]))
let yaws: [Float] = yawData.withUnsafeBytes { Array($0.bindMemory(to: Float.self)) }
let block = Int(a[2])!
let outPath = a[3]
let srcAz = a.count > 4 ? Double(a[4])! : 0
let dist = a.count > 5 ? Double(a[5])! : 2
let signal = a.count > 6 ? a[6] : "noise"
let mode = a.count > 7 ? a[7] : "listener"

let total = yaws.count * block
var x = [Float](repeating: 0, count: total)
var seed: UInt64 = 12345
func rnd() -> Float { seed = seed &* 6364136223846793005 &+ 1442695040888963407; return Float(Int64(bitPattern: seed >> 11) % 2_000_000) / 1_000_000 - 1 }
if signal == "noise" {
    for i in 0..<total { x[i] = 0.3 * rnd() }
} else {
    // Repeating 120 ms broadband chime every 250 ms.
    for i in 0..<total {
        let t = Double(i % Int(0.25 * fs)) / fs
        if t < 0.12 {
            let env = Float(exp(-t * 30))
            x[i] = env * (0.25 * rnd() + 0.2 * Float(sin(2 * .pi * 1760 * t) + sin(2 * .pi * 2637 * t)))
        }
    }
}

let engine = AVAudioEngine()
let player = AVAudioPlayerNode()
let env = AVAudioEnvironmentNode()
engine.attach(player); engine.attach(env)
try engine.enableManualRenderingMode(.offline, format: stereo, maximumFrameCount: AVAudioFrameCount(block))
engine.connect(player, to: env, format: mono)
engine.connect(env, to: engine.mainMixerNode, format: stereo)
env.outputType = .headphones
env.reverbParameters.enable = false
player.renderingAlgorithm = .HRTFHQ
func pos(_ azDeg: Double) -> AVAudio3DPoint {
    let r = azDeg * .pi / 180
    return AVAudio3DPoint(x: Float(dist * sin(r)), y: 0, z: Float(-dist * cos(r)))
}
player.position = pos(srcAz)
let buf = AVAudioPCMBuffer(pcmFormat: mono, frameCapacity: AVAudioFrameCount(total))!
buf.frameLength = AVAudioFrameCount(total)
for i in 0..<total { buf.floatChannelData![0][i] = x[i] }
try engine.start()
player.scheduleBuffer(buf, at: nil, options: [], completionHandler: nil)
player.play()
let out = AVAudioPCMBuffer(pcmFormat: engine.manualRenderingFormat, frameCapacity: AVAudioFrameCount(block))!
var outData = Data()
for k in 0..<yaws.count {
    if mode == "listener" {
        env.listenerAngularOrientation = AVAudio3DAngularOrientation(yaw: yaws[k], pitch: 0, roll: 0)
    } else {
        // Equivalent head-relative motion: source moves opposite to a head yaw (sign to be verified).
        player.position = pos(srcAz - Double(yaws[k]))
    }
    let st = try engine.renderOffline(AVAudioFrameCount(block), to: out)
    precondition(st == .success)
    var inter = [Float](repeating: 0, count: Int(out.frameLength) * 2)
    for i in 0..<Int(out.frameLength) { inter[2*i] = out.floatChannelData![0][i]; inter[2*i+1] = out.floatChannelData![1][i] }
    inter.withUnsafeBufferPointer { outData.append(Data(buffer: $0)) }
}
try outData.write(to: URL(fileURLWithPath: outPath))
print("rendered \(yaws.count) blocks of \(block) frames, mode \(mode)")
