import ARKit
import SwiftUI
import UIKit

private struct StatusObservation: Hashable {
    let status: AccessibleControlStatus
    let voiceOver: Bool
    let active: Bool
    let obscured: Bool
}

struct ContentView: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.openURL) private var openURL
    @Environment(\.scenePhase) private var scenePhase
    @Environment(\.accessibilityVoiceOverEnabled) private var voiceOverEnabled
    @StateObject private var audio = AudioRouteMonitor()
    @State private var settings = false
    @State private var preview = false
    @State private var previousStatus: AccessibleControlStatus?

    private var accessibleStatus: AccessibleControlStatus {
        AccessibleControlStatus(phase: model.control.phase, message: model.controlMessage,
            lidarAvailable: ARSessionManager.supported,
            serverConfigured: ControlServerAddress.parse(model.serverText) != nil,
            serverConnected: model.socketUp, audio: audio.output, audioProblem: model.audioProblem,
            voice: model.voiceStatus, tracking: model.tracking)
    }

    var body: some View {
        let status = accessibleStatus
        let observation = StatusObservation(status: status, voiceOver: voiceOverEnabled,
            active: scenePhase == .active, obscured: settings || preview)
        GeometryReader { geometry in
            ScrollView {
                VStack(alignment: .leading, spacing: 0) {
                    header.frame(height: 68)
                    Text(model.control.title)
                        .font(Theme.font(54, .medium, relativeTo: .largeTitle))
                        .tracking(-2.97).lineSpacing(-5)
                        .foregroundStyle(Theme.ink)
                        .fixedSize(horizontal: false, vertical: true)
                        .padding(.top, 36)
                        .accessibilityAddTraits(.isHeader)
                        .accessibilityLabel("App status")
                        .accessibilityValue(status.cameraDescription)
                        .accessibilityIdentifier("sessionStatus")
                    statusRows.padding(.top, 32)
                    if voiceOverEnabled {
                        Button("Read status") {
                            previousStatus = status
                            announce(status.summary, queued: false)
                        }
                            .font(Theme.font(15, .medium, relativeTo: .subheadline))
                            .frame(minHeight: 44)
                            .accessibilityHint("Reads camera, LiDAR, audio, server, and voice command status.")
                            .accessibilityIdentifier("readStatus")
                    }
                    if let message = model.controlMessage {
                        Text(message).font(Theme.font(15, relativeTo: .subheadline))
                            .foregroundStyle(Theme.secondary).padding(.top, 16)
                    }
                    if let problem = model.audioProblem { helpText(problem) }
                    if let help = model.voiceStatus.help { helpText(help) }
                    if model.voiceStatus == .permissionDenied {
                        Button("Open iPhone Settings", action: openSettings)
                            .font(Theme.font(15, .medium, relativeTo: .subheadline))
                            .frame(minHeight: 44)
                    }
                    Spacer(minLength: 28)
                    cameraControl.frame(maxWidth: .infinity).padding(.top, 20)
                    if model.control.phase == .running {
                        Button("Check camera view") { preview = true }
                            .font(Theme.font(15, .medium, relativeTo: .subheadline))
                            .frame(maxWidth: .infinity, minHeight: 44)
                            .accessibilityIdentifier("showCameraPreview")
                    }
                }
                .padding(.horizontal, 28).padding(.bottom, 22)
                .frame(minHeight: geometry.size.height, alignment: .top)
                .frame(maxWidth: 500).frame(maxWidth: .infinity)
            }.background(Theme.canvas)
        }
        .sheet(isPresented: $settings) { ConnectionSettingsView().environmentObject(model) }
        .sheet(isPresented: $preview) { CameraPreviewSheet(session: model.arSession) }
        .accessibilityElement(children: .contain)
        .accessibilityAction(.magicTap) { if !settings && !preview { performCameraAction() } }
        .onAppear { model.refreshCameraAccess(); audio.refresh() }
        .onChange(of: scenePhase) { _, phase in
            if phase == .active { audio.refresh() }
            if phase == .background { preview = false }
        }
        .onChange(of: model.control.phase) { _, phase in
            if phase != .running { preview = false }
        }
        .task(id: observation) {
            guard observation.voiceOver else { previousStatus = status; return }
            // Keep pending failures through permission alerts or sheets; announce when the panel returns.
            guard observation.active, !observation.obscured else { return }
            guard previousStatus != nil else { previousStatus = status; return }
            // Coalesce asynchronous camera, socket and permission updates into one announcement.
            do { try await Task.sleep(for: .milliseconds(400)) } catch { return }
            guard !Task.isCancelled, scenePhase == .active, !settings, !preview,
                  let previous = previousStatus else { return }
            previousStatus = status
            if let text = status.announcement(since: previous) { announce(text) }
        }
        .task(id: status.waitingForServer && voiceOverEnabled && scenePhase == .active && !settings && !preview) {
            guard status.waitingForServer, voiceOverEnabled, scenePhase == .active, !settings, !preview else { return }
            do { try await Task.sleep(for: .seconds(12)) } catch { return }
            guard !Task.isCancelled, accessibleStatus.waitingForServer else { return }
            announce("The server has not connected. Check Wi-Fi, Tailscale, and the address in Connection settings.")
        }
    }

    private var header: some View {
        HStack(spacing: 9) {
            MarcoPoloMark().frame(width: 26, height: 26)
            Text("Marco Polo").font(Theme.font(20, .semibold, relativeTo: .title3))
                .tracking(-0.7).foregroundStyle(Theme.ink)
            Spacer()
            Button { settings = true } label: {
                Image(systemName: "gearshape").font(.system(size: 20))
                    .foregroundStyle(Theme.secondary)
                    .frame(width: 44, height: 44, alignment: .trailing)
            }
            .accessibilityLabel("Connection settings").accessibilityIdentifier("connectionSettings")
        }
    }

    private var statusRows: some View {
        VStack(spacing: 0) {
            statusRow("Camera", model.control.label,
                color: model.control.needsAttention ? Theme.amber : model.control.phase == .running ? Theme.green : Theme.ink)
            separator
            statusRow("LiDAR", ARSessionManager.supported ? "Available" : "Not supported",
                color: ARSessionManager.supported ? Theme.green : Theme.secondary)
            separator
            statusRow("Audio", audio.output.name, detail: audio.output.spatialLabel)
            separator
            statusRow("Server", model.socketUp ? "Connected" : model.running ? "Connecting" : "Not connected",
                color: model.socketUp ? Theme.green : Theme.secondary)
            separator
            statusRow("Voice commands", model.voiceStatus.label,
                color: model.voiceStatus.help == nil ? Theme.ink : Theme.amber)
        }
    }
    private var separator: some View {
        Rectangle().fill(Theme.border).frame(height: 0.5).accessibilityHidden(true)
    }
    private func statusRow(_ label: String, _ value: String, color: Color = Theme.ink, detail: String? = nil) -> some View {
        VStack(alignment: .trailing, spacing: 4) {
            ViewThatFits(in: .horizontal) {
                HStack(alignment: .firstTextBaseline, spacing: 16) {
                    Text(label).font(Theme.font(17)).foregroundStyle(Theme.ink)
                    Spacer(minLength: 16)
                    Text(value).font(Theme.font(16)).foregroundStyle(color).fixedSize()
                }
                VStack(alignment: .leading, spacing: 8) {
                    Text(label).font(Theme.font(17)).foregroundStyle(Theme.ink)
                    Text(value).font(Theme.font(16)).foregroundStyle(color)
                }.frame(maxWidth: .infinity, alignment: .leading)
            }
            if let detail {
                Text(detail).font(Theme.font(13, relativeTo: .footnote))
                    .foregroundStyle(Theme.secondary).multilineTextAlignment(.trailing)
            }
        }
        .frame(maxWidth: .infinity, minHeight: detail == nil ? 52 : 74)
        .padding(.vertical, 2)
        .accessibilityElement(children: .ignore).accessibilityLabel(label)
        .accessibilityValue(detail.map { "\(value), \($0)" } ?? value)
        .accessibilityIdentifier("status\(label)")
    }
    private var cameraControl: some View {
        Button(action: performCameraAction) {
            VStack(spacing: 14) {
                ZStack {
                    Circle().fill(model.running ? Theme.ink : Theme.blue)
                    if model.control.phase == .permission { ProgressView().tint(.white) }
                    else {
                        Image(systemName: model.running ? "stop.fill" : model.control.phase == .denied ? "gearshape" : "play.fill")
                            .font(.system(size: 28)).foregroundStyle(.white)
                            .offset(x: model.running || model.control.phase == .denied ? 0 : 2)
                    }
                }.frame(width: 96, height: 96)
                Text(model.control.action).font(Theme.font(17, .medium, relativeTo: .headline)).foregroundStyle(Theme.ink)
            }.contentShape(Rectangle())
        }
        .buttonStyle(.plain)
        .disabled([.permission, .unsupported].contains(model.control.phase))
        .opacity(model.control.phase == .unsupported ? 0.45 : 1)
        .accessibilityLabel(model.control.action)
        .accessibilityValue(model.control.label)
        .accessibilityHint(accessibleStatus.cameraActionHint)
        .accessibilityIdentifier("cameraToggle")
    }

    private func helpText(_ text: String) -> some View {
        Text(text).font(Theme.font(15, relativeTo: .subheadline))
            .foregroundStyle(Theme.secondary).padding(.top, 16)
    }

    private func openSettings() {
        if let url = URL(string: UIApplication.openSettingsURLString) { openURL(url) }
    }

    private func performCameraAction() {
        switch model.control.phase {
        case .denied: openSettings()
        case .permission, .unsupported: announce(accessibleStatus.cameraDescription, queued: false)
        default:
            if model.running || model.control.phase == .starting { model.stop() }
            else if ControlServerAddress.parse(model.serverText) == nil { settings = true }
            else { model.start() }
        }
    }

    private func announce(_ text: String, queued: Bool = true) {
        guard voiceOverEnabled, UIAccessibility.isVoiceOverRunning else { return }
        let speech = NSAttributedString(string: text,
            attributes: [.accessibilitySpeechQueueAnnouncement: NSNumber(value: queued)])
        UIAccessibility.post(notification: .announcement, argument: speech)
    }
}

struct ConnectionSettingsView: View {
    @EnvironmentObject private var model: AppModel
    @Environment(\.dismiss) private var dismiss
    @State private var address = ""
    private var valid: Bool { ControlServerAddress.parse(address) != nil }
    var body: some View {
        NavigationStack {
            Form {
                Section {
                    TextField("https://server-mac.your-tailnet.ts.net", text: $address)
                        .keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                        .accessibilityLabel("Server address")
                } header: { Text("Server address").font(Theme.font(14, .medium, relativeTo: .subheadline)) }
                footer: {
                    Text(model.running ? "Stop the camera before changing servers." : "Use your server’s Tailscale address.")
                        .font(Theme.font(13, relativeTo: .footnote))
                }
                .disabled(model.running)
                #if DEBUG
                Section { NavigationLink("Developer tools") { DiagnosticsView().environmentObject(model) } }
                #endif
            }
            .font(Theme.font(17)).scrollContentBackground(.hidden).background(Theme.canvas)
            .toolbar {
                ToolbarItem(placement: .principal) { Text("Connection").font(Theme.font(18, .semibold)) }
                ToolbarItem(placement: .cancellationAction) {
                    Button("Cancel") { dismiss() }.font(Theme.font(17))
                }
                ToolbarItem(placement: .confirmationAction) {
                    Button("Save") {
                        if let url = ControlServerAddress.parse(address) {
                            model.serverText = url.absoluteString; Config.serverURL = url
                        }
                        dismiss()
                    }.font(Theme.font(17, .semibold)).disabled(!valid || model.running)
                }
            }
        }
        .onAppear { address = model.serverText }.presentationDetents([.medium, .large])
        .accessibilityAction(.escape) { dismiss() }
    }
}

private struct CameraPreviewSheet: View {
    let session: ARSession
    @Environment(\.dismiss) private var dismiss
    var body: some View {
        ZStack(alignment: .topTrailing) {
            ARCameraPreview(session: session).ignoresSafeArea()
            Button("Done") { dismiss() }.font(Theme.font(17, .medium)).foregroundStyle(.white)
                .padding(16).background(.black.opacity(0.65), in: Capsule()).padding(20)
                .accessibilityLabel("Close camera preview")
        }
        .accessibilityAction(.escape) { dismiss() }
    }
}
private struct ARCameraPreview: UIViewRepresentable {
    let session: ARSession
    func makeUIView(context: Context) -> ARSCNView {
        let view = ARSCNView(frame: .zero)
        let captureDelegate = session.delegate
        let captureQueue = session.delegateQueue
        view.session = session // Reuse capture; never start another camera or replace the ARSession delegate.
        session.delegate = captureDelegate
        session.delegateQueue = captureQueue
        view.scene = SCNScene()
        view.accessibilityElementsHidden = true // The preview has no interpreted status; controls stay accessible.
        return view
    }
    func updateUIView(_ view: ARSCNView, context: Context) {}
}
