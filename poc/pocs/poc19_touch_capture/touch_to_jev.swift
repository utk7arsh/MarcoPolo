// POC 19: "touched jar" -> photo for Jev / the guardian -> bounding boxes back on the image.
//
// The real app does this on the iPhone with an ARFrame; everything here except the ARKit glue is the
// same code (CoreImage, Vision, Foundation), run on a real photo of a hand reaching for a jar.
//
//   1. Vision hand pose -> 21 joints (normalised, origin BOTTOM-left)
//   2. touch region = box around the hand, grown toward the object under it -> crop (pixels, origin TOP-left)
//   3. crop -> JPEG (~1024 px max side) = the `frame` image for Jev, and the photo for the guardian
//   4. build the exact Jev multipart request (Noul "is a jar touched?", Box "the jar the hand is
//      touching", Choice "which enrolled jar?" with each option described by an enrolled photo)
//   5. map a Box answer (fractions of the CROP, origin top-left) back to full-image pixels and draw it
//   6. guardian photo: the crop with the box highlighted, ready for Photon
//
// ARKit glue on the phone (not compiled here):
//   let ci = CIImage(cvPixelBuffer: frame.capturedImage).oriented(.right)   // landscape sensor -> upright portrait
//   let cg = CIContext().createCGImage(ci, from: ci.extent)!                // then call touchCapture(cg, ...)
//
// Usage: touch_to_jev <photo.jpg> <out_dir> [<enrolled_name>=<x0,y0,x1,y1 in full-image pixels> ...]

import AppKit
import CoreImage
import Foundation
import Vision

struct PixelBox { var x0, y0, x1, y1: CGFloat }   // pixels, origin top-left

/// Jev's Box answer: fractions of the image that was SENT, measured from its top-left corner.
struct JevBox { var top, bottom, left, right: CGFloat }

func jpeg(_ cg: CGImage, maxSide: CGFloat = 1024, quality: CGFloat = 0.85) -> Data {
    let s = min(1, maxSide / CGFloat(max(cg.width, cg.height)))
    var ci = CIImage(cgImage: cg)
    if s < 1 { ci = ci.transformed(by: CGAffineTransform(scaleX: s, y: s)) }
    let ctx = CIContext()
    return ctx.jpegRepresentation(of: ci, colorSpace: CGColorSpace(name: CGColorSpace.sRGB)!,
                                  options: [kCGImageDestinationLossyCompressionQuality as CIImageRepresentationOption: quality])!
}

/// Steps 1-2: where is the hand, and which part of the image shows what it is touching?
func touchRegion(_ cg: CGImage) throws -> (joints: [CGPoint], region: PixelBox)? {
    let req = VNDetectHumanHandPoseRequest()
    req.maximumHandCount = 2
    try VNImageRequestHandler(cgImage: cg).perform([req])
    guard let hand = req.results?.max(by: { $0.confidence < $1.confidence }) else { return nil }
    let W = CGFloat(cg.width), H = CGFloat(cg.height)
    let pts = try hand.recognizedPoints(.all).values.filter { $0.confidence > 0.3 }
        .map { CGPoint(x: $0.location.x * W, y: (1 - $0.location.y) * H) }   // Vision: bottom-left -> top-left
    guard pts.count >= 6 else { return nil }
    let xs = pts.map(\.x), ys = pts.map(\.y)
    let w = xs.max()! - xs.min()!, h = ys.max()! - ys.min()!
    // grow the box (x1.6) and push it down: the touched object is under and around the fingers
    var r = PixelBox(x0: xs.min()! - 0.3 * w, y0: ys.min()! - 0.2 * h, x1: xs.max()! + 0.3 * w, y1: ys.max()! + 0.9 * h)
    r.x0 = max(0, r.x0); r.y0 = max(0, r.y0); r.x1 = min(W, r.x1); r.y1 = min(H, r.y1)
    return (pts, r)
}

func crop(_ cg: CGImage, _ b: PixelBox) -> CGImage {
    cg.cropping(to: CGRect(x: b.x0, y: b.y0, width: b.x1 - b.x0, height: b.y1 - b.y0).integral)!
}

/// Step 5: Box answer on the crop -> pixels on the full image.
func toFullImage(_ jb: JevBox, crop c: PixelBox) -> PixelBox {
    let cw = c.x1 - c.x0, ch = c.y1 - c.y0
    return PixelBox(x0: c.x0 + jb.left * cw, y0: c.y0 + jb.top * ch, x1: c.x0 + jb.right * cw, y1: c.y0 + jb.bottom * ch)
}

/// Step 4: the exact multipart request for POST https://api.typesafe.ai/v1/systemone
func jevRequest(frameJPEG: Data, enrolled: [(name: String, jpeg: Data)]) -> (json: [String: Any], body: Data, boundary: String) {
    let frameRef = "frame-" + UUID().uuidString
    var assets: [String: Any] = [frameRef: ["type": "image", "part": "frame"]]
    var criteria: [String: Any] = [:]
    var parts: [(String, Data)] = [("frame", frameJPEG)]
    for (i, e) in enrolled.enumerated() {
        let ref = "jar\(i)-" + UUID().uuidString
        assets[ref] = ["type": "image", "part": "jar\(i)"]
        criteria[e.name] = "the jar shown in \(ref)"                  // image reference inside the description
        parts.append(("jar\(i)", e.jpeg))
    }
    criteria["none"] = "none of these jars, or no jar is being touched"
    let json: [String: Any] = [
        "model": "jev-preview",
        "state": ["frame": frameRef],
        "assets": assets,
        "questions": [
            "touching_jar": ["type": "noul", "instructions": "Is the hand in `frame` touching a jar or bottle?"],
            "touched_box": ["type": "box", "instructions": "the jar or bottle that the hand is touching in `frame`"],
            "which_jar": ["type": "choice", "instructions": "Which jar is the hand touching in `frame`?", "criteria": criteria],
        ],
    ]
    let boundary = "marco-" + UUID().uuidString
    var body = Data()
    func add(_ s: String) { body.append(s.data(using: .utf8)!) }
    add("--\(boundary)\r\nContent-Disposition: form-data; name=\"request\"\r\nContent-Type: application/json\r\n\r\n")
    body.append(try! JSONSerialization.data(withJSONObject: json, options: [.prettyPrinted, .sortedKeys]))
    add("\r\n")
    for (name, data) in parts {
        add("--\(boundary)\r\nContent-Disposition: form-data; name=\"\(name)\"; filename=\"\(name).jpg\"\r\nContent-Type: image/jpeg\r\n\r\n")
        body.append(data); add("\r\n")
    }
    add("--\(boundary)--\r\n")
    return (json, body, boundary)
}

/// On the phone: send it (needs a key; keep the key on a small relay server, per TypeSafe's docs).
func sendToJev(body: Data, boundary: String, apiKey: String) async throws -> Data {
    var req = URLRequest(url: URL(string: "https://api.typesafe.ai/v1/systemone")!)
    req.httpMethod = "POST"
    req.setValue("Bearer \(apiKey)", forHTTPHeaderField: "Authorization")
    req.setValue("true", forHTTPHeaderField: "TypeSafe-Danger-Zone-Images")
    req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
    req.httpBody = body
    return try await URLSession.shared.data(for: req).0
}

/// Parse a Box answer from Jev's JSON response.
func parseBox(_ response: Data, id: String) -> (JevBox, Double)? {
    guard let j = try? JSONSerialization.jsonObject(with: response) as? [String: Any],
          let a = (j["answers"] as? [String: Any])?[id] as? [String: Any],
          let b = a["box"] as? [String: Double] else { return nil }
    return (JevBox(top: b["top"]!, bottom: b["bottom"]!, left: b["left"]!, right: b["right"]!), a["confidence"] as? Double ?? 0)
}

/// Step 6 + drawing: boxes on an image (top-left pixel coordinates).
func draw(_ cg: CGImage, boxes: [(PixelBox, NSColor, String)], dots: [CGPoint] = [], out: String) {
    let W = CGFloat(cg.width), H = CGFloat(cg.height)
    let rep = NSBitmapImageRep(cgImage: cg)
    NSGraphicsContext.saveGraphicsState()
    NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
    let lw = max(3, W / 300)
    for p in dots {  // flip to AppKit's bottom-left origin for drawing
        NSColor.systemBlue.setFill()
        NSBezierPath(ovalIn: NSRect(x: p.x - lw * 1.5, y: H - p.y - lw * 1.5, width: lw * 3, height: lw * 3)).fill()
    }
    for (b, color, label) in boxes {
        color.setStroke()
        let r = NSRect(x: b.x0, y: H - b.y1, width: b.x1 - b.x0, height: b.y1 - b.y0)
        let path = NSBezierPath(roundedRect: r, xRadius: lw * 2, yRadius: lw * 2); path.lineWidth = lw; path.stroke()
        let attrs: [NSAttributedString.Key: Any] = [.font: NSFont.boldSystemFont(ofSize: max(18, W / 45)), .foregroundColor: NSColor.white,
                                                    .backgroundColor: color]
        (" " + label + " " as NSString).draw(at: NSPoint(x: b.x0, y: H - b.y0 + lw), withAttributes: attrs)
    }
    NSGraphicsContext.restoreGraphicsState()
    try! rep.representation(using: .jpeg, properties: [.compressionFactor: 0.85])!.write(to: URL(fileURLWithPath: out))
}

// ---------------------------------------------------------------- run on a real photo
let args = CommandLine.arguments
let img = NSImage(contentsOfFile: args[1])!.cgImage(forProposedRect: nil, context: nil, hints: nil)!
let outDir = args[2]
guard let (joints, region) = try touchRegion(img) else { print("no hand found"); exit(0) }
let touchCrop = crop(img, region)
let frameJPEG = jpeg(touchCrop)
try frameJPEG.write(to: URL(fileURLWithPath: "\(outDir)/frame_for_jev.jpg"))

var enrolled: [(String, Data)] = []
var enrolledBoxes: [(PixelBox, NSColor, String)] = []
for spec in args.dropFirst(3) {
    let kv = spec.split(separator: "="), v = kv[1].split(separator: ",").map { CGFloat(Double($0)!) }
    let b = PixelBox(x0: v[0], y0: v[1], x1: v[2], y1: v[3])
    enrolled.append((String(kv[0]), jpeg(crop(img, b), maxSide: 384)))
    enrolledBoxes.append((b, .systemGreen, String(kv[0])))
}
let (json, body, boundary) = jevRequest(frameJPEG: frameJPEG, enrolled: enrolled)
try JSONSerialization.data(withJSONObject: json, options: [.prettyPrinted, .sortedKeys]).write(to: URL(fileURLWithPath: "\(outDir)/jev_request.json"))
try body.write(to: URL(fileURLWithPath: "\(outDir)/jev_request.multipart"))
print("hand: \(joints.count) joints; touch crop \(Int(region.x1 - region.x0))x\(Int(region.y1 - region.y0)) px -> JPEG \(frameJPEG.count / 1024) KB")
print("Jev request: \(body.count / 1024) KB multipart, \(enrolled.count) enrolled jar photos as Choice options, boundary \(boundary)")

// Stand-in for a Jev Box answer (fractions of the crop) so the drawing/mapping path is exercised end to end.
// On the phone this comes from parseBox(response, id: "touched_box").
let standIn = JevBox(top: 0.30, bottom: 0.92, left: 0.18, right: 0.62)
let full = toFullImage(standIn, crop: region)
draw(img, boxes: [(region, .systemOrange, "touch crop sent to Jev")] + enrolledBoxes + [(full, .systemPink, "Box answer (stand-in)")],
     dots: joints, out: "\(outDir)/overlay_full.jpg")
// Guardian photo for Photon: the crop with the touched jar highlighted.
let local = PixelBox(x0: standIn.left * CGFloat(touchCrop.width), y0: standIn.top * CGFloat(touchCrop.height),
                     x1: standIn.right * CGFloat(touchCrop.width), y1: standIn.bottom * CGFloat(touchCrop.height))
draw(touchCrop, boxes: [(local, .systemPink, "What is this jar?")], out: "\(outDir)/guardian_photo.jpg")
print("wrote frame_for_jev.jpg, jev_request.json, jev_request.multipart, overlay_full.jpg, guardian_photo.jpg")
