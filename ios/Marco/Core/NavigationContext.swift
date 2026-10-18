import Foundation
import simd

/// A coordinate frame is valid only within the capture run that produced it. Revision also fences a reset
/// before its main-thread map callback is delivered.
struct NavigationScope: Equatable {
    var captureGeneration: Int
    var mapId: String
    var revision: Int
}

struct NavigationPose {
    static let freshS = 0.5
    var scope: NavigationScope
    var transform: simd_float4x4
    var timestamp: Double

    func usable(now: Double, in currentScope: NavigationScope?) -> Bool {
        let age = now - timestamp
        return scope == currentScope && age.isFinite && age >= 0 && age <= Self.freshS
    }
}

/// Only the latest uncancelled Find may start guidance. Other query kinds never enter this state.
struct FindRequests {
    struct Request: Equatable {
        var id: String
        var name: String
        var scope: NavigationScope
    }
    private(set) var pending: Request?

    mutating func begin(id: String, name: String, scope: NavigationScope) {
        pending = Request(id: id, name: name, scope: scope)
    }

    mutating func cancel() { pending = nil }

    mutating func consume(id: String?, in scope: NavigationScope?) -> Request? {
        guard let request = pending, request.id == id else { return nil }
        pending = nil
        return request.scope == scope ? request : nil
    }
}

/// "Where are my keys?" before the camera has seen them, or when they aren't where it last saw them: Marco says so
/// and keeps watching. The item's next sighting (the server's seen, moved or put_down event) within `windowS`
/// starts guidance as if the answer had found it. A new Find or Stop ends the watch; so does a new scope.
struct Lookout {
    static let windowS = 60.0
    struct Spot: Equatable {
        var itemId: String
        var name: String
        var position: SIMD3<Float>
        var surface: String?
    }
    private(set) var itemId: String?
    private(set) var name = ""
    private(set) var scope: NavigationScope?
    private(set) var spot: Spot?                 // seen, waiting for a usable pose to guide from
    private var until = 0.0

    var watching: Bool { itemId != nil }

    mutating func watch(itemId: String, name: String, scope: NavigationScope, now: Double) {
        self.itemId = itemId
        self.name = name
        self.scope = scope
        spot = nil
        until = now + Self.windowS
    }

    mutating func cancel() {
        itemId = nil
        scope = nil
        spot = nil
    }

    /// A world event from the server: the watched item's new position, if this is a sighting of it.
    mutating func sighted(_ e: WorldEventMsg) {
        guard e.item_id == itemId, ["seen", "moved", "put_down"].contains(e.kind), let p = Geo.vec(e.position) else { return }
        spot = Spot(itemId: e.item_id, name: name, position: p, surface: e.surface)
    }

    /// Where to guide to, once. Call when the pose is usable in `scope`.
    mutating func take() -> Spot? {
        guard let s = spot else { return nil }
        cancel()
        return s
    }

    /// The item's name, once, when the window runs out with nothing seen.
    mutating func expired(now: Double) -> String? {
        guard itemId != nil, spot == nil, now >= until else { return nil }
        let n = name
        cancel()
        return n
    }
}
