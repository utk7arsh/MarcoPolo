import AVFAudio
import Combine

final class AudioRouteMonitor: ObservableObject {
    @Published private(set) var output = AudioRouteState()
    private var observations: [NSObjectProtocol] = []

    init() {
        for name in [AVAudioSession.routeChangeNotification, AVAudioSession.spatialPlaybackCapabilitiesChangedNotification] {
            observations.append(NotificationCenter.default.addObserver(forName: name, object: nil, queue: .main) {
                [weak self] _ in self?.refresh()
            })
        }
        refresh()
    }
    func refresh() {
        let outputs = AVAudioSession.sharedInstance().currentRoute.outputs
        guard !outputs.isEmpty else { output = AudioRouteState(); return }
        let external = outputs.contains { ![.builtInSpeaker, .builtInReceiver].contains($0.portType) }
        output = AudioRouteState(name: external ? outputs.map(\.portName).joined(separator: ", ") : "iPhone",
                                 external: external, spatial: outputs.contains { $0.isSpatialAudioEnabled })
    }
    deinit { for token in observations { NotificationCenter.default.removeObserver(token) } }
}
