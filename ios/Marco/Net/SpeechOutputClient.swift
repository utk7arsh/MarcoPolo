import Foundation

/// Only already-decided Marco lines leave the phone. No key, recognition, prompts or labels.
/// Called on the main thread; completions return there. A new line or Stop invalidates old replies.
final class SpeechOutputClient {
    typealias Load = (URLRequest, @escaping (Data?, URLResponse?, Error?) -> Void) -> (() -> Void)
    private var base: URL?
    private let load: Load
    private let clock: () -> TimeInterval
    private var cancelLoad: (() -> Void)?
    private var revision = 0
    private var retryAfter: TimeInterval = 0
    private var cache: [(text: String, audio: Data)] = []
    private let maxEntries: Int
    private let maxBytes: Int
    static let maxAudioBytes = 24_000 * 2 * 20 + 44

    init(session: URLSession = SpeechOutputClient.makeSession(), maxEntries: Int = 64,
         maxBytes: Int = 8 * 1024 * 1024,
         clock: @escaping () -> TimeInterval = { ProcessInfo.processInfo.systemUptime }, load: Load? = nil) {
        self.clock = clock
        self.maxEntries = maxEntries
        self.maxBytes = maxBytes
        self.load = load ?? { request, done in
            let task = session.dataTask(with: request, completionHandler: done)
            task.resume()
            return { task.cancel() }
        }
    }

    static func makeSession() -> URLSession {
        let c = URLSessionConfiguration.ephemeral
        c.timeoutIntervalForRequest = 3
        c.timeoutIntervalForResource = 3
        c.waitsForConnectivity = false
        c.httpMaximumConnectionsPerHost = 2
        return URLSession(configuration: c)
    }

    func configure(base: URL?) {
        cancel()
        if self.base != base { cache.removeAll(); retryAfter = 0 }
        self.base = base
    }

    func cancel() {
        revision += 1
        cancelLoad?()
        cancelLoad = nil
    }

    static func request(base: URL, text: String) -> URLRequest {
        var request = URLRequest(url: base.appendingPathComponent("v1/speech"))
        request.httpMethod = "POST"
        request.timeoutInterval = 3
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("audio/wav", forHTTPHeaderField: "Accept")
        request.httpBody = try? JSONEncoder().encode(["text": text])
        return request
    }

    static func validAudio(_ data: Data, response: URLResponse?) -> Bool {
        guard let http = response as? HTTPURLResponse, http.statusCode == 200,
              http.mimeType == "audio/wav", data.count >= 46, data.count <= maxAudioBytes else { return false }
        // /v1/speech wraps raw PCM with Python wave: a fixed 44-byte PCM header.
        // Validate that contract before caching, so a RIFF signature attached to
        // invalid/truncated audio cannot permanently pin this phrase to fallback.
        let h = [UInt8](data.prefix(44))
        func tag(_ offset: Int, _ value: String) -> Bool { h[offset..<(offset + 4)].elementsEqual(value.utf8) }
        func u16(_ i: Int) -> UInt32 { UInt32(h[i]) | UInt32(h[i + 1]) << 8 }
        func u32(_ i: Int) -> UInt32 { u16(i) | u16(i + 2) << 16 }
        let samples = data.count - 44
        return tag(0, "RIFF") && u32(4) == UInt32(data.count - 8) && tag(8, "WAVE") &&
            tag(12, "fmt ") && u32(16) == 16 && u16(20) == 1 && u16(22) == 1 &&
            u32(24) == 24_000 && u32(28) == 48_000 && u16(32) == 2 && u16(34) == 16 &&
            tag(36, "data") && u32(40) == UInt32(samples) && samples % 2 == 0
    }

    /// nil selects the existing Apple voice. Cached phrases are usable during an outage.
    func audio(for text: String, completion: @escaping (Data?) -> Void) {
        cancel()
        let ticket = revision
        if let i = cache.firstIndex(where: { $0.text == text }) {
            let hit = cache.remove(at: i)
            cache.append(hit)
            completion(hit.audio)
            return
        }
        guard let base, text.count <= 360, !text.trimmingCharacters(in: .whitespacesAndNewlines).isEmpty,
              clock() >= retryAfter else { completion(nil); return }
        cancelLoad = load(Self.request(base: base, text: text)) { [weak self] data, response, error in
            DispatchQueue.main.async {
                guard let self, self.revision == ticket else { return }
                self.cancelLoad = nil
                guard error == nil, let data, Self.validAudio(data, response: response) else {
                    self.retryAfter = self.clock() + 15
                    completion(nil)
                    return
                }
                if data.count <= self.maxBytes && self.maxEntries > 0 {
                    self.cache.append((text, data))
                    while self.cache.count > self.maxEntries || self.cache.reduce(0, { $0 + $1.audio.count }) > self.maxBytes {
                        self.cache.removeFirst()
                    }
                }
                completion(data)
            }
        }
    }
}
