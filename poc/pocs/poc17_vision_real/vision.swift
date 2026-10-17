// POC 17: Apple Vision on real photos -- the two on-device building blocks of "tell my hand which jar":
//   * VNRecognizeTextRequest (accurate)  -> can Marco read jar/bottle/can labels by itself?
//   * VNDetectHumanHandPoseRequest       -> does it find the hand and the index fingertip near objects?
// Writes JSON results and an overlay PNG per image (green = text boxes, red = fingertips, blue = joints).
// Usage: vision <out_dir> <image> [<image> ...]
import AppKit
import Foundation
import Vision

let args = Array(CommandLine.arguments.dropFirst())
let outDir = args[0]
var report: [[String: Any]] = []

for path in args.dropFirst() {
    guard let img = NSImage(contentsOfFile: path),
          let cg = img.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
    let W = CGFloat(cg.width), H = CGFloat(cg.height)
    let handler = VNImageRequestHandler(cgImage: cg, options: [:])
    let text = VNRecognizeTextRequest()
    text.recognitionLevel = .accurate
    text.usesLanguageCorrection = true
    let hands = VNDetectHumanHandPoseRequest()
    hands.maximumHandCount = 4
    let t0 = Date()
    try? handler.perform([text, hands])
    let dt = Date().timeIntervalSince(t0)

    var lines: [[String: Any]] = []
    for o in text.results ?? [] {
        guard let c = o.topCandidates(1).first else { continue }
        lines.append(["text": c.string, "conf": c.confidence,
                      "box": [o.boundingBox.minX, o.boundingBox.minY, o.boundingBox.width, o.boundingBox.height]])
    }
    var handOut: [[String: Any]] = []
    let rep = NSBitmapImageRep(cgImage: cg)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    let lw = max(2, W / 400)
    NSColor.systemGreen.setStroke()
    for o in text.results ?? [] {
        let b = o.boundingBox
        let r = NSBezierPath(rect: NSRect(x: b.minX * W, y: b.minY * H, width: b.width * W, height: b.height * H))
        r.lineWidth = lw; r.stroke()
    }
    for h in hands.results ?? [] {
        guard let pts = try? h.recognizedPoints(.all) else { continue }
        var tip: [String: Any] = [:]
        for (name, p) in pts where p.confidence > 0.3 {
            let isTip = name == .indexTip
            (isTip ? NSColor.systemRed : NSColor.systemBlue).setFill()
            let s = isTip ? lw * 6 : lw * 3
            NSBezierPath(ovalIn: NSRect(x: p.location.x * W - s / 2, y: p.location.y * H - s / 2, width: s, height: s)).fill()
            if isTip { tip = ["x": p.location.x, "y": p.location.y, "conf": p.confidence] }
        }
        handOut.append(["confidence": h.confidence, "chirality": h.chirality == .left ? "left" : (h.chirality == .right ? "right" : "unknown"),
                        "joints_found": pts.values.filter { $0.confidence > 0.3 }.count, "index_tip": tip])
    }
    NSGraphicsContext.restoreGraphicsState()
    let name = URL(fileURLWithPath: path).deletingLastPathComponent().lastPathComponent
    try? rep.representation(using: .png, properties: [:])?.write(to: URL(fileURLWithPath: "\(outDir)/\(name).png"))
    report.append(["image": path, "seconds": dt, "width": cg.width, "height": cg.height, "text": lines, "hands": handOut])
}
let data = try JSONSerialization.data(withJSONObject: report, options: [.prettyPrinted])
try data.write(to: URL(fileURLWithPath: "\(outDir)/results.json"))
print("processed \(report.count) images")
