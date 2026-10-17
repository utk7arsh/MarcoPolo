// Rasterise an SVG with AppKit (NSImage reads SVG on recent macOS). Usage: svg2png in.svg out.png [width]
import AppKit
let a = CommandLine.arguments
guard let img = NSImage(contentsOf: URL(fileURLWithPath: a[1])) else { print("cannot load"); exit(1) }
let w = a.count > 3 ? Double(a[3])! : Double(img.size.width)
let h = w * Double(img.size.height) / Double(img.size.width)
let rep = NSBitmapImageRep(bitmapDataPlanes: nil, pixelsWide: Int(w), pixelsHigh: Int(h), bitsPerSample: 8,
                           samplesPerPixel: 4, hasAlpha: true, isPlanar: false, colorSpaceName: .deviceRGB, bytesPerRow: 0, bitsPerPixel: 0)!
NSGraphicsContext.saveGraphicsState()
NSGraphicsContext.current = NSGraphicsContext(bitmapImageRep: rep)
img.draw(in: NSRect(x: 0, y: 0, width: w, height: h))
NSGraphicsContext.restoreGraphicsState()
try rep.representation(using: .png, properties: [:])!.write(to: URL(fileURLWithPath: a[2]))
print("ok \(Int(w))x\(Int(h))")
