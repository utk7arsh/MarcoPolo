import SwiftUI

@main
struct MarcoApp: App {
    @StateObject private var model = AppModel()
    @Environment(\.scenePhase) private var scenePhase

    var body: some Scene {
        WindowGroup {
            ContentView().environmentObject(model)
        }
        .onChange(of: scenePhase) { _, phase in
            if phase == .background { model.saveMap() }      // §3.4: save the ARWorldMap when leaving
        }
    }
}
