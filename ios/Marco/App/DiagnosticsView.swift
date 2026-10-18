import PhotosUI
import SwiftUI
import UIKit

/// A debug screen for building and testing. The user in the vest never sees it: everything also works by voice.
struct DiagnosticsView: View {
    @EnvironmentObject var model: AppModel
    @AppStorage("flipAirpodsYaw") private var flipYaw = false
    @State private var itemName = ""
    @State private var photo: PhotosPickerItem?
    @State private var talking = false

    var body: some View {
        NavigationStack {
            Form {
                Section("Server") {
                    TextField("https://server-mac.your-tailnet.ts.net", text: $model.serverText)
                        .textInputAutocapitalization(.never)
                        .autocorrectionDisabled()
                        .keyboardType(.URL)
                    Button(model.running ? "Running" : "Start") { model.start() }
                        .disabled(model.running)
                    row("socket", model.socketUp ? "connected" : "down")
                    row("tracking", model.tracking)
                    row("map", String(model.mapId.prefix(8)))
                    row("frames accepted", "\(model.framesAccepted)")
                    row("last upload", model.lastUpload)
                }

                Section("Ask") {
                    Text(talking ? "Listening..." : "Hold to talk")
                        .frame(maxWidth: .infinity, minHeight: 56)
                        .background(talking ? Color.orange.opacity(0.3) : Color.blue.opacity(0.15))
                        .clipShape(RoundedRectangle(cornerRadius: 10))
                        .onLongPressGesture(minimumDuration: 0, maximumDistance: 80, perform: {}, onPressingChanged: { down in
                            talking = down
                            model.pushToTalk(down)
                        })
                    row("heard", model.heard)
                    ForEach(Config.demoItems, id: \.self) { name in
                        Button("Where are my \(name)?") { model.act(.find(name), "where are my \(name)") }
                    }
                    Button("What is this?") { model.act(.whatIsThis, "what is this") }
                    Button("This is the door") { model.act(.setDoor, "this is the door") }
                    Button("Stop") { model.stopGuidance() }
                }

                Section("Guidance") {
                    row("phase", model.phase.rawValue)
                    row("azimuth (head)", String(format: "%.0f deg", model.relAzimuth))
                    row("distance", String(format: "%.2f m", model.distance))
                }

                Section("Head tracking") {
                    row("source", model.headSource)
                    row("head yaw", String(format: "%.0f deg", model.headYaw))
                    Toggle("Flip AirPods yaw sign", isOn: $flipYaw)
                }

                Section("Register an item (one photo)") {
                    TextField("name, e.g. keys", text: $itemName)
                    PhotosPicker("Choose its photo", selection: $photo, matching: .images)
                        .disabled(itemName.trimmingCharacters(in: .whitespaces).isEmpty)
                }

                Section("Map") {
                    Button("Save map now") { model.saveMap() }
                    Button("Forget the map and start a new one", role: .destructive) { model.newMap() }
                }

                Section("Log") {
                    ForEach(Array(model.log.enumerated()), id: \.offset) { _, line in
                        Text(line).font(.caption.monospaced())
                    }
                }
            }
            .navigationTitle("Marco")
        }
        .onChange(of: photo) { _, item in
            guard let item else { return }
            let name = itemName.trimmingCharacters(in: .whitespaces)
            Task {
                // Library photos are often HEIC; the server wants JPEG (EXIF orientation is fine there).
                if let data = try? await item.loadTransferable(type: Data.self),
                   let jpeg = UIImage(data: data)?.jpegData(compressionQuality: 0.9) {
                    model.register(name: name, photo: jpeg)
                }
                photo = nil
            }
        }
    }

    private func row(_ key: String, _ value: String) -> some View {
        HStack {
            Text(key).foregroundStyle(.secondary)
            Spacer()
            Text(value).multilineTextAlignment(.trailing)
        }
    }
}
