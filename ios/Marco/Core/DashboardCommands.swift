import Foundation
import simd

/// What the app does with a dashboard `command` (docs/INTERFACES.md §4), as pure logic: drop repeats, refuse
/// commands for another session or past their deadline, and hand Find (the exact item and its position) or Stop
/// back to the app, which acks accepted, then applied or rejected.
enum CommandDecision: Equatable {
    case duplicate                                    // already handled: say nothing
    case reject(String)                               // ack "rejected" with this reason
    case find(itemId: String, name: String, position: SIMD3<Float>, surface: String?)
    case stop
}

struct CommandGate {
    static let lateSlackS = 2.0                       // clocks differ a little between the phone and the server
    private(set) var seen: [String] = []              // newest last, bounded

    mutating func check(_ c: CommandMsg, sessionId: String, now: Date = Date()) -> CommandDecision {
        if seen.contains(c.command_id) { return .duplicate }
        seen.append(c.command_id)
        if seen.count > 50 { seen.removeFirst(seen.count - 50) }
        guard c.session_id == sessionId else { return .reject("session_mismatch: this iPhone is on another session") }
        if let e = c.expires_wall, let deadline = Self.wall(e), now.timeIntervalSince(deadline) > Self.lateSlackS {
            return .reject("expired: the command arrived too late")
        }
        switch c.action {
        case "stop":
            return .stop
        case "find":
            guard let id = c.item_id, let p = Geo.vec(c.position) else { return .reject("invalid: Find needs an item and a position") }
            return .find(itemId: id, name: c.name ?? "item", position: p, surface: c.surface)
        default:
            return .reject("invalid: unknown action \(c.action)")
        }
    }

    static func wall(_ s: String) -> Date? {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
        if let d = f.date(from: s) { return d }
        f.formatOptions = [.withInternetDateTime]
        return f.date(from: s)
    }
}
