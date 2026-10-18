import Foundation

/// A value shared between the ARKit queue, the hand queue and the main thread.
final class Locked<T> {
    private var value: T
    private let lock = NSLock()

    init(_ value: T) { self.value = value }

    func read<R>(_ f: (T) -> R) -> R {
        lock.lock()
        defer { lock.unlock() }
        return f(value)
    }

    func write(_ f: (inout T) -> Void) {
        lock.lock()
        defer { lock.unlock() }
        f(&value)
    }
}
