import Foundation

/// One GET /v1/items when the app starts, turned into a sentence that says what to fix. The server (venue Mac or
/// the Vultr box, `deploy/vultr/`) is only reachable over the tailnet through `tailscale serve`, so most failures
/// are "Tailscale is off on the phone" or "this phone's login isn't on the allow-list", not bugs.
enum ServerCheck {
    /// GET /v1/items with a short timeout; reports the outcome (and the item count) on the main thread.
    static func run(base: URL, session: URLSession = .shared, report: @escaping (String) -> Void) {
        var req = URLRequest(url: base.appendingPathComponent("v1/items"))
        req.timeoutInterval = 6
        let t0 = ProcessInfo.processInfo.systemUptime
        session.dataTask(with: req) { data, resp, err in
            let ms = (ProcessInfo.processInfo.systemUptime - t0) * 1000
            let code = (resp as? HTTPURLResponse)?.statusCode
            let items = (data.flatMap { try? JSONSerialization.jsonObject(with: $0) } as? [Any])?.count
            let line = describe(host: base.host ?? "the server", status: code, error: (err as? URLError)?.code, ms: ms, items: items)
            DispatchQueue.main.async { report(line) }
        }.resume()
    }

    static func describe(host: String, status: Int?, error: URLError.Code?, ms: Double, items: Int?) -> String {
        if let error {
            switch error {
            case .cannotFindHost, .dnsLookupFailed:
                return "Can't find \(host). Is the Tailscale app on, and signed in to the team tailnet?"
            case .secureConnectionFailed, .serverCertificateUntrusted, .serverCertificateHasBadDate,
                 .serverCertificateNotYetValid, .serverCertificateHasUnknownRoot:
                return "HTTPS failed with \(host). Use the https://<machine>.<tailnet>.ts.net name that `tailscale serve` prints."
            case .notConnectedToInternet:
                return "This phone is offline. Join Wi-Fi or use cellular, with Tailscale on."
            case .appTransportSecurityRequiresSecureConnection:
                return "iOS blocks plain http to \(host). Use the https://….ts.net address."
            default:
                return "Can't reach \(host) (\(error.rawValue)). Is Tailscale connected, and is the server up (`marco-vultr.sh status`)?"
            }
        }
        switch status {
        case 200?:
            return String(format: "Server OK: %d item%@ registered, %.0f ms.", items ?? 0, items == 1 ? "" : "s", ms)
        case 403?:
            return "The server refused this phone (403): add its tailnet login to TAILSCALE_ALLOWED_LOGINS and redeploy."
        case let c?:
            return "The server answered HTTP \(c) to GET /v1/items."
        case nil:
            return "No answer from \(host)."
        }
    }
}
