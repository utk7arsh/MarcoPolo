import CoreVideo
import Foundation

/// Byte formats of docs/INTERFACES.md §2-3: float16 little-endian depth, DEFLATE compression, the hand patches,
/// and the multipart body of the uploads.
enum Wire {
    static let depthWidth = 256
    static let depthHeight = 192

    static func float16LE(_ values: [Float]) -> Data {
        let bits = values.map { Float16($0).bitPattern.littleEndian }
        return bits.withUnsafeBytes { Data($0) }
    }

    /// Apple's .zlib is raw DEFLATE (RFC 1951, no zlib header). The server accepts it and real zlib.
    static func deflate(_ data: Data) throws -> Data {
        try (data as NSData).compressed(using: .zlib) as Data
    }

    static func inflate(_ data: Data) throws -> Data {
        try (data as NSData).decompressed(using: .zlib) as Data
    }

    /// The `depth` part: float16 metres, 256x192, row 0 = top of the sensor image.
    static func depthPayload(_ depth: [Float]) throws -> Data { try deflate(float16LE(depth)) }

    /// The `confidence` part: ARKit confidence 0/1/2 per depth pixel.
    static func confidencePayload(_ conf: [UInt8]) throws -> Data { try deflate(Data(conf)) }

    /// The hand message's patches: a size x size window of the depth and confidence maps around each joint's
    /// depth pixel u = floor(x * w), v = floor((1 - y) * h) (Vision's origin is bottom-left, the maps' top-left),
    /// padded with NaN and 0 outside the map. Joint-major, then row, then column.
    static func patches(depth: [Float], conf: [UInt8], width w: Int, height h: Int, joints: [Joint],
                        size: Int = HandJoints.patch) -> (depth: [Float], conf: [UInt8]) {
        let r = size / 2
        var dp = [Float](repeating: .nan, count: joints.count * size * size)
        var cp = [UInt8](repeating: 0, count: joints.count * size * size)
        for (j, p) in joints.enumerated() where p.x.isFinite && p.y.isFinite {
            let u = Int((p.x * Double(w)).rounded(.down))
            let v = Int(((1 - p.y) * Double(h)).rounded(.down))
            for dy in -r...r {
                for dx in -r...r {
                    let uu = u + dx, vv = v + dy
                    guard uu >= 0, uu < w, vv >= 0, vv < h else { continue }
                    let k = j * size * size + (dy + r) * size + (dx + r)
                    dp[k] = depth[vv * w + uu]
                    cp[k] = conf[vv * w + uu]
                }
            }
        }
        return (dp, cp)
    }

    /// The same patches read straight from ARKit's buffers (Float32 depth, UInt8 confidence): only the 21 windows,
    /// instead of copying both whole 256x192 maps for every hand message. Byte-identical to `patches(depth:conf:...)`.
    static func patches(depth: CVPixelBuffer, conf: CVPixelBuffer, joints: [Joint],
                        size: Int = HandJoints.patch) -> (depth: [Float], conf: [UInt8])? {
        guard CVPixelBufferGetPixelFormatType(depth) == kCVPixelFormatType_DepthFloat32,
              CVPixelBufferGetPixelFormatType(conf) == kCVPixelFormatType_OneComponent8 else { return nil }
        let w = CVPixelBufferGetWidth(depth), h = CVPixelBufferGetHeight(depth)
        guard CVPixelBufferGetWidth(conf) == w, CVPixelBufferGetHeight(conf) == h else { return nil }
        CVPixelBufferLockBaseAddress(depth, .readOnly)
        CVPixelBufferLockBaseAddress(conf, .readOnly)
        defer {
            CVPixelBufferUnlockBaseAddress(conf, .readOnly)
            CVPixelBufferUnlockBaseAddress(depth, .readOnly)
        }
        guard let db = CVPixelBufferGetBaseAddress(depth), let cb = CVPixelBufferGetBaseAddress(conf) else { return nil }
        let dRow = CVPixelBufferGetBytesPerRow(depth), cRow = CVPixelBufferGetBytesPerRow(conf)
        let r = size / 2
        var dp = [Float](repeating: .nan, count: joints.count * size * size)
        var cp = [UInt8](repeating: 0, count: joints.count * size * size)
        for (j, p) in joints.enumerated() where p.x.isFinite && p.y.isFinite {
            let u = Int((p.x * Double(w)).rounded(.down))
            let v = Int(((1 - p.y) * Double(h)).rounded(.down))
            for dy in -r...r {
                let vv = v + dy
                guard vv >= 0, vv < h else { continue }
                let drow = (db + vv * dRow).assumingMemoryBound(to: Float32.self)
                let crow = (cb + vv * cRow).assumingMemoryBound(to: UInt8.self)
                for dx in -r...r {
                    let uu = u + dx
                    guard uu >= 0, uu < w else { continue }
                    let k = j * size * size + (dy + r) * size + (dx + r)
                    dp[k] = drow[uu]
                    cp[k] = crow[uu]
                }
            }
        }
        return (dp, cp)
    }

    struct FilePart {
        var field: String
        var filename: String
        var contentType: String
        var data: Data
    }

    /// multipart/form-data body; send with Content-Type "multipart/form-data; boundary=<boundary>".
    static func multipart(boundary: String, fields: [(String, String)], files: [FilePart]) -> Data {
        var body = Data()
        func add(_ s: String) { body.append(s.data(using: .utf8)!) }
        for (name, value) in fields {
            add("--\(boundary)\r\nContent-Disposition: form-data; name=\"\(name)\"\r\n\r\n\(value)\r\n")
        }
        for f in files {
            add("--\(boundary)\r\nContent-Disposition: form-data; name=\"\(f.field)\"; filename=\"\(f.filename)\"\r\n")
            add("Content-Type: \(f.contentType)\r\n\r\n")
            body.append(f.data)
            add("\r\n")
        }
        add("--\(boundary)--\r\n")
        return body
    }
}

/// At most one upload in flight; while it runs only the newest waiting item is kept (latest frame wins, §3.1).
struct LatestWins<T> {
    private(set) var inFlight = false
    private(set) var pending: T?
    private(set) var dropped = 0

    /// Returns the item to start now, or nil if it was queued behind the running one.
    mutating func offer(_ x: T) -> T? {
        if !inFlight {
            inFlight = true
            return x
        }
        if pending != nil { dropped += 1 }
        pending = x
        return nil
    }

    /// Call when the running upload finishes. Returns the next item to start, if one is waiting.
    mutating func finished() -> T? {
        if let p = pending {
            pending = nil
            return p
        }
        inFlight = false
        return nil
    }
}

/// Picks messages out of the 60 Hz ARKit stream at a target rate (frames 1/s, poses 10/s, hands 15/s).
struct Throttle {
    let interval: Double
    let slack: Double
    private(set) var last = -Double.infinity

    /// slack: accept a frame this early, so a 60 Hz source with jitter still gives the full rate.
    init(hz: Double, slack: Double = 0.004) {
        interval = 1 / hz
        self.slack = slack
    }

    mutating func ready(_ now: Double) -> Bool {
        guard now - last >= interval - slack else { return false }
        last = now
        return true
    }
}
