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
