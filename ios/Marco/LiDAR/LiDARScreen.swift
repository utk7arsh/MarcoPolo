import ARKit
import MetalKit
import SwiftUI

/// The LiDAR view: the depth the chest LiDAR sees right now, full screen. Near is red, far is blue; past the LiDAR's
/// 5 m range the camera shows through dimly. Nothing else on screen but a close button.
struct LiDARScreen: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var error: String?

    var body: some View {
        ZStack(alignment: .topTrailing) {
            Color.black.ignoresSafeArea()
            LiDARMetalView(session: model.arSession, fps: model.lidarFPS, error: $error)
                .ignoresSafeArea()
                .accessibilityHidden(true)
            Button { dismiss() } label: {
                Image(systemName: "xmark")
                    .font(.system(size: 15, weight: .semibold))
                    .foregroundStyle(.white)
                    .frame(width: 36, height: 36)
                    .background(.black.opacity(0.45), in: Circle())
            }
            .padding(16)
            .accessibilityLabel("Close LiDAR view")
            if let error {
                Text(error)
                    .font(Theme.font(17)).foregroundStyle(.white).multilineTextAlignment(.center).padding(32)
                    .frame(maxWidth: .infinity, maxHeight: .infinity)
            }
        }
        .preferredColorScheme(.dark)
        .accessibilityAction(.escape) { dismiss() }
        .onChange(of: model.running) { _, running in if !running { dismiss() } }
    }
}

/// The Metal view, sharing the app's ARSession (read-only: see LiDARRenderer).
private struct LiDARMetalView: UIViewRepresentable {
    let session: ARSession
    let fps: Int                                        // AppModel.lidarFPS: lower when the phone runs hot
    @Binding var error: String?

    /// Holds the renderer: MTKView keeps its delegate weakly.
    final class Coordinator {
        var renderer: LiDARRenderer?
    }

    func makeCoordinator() -> Coordinator { Coordinator() }

    func makeUIView(context: Context) -> MTKView {
        let view = MTKView(frame: .zero, device: MTLCreateSystemDefaultDevice())
        view.backgroundColor = .black
        do {
            let renderer = try LiDARRenderer(session: session, view: view)
            renderer.mode = .depth
            renderer.overlay = 1                        // the depth itself, not a blend over the camera
            view.delegate = renderer
            context.coordinator.renderer = renderer
        } catch {
            let message = "The LiDAR view couldn't start: \(error.localizedDescription)"
            DispatchQueue.main.async { self.error = message }
        }
        return view
    }

    func updateUIView(_ view: MTKView, context: Context) {
        if view.preferredFramesPerSecond != fps { view.preferredFramesPerSecond = fps }
    }
}
