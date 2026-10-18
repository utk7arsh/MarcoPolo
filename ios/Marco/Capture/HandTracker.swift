import CoreVideo
import Foundation
import simd
import Vision

/// Vision hand pose on the sensor image. Orientation .up keeps the joints in the sensor frame, which is what the
/// server expects (docs/INTERFACES.md §3.2; if accuracy is poor in the hour-one test, try .right and tell Vedant).
final class HandTracker {
    static let visionJoints: [VNHumanHandPoseObservation.JointName] = [
        .wrist, .thumbCMC, .thumbMP, .thumbIP, .thumbTip, .indexMCP, .indexPIP, .indexDIP, .indexTip,
        .middleMCP, .middlePIP, .middleDIP, .middleTip, .ringMCP, .ringPIP, .ringDIP, .ringTip,
        .littleMCP, .littlePIP, .littleDIP, .littleTip]

    private let request: VNDetectHumanHandPoseRequest = {
        let r = VNDetectHumanHandPoseRequest()
        r.maximumHandCount = 2
        return r
    }()

    /// The hand whose index fingertip Vision is surest of; nil when no hand is in view.
    func detect(_ pixelBuffer: CVPixelBuffer) throws -> (joints: [Joint], chirality: String)? {
        let handler = VNImageRequestHandler(cvPixelBuffer: pixelBuffer, orientation: .up, options: [:])
        try handler.perform([request])
        var best: (joints: [Joint], chirality: String, tip: Double)?
        for obs in request.results ?? [] {
            let points = try obs.recognizedPoints(.all)
            let joints = zip(HandJoints.names, Self.visionJoints).map { name, j -> Joint in
                guard let p = points[j] else { return Joint(name: name, x: 0, y: 0, conf: 0) }
                return Joint(name: name, x: Double(p.location.x), y: Double(p.location.y), conf: Double(p.confidence))
            }
            let tip = joints[8].conf
            let chirality: String
            switch obs.chirality {
            case .left: chirality = "left"
            case .right: chirality = "right"
            default: chirality = "unknown"
            }
            if best == nil || tip > best!.tip { best = (joints, chirality, tip) }
        }
        return best.map { ($0.joints, $0.chirality) }
    }
}

extension HandMsg {
    /// The hand message for one ARFrame: joints plus 9x9 depth and confidence patches around each of them.
    static func make(sessionId: String, mapId: String, t: Double, transform: simd_float4x4, joints: [Joint],
                     chirality: String, depth: [Float], conf: [UInt8], width: Int, height: Int) -> HandMsg {
        let p = Wire.patches(depth: depth, conf: conf, width: width, height: height, joints: joints)
        return HandMsg(session_id: sessionId, map_id: mapId, t_device: t, camera_transform: Geo.flat(transform),
                       chirality: chirality, joints: joints,
                       depth_patches_f16_b64: Wire.float16LE(p.depth).base64EncodedString(),
                       conf_patches_u8_b64: Data(p.conf).base64EncodedString())
    }
}
