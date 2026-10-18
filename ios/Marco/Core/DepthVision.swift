import CoreGraphics
import CoreVideo
import Foundation
import simd

// The LiDAR view's logic that needs no GPU and no ARKit, so `sh ios/check.sh` tests it on the Mac: the depth colour
// scale, reading the depth under a point on screen, projecting world points onto the screen, and which remembered
// items to label. LiDAR/LiDARRenderer.swift and LiDAR/LiDARShaders.metal draw with the same conventions.

// MARK: - Colour scale

/// LiDAR depth as colour on Google's Turbo scale: near is warm (red), far is cool (blue).
enum DepthPalette {
    static let nearM: Float = 0.2
    static let farM: Float = 5.0          // ARKit's LiDAR range (poc/research/arkit_lidar_facts.md)

    /// 0 at `near`, 1 at `far`, clamped; non-finite depth counts as far.
    static func normalized(_ depthM: Float, near: Float = nearM, far: Float = farM) -> Float {
        guard depthM.isFinite else { return 1 }
        return min(max((depthM - near) / (far - near), 0), 1)
    }

    /// Turbo, the polynomial fit used in shaders. x in 0...1: 0 is dark blue, 1 is dark red.
    static func turbo(_ x: Float) -> SIMD3<Float> {
        let t = min(max(x, 0), 1)
        let v4 = SIMD4<Float>(1, t, t * t, t * t * t)
        let v2 = SIMD2<Float>(v4.z * v4.z, v4.w * v4.z)
        let r = simd_dot(v4, SIMD4(0.13572138, 4.61539260, -42.66032258, 132.13108234)) + simd_dot(v2, SIMD2(-152.94239396, 59.28637943))
        let g = simd_dot(v4, SIMD4(0.09140261, 2.19418839, 4.84296658, -14.18503333)) + simd_dot(v2, SIMD2(4.27729857, 2.82956604))
        let b = simd_dot(v4, SIMD4(0.10667330, 12.64194608, -60.58204836, 110.36276771)) + simd_dot(v2, SIMD2(-89.90310912, 27.34824973))
        return simd_clamp(SIMD3(r, g, b), SIMD3(repeating: 0), SIMD3(repeating: 1))
    }

    /// The colour the LiDAR view paints a depth with (LiDARShaders.metal uses the same formula).
    static func color(depthM: Float) -> SIMD3<Float> { turbo(1 - normalized(depthM)) }
}

// MARK: - Depth under a point

/// The depth under a point: the median of the valid, confident LiDAR pixels in a small window, so one flying pixel
/// at an edge (poc/research: edge RMSE 27 cm) doesn't decide the reading.
enum DepthProbe {
    static func median(depth: [Float], confidence: [UInt8]?, width: Int, height: Int, u: Int, v: Int,
                       radius: Int = 2, minConfidence: UInt8 = 1) -> Float? {
        guard width > 0, height > 0, (0..<width).contains(u), (0..<height).contains(v) else { return nil }
        var vals: [Float] = []
        for y in max(0, v - radius)...min(height - 1, v + radius) {
            for x in max(0, u - radius)...min(width - 1, u + radius) {
                let i = y * width + x
                let d = depth[i]
                guard d.isFinite, d > 0.05, d < 8 else { continue }
                if let c = confidence, c[i] < minConfidence { continue }
                vals.append(d)
            }
        }
        guard !vals.isEmpty else { return nil }
        vals.sort()
        return vals[vals.count / 2]
    }

    /// The same, straight from ARKit's buffers (Float32 depth, UInt8 confidence) at a normalized image point
    /// (origin top-left, sensor orientation). Rows may be padded, so it reads row by row.
    static func median(depth: CVPixelBuffer, confidence: CVPixelBuffer?, at p: CGPoint,
                       radius: Int = 2, minConfidence: UInt8 = 1) -> Float? {
        guard CVPixelBufferGetPixelFormatType(depth) == kCVPixelFormatType_DepthFloat32 else { return nil }
        let w = CVPixelBufferGetWidth(depth), h = CVPixelBufferGetHeight(depth)
        let u = Int((p.x * CGFloat(w)).rounded(.down)), v = Int((p.y * CGFloat(h)).rounded(.down))
        guard (0..<w).contains(u), (0..<h).contains(v) else { return nil }
        let x0 = max(0, u - radius), x1 = min(w - 1, u + radius), y0 = max(0, v - radius), y1 = min(h - 1, v + radius)
        let ww = x1 - x0 + 1, hh = y1 - y0 + 1
        var d = [Float](repeating: .nan, count: ww * hh)
        var c: [UInt8]? = nil
        CVPixelBufferLockBaseAddress(depth, .readOnly)
        if let base = CVPixelBufferGetBaseAddress(depth) {
            let row = CVPixelBufferGetBytesPerRow(depth)
            for y in 0..<hh {
                let src = (base + (y0 + y) * row).assumingMemoryBound(to: Float32.self)
                for x in 0..<ww { d[y * ww + x] = src[x0 + x] }
            }
        }
        CVPixelBufferUnlockBaseAddress(depth, .readOnly)
        if let conf = confidence, CVPixelBufferGetWidth(conf) == w, CVPixelBufferGetHeight(conf) == h {
            var cc = [UInt8](repeating: 0, count: ww * hh)
            CVPixelBufferLockBaseAddress(conf, .readOnly)
            if let base = CVPixelBufferGetBaseAddress(conf) {
                let row = CVPixelBufferGetBytesPerRow(conf)
                for y in 0..<hh {
                    let src = (base + (y0 + y) * row).assumingMemoryBound(to: UInt8.self)
                    for x in 0..<ww { cc[y * ww + x] = src[x0 + x] }
                }
            }
            CVPixelBufferUnlockBaseAddress(conf, .readOnly)
            c = cc
        }
        return median(depth: d, confidence: c, width: ww, height: hh, u: u - x0, v: v - y0,
                      radius: radius, minConfidence: minConfidence)
    }
}

/// How much of the LiDAR map is usable right now, for the view's status line.
struct DepthStats: Equatable {
    var validFraction = 0.0           // finite, inside the LiDAR range
    var highFraction = 0.0            // ...and high confidence
    var nearestM: Float?              // 5th percentile of valid depth: the closest real surface, not one stray pixel
    var medianM: Float?

    static func of(depth: [Float], confidence: [UInt8]?, step: Int = 4) -> DepthStats {
        var valid: [Float] = []
        var high = 0, total = 0
        var i = 0
        while i < depth.count {
            total += 1
            let d = depth[i]
            if d.isFinite, d > 0.05, d <= DepthPalette.farM {
                valid.append(d)
                if let c = confidence, c[i] >= 2 { high += 1 }
            }
            i += max(1, step)
        }
        guard total > 0 else { return DepthStats() }
        valid.sort()
        return DepthStats(validFraction: Double(valid.count) / Double(total),
                          highFraction: confidence == nil ? 0 : Double(high) / Double(total),
                          nearestM: valid.isEmpty ? nil : valid[valid.count / 20],
                          medianM: valid.isEmpty ? nil : valid[valid.count / 2])
    }
}

// MARK: - Camera and screen geometry

/// Pinhole maths in ARKit's camera conventions (+x right, +y up, looking down -z; intrinsics for the sensor-oriented
/// image), the same as server/marco/geometry.py. Image points are normalized, origin top-left, sensor orientation.
enum CameraMath {
    static func unproject(_ p: CGPoint, depthM d: Float, intrinsics K: simd_float3x3, imageSize: CGSize,
                          cameraToWorld T: simd_float4x4) -> SIMD3<Float> {
        let px = Float(p.x * imageSize.width), py = Float(p.y * imageSize.height)
        let fx = K.columns.0.x, fy = K.columns.1.y, cx = K.columns.2.x, cy = K.columns.2.y
        let pc = SIMD4<Float>((px - cx) / fx * d, -(py - cy) / fy * d, -d, 1)
        let w = T * pc
        return SIMD3(w.x, w.y, w.z)
    }

    /// World point to normalized image point plus its distance along the optical axis; nil when behind the camera.
    static func project(_ w: SIMD3<Float>, intrinsics K: simd_float3x3, imageSize: CGSize,
                        cameraToWorld T: simd_float4x4) -> (point: CGPoint, depthM: Float)? {
        let pc = simd_inverse(T) * SIMD4(w.x, w.y, w.z, 1)
        let z = -pc.z
        guard z > 0.05 else { return nil }
        let fx = K.columns.0.x, fy = K.columns.1.y, cx = K.columns.2.x, cy = K.columns.2.y
        let px = cx + fx * pc.x / z, py = cy - fy * pc.y / z
        return (CGPoint(x: CGFloat(px) / imageSize.width, y: CGFloat(py) / imageSize.height), z)
    }
}

/// Between the screen and the camera image. `displayTransform` is ARFrame.displayTransform(for:viewportSize:): it
/// maps normalized image coordinates to normalized view coordinates (rotation for portrait plus aspect fill).
enum ViewMapping {
    static func imagePoint(fromView v: CGPoint, viewSize: CGSize, displayTransform t: CGAffineTransform) -> CGPoint {
        CGPoint(x: v.x / viewSize.width, y: v.y / viewSize.height).applying(t.inverted())
    }

    static func viewPoint(fromImage p: CGPoint, viewSize: CGSize, displayTransform t: CGAffineTransform) -> CGPoint {
        let n = p.applying(t)
        return CGPoint(x: n.x * viewSize.width, y: n.y * viewSize.height)
    }
}

// MARK: - Remembered items on screen

/// An item the server remembers, in the current map's world frame (GET /v1/items, then events).
struct ItemMark: Equatable, Identifiable {
    let id: String
    var name: String
    var position: SIMD3<Float>
    var surface: String?
    var state: String?

    /// Positions that are stale (another map) or gone aren't drawn: they would point at the wrong place.
    var shown: Bool { !["stale", "missing", "picked_up"].contains(state ?? "") }
}

struct PlacedItem: Equatable, Identifiable {
    let id: String
    let name: String
    let text: String
    let screen: CGPoint               // view points
    let distanceM: Float              // straight line from the camera
    let isTarget: Bool
}

enum ItemOverlay {
    /// "keys · 1.6 m · table"
    static func text(name: String, distanceM: Float, surface: String?) -> String {
        [name, String(format: "%.1f m", distanceM), surface].compactMap { $0 }.joined(separator: " · ")
    }

    /// The marks in front of the camera and on screen, the guidance target first, then nearest first.
    static func place(_ marks: [ItemMark], cameraToWorld T: simd_float4x4, intrinsics K: simd_float3x3, imageSize: CGSize,
                      viewSize: CGSize, displayTransform: CGAffineTransform, targetId: String?,
                      margin: CGFloat = 24, limit: Int = 8) -> (shown: [PlacedItem], outOfView: Int) {
        let cam = SIMD3(T.columns.3.x, T.columns.3.y, T.columns.3.z)
        var placed: [PlacedItem] = []
        var out = 0
        for m in marks where m.shown {
            guard let pr = CameraMath.project(m.position, intrinsics: K, imageSize: imageSize, cameraToWorld: T) else {
                out += 1
                continue
            }
            let s = ViewMapping.viewPoint(fromImage: pr.point, viewSize: viewSize, displayTransform: displayTransform)
            guard s.x >= margin, s.x <= viewSize.width - margin, s.y >= margin, s.y <= viewSize.height - margin else {
                out += 1
                continue
            }
            let dist = simd_distance(cam, m.position)
            placed.append(PlacedItem(id: m.id, name: m.name, text: text(name: m.name, distanceM: dist, surface: m.surface),
                                     screen: s, distanceM: dist, isTarget: m.id == targetId))
        }
        placed.sort { ($0.isTarget ? 0 : 1, $0.distanceM) < ($1.isTarget ? 0 : 1, $1.distanceM) }
        out += max(0, placed.count - limit)
        return (Array(placed.prefix(limit)), out)
    }

    /// For VoiceOver: "Straight ahead, 1.4 meters. Keys, 1.6 meters, on the left. 2 more items out of view."
    static func spoken(centerM: Float?, items: [PlacedItem], outOfView: Int, viewWidth: CGFloat) -> String {
        var parts: [String] = []
        parts.append(centerM.map { String(format: "Straight ahead, %.1f meters.", $0) } ?? "No depth straight ahead.")
        for it in items {
            let side = it.screen.x < viewWidth / 3 ? "on the left" : it.screen.x > viewWidth * 2 / 3 ? "on the right" : "ahead"
            parts.append(String(format: "%@, %.1f meters, %@.", it.name.prefix(1).uppercased() + it.name.dropFirst(), it.distanceM, side))
        }
        if outOfView > 0 { parts.append("\(outOfView) more item\(outOfView == 1 ? "" : "s") out of view.") }
        return parts.joined(separator: " ")
    }
}

// MARK: - Point cloud

/// Adds a frame's LiDAR points to the room cloud only after the camera moved or turned, so holding still doesn't
/// flood the buffer with the same surfaces.
struct PointAccumulationGate {
    var minMoveM: Float = 0.02
    var minTurnDeg: Float = 2
    private var last: simd_float4x4?

    init(minMoveM: Float = 0.02, minTurnDeg: Float = 2) {
        self.minMoveM = minMoveM
        self.minTurnDeg = minTurnDeg
    }

    mutating func shouldAdd(_ T: simd_float4x4) -> Bool {
        guard let l = last else {
            last = T
            return true
        }
        let move = simd_distance(SIMD3(T.columns.3.x, T.columns.3.y, T.columns.3.z), SIMD3(l.columns.3.x, l.columns.3.y, l.columns.3.z))
        let a = simd_normalize(SIMD3(T.columns.2.x, T.columns.2.y, T.columns.2.z))
        let b = simd_normalize(SIMD3(l.columns.2.x, l.columns.2.y, l.columns.2.z))
        let turn = acos(min(max(simd_dot(a, b), -1), 1)) * 180 / .pi
        guard move >= minMoveM || turn >= minTurnDeg else { return false }
        last = T
        return true
    }

    mutating func reset() { last = nil }
}
