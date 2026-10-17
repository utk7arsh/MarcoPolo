// Registration boxes the way the app would get them ("hold up your keys"): Apple Vision's foreground
// instance mask -> bounding box of the largest foreground instance. Writes register/boxes.json per item.
import AppKit
import Vision
let root = CommandLine.arguments[1]
let fm = FileManager.default
for item in try fm.contentsOfDirectory(atPath: root).sorted() where item.contains("--") {
    let dir = "\(root)/\(item)/register"
    var out: [String: [Double]] = [:]
    for f in (try? fm.contentsOfDirectory(atPath: dir))?.filter({ $0.hasSuffix(".jpg") }).sorted() ?? [] {
        guard let cg = NSImage(contentsOfFile: "\(dir)/\(f)")?.cgImage(forProposedRect: nil, context: nil, hints: nil) else { continue }
        let req = VNGenerateForegroundInstanceMaskRequest()
        let h = VNImageRequestHandler(cgImage: cg)
        try? h.perform([req])
        guard let obs = req.results?.first, !obs.allInstances.isEmpty else {
            out[f] = [0.15, 0.15, 0.85, 0.85].map { $0 * Double(cg.width) }; continue   // fallback: central box
        }
        // Several instances: take the one nearest the image centre (how a person holds an item up to the camera).
        var best: (d: Double, b: [Int])? = nil
        var x0 = 0, y0 = 0, x1 = 0, y1 = 0, w = 1, hh = 1
        for inst in obs.allInstances {
            guard let mask = try? obs.generateScaledMaskForImage(forInstances: IndexSet(integer: inst), from: h) else { continue }
            CVPixelBufferLockBaseAddress(mask, .readOnly)
            w = CVPixelBufferGetWidth(mask); hh = CVPixelBufferGetHeight(mask); let rb = CVPixelBufferGetBytesPerRow(mask)
            let base = CVPixelBufferGetBaseAddress(mask)!.assumingMemoryBound(to: Float32.self)
            var a0 = w, b0 = hh, a1 = 0, b1 = 0, n = 0
            for y in 0..<hh { for x in 0..<w where base[y * rb / 4 + x] > 0.5 { a0 = min(a0, x); a1 = max(a1, x); b0 = min(b0, y); b1 = max(b1, y); n += 1 } }
            CVPixelBufferUnlockBaseAddress(mask, .readOnly)
            guard a1 > a0, n > (w * hh) / 200 else { continue }
            let cx = Double(a0 + a1) / 2 / Double(w) - 0.5, cy = Double(b0 + b1) / 2 / Double(hh) - 0.5
            let d = (cx * cx + cy * cy).squareRoot()
            if best == nil || d < best!.d { best = (d, [a0, b0, a1, b1]) }
        }
        if let b = best?.b { x0 = b[0]; y0 = b[1]; x1 = b[2]; y1 = b[3] }
        let sx = Double(cg.width) / Double(w), sy = Double(cg.height) / Double(hh)
        out[f] = x1 > x0 ? [Double(x0) * sx, Double(y0) * sy, Double(x1) * sx, Double(y1) * sy] : [0.15, 0.15, 0.85, 0.85].map { $0 * Double(cg.width) }
    }
    let data = try JSONSerialization.data(withJSONObject: out, options: [.prettyPrinted, .sortedKeys])
    try data.write(to: URL(fileURLWithPath: "\(dir)/boxes.json"))
    print(item, out.count)
}
