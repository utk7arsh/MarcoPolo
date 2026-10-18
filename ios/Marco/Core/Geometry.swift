import Foundation
import simd

/// The server's geometry conventions (server/marco/geometry.py), so the phone and the server agree on every angle.
/// World: ARKit, metres, +y up. Heading: 0 = world -z, +90 = world +x (turning right).
enum Geo {
    /// simd matrices as the wire wants them: column-major, [c0.x, c0.y, c0.z, c0.w, c1.x, ...].
    static func flat(_ m: simd_float4x4) -> [Float] {
        [m.columns.0, m.columns.1, m.columns.2, m.columns.3].flatMap { [$0.x, $0.y, $0.z, $0.w] }
    }

    static func flat(_ m: simd_float3x3) -> [Float] {
        [m.columns.0, m.columns.1, m.columns.2].flatMap { [$0.x, $0.y, $0.z] }
    }

    static func position(_ T: simd_float4x4) -> SIMD3<Float> {
        SIMD3(T.columns.3.x, T.columns.3.y, T.columns.3.z)
    }

    static func vec(_ a: [Float]?) -> SIMD3<Float>? {
        guard let a, a.count == 3 else { return nil }
        return SIMD3(a[0], a[1], a[2])
    }

    /// Heading of the camera's optical axis (its -z) on the floor.
    static func headingDeg(_ T: simd_float4x4) -> Double {
        let f = -T.columns.2
        return atan2(Double(f.x), Double(-f.z)) * 180 / .pi
    }

    static func wrap180(_ a: Double) -> Double {
        let r = (a + 180).truncatingRemainder(dividingBy: 360)
        return (r < 0 ? r + 360 : r) - 180
    }

    /// Target direction relative to a heading: 0 ahead, +90 right, -90 left, +-180 behind.
    static func relativeAzimuthDeg(from user: SIMD3<Float>, headingDeg h: Double, to target: SIMD3<Float>) -> Double {
        let d = target - user
        return wrap180(atan2(Double(d.x), Double(-d.z)) * 180 / .pi - h)
    }

    /// 12 = ahead, 3 = right, 6 = behind, 9 = left. Rounds half to even, like the server (Python's round).
    static func clockPosition(_ relAz: Double) -> Int {
        var c = Int((relAz / 30).rounded(.toNearestOrEven)) % 12
        if c < 0 { c += 12 }
        return c == 0 ? 12 : c
    }

    static func steps(_ horizontalM: Double, stepM: Double = 0.7) -> Int {
        max(1, Int((horizontalM / stepM).rounded(.toNearestOrEven)))
    }

    static func horizontalDistance(_ a: SIMD3<Float>, _ b: SIMD3<Float>) -> Double {
        let d = b - a
        return Double(hypot(d.x, d.z))
    }

    /// Where a world point sits for a listener at `ear` facing `headYawDeg`: x right, y up, -z ahead (the
    /// coordinates of AVAudioEnvironmentNode with an unrotated listener at the origin).
    static func listenerRelative(ear: SIMD3<Float>, headYawDeg: Double, target: SIMD3<Float>) -> SIMD3<Float> {
        let d = target - ear
        let h = Float(headYawDeg * .pi / 180)
        let fwd = SIMD3<Float>(sin(h), 0, -cos(h))
        let right = SIMD3<Float>(cos(h), 0, sin(h))
        return SIMD3(simd_dot(d, right), d.y, -simd_dot(d, fwd))
    }
}
