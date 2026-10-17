// Lists Apple's built-in on-device sound classes (SoundAnalysis, version1) relevant to "something dropped".
import Foundation
import SoundAnalysis
let req = try SNClassifySoundRequest(classifierIdentifier: .version1)
let all = req.knownClassifications
print("total classes: \(all.count)")
let keys = ["drop", "thump", "thud", "knock", "clatter", "keys", "jingle", "coin", "glass", "shatter", "slam", "bounce", "impact", "tap", "clink", "rattle"]
print(all.filter { c in keys.contains { c.lowercased().contains($0) } }.joined(separator: ", "))
