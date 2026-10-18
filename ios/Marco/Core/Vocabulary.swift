import Foundation

/// The items the user has registered, by the names the server knows them by, and the matching that turns what was
/// said into one of them: "car keys" -> "keys", "my specs" -> "glasses case", "walet" (a recognizer slip) -> "wallet".
/// The server also matches names (exact, plural, substring), so a phrase that matches nothing here is sent as heard.
struct ItemVocabulary {
    private(set) var names: [String] = []

    init(_ names: [String] = []) { for n in names { add(n) } }

    /// True if the name was new.
    @discardableResult
    mutating func add(_ name: String) -> Bool {
        let n = name.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !n.isEmpty, !names.contains(where: { $0.lowercased() == n.lowercased() }) else { return false }
        names.append(n)
        return true
    }

    /// The registered item a phrase names. nil if none does, or if two fit equally well ("jar", with a cumin jar and a
    /// paprika jar registered): then the words go to the server as heard.
    func resolve(_ phrase: String) -> ItemMatch? {
        let p = Words.content(phrase)
        guard !p.isEmpty else { return nil }
        var best: ItemMatch?
        var tied = false
        for name in names {
            guard let m = Words.compare(p, Words.content(name), name: name) else { continue }
            if let b = best, abs(m.score - b.score) < 1e-9 {
                tied = true
            } else if best == nil || m.score > best!.score {
                best = m
                tied = false
            }
        }
        return tied ? nil : best
    }
}

struct ItemMatch: Equatable {
    enum How: String { case exact, synonym, spelling, partial }
    let name: String
    let how: How
    let score: Double
    /// All of the name and nothing else was said (synonyms and one-letter slips allowed), so the command can go out
    /// without waiting for more words.
    var complete: Bool { score >= 1 }
}

/// Word-level matching for item names: content words only, plurals folded, a few everyday synonyms.
enum Words {
    /// Determiners and fillers that never name an item.
    static let stop: Set<String> = ["my", "the", "a", "an", "our", "your", "his", "her", "their", "its", "some", "of",
                                    "for", "me", "please", "that", "this", "those", "these"]

    /// Everyday words for the same thing, as stems. Kept small: a wrong synonym sends the user to the wrong item.
    static let synonyms: [[String]] = [
        ["key", "keyring", "keychain", "fob"],
        ["wallet", "billfold", "cardholder"],
        ["glass", "spec", "spectacle", "eyeglass", "sunglass", "shade"],
        ["phone", "iphone", "cellphone", "cell", "mobile"],
        ["remote", "clicker", "controller"],
        ["mug", "cup", "teacup"],
        ["bottle", "flask", "tumbler", "thermos"],
        ["medicine", "medication", "med", "pill", "prescription"],
        ["headphone", "earphone", "earbud", "airpod"],
        ["charger", "cable", "cord"],
        ["cane", "stick"],
        ["bag", "backpack", "rucksack", "handbag", "tote"],
    ]
    private static let concept: [String: Int] = {
        var m: [String: Int] = [:]
        for (i, group) in synonyms.enumerated() { for w in group { m[w] = i } }
        return m
    }()

    /// The stems of the words that could name an item: "my car keys" -> ["car", "key"].
    static func content(_ s: String) -> [String] {
        Speech.normalize(s).split(separator: " ").map { w -> String in
            var t = String(w)
            if t.hasSuffix("'s") { t.removeLast(2) }
            return t.replacingOccurrences(of: "'", with: "")
        }.filter { !$0.isEmpty && !stop.contains($0) }.map(stem)
    }

    /// Folds plurals the same way on both sides; consistency matters more than grammar here.
    static func stem(_ w: String) -> String {
        if w.count > 4 && w.hasSuffix("ies") { return String(w.dropLast(3)) + "y" }                  // batteries
        if w.count > 4 && ["sses", "xes", "ches", "shes"].contains(where: { w.hasSuffix($0) }) {     // glasses, boxes
            return String(w.dropLast(2))
        }
        if w.count > 3 && w.hasSuffix("s") && !["ss", "us", "is"].contains(where: { w.hasSuffix($0) }) {
            return String(w.dropLast())                                                              // keys
        }
        return w
    }

    /// 0: the same word, 1: a synonym, 2: one letter off (5+ letters, so "cane" never matches "cake"), nil: different.
    static func level(_ a: String, _ b: String) -> Int? {
        if a == b { return 0 }
        if let x = concept[a], x == concept[b] { return 1 }
        if a.count >= 5, b.count >= 5, editDistance(a, b) <= 1 { return 2 }
        return nil
    }

    /// Scores a said phrase against one name, both as stems. All words of both: 1 and up. The name plus more words
    /// ("car keys" for "keys"): 0.8 and up. Part of the name ("bottle" for "blue water bottle"): 0.7 and up. The
    /// same last word, the noun ("red mug" for "coffee mug"): 0.5 and up. Overlap breaks ties within a tier.
    static func compare(_ p: [String], _ n: [String], name: String) -> ItemMatch? {
        guard !p.isEmpty, !n.isEmpty else { return nil }
        var worst = 0
        var nameHit = Array(repeating: false, count: n.count)
        var saidHit = Array(repeating: false, count: p.count)
        for (i, a) in n.enumerated() {
            for (j, b) in p.enumerated() {
                guard let l = level(b, a) else { continue }
                nameHit[i] = true
                saidHit[j] = true
                worst = max(worst, l)
            }
        }
        let nh = nameHit.filter { $0 }.count, sh = saidHit.filter { $0 }.count
        guard nh > 0 else { return nil }
        let base: Double
        if nh == n.count && sh == p.count { base = 1.0 }
        else if nh == n.count { base = 0.8 }
        else if sh == p.count { base = 0.7 }
        else if nameHit[n.count - 1] && saidHit[p.count - 1] { base = 0.5 }
        else { return nil }
        let overlap = Double(nh + sh) / Double(n.count + p.count)
        let score = base + 0.1 * overlap - [0, 0.03, 0.06][worst]
        let how: ItemMatch.How = base < 1 ? .partial : [.exact, .synonym, .spelling][worst]
        return ItemMatch(name: name, how: how, score: score)
    }

    static func editDistance(_ a: String, _ b: String) -> Int {
        let x = Array(a), y = Array(b)
        if x.isEmpty || y.isEmpty { return max(x.count, y.count) }
        var row = Array(0...y.count)
        for i in 1...x.count {
            var diag = row[0]
            row[0] = i
            for j in 1...y.count {
                let up = row[j]
                row[j] = min(up + 1, row[j - 1] + 1, diag + (x[i - 1] == y[j - 1] ? 0 : 1))
                diag = up
            }
        }
        return row[y.count]
    }
}
