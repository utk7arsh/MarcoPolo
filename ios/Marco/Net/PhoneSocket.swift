import Foundation

/// The /v1/phone WebSocket (docs/INTERFACES.md §3.2 and §4): JSON both ways, reconnects with backoff, and pings
/// so idle connections stay open. Safe to call from any thread.
final class PhoneSocket: NSObject, URLSessionWebSocketDelegate {
    let url: URL
    var onMessage: ((ServerMessage) -> Void)?
    var onState: ((Bool) -> Void)?
    var onUndecodable: ((String) -> Void)?

    private let queue = DispatchQueue(label: "marco.socket")
    private var session: URLSession!
    private var task: URLSessionWebSocketTask?
    private var open = false
    private var stopped = true
    private var backoff = 0.5
    private var held: [String] = []          // sendWhenOpen messages waiting for a connection
    private let encoder = JSONEncoder()

    init(base: URL) {
        url = Self.socketURL(base)
        super.init()
        session = URLSession(configuration: .default, delegate: self, delegateQueue: nil)
    }

    static func socketURL(_ base: URL) -> URL {
        var c = URLComponents(url: base.appendingPathComponent("v1/phone"), resolvingAgainstBaseURL: false)!
        c.scheme = c.scheme == "https" ? "wss" : "ws"
        return c.url!
    }

    func connect() {
        queue.async {
            self.stopped = false
            self.openTask()
        }
    }

    func close() {
        queue.async {
            self.stopped = true
            self.task?.cancel(with: .goingAway, reason: nil)
            self.task = nil
        }
    }

    /// Fire and forget (poses, hands, guidance): dropped while disconnected, because stale ones are useless.
    func send<T: Encodable>(_ msg: T) {
        guard let s = encode(msg) else { return }
        send(text: s)
    }

    /// Held until the socket is open (map lifecycle, queries).
    func sendWhenOpen<T: Encodable>(_ msg: T) {
        guard let s = encode(msg) else { return }
        sendWhenOpen(text: s)
    }

    /// Already-encoded JSON, so a caller that also records it encodes once and records exactly what was sent.
    func send(json: Data) { send(text: String(decoding: json, as: UTF8.self)) }
    func sendWhenOpen(json: Data) { sendWhenOpen(text: String(decoding: json, as: UTF8.self)) }

    private func send(text s: String) {
        queue.async {
            guard self.open, let task = self.task else { return }
            task.send(.string(s)) { err in
                if err != nil { self.queue.async { self.dropped(task) } }
            }
        }
    }

    private func sendWhenOpen(text s: String) {
        queue.async {
            if self.open, let task = self.task {
                task.send(.string(s)) { _ in }
            } else {
                self.held = Array((self.held + [s]).suffix(20))
            }
        }
    }

    private func encode<T: Encodable>(_ msg: T) -> String? {
        guard let d = try? encoder.encode(msg) else { return nil }
        return String(decoding: d, as: UTF8.self)
    }

    private func openTask() {
        guard !stopped else { return }
        let t = session.webSocketTask(with: url)
        task = t
        t.resume()
        receive(t)
    }

    private func receive(_ t: URLSessionWebSocketTask) {
        t.receive { [weak self] result in
            guard let self else { return }
            switch result {
            case .success(let m):
                var data: Data?
                switch m {
                case .string(let s): data = Data(s.utf8)
                case .data(let d): data = d
                @unknown default: data = nil
                }
                if let data {
                    if let msg = try? ServerMessage.decode(data) {
                        self.onMessage?(msg)
                    } else {
                        self.onUndecodable?(String(decoding: data.prefix(200), as: UTF8.self))
                    }
                }
                self.receive(t)
            case .failure:
                self.queue.async { self.dropped(t) }
            }
        }
    }

    private func dropped(_ t: URLSessionWebSocketTask) {
        guard t === task else { return }
        task = nil
        if open {
            open = false
            onState?(false)
        }
        guard !stopped else { return }
        let wait = backoff
        backoff = min(backoff * 2, 8)
        queue.asyncAfter(deadline: .now() + wait) { self.openTask() }
    }

    private func ping(_ t: URLSessionWebSocketTask) {
        queue.asyncAfter(deadline: .now() + 10) { [weak self] in
            guard let self, t === self.task, self.open else { return }
            t.sendPing { err in
                if err != nil { self.queue.async { self.dropped(t) } } else { self.ping(t) }
            }
        }
    }

    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask, didOpenWithProtocol protocol: String?) {
        queue.async {
            guard webSocketTask === self.task else { return }
            self.open = true
            self.backoff = 0.5
            self.onState?(true)
            for s in self.held { webSocketTask.send(.string(s)) { _ in } }
            self.held.removeAll()
            self.ping(webSocketTask)
        }
    }

    func urlSession(_ session: URLSession, webSocketTask: URLSessionWebSocketTask,
                    didCloseWith closeCode: URLSessionWebSocketTask.CloseCode, reason: Data?) {
        // 1008 = the server's auth gate said no (check TAILSCALE_ALLOWED_LOGINS on the server).
        queue.async { self.dropped(webSocketTask) }
    }
}
