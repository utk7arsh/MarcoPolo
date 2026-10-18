import Foundation

/// HTTP to the server: POST /v1/frames (latest frame wins), POST /v1/items, and GETs for label audio.
final class Uploader {
    struct Frame {
        var meta: FrameMeta
        var jpeg: Data
        var depth: Data
        var confidence: Data
    }

    let base: URL
    private let session: URLSession
    private var gate = LatestWins<Frame>()
    private let lock = NSLock()
    /// HTTP status and body (or the error) of each frame upload. A 422 body says what is wrong with the frame.
    var onResult: ((Int, String) -> Void)?

    init(base: URL, session: URLSession = .shared) {
        self.base = base
        self.session = session
    }

    func submit(_ f: Frame) {
        lock.lock()
        let start = gate.offer(f)
        lock.unlock()
        if let start { post(start) }
    }

    static func frameRequest(base: URL, _ f: Frame, boundary: String = "marco-\(UUID().uuidString)") throws -> (URLRequest, Data) {
        var req = URLRequest(url: base.appendingPathComponent("v1/frames"))
        req.httpMethod = "POST"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        let meta = String(decoding: try JSONEncoder().encode(f.meta), as: UTF8.self)
        let body = Wire.multipart(boundary: boundary, fields: [("meta", meta)], files: [
            .init(field: "image", filename: "frame.jpg", contentType: "image/jpeg", data: f.jpeg),
            .init(field: "depth", filename: "frame.depth", contentType: "application/octet-stream", data: f.depth),
            .init(field: "confidence", filename: "frame.conf", contentType: "application/octet-stream", data: f.confidence)])
        return (req, body)
    }

    private func post(_ f: Frame) {
        guard let (req, body) = try? Self.frameRequest(base: base, f) else { return finish() }
        session.uploadTask(with: req, from: body) { [weak self] data, resp, err in
            guard let self else { return }
            let code = (resp as? HTTPURLResponse)?.statusCode ?? -1
            self.onResult?(code, err?.localizedDescription ?? String(decoding: data ?? Data(), as: UTF8.self))
            self.finish()
        }.resume()
    }

    private func finish() {
        lock.lock()
        let next = gate.finished()
        lock.unlock()
        if let next { post(next) }
    }

    /// POST /v1/items: register an item from one ordinary photo and its name (§3.3).
    func register(name: String, photo: Data, completion: @escaping (Result<RegistrationReply, Error>) -> Void) {
        let boundary = "marco-\(UUID().uuidString)"
        var req = URLRequest(url: base.appendingPathComponent("v1/items"))
        req.httpMethod = "POST"
        req.setValue("multipart/form-data; boundary=\(boundary)", forHTTPHeaderField: "Content-Type")
        let body = Wire.multipart(boundary: boundary, fields: [("name", name)],
                                  files: [.init(field: "photo", filename: "photo.jpg", contentType: "image/jpeg", data: photo)])
        session.uploadTask(with: req, from: body) { data, resp, err in
            if let err { return completion(.failure(err)) }
            let code = (resp as? HTTPURLResponse)?.statusCode ?? -1
            guard code == 200, let data, let r = try? JSONDecoder().decode(RegistrationReply.self, from: data) else {
                return completion(.failure(URLError(.badServerResponse)))
            }
            completion(.success(r))
        }.resume()
    }

    /// GET /v1/items: what the server knows, including labels made before this launch.
    func items(completion: @escaping ([ItemInfo]?) -> Void) {
        session.dataTask(with: base.appendingPathComponent("v1/items")) { data, resp, _ in
            guard (resp as? HTTPURLResponse)?.statusCode == 200, let data else { return completion(nil) }
            completion(try? JSONDecoder().decode([ItemInfo].self, from: data))
        }.resume()
    }

    /// GET a server path such as a label_audio_url ("/v1/audio/..."): the body and its MIME type.
    func fetch(path: String, completion: @escaping (Data?, String?) -> Void) {
        guard let url = URL(string: path, relativeTo: base) else { return completion(nil, nil) }
        session.dataTask(with: url) { data, resp, _ in
            let http = resp as? HTTPURLResponse
            completion(http?.statusCode == 200 ? data : nil, http?.mimeType)
        }.resume()
    }
}
