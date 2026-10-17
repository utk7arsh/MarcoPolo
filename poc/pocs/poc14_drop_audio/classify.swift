// POC 14: run Apple's built-in on-device sound classifier (SoundAnalysis, version1, 303 classes) over
// audio files; print per-file max confidence for drop-related classes and the top classes overall.
// Usage: classify <out.json> <file1> <file2> ...
import AVFoundation
import Foundation
import SoundAnalysis

final class Collector: NSObject, SNResultsObserving {
    var maxConf: [String: Double] = [:]
    func request(_ request: SNRequest, didProduce result: SNResult) {
        guard let r = result as? SNClassificationResult else { return }
        for c in r.classifications { maxConf[c.identifier] = max(maxConf[c.identifier] ?? 0, c.confidence) }
    }
    func request(_ request: SNRequest, didFailWithError error: Error) { print("fail \(error)") }
}

let args = Array(CommandLine.arguments.dropFirst())
let outPath = args[0]
var results: [[String: Any]] = []
let watch = ["thump_thud", "keys_jangling", "coin_dropping", "glass_breaking", "knock", "tap", "glass_clink", "door_slam", "basketball_bounce", "bowling_impact"]
for path in args.dropFirst() {
    let url = URL(fileURLWithPath: path)
    do {
        let analyzer = try SNAudioFileAnalyzer(url: url)
        let req = try SNClassifySoundRequest(classifierIdentifier: .version1)
        req.windowDuration = CMTime(seconds: 1.0, preferredTimescale: 48_000)
        req.overlapFactor = 0.5
        let col = Collector()
        try analyzer.add(req, withObserver: col)
        analyzer.analyze()
        let top = col.maxConf.sorted { $0.value > $1.value }.prefix(5).map { "\($0.key)=\(String(format: "%.2f", $0.value))" }
        var w: [String: Double] = [:]
        for k in watch { w[k] = col.maxConf[k] ?? 0 }
        results.append(["path": path, "watch": w, "top": top, "all": col.maxConf])
    } catch {
        results.append(["path": path, "error": "\(error)"])
    }
}
let data = try JSONSerialization.data(withJSONObject: results, options: [.prettyPrinted])
try data.write(to: URL(fileURLWithPath: outPath))
print("classified \(results.count) files")
