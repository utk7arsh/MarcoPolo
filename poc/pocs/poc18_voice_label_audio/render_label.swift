// POC 18: a guardian's iMessage voice memo (CAF/Opus) becomes the jar's own voice, played from the
// jar's position through Apple's spatial-audio engine (AVAudioEnvironmentNode, HRTFHQ).
// Usage: render_label <memo.caf> <out.caf> <az_deg> <el_deg> <dist_m>
import AVFoundation
import Foundation

let a = CommandLine.arguments
let inURL = URL(fileURLWithPath: a[1])
let az = Double(a[3])! * .pi / 180, el = Double(a[4])! * .pi / 180, dist = Double(a[5])!

let file = try AVAudioFile(forReading: inURL)       // decodes Opus-in-CAF
let src = file.processingFormat
let monoFmt = AVAudioFormat(standardFormatWithSampleRate: src.sampleRate, channels: 1)!
let n = AVAudioFrameCount(file.length)
let buf = AVAudioPCMBuffer(pcmFormat: src, frameCapacity: n)!
try file.read(into: buf)
var peak: Float = 0
for i in 0..<Int(buf.frameLength) { peak = max(peak, abs(buf.floatChannelData![0][i])) }
print("decoded \(buf.frameLength) frames @ \(src.sampleRate) Hz, \(src.channelCount) ch, peak \(peak)")

let engine = AVAudioEngine()
let player = AVAudioPlayerNode()
let env = AVAudioEnvironmentNode()
engine.attach(player); engine.attach(env)
let stereo = AVAudioFormat(standardFormatWithSampleRate: src.sampleRate, channels: 2)!
try engine.enableManualRenderingMode(.offline, format: stereo, maximumFrameCount: 4096)
engine.connect(player, to: env, format: monoFmt)
engine.connect(env, to: engine.mainMixerNode, format: stereo)
env.outputType = .headphones
env.distanceAttenuationParameters.referenceDistance = 0.3   // keep getting louder inside 1 m (see REPORT)
player.renderingAlgorithm = .HRTFHQ
player.position = AVAudio3DPoint(x: Float(dist * cos(el) * sin(az)), y: Float(dist * sin(el)), z: Float(-dist * cos(el) * cos(az)))
try engine.start()
player.scheduleBuffer(buf, at: nil, options: [], completionHandler: nil)
player.play()
let out = try AVAudioFile(forWriting: URL(fileURLWithPath: a[2]), settings: stereo.settings)
let ob = AVAudioPCMBuffer(pcmFormat: engine.manualRenderingFormat, frameCapacity: 4096)!
var rendered: AVAudioFrameCount = 0
while rendered < n + 4800 {
    let st = try engine.renderOffline(4096, to: ob)
    guard st == .success else { break }
    try out.write(from: ob)
    rendered += ob.frameLength
}
var lE: Float = 0, rE: Float = 0
// quick level check on the last block (for logging only)
for i in 0..<Int(ob.frameLength) { lE += ob.floatChannelData![0][i] * ob.floatChannelData![0][i]; rE += ob.floatChannelData![1][i] * ob.floatChannelData![1][i] }
print("rendered \(rendered) frames spatialised at az \(a[3]) el \(a[4]) dist \(a[5]) m -> \(a[2])")
