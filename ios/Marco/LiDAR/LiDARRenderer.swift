import ARKit
import MetalKit
import simd
import UIKit

enum LiDARMode: String, CaseIterable, Identifiable {
    case camera = "Camera", depth = "Depth", points = "Points"
    var id: String { rawValue }
}

/// What the screen overlays, refreshed about 10 times a second from the frame being drawn.
struct LiDARReadout: Equatable {
    var centerM: Float?
    var items: [PlacedItem] = []
    var outOfView = 0
    var stats = DepthStats()
    var tracking = "starting"
    var trackingNormal = false
    var hasDepth = false
    var pin: CGPoint?                 // view points
    var pinM: Float?
    var points = 0
    var fps = 0
}

enum LiDARError: LocalizedError {
    case noGPU
    case missingFunction(String)

    var errorDescription: String? {
        switch self {
        case .noGPU: return "This iPhone has no Metal GPU available."
        case .missingFunction(let f): return "Shader function \(f) is missing."
        }
    }
}

/// Draws the shared ARSession's current frame: the camera, the LiDAR heat map, and a room point cloud kept on the GPU.
/// It only reads `session.currentFrame`. It never runs, configures or becomes the delegate of the session (the capture
/// pipeline owns it), so this screen can't disturb frame upload. Runs on the main thread (MTKView's draw loop).
final class LiDARRenderer: NSObject, MTKViewDelegate {
    static let capacity = 600_000                     // points kept; the oldest are overwritten (19 MB)
    static let gridW = 128, gridH = 96                // LiDAR samples per added frame: every second depth pixel

    var mode: LiDARMode = .depth
    var overlay: Float = 0.6
    var highConfidenceOnly = false
    var marks: [ItemMark] = []
    var targetId: String?
    var onReadout: ((LiDARReadout) -> Void)?

    private let session: ARSession
    private let commandQueue: MTLCommandQueue
    private let quadPipeline: MTLRenderPipelineState
    private let pointPipeline: MTLRenderPipelineState
    private let unproject: MTLComputePipelineState
    private let quadDepth: MTLDepthStencilState
    private let pointDepth: MTLDepthStencilState
    private let particles: MTLBuffer
    private let blankDepth: MTLTexture
    private let blankConfidence: MTLTexture
    private var cache: CVMetalTextureCache?
    private var written = 0
    private var gate = PointAccumulationGate()
    private var lastFrameTime: TimeInterval = 0
    private var lastReadout: CFTimeInterval = 0
    private var lastStats: CFTimeInterval = 0
    private var stats = DepthStats()
    private var drawTimes: [CFTimeInterval] = []
    private var pinWorld: SIMD3<Float>?

    init(session: ARSession, view: MTKView) throws {
        guard let device = view.device ?? MTLCreateSystemDefaultDevice(), let queue = device.makeCommandQueue() else {
            throw LiDARError.noGPU
        }
        view.device = device
        view.colorPixelFormat = .bgra8Unorm
        view.depthStencilPixelFormat = .depth32Float
        view.preferredFramesPerSecond = 60        // the camera's rate; AppModel.lidarFPS lowers it when the phone is hot
        view.framebufferOnly = true
        view.clearColor = MTLClearColor(red: 0, green: 0, blue: 0, alpha: 1)

        let lib = try device.makeLibrary(source: LiDARShaderSource.source, options: nil)
        func fn(_ name: String) throws -> MTLFunction {
            guard let f = lib.makeFunction(name: name) else { throw LiDARError.missingFunction(name) }
            return f
        }
        let quad = MTLRenderPipelineDescriptor()
        quad.vertexFunction = try fn("lidarQuadVertex")
        quad.fragmentFunction = try fn("lidarQuadFragment")
        quad.colorAttachments[0].pixelFormat = view.colorPixelFormat
        quad.depthAttachmentPixelFormat = view.depthStencilPixelFormat
        quadPipeline = try device.makeRenderPipelineState(descriptor: quad)

        let point = MTLRenderPipelineDescriptor()
        point.vertexFunction = try fn("lidarPointVertex")
        point.fragmentFunction = try fn("lidarPointFragment")
        point.colorAttachments[0].pixelFormat = view.colorPixelFormat
        point.depthAttachmentPixelFormat = view.depthStencilPixelFormat
        pointPipeline = try device.makeRenderPipelineState(descriptor: point)
        unproject = try device.makeComputePipelineState(function: try fn("lidarUnproject"))

        let always = MTLDepthStencilDescriptor()
        always.depthCompareFunction = .always
        always.isDepthWriteEnabled = false
        let less = MTLDepthStencilDescriptor()
        less.depthCompareFunction = .less
        less.isDepthWriteEnabled = true
        guard let qd = device.makeDepthStencilState(descriptor: always), let pd = device.makeDepthStencilState(descriptor: less),
              let buf = device.makeBuffer(length: Self.capacity * MemoryLayout<LiDARParticle>.stride, options: .storageModeShared)
        else { throw LiDARError.noGPU }
        memset(buf.contents(), 0, buf.length)                     // w = 0 everywhere: every slot starts empty
        quadDepth = qd
        pointDepth = pd
        particles = buf

        // Stand-ins while a frame has no depth yet, so the shaders always have their textures bound.
        func blank(_ format: MTLPixelFormat, _ bytes: [UInt8]) throws -> MTLTexture {
            let d = MTLTextureDescriptor.texture2DDescriptor(pixelFormat: format, width: 1, height: 1, mipmapped: false)
            d.usage = [.shaderRead]
            guard let t = device.makeTexture(descriptor: d) else { throw LiDARError.noGPU }
            bytes.withUnsafeBytes { t.replace(region: MTLRegionMake2D(0, 0, 1, 1), mipmapLevel: 0, withBytes: $0.baseAddress!, bytesPerRow: bytes.count) }
            return t
        }
        blankDepth = try blank(.r32Float, [0, 0, 0, 0])
        blankConfidence = try blank(.r8Uint, [0])
        self.session = session
        commandQueue = queue
        super.init()
        CVMetalTextureCacheCreate(nil, nil, device, nil, &cache)
    }

    func mtkView(_ view: MTKView, drawableSizeWillChange size: CGSize) {}

    func draw(in view: MTKView) {
        let size = view.bounds.size
        guard size.width > 0, size.height > 0, let frame = session.currentFrame,
              let pass = view.currentRenderPassDescriptor, let drawable = view.currentDrawable,
              let cmd = commandQueue.makeCommandBuffer(),
              let yRef = texture(frame.capturedImage, .r8Unorm, plane: 0),
              let cRef = texture(frame.capturedImage, .rg8Unorm, plane: 1),
              let yTex = CVMetalTextureGetTexture(yRef), let cTex = CVMetalTextureGetTexture(cRef) else { return }
        let display = frame.displayTransform(for: .portrait, viewportSize: size)
        let inv = display.inverted()
        let depth = frame.smoothedSceneDepth ?? frame.sceneDepth
        let dRef = depth.flatMap { texture($0.depthMap, .r32Float, plane: 0) }
        let kRef = depth?.confidenceMap.flatMap { texture($0, .r8Uint, plane: 0) }
        let dTex = dRef.flatMap { CVMetalTextureGetTexture($0) } ?? blankDepth
        let kTex = kRef.flatMap { CVMetalTextureGetTexture($0) } ?? blankConfidence
        let hasDepth = dRef != nil && kRef != nil
        let isNew = frame.timestamp != lastFrameTime
        lastFrameTime = frame.timestamp
        var normal = false
        if case .normal = frame.camera.trackingState { normal = true }
        let minConf: UInt32 = highConfidenceOnly ? 2 : 1

        // The room cloud is only built in Points mode, so the plain depth view costs no extra GPU work.
        if mode == .points, isNew, hasDepth, normal, gate.shouldAdd(frame.camera.transform),
           let enc = cmd.makeComputeCommandEncoder() {
            let K = frame.camera.intrinsics, res = frame.camera.imageResolution
            var u = LiDARUnprojectUniforms(cameraToWorld: frame.camera.transform,
                                           intrinsics: SIMD4(K.columns.0.x, K.columns.1.y, K.columns.2.x, K.columns.2.y),
                                           imageSize: SIMD2(Float(res.width), Float(res.height)),
                                           gridW: UInt32(Self.gridW), gridH: UInt32(Self.gridH),
                                           base: UInt32(written % Self.capacity), capacity: UInt32(Self.capacity),
                                           nearM: DepthPalette.nearM, farM: DepthPalette.farM, minConfidence: minConf)
            enc.setComputePipelineState(unproject)
            enc.setBytes(&u, length: MemoryLayout<LiDARUnprojectUniforms>.stride, index: 0)
            enc.setBuffer(particles, offset: 0, index: 1)
            enc.setTextures([yTex, cTex, dTex, kTex], range: 0..<4)
            let w = unproject.threadExecutionWidth, h = max(1, unproject.maxTotalThreadsPerThreadgroup / w)
            enc.dispatchThreads(MTLSize(width: Self.gridW, height: Self.gridH, depth: 1),
                                threadsPerThreadgroup: MTLSize(width: w, height: h, depth: 1))
            enc.endEncoding()
            written += Self.gridW * Self.gridH
        }

        guard let enc = cmd.makeRenderCommandEncoder(descriptor: pass) else { return }
        var q = LiDARQuadUniforms(viewToImage: SIMD4(Float(inv.a), Float(inv.b), Float(inv.c), Float(inv.d)),
                                  viewToImageT: SIMD2(Float(inv.tx), Float(inv.ty)),
                                  overlay: mode == .depth && hasDepth ? overlay : 0, minConfidence: Float(minConf),
                                  nearM: DepthPalette.nearM, farM: DepthPalette.farM,
                                  cameraBrightness: mode == .points ? 0.22 : mode == .depth ? 0.3 : 1)   // dim where there's no depth
        enc.setRenderPipelineState(quadPipeline)
        enc.setDepthStencilState(quadDepth)
        enc.setFragmentBytes(&q, length: MemoryLayout<LiDARQuadUniforms>.stride, index: 0)
        enc.setFragmentTextures([yTex, cTex, dTex, kTex], range: 0..<4)
        enc.drawPrimitives(type: .triangleStrip, vertexStart: 0, vertexCount: 4)
        let count = min(written, Self.capacity)
        if mode == .points, count > 0 {
            var vp = frame.camera.projectionMatrix(for: .portrait, viewportSize: size, zNear: 0.02, zFar: 30)
                * frame.camera.viewMatrix(for: .portrait)
            var scale = Float(view.contentScaleFactor) * 3
            enc.setRenderPipelineState(pointPipeline)
            enc.setDepthStencilState(pointDepth)
            enc.setVertexBytes(&vp, length: MemoryLayout<simd_float4x4>.stride, index: 0)
            enc.setVertexBuffer(particles, offset: 0, index: 1)
            enc.setVertexBytes(&scale, length: MemoryLayout<Float>.stride, index: 2)
            enc.drawPrimitives(type: .point, vertexStart: 0, vertexCount: count)
        }
        enc.endEncoding()
        let keep: [CVMetalTexture?] = [yRef, cRef, dRef, kRef]   // the GPU reads these buffers until it completes
        cmd.addCompletedHandler { _ in withExtendedLifetime(keep) {} }
        cmd.present(drawable)
        cmd.commit()

        updateReadout(frame, size: size, display: display, hasDepth: hasDepth, normal: normal)
    }

    /// Drops a pin on whatever is under `point` (view points), anchored in the world, so it stays on the object as you
    /// move. False when there's no confident depth there.
    @discardableResult
    func measure(at point: CGPoint, viewSize: CGSize) -> Bool {
        guard let frame = session.currentFrame, let depth = frame.smoothedSceneDepth ?? frame.sceneDepth else { return false }
        let display = frame.displayTransform(for: .portrait, viewportSize: viewSize)
        let img = ViewMapping.imagePoint(fromView: point, viewSize: viewSize, displayTransform: display)
        guard let d = DepthProbe.median(depth: depth.depthMap, confidence: depth.confidenceMap, at: img) else {
            pinWorld = nil
            return false
        }
        pinWorld = CameraMath.unproject(img, depthM: d, intrinsics: frame.camera.intrinsics,
                                        imageSize: frame.camera.imageResolution, cameraToWorld: frame.camera.transform)
        return true
    }

    func clearPin() { pinWorld = nil }

    func clearPoints() {
        written = 0
        gate.reset()
    }

    private func updateReadout(_ frame: ARFrame, size: CGSize, display: CGAffineTransform, hasDepth: Bool, normal: Bool) {
        guard onReadout != nil else { return }          // nothing on screen reads it: skip the CPU work
        let now = CACurrentMediaTime()
        drawTimes.append(now)
        drawTimes.removeAll { now - $0 > 1 }
        guard now - lastReadout >= 0.1 else { return }
        lastReadout = now
        var r = LiDARReadout()
        r.hasDepth = hasDepth
        r.trackingNormal = normal
        r.tracking = ARSessionManager.describe(frame.camera.trackingState)
        r.fps = drawTimes.count
        r.points = min(written, Self.capacity)
        if let depth = frame.smoothedSceneDepth ?? frame.sceneDepth {
            let center = ViewMapping.imagePoint(fromView: CGPoint(x: size.width / 2, y: size.height / 2), viewSize: size,
                                                displayTransform: display)
            r.centerM = DepthProbe.median(depth: depth.depthMap, confidence: depth.confidenceMap, at: center,
                                          minConfidence: highConfidenceOnly ? 2 : 1)
            if now - lastStats >= 0.5 {
                lastStats = now
                let d = FrameEncoder.plane(depth.depthMap, as: Float32.self)
                let c = depth.confidenceMap.map { FrameEncoder.plane($0, as: UInt8.self).values }
                stats = DepthStats.of(depth: d.values, confidence: c)
            }
        }
        r.stats = stats
        if normal {                                   // world positions only mean something while tracking is normal
            let T = frame.camera.transform
            let placed = ItemOverlay.place(marks, cameraToWorld: T, intrinsics: frame.camera.intrinsics,
                                           imageSize: frame.camera.imageResolution, viewSize: size,
                                           displayTransform: display, targetId: targetId)
            r.items = placed.shown
            r.outOfView = placed.outOfView
            if let w = pinWorld, let pr = CameraMath.project(w, intrinsics: frame.camera.intrinsics,
                                                               imageSize: frame.camera.imageResolution, cameraToWorld: T) {
                r.pin = ViewMapping.viewPoint(fromImage: pr.point, viewSize: size, displayTransform: display)
                r.pinM = simd_distance(SIMD3(T.columns.3.x, T.columns.3.y, T.columns.3.z), w)
            }
        } else {
            r.outOfView = marks.filter(\.shown).count
        }
        onReadout?(r)
    }

    private func texture(_ pb: CVPixelBuffer, _ format: MTLPixelFormat, plane: Int) -> CVMetalTexture? {
        guard let cache else { return nil }
        let planar = CVPixelBufferIsPlanar(pb)
        let w = planar ? CVPixelBufferGetWidthOfPlane(pb, plane) : CVPixelBufferGetWidth(pb)
        let h = planar ? CVPixelBufferGetHeightOfPlane(pb, plane) : CVPixelBufferGetHeight(pb)
        var out: CVMetalTexture?
        guard CVMetalTextureCacheCreateTextureFromImage(nil, cache, pb, nil, format, w, h, plane, &out) == kCVReturnSuccess else {
            return nil
        }
        return out
    }
}
