import Foundation
import MetricKit

/// Keeps Apple's MetricKit diagnostics (crashes, CPU and disk-write limit hits, hangs, each with call stacks) as JSON in
/// Documents/diagnostics, which Finder shows under iPhone > Files > Marco Polo. iOS hands them over on the next
/// launch after the event, so a crash during a demo can be read afterwards instead of guessed at.
final class CrashReports: NSObject, MXMetricManagerSubscriber {
    static let shared = CrashReports()

    private var started = false
    private static var folder: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("diagnostics")
    }

    func start() {
        guard !started else { return }
        started = true
        MXMetricManager.shared.add(self)
    }

    func didReceive(_ payloads: [MXDiagnosticPayload]) {
        let dir = Self.folder
        try? FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        let stamp = ISO8601DateFormatter().string(from: Date()).replacingOccurrences(of: ":", with: "-")
        for (i, p) in payloads.enumerated() {
            let kinds = [p.crashDiagnostics.map { "crash\($0.count)" }, p.cpuExceptionDiagnostics.map { "cpu\($0.count)" },
                         p.hangDiagnostics.map { "hang\($0.count)" }, p.diskWriteExceptionDiagnostics.map { "disk\($0.count)" }]
                .compactMap { $0 }.joined(separator: "-")
            let name = "marco-\(stamp)-\(i)\(kinds.isEmpty ? "" : "-" + kinds).json"
            try? p.jsonRepresentation().write(to: dir.appendingPathComponent(name), options: .atomic)
        }
    }
}
