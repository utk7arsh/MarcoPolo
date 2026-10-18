import Foundation

/// Capture state and permission tickets are independent of ARKit so stop/retry races can be tested on a Mac.
struct CaptureControl {
    enum Phase: Hashable {
        case ready, permission, starting, running, denied, unsupported, interrupted, failed
    }
    private(set) var phase: Phase = .ready
    private(set) var generation = 0

    var title: String {
        switch phase {
        case .ready: return "Ready to\nstart."
        case .permission: return "Camera\naccess."
        case .starting: return "Starting\ncamera."
        case .running: return "Camera\nrunning."
        case .denied, .failed, .interrupted: return "Needs\nattention."
        case .unsupported: return "LiDAR\nrequired."
        }
    }
    var label: String {
        switch phase {
        case .ready: return "Ready"
        case .permission: return "Awaiting access"
        case .starting: return "Starting"
        case .running: return "Running"
        case .denied: return "Access disabled"
        case .unsupported: return "Not supported"
        case .interrupted: return "Interrupted"
        case .failed: return "Unavailable"
        }
    }
    var action: String {
        switch phase {
        case .running: return "Stop camera"
        case .starting: return "Cancel"
        case .denied: return "Open Settings"
        case .permission: return "Allow camera access"
        case .unsupported: return "LiDAR required"
        default: return "Start camera"
        }
    }
    var needsAttention: Bool { [.denied, .failed, .interrupted].contains(phase) }
    mutating func begin(supported: Bool) -> Int? {
        guard ![.permission, .starting, .running].contains(phase) else { return nil }
        guard supported else { phase = .unsupported; return nil }
        generation += 1
        phase = .permission
        return generation
    }
    mutating func permission(granted: Bool, ticket: Int) -> Bool {
        guard ticket == generation, phase == .permission else { return false }
        phase = granted ? .starting : .denied
        return granted
    }
    mutating func firstFrame(ticket: Int) {
        guard ticket == generation, phase == .starting else { return }
        phase = .running
    }
    mutating func stop(reason: Phase = .ready) {
        generation += 1
        phase = reason
    }
}

enum ControlServerAddress {
    static func parse(_ value: String) -> URL? {
        guard let c = URLComponents(string: value.trimmingCharacters(in: .whitespacesAndNewlines)),
              ["http", "https"].contains(c.scheme?.lowercased() ?? ""),
              let host = c.host, !host.isEmpty,
              c.user == nil, c.password == nil, c.query == nil, c.fragment == nil else { return nil }
        return c.url
    }
}

struct AudioRouteState: Hashable {
    var name = "Unknown"
    var external = false
    var spatial: Bool?
    var spatialLabel: String {
        switch spatial {
        case true: return "Spatial audio available"
        case false: return "Spatial audio off"
        case nil: return "Spatial audio unknown"
        }
    }
}
