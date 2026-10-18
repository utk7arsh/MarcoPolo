import Foundation
import simd

/// The LiDAR view's Metal shaders, compiled on the phone at runtime (`MTLDevice.makeLibrary(source:)`) when the view
/// opens. Kept as source, not a .metal file, because Xcode 26 ships the Metal compiler as a separate download
/// (`xcodebuild -downloadComponent MetalToolchain`): a .metal file would break the build for anyone without it.
/// Tests/main.swift compiles this same source with the Mac's Metal runtime and checks every entry point exists.
/// Swift mirrors of the shader structs. Field offsets must match the Metal side byte for byte; Tests/main.swift checks
/// them and runs `lidarUnproject` on the Mac's GPU against CameraMath.unproject.
struct LiDARQuadUniforms {
    var viewToImage: SIMD4<Float>      // a, b, c, d of the inverse display transform (view -> image)
    var viewToImageT: SIMD2<Float>     // tx, ty
    var overlay: Float                 // 0 camera only .. 1 depth only
    var minConfidence: Float
    var nearM: Float
    var farM: Float
    var cameraBrightness: Float
}

struct LiDARUnprojectUniforms {
    var cameraToWorld: simd_float4x4
    var intrinsics: SIMD4<Float>       // fx, fy, cx, cy
    var imageSize: SIMD2<Float>
    var gridW: UInt32
    var gridH: UInt32
    var base: UInt32
    var capacity: UInt32
    var nearM: Float
    var farM: Float
    var minConfidence: UInt32
}

/// One point of the room cloud on the GPU: world position (w = 0 marks an empty slot) and colour.
struct LiDARParticle {
    var position: SIMD4<Float>
    var color: SIMD4<Float>
}

enum LiDARShaderSource {
    static let functions = ["lidarQuadVertex", "lidarQuadFragment", "lidarUnproject", "lidarPointVertex", "lidarPointFragment"]

    static let source = #"""
// The LiDAR view's GPU side (LiDARRenderer.swift). Conventions match Core/DepthVision.swift and server/marco/geometry.py:
// image and depth in the sensor's orientation (origin top-left), ARKit camera axes (+x right, +y up, looking down -z).
#include <metal_stdlib>
using namespace metal;

// Layouts are mirrored by the Swift structs in LiDARRenderer.swift (sizes asserted there).
struct QuadUniforms {
    float4 viewToImage;      // a, b, c, d of the affine map: view (0..1, top-left) -> image (0..1, top-left)
    float2 viewToImageT;     // tx, ty
    float overlay;           // 0 camera only .. 1 depth only
    float minConfidence;     // 0, 1 or 2
    float nearM;
    float farM;
    float cameraBrightness;  // dims the camera under the point cloud
};

struct UnprojectUniforms {
    float4x4 cameraToWorld;  // ARFrame.camera.transform
    float4 intrinsics;       // fx, fy, cx, cy for imageSize
    float2 imageSize;        // capturedImage, normally 1920x1440
    uint gridW;
    uint gridH;
    uint base;               // ring-buffer slot of this frame's first point
    uint capacity;
    float nearM;
    float farM;
    uint minConfidence;
};

struct Particle {
    float4 position;         // world; w = 0 marks an empty slot
    float4 color;
};

// Google's Turbo colour scale, polynomial fit. x: 0 dark blue .. 1 dark red. (DepthPalette.turbo in Swift.)
static float3 turbo(float x) {
    x = saturate(x);
    const float4 kRed4 = float4(0.13572138, 4.61539260, -42.66032258, 132.13108234);
    const float4 kGreen4 = float4(0.09140261, 2.19418839, 4.84296658, -14.18503333);
    const float4 kBlue4 = float4(0.10667330, 12.64194608, -60.58204836, 110.36276771);
    const float2 kRed2 = float2(-152.94239396, 59.28637943);
    const float2 kGreen2 = float2(4.27729857, 2.82956604);
    const float2 kBlue2 = float2(-89.90310912, 27.34824973);
    float4 v4 = float4(1.0, x, x * x, x * x * x);
    float2 v2 = v4.zw * v4.z;
    return saturate(float3(dot(v4, kRed4) + dot(v2, kRed2), dot(v4, kGreen4) + dot(v2, kGreen2), dot(v4, kBlue4) + dot(v2, kBlue2)));
}

// ARKit's capturedImage is full-range BT.601 YCbCr (Apple's ARKit Metal template).
static float3 ycbcrToRGB(float y, float2 cbcr) {
    const float4x4 m = float4x4(float4(+1.0000f, +1.0000f, +1.0000f, +0.0000f),
                                float4(+0.0000f, -0.3441f, +1.7720f, +0.0000f),
                                float4(+1.4020f, -0.7141f, +0.0000f, +0.0000f),
                                float4(-0.7010f, +0.5291f, -0.8860f, +1.0000f));
    return (m * float4(y, cbcr, 1.0)).rgb;
}

static uint2 texel(float2 uv, uint w, uint h) {
    float2 p = clamp(uv, 0.0, 0.99999) * float2(w, h);
    return min(uint2(p), uint2(w - 1, h - 1));
}

// MARK: - Camera with the depth heat map (Camera and Depth modes; dimmed under Points)

struct QuadOut {
    float4 position [[position]];
    float2 viewUV;
};

vertex QuadOut lidarQuadVertex(uint vid [[vertex_id]]) {
    const float2 pos[4] = { float2(-1, -1), float2(1, -1), float2(-1, 1), float2(1, 1) };
    const float2 uv[4] = { float2(0, 1), float2(1, 1), float2(0, 0), float2(1, 0) };   // view, origin top-left
    QuadOut o;
    o.position = float4(pos[vid], 0, 1);
    o.viewUV = uv[vid];
    return o;
}

fragment float4 lidarQuadFragment(QuadOut in [[stage_in]],
                                  constant QuadUniforms &u [[buffer(0)]],
                                  texture2d<float> yTex [[texture(0)]],
                                  texture2d<float> cbcrTex [[texture(1)]],
                                  texture2d<float> depthTex [[texture(2)]],
                                  texture2d<uint> confTex [[texture(3)]]) {
    constexpr sampler linear(address::clamp_to_edge, filter::linear);
    float2 v = in.viewUV;
    float2 img = float2(u.viewToImage.x * v.x + u.viewToImage.z * v.y + u.viewToImageT.x,
                        u.viewToImage.y * v.x + u.viewToImage.w * v.y + u.viewToImageT.y);
    float3 rgb = ycbcrToRGB(yTex.sample(linear, img).r, cbcrTex.sample(linear, img).rg) * u.cameraBrightness;
    if (u.overlay <= 0.0) { return float4(rgb, 1); }
    uint2 dp = texel(img, depthTex.get_width(), depthTex.get_height());
    float d = depthTex.read(dp).r;
    uint c = confTex.read(texel(img, confTex.get_width(), confTex.get_height())).r;
    bool ok = isfinite(d) && d > 0.05 && d <= u.farM && float(c) >= u.minConfidence;
    float t = saturate((d - u.nearM) / (u.farM - u.nearM));
    float3 heat = turbo(1.0 - t);                                  // near warm, far cool
    return float4(mix(rgb, heat, ok ? u.overlay : 0.0), 1);
}

// MARK: - Room point cloud (Points mode)

kernel void lidarUnproject(uint2 gid [[thread_position_in_grid]],
                           constant UnprojectUniforms &u [[buffer(0)]],
                           device Particle *particles [[buffer(1)]],
                           texture2d<float> yTex [[texture(0)]],
                           texture2d<float> cbcrTex [[texture(1)]],
                           texture2d<float> depthTex [[texture(2)]],
                           texture2d<uint> confTex [[texture(3)]]) {
    if (gid.x >= u.gridW || gid.y >= u.gridH) { return; }
    constexpr sampler linear(address::clamp_to_edge, filter::linear);
    uint index = (u.base + gid.y * u.gridW + gid.x) % u.capacity;
    float2 uv = (float2(gid) + 0.5) / float2(u.gridW, u.gridH);    // normalized image point, origin top-left
    float d = depthTex.read(texel(uv, depthTex.get_width(), depthTex.get_height())).r;
    uint c = confTex.read(texel(uv, confTex.get_width(), confTex.get_height())).r;
    if (!(isfinite(d) && d > u.nearM && d < u.farM) || c < u.minConfidence) {
        particles[index].position = float4(0);
        return;
    }
    float2 px = uv * u.imageSize;
    float3 pc = float3((px.x - u.intrinsics.z) / u.intrinsics.x * d, -(px.y - u.intrinsics.w) / u.intrinsics.y * d, -d);
    float4 pw = u.cameraToWorld * float4(pc, 1.0);
    float3 rgb = ycbcrToRGB(yTex.sample(linear, uv).r, cbcrTex.sample(linear, uv).rg);
    particles[index].position = float4(pw.xyz / pw.w, 1.0);
    particles[index].color = float4(rgb, 1.0);
}

struct PointOut {
    float4 position [[position]];
    float size [[point_size]];
    float4 color;
};

vertex PointOut lidarPointVertex(uint vid [[vertex_id]],
                                 constant float4x4 &viewProjection [[buffer(0)]],
                                 const device Particle *particles [[buffer(1)]],
                                 constant float &pointScale [[buffer(2)]]) {
    Particle p = particles[vid];
    PointOut o;
    if (p.position.w == 0) {                       // empty slot: outside the clip volume
        o.position = float4(2, 2, 2, 1);
        o.size = 0;
        o.color = float4(0);
        return o;
    }
    float4 clip = viewProjection * float4(p.position.xyz, 1.0);
    o.position = clip;
    o.size = clamp(pointScale / max(clip.w, 0.15), 1.5, 12.0);   // nearer points draw bigger
    o.color = p.color;
    return o;
}

fragment float4 lidarPointFragment(PointOut in [[stage_in]], float2 pc [[point_coord]]) {
    if (length(pc - 0.5) > 0.5) { discard_fragment(); }
    return in.color;
}
"""#
}
