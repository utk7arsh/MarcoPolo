// Computes Apple Vision image feature prints (VNGenerateImageFeaturePrintRequest, the API the app
// would use for "only your bottle answers") on object crops from a real iPhone video.
//
// Usage: featureprint <video.MOV> <boxes.txt> <out.bin> <sizes csv, 0 = native> [preview_dir]
//   boxes.txt lines: frame_id x0 y0 x1 y1   (normalised [0,1], image as stored in the file)
// Output: float32 records [frame_id, size, dim, v0..v(dim-1)]

import AVFoundation
import CoreImage
import Foundation
import ImageIO
import UniformTypeIdentifiers
import Vision

let a = CommandLine.arguments
let asset = AVURLAsset(url: URL(fileURLWithPath: a[1]))
let boxesText = try String(contentsOfFile: a[2], encoding: .utf8)
let outPath = a[3]
let sizes = a[4].split(separator: ",").map { Int($0)! }
let preview = a.count > 5 && a[5] != "-" ? a[5] : nil
let useMask = a.count > 6 && a[6] == "mask"

let track = asset.tracks(withMediaType: .video).first!
let fps = Double(track.nominalFrameRate)
let gen = AVAssetImageGenerator(asset: asset)
gen.appliesPreferredTrackTransform = true  // Objectron annotations are in the upright (portrait) frame
gen.requestedTimeToleranceBefore = .zero
gen.requestedTimeToleranceAfter = .zero
let ctx = CIContext()

var out = Data()
var count = 0
for line in boxesText.split(separator: "\n") {
    let p = line.split(separator: " ").map { Double($0)! }
    let fid = Int(p[0])
    let t = CMTime(seconds: (Double(fid) + 0.5) / fps, preferredTimescale: 600)
    guard let img = try? gen.copyCGImage(at: t, actualTime: nil) else { continue }
    let W = Double(img.width), H = Double(img.height)
    // pad box by 10 %
    var x0 = p[1], y0 = p[2], x1 = p[3], y1 = p[4]
    let pw = (x1 - x0) * 0.1, ph = (y1 - y0) * 0.1
    x0 = max(0, x0 - pw); y0 = max(0, y0 - ph); x1 = min(1, x1 + pw); y1 = min(1, y1 + ph)
    let rect = CGRect(x: x0 * W, y: y0 * H, width: (x1 - x0) * W, height: (y1 - y0) * H).integral
    guard rect.width > 8, rect.height > 8, var crop = img.cropping(to: rect) else { continue }
    if useMask {
        // Remove the background with Vision's foreground instance mask (macOS 14 / iOS 17), then
        // composite the object onto neutral grey, so only the object itself is compared.
        let mreq = VNGenerateForegroundInstanceMaskRequest()
        let mh = VNImageRequestHandler(cgImage: crop, options: [:])
        try? mh.perform([mreq])
        if let obs = mreq.results?.first, !obs.allInstances.isEmpty,
           let mbuf = try? obs.generateScaledMaskForImage(forInstances: obs.allInstances, from: mh) {
            let src = CIImage(cgImage: crop)
            let mask = CIImage(cvPixelBuffer: mbuf)
            let grey = CIImage(color: CIColor(red: 0.5, green: 0.5, blue: 0.5)).cropped(to: src.extent)
            let comp = src.applyingFilter("CIBlendWithMask", parameters: [kCIInputBackgroundImageKey: grey, kCIInputMaskImageKey: mask])
            if let c = ctx.createCGImage(comp, from: src.extent) { crop = c }
        }
    }
    for s in sizes {
        var cg = crop
        if s > 0 {
            // Simulate a farther view: the object spans `s` pixels (longest side), as the detector crop would.
            let scale = Double(s) / Double(max(crop.width, crop.height))
            let ci = CIImage(cgImage: crop).transformed(by: CGAffineTransform(scaleX: scale, y: scale))
            cg = ctx.createCGImage(ci, from: ci.extent)!
        }
        let req = VNGenerateImageFeaturePrintRequest()
        let h = VNImageRequestHandler(cgImage: cg, options: [:])
        try h.perform([req])
        guard let fp = req.results?.first as? VNFeaturePrintObservation else { continue }
        let n = fp.elementCount
        var header: [Float] = [Float(fid), Float(s), Float(n)]
        header.withUnsafeBufferPointer { out.append(Data(buffer: $0)) }
        if fp.elementType == .float {
            out.append(fp.data)
        } else {
            let d = fp.data.withUnsafeBytes { Array($0.bindMemory(to: Double.self)).map { Float($0) } }
            d.withUnsafeBufferPointer { out.append(Data(buffer: $0)) }
        }
        count += 1
        if let dir = preview, count <= 3 * sizes.count {
            let url = URL(fileURLWithPath: "\(dir)/f\(fid)_s\(s).jpg")
            if let dest = CGImageDestinationCreateWithURL(url as CFURL, UTType.jpeg.identifier as CFString, 1, nil) {
                CGImageDestinationAddImage(dest, cg, nil); CGImageDestinationFinalize(dest)
            }
        }
    }
}
try out.write(to: URL(fileURLWithPath: outPath))
print("feature prints: \(count), video \(track.naturalSize) fps \(fps)")
