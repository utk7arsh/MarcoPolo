import Foundation

/// ARSessionManager confines this state and disk writes to its serial AR queue. A save may finish after pause,
/// but never after another capture start/reset or a newer save request, even when a restored map has the same ID.
struct WorldMapLifecycle {
    struct SaveTicket: Equatable {
        var mapId: String
        var generation: Int
        var serial: Int
    }

    private(set) var mapId = UUID().uuidString
    private var generation = 0
    private var saveSerial = 0

    mutating func begin(restoredMapId: String? = nil) {
        generation += 1
        mapId = restoredMapId ?? UUID().uuidString
        saveSerial = 0
    }

    mutating func prepareSave() -> SaveTicket {
        saveSerial += 1
        return SaveTicket(mapId: mapId, generation: generation, serial: saveSerial)
    }

    func accepts(_ ticket: SaveTicket) -> Bool {
        ticket.mapId == mapId && ticket.generation == generation && ticket.serial == saveSerial
    }
}
