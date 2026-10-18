import CoreImage
import CoreVideo
import Foundation
import ImageIO

/// The ARFrame's buffers as the wire payloads of docs/INTERFACES.md §3.1.
final class FrameEncoder {
    private let context = CIContext()
    private let srgb = CGColorSpace(name: CGColorSpace.sRGB)!

    /// capturedImage (YCbCr, the sensor's landscape orientation) -> JPEG scaled by jpeg_scale, with no orientation
    /// tag. Never rotate it: the server turns it upright from gravity and maps boxes back to sensor pixels.
    func jpeg(_ pixelBuffer: CVPixelBuffer, scale: Double = Config.jpegScale, quality: Double = Config.jpegQuality) -> Data? {
        let image = CIImage(cvPixelBuffer: pixelBuffer).transformed(by: CGAffineTransform(scaleX: scale, y: scale))
        let q = CIImageRepresentationOption(rawValue: kCGImageDestinationLossyCompressionQuality as String)
        return context.jpegRepresentation(of: image, colorSpace: srgb, options: [q: quality])
    }

    /// A one-plane CVPixelBuffer (Float32 depth in metres, or UInt8 confidence) as a dense row-major array, row 0 at
    /// the top of the sensor image. Rows in the buffer may be padded, so copy row by row.
    static func plane<T>(_ pb: CVPixelBuffer, as _: T.Type) -> (values: [T], width: Int, height: Int) {
        CVPixelBufferLockBaseAddress(pb, .readOnly)
        defer { CVPixelBufferUnlockBaseAddress(pb, .readOnly) }
        let w = CVPixelBufferGetWidth(pb), h = CVPixelBufferGetHeight(pb), rowBytes = CVPixelBufferGetBytesPerRow(pb)
        guard let base = CVPixelBufferGetBaseAddress(pb) else { return ([], 0, 0) }
        var out = [T]()
        out.reserveCapacity(w * h)
        for y in 0..<h {
            let row = (base + y * rowBytes).assumingMemoryBound(to: T.self)
            out.append(contentsOf: UnsafeBufferPointer(start: row, count: w))
        }
        return (out, w, h)
    }
}
