import Foundation

/// Records what the phone sends, on the phone, in the server's own recording layout (server/marco/recorder.py):
///
///   <root>/<session_id>/frames.jsonl            one line per frame: the meta JSON + received_wall
///   <root>/<session_id>/frames/<id:06d>.jpg     the JPEG as sent
///   <root>/<session_id>/frames/<id:06d>.depth   DEFLATE(float16) as sent
///   <root>/<session_id>/frames/<id:06d>.conf    DEFLATE(uint8) as sent
///   <root>/<session_id>/phone.jsonl             every WebSocket message (pose, hand, guidance, query, map) + received_wall
///
/// So a walk recorded in the vest with no server or network (INTERFACES.md §8.4) goes straight into server/tools
/// (check_recording, inspect_session, run_offline, replay). Messages are recorded whether or not the socket is up.
/// Safe from any thread; files are written on the recorder's own queue.
final class Recorder {
    let root: URL
    private let queue = DispatchQueue(label: "marco.recorder", qos: .utility)
    private let lock = NSLock()
    private var dir: URL?                        // the recorder queue only
    private var active = false
    private var counts = (frames: 0, messages: 0, bytes: 0)

    init(root: URL) { self.root = root }

    static var documents: URL {
        FileManager.default.urls(for: .documentDirectory, in: .userDomainMask)[0].appendingPathComponent("sessions")
    }

    var isRecording: Bool { lock.lock(); defer { lock.unlock() }; return active }
    var progress: (frames: Int, messages: Int, bytes: Int) { lock.lock(); defer { lock.unlock() }; return counts }

    /// The folder name the server would use for this session id (letters, digits, - and _ only, at most 64).
    static func folderName(_ sessionId: String) -> String {
        let safe = String(sessionId.filter { $0.isLetter || $0.isNumber || $0 == "-" || $0 == "_" }.prefix(64))
        return safe.isEmpty ? "unknown" : safe
    }

    /// Starts (or resumes, for the same session id) a recording. Returns its folder.
    @discardableResult
    func start(sessionId: String) -> URL {
        let d = root.appendingPathComponent(Self.folderName(sessionId))
        lock.lock()
        active = true
        lock.unlock()
        queue.async {
            try? FileManager.default.createDirectory(at: d.appendingPathComponent("frames"), withIntermediateDirectories: true)
            self.dir = d
        }
        return d
    }

    func stop() {
        lock.lock()
        active = false
        lock.unlock()
        queue.async { self.dir = nil }
    }

    /// One frame upload, as sent.
    func frame(meta: Data, frameId: Int, jpeg: Data, depth: Data, confidence: Data) {
        guard isRecording else { return }
        queue.async {
            guard let d = self.dir else { return }
            let base = d.appendingPathComponent("frames").appendingPathComponent(String(format: "%06d", frameId))
            do {
                try jpeg.write(to: base.appendingPathExtension("jpg"))
                try depth.write(to: base.appendingPathExtension("depth"))
                try confidence.write(to: base.appendingPathExtension("conf"))
                let n = self.append(Self.stamped(meta), to: d.appendingPathComponent("frames.jsonl"))
                self.count(frames: 1, bytes: jpeg.count + depth.count + confidence.count + n)
            } catch {}
        }
    }

    /// One phone-to-server WebSocket message, as sent (JSON bytes).
    func message(_ json: Data) {
        guard isRecording else { return }
        queue.async {
            guard let d = self.dir else { return }
            let n = self.append(Self.stamped(json), to: d.appendingPathComponent("phone.jsonl"))
            self.count(messages: 1, bytes: n)
        }
    }

    /// Waits until everything handed to the recorder is on disk (tests, and before zipping).
    func flush() { queue.sync {} }

    /// The JSON object with `"received_wall": <unix seconds>` added, as the server's recorder writes it.
    static func stamped(_ json: Data, wall: Double = Date().timeIntervalSince1970) -> Data {
        guard let close = json.lastIndex(of: UInt8(ascii: "}")) else { return json }
        let empty = json[..<close].allSatisfy { $0 == UInt8(ascii: "{") || $0 == UInt8(ascii: " ") }
        var out = Data(json[..<close])
        out.append(Data("\(empty ? "" : ",")\"received_wall\":\(wall)}".utf8))
        return out
    }

    private func append(_ line: Data, to file: URL) -> Int {
        var data = line
        data.append(0x0A)
        if let h = try? FileHandle(forWritingTo: file) {
            defer { try? h.close() }
            _ = try? h.seekToEnd()
            try? h.write(contentsOf: data)
        } else {
            try? data.write(to: file)
        }
        return data.count
    }

    private func count(frames: Int = 0, messages: Int = 0, bytes: Int) {
        lock.lock()
        counts.frames += frames
        counts.messages += messages
        counts.bytes += bytes
        lock.unlock()
    }
}
