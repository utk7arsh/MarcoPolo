import SwiftUI

@main
struct MarcoApp: App {
    @StateObject private var model = AppModel()
    @Environment(\.scenePhase) private var scenePhase

    init() { CrashReports.shared.start() }

    var body: some Scene {
        WindowGroup {
            ContentView().environmentObject(model)
                .tint(Theme.blue)
                .preferredColorScheme(.light)
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .background { model.stop() } // Saves the world map, releases camera/audio, and invalidates pending starts.
            if phase == .active { model.refreshCameraAccess() }
        }
    }
}
