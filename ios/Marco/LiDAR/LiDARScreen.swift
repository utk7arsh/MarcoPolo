import ARKit
import MetalKit
import SwiftUI
import UIKit

/// The screen's state; owns the renderer, because MTKView holds its delegate weakly.
final class LiDARScreenModel: ObservableObject {
    @Published var readout = LiDARReadout()
    @Published var mode: LiDARMode = .depth
    @Published var overlay = 0.6
    @Published var highConfidenceOnly = false
    @Published var error: String?
    var renderer: LiDARRenderer?
}

/// The LiDAR view: what the chest camera and LiDAR see right now, and where the server remembers things. Camera, a
/// depth heat map, or the room as a point cloud; tap anything to measure it. For sighted helpers and demos; the wearer
/// never needs it, and VoiceOver gets the same information from "Describe view".
struct LiDARScreen: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @Environment(\.accessibilityVoiceOverEnabled) private var voiceOver
    @StateObject private var screen = LiDARScreenModel()
    @State private var size: CGSize = .zero

    var body: some View {
        let r = screen.readout
        ZStack {
            Color.black.ignoresSafeArea()
            LiDARMetalView(session: model.arSession, screen: screen, marks: model.itemMarks, targetId: model.guidanceTargetId)
                .ignoresSafeArea()
                .accessibilityHidden(true)
                .onTapGesture(coordinateSpace: .local) { p in
                    if screen.renderer?.measure(at: p, viewSize: size) == false { haptic(.warning) } else { haptic(.success) }
                }
                .onLongPressGesture { screen.renderer?.clearPin() }

            // Overlays share the Metal view's coordinates: full screen, ignoring the safe area.
            GeometryReader { geo in
                ZStack {
                    Reticle(distanceM: r.centerM).position(x: geo.size.width / 2, y: geo.size.height / 2)
                    ForEach(r.items) { item in ItemTag(item: item).position(item.screen) }
                    if let pin = r.pin { MeasurePin(distanceM: r.pinM).position(pin) }
                }
                .onAppear { size = geo.size }
                .onChange(of: geo.size) { _, s in size = s }
            }
            .ignoresSafeArea()
            .allowsHitTesting(false)
            .accessibilityHidden(true)

            VStack(spacing: 0) {
                topBar(r)
                Spacer()
                panel(r)
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 8)

            if let e = screen.error {
                Text(e).font(Theme.font(17)).foregroundStyle(.white).multilineTextAlignment(.center).padding(32)
            }
        }
        .preferredColorScheme(.dark)
        .statusBarHidden(false)
        .accessibilityAction(.escape) { dismiss() }
        .accessibilityAction(.magicTap) { announce(describe(r)) }
        .onChange(of: model.running) { _, running in if !running { dismiss() } }
        .task {
            // Fresh remembered positions from the server (Vultr) while the view is open; events also move them live.
            while !Task.isCancelled {
                model.refreshItemsNow()
                try? await Task.sleep(for: .seconds(5))
            }
        }
    }

    // MARK: - Pieces

    private func topBar(_ r: LiDARReadout) -> some View {
        HStack(spacing: 10) {
            HStack(spacing: 8) {
                Circle().fill(r.trackingNormal ? Color(red: 0.36, green: 0.78, blue: 0.55) : Color(red: 0.95, green: 0.68, blue: 0.25))
                    .frame(width: 8, height: 8)
                Text(r.trackingNormal ? "Tracking" : r.tracking.capitalized)
                    .font(Theme.font(14, .medium, relativeTo: .subheadline))
                Text("· \(r.fps) fps").font(Theme.font(14, relativeTo: .subheadline)).foregroundStyle(.white.opacity(0.6))
            }
            .padding(.horizontal, 12).frame(height: 36)
            .background(.ultraThinMaterial, in: Capsule())
            .accessibilityElement(children: .combine)
            .accessibilityLabel(r.trackingNormal ? "Tracking normal" : "Tracking \(r.tracking)")
            Spacer()
            if voiceOver {
                Button("Describe view") { announce(describe(r)) }
                    .font(Theme.font(15, .medium)).padding(.horizontal, 14).frame(height: 36)
                    .background(.ultraThinMaterial, in: Capsule())
            }
            Button("Done") { dismiss() }
                .font(Theme.font(16, .semibold)).foregroundStyle(.white)
                .padding(.horizontal, 16).frame(height: 36)
                .background(Theme.blue, in: Capsule())
                .accessibilityLabel("Close LiDAR view")
        }
        .padding(.top, 6)
    }

    private func panel(_ r: LiDARReadout) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Picker("View", selection: $screen.mode) {
                ForEach(LiDARMode.allCases) { Text($0.rawValue).tag($0) }
            }
            .pickerStyle(.segmented)
            .accessibilityLabel("LiDAR view mode")

            switch screen.mode {
            case .camera:
                Text("The chest camera, as the server receives it once a second. Tap anything to measure it.")
                    .font(Theme.font(14, relativeTo: .footnote)).foregroundStyle(.white.opacity(0.75))
            case .depth:
                HStack(spacing: 12) {
                    Text("Overlay").font(Theme.font(15, relativeTo: .subheadline))
                    Slider(value: $screen.overlay, in: 0...1).tint(Theme.blue)
                        .accessibilityLabel("Depth overlay strength")
                }
                legend
            case .points:
                HStack {
                    Text("\(r.points.formatted()) points in the room")
                        .font(Theme.font(15, .medium, relativeTo: .subheadline))
                    Spacer()
                    Button("Clear") { screen.renderer?.clearPoints() }
                        .font(Theme.font(15, .medium)).accessibilityLabel("Clear the point cloud")
                }
                Text("Walk slowly: the cloud grows as you move, coloured by the camera.")
                    .font(Theme.font(13, relativeTo: .footnote)).foregroundStyle(.white.opacity(0.7))
            }
            if screen.mode != .camera {
                Toggle("High-confidence depth only", isOn: $screen.highConfidenceOnly)
                    .font(Theme.font(15, relativeTo: .subheadline)).tint(Theme.blue)
            }
            Divider().overlay(.white.opacity(0.15))
            stat(r.hasDepth ? String(format: "Depth %.0f%% valid · %.0f%% high", r.stats.validFraction * 100, r.stats.highFraction * 100)
                            : "Waiting for LiDAR depth",
                 r.stats.nearestM.map { String(format: "nearest %.2f m", $0) })
            stat(itemsLine(r), model.socketUp ? "server connected" : "server offline")
        }
        .padding(16)
        .foregroundStyle(.white)
        .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: 22, style: .continuous))
    }

    private var legend: some View {
        VStack(spacing: 4) {
            LinearGradient(colors: stride(from: 0.0, through: 1.0, by: 0.1).map { t -> Color in
                let c = DepthPalette.color(depthM: DepthPalette.nearM + Float(t) * (DepthPalette.farM - DepthPalette.nearM))
                return Color(red: Double(c.x), green: Double(c.y), blue: Double(c.z))
            }, startPoint: .leading, endPoint: .trailing)
            .frame(height: 8).clipShape(Capsule())
            HStack {
                Text(String(format: "%.1f m", DepthPalette.nearM))
                Spacer()
                Text(String(format: "%.0f m", DepthPalette.farM))
            }
            .font(Theme.font(12, relativeTo: .caption)).foregroundStyle(.white.opacity(0.7))
        }
        .accessibilityElement(children: .ignore)
        .accessibilityLabel("Colour scale: red is near, blue is 5 meters away")
    }

    private func stat(_ left: String, _ right: String?) -> some View {
        HStack {
            Text(left)
            Spacer(minLength: 8)
            if let right { Text(right).foregroundStyle(.white.opacity(0.65)) }
        }
        .font(Theme.font(13, relativeTo: .footnote))
        .accessibilityElement(children: .combine)
    }

    private func itemsLine(_ r: LiDARReadout) -> String {
        let total = model.itemMarks.filter(\.shown).count
        guard total > 0 else { return "No remembered items yet" }
        return "\(total) remembered · \(r.items.count) in view"
    }

    private func describe(_ r: LiDARReadout) -> String {
        ItemOverlay.spoken(centerM: r.centerM, items: r.items, outOfView: r.outOfView, viewWidth: max(size.width, 1))
    }

    private func announce(_ text: String) {
        UIAccessibility.post(notification: .announcement, argument: text)
    }

    private func haptic(_ kind: UINotificationFeedbackGenerator.FeedbackType) {
        UINotificationFeedbackGenerator().notificationOccurred(kind)
    }
}

/// The Metal view, sharing the app's ARSession (read-only: see LiDARRenderer).
private struct LiDARMetalView: UIViewRepresentable {
    let session: ARSession
    let screen: LiDARScreenModel
    let marks: [ItemMark]
    let targetId: String?

    func makeUIView(context: Context) -> MTKView {
        let view = MTKView(frame: .zero, device: MTLCreateSystemDefaultDevice())
        view.backgroundColor = .black
        do {
            let renderer = try LiDARRenderer(session: session, view: view)
            renderer.onReadout = { [weak screen] r in screen?.readout = r }
            view.delegate = renderer
            screen.renderer = renderer
        } catch {
            let message = "The LiDAR view couldn't start: \(error.localizedDescription)"
            DispatchQueue.main.async { screen.error = message }
        }
        return view
    }

    func updateUIView(_ view: MTKView, context: Context) {
        guard let r = screen.renderer else { return }
        r.mode = screen.mode
        r.overlay = Float(screen.overlay)
        r.highConfidenceOnly = screen.highConfidenceOnly
        r.marks = marks
        r.targetId = targetId
    }
}

/// The centre crosshair and the LiDAR distance under it.
private struct Reticle: View {
    let distanceM: Float?

    var body: some View {
        VStack(spacing: 10) {
            ZStack {
                Circle().stroke(.white.opacity(0.9), lineWidth: 1.5).frame(width: 34, height: 34)
                Circle().fill(.white).frame(width: 4, height: 4)
            }
            .shadow(color: .black.opacity(0.5), radius: 3)
            Text(distanceM.map { String(format: "%.2f m", $0) } ?? "no depth")
                .font(Theme.font(20, .semibold, relativeTo: .title3)).monospacedDigit()
                .foregroundStyle(.white).padding(.horizontal, 12).padding(.vertical, 4)
                .background(.black.opacity(0.45), in: Capsule())
        }
        .offset(y: 26)            // the circle, not the label, sits on the centre
    }
}

/// A remembered item where the server says it is: name, distance, surface. The guidance target is blue.
private struct ItemTag: View {
    let item: PlacedItem

    var body: some View {
        VStack(spacing: 6) {
            Text(item.text)
                .font(Theme.font(15, .semibold, relativeTo: .subheadline)).lineLimit(1)
                .foregroundStyle(.white).padding(.horizontal, 12).padding(.vertical, 6)
                .background(item.isTarget ? Theme.blue : Color.black.opacity(0.62), in: Capsule())
                .overlay(Capsule().stroke(.white.opacity(item.isTarget ? 0.9 : 0.25), lineWidth: 1))
            ZStack {
                Circle().fill(item.isTarget ? Theme.blue : .white).frame(width: 12, height: 12)
                if item.isTarget { Circle().stroke(Theme.blue.opacity(0.6), lineWidth: 3).frame(width: 30, height: 30) }
            }
        }
        .offset(y: -22)            // the dot, not the label, sits on the item
        .shadow(color: .black.opacity(0.4), radius: 4)
    }
}

/// The tap-to-measure pin, anchored on the surface it was dropped on.
private struct MeasurePin: View {
    let distanceM: Float?

    var body: some View {
        VStack(spacing: 4) {
            Text(distanceM.map { String(format: "%.2f m", $0) } ?? "")
                .font(Theme.font(15, .semibold)).monospacedDigit().foregroundStyle(.black)
                .padding(.horizontal, 10).padding(.vertical, 4)
                .background(.white, in: Capsule())
            Image(systemName: "mappin").font(.system(size: 20, weight: .bold)).foregroundStyle(.white)
        }
        .offset(y: -20)
        .shadow(color: .black.opacity(0.45), radius: 4)
    }
}
