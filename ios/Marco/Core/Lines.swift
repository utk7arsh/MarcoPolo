import Foundation

/// Everything Marco says, in one place (so wording changes don't touch the logic).
enum Lines {
    static let bearings = "Getting my bearings."     // never say the wake word: the mic would hear it
    static let doorSet = "Got it, this is the door."
    static let notUnderstood = "Sorry, I didn't catch that."
    static let noServer = "I can't reach the server."
    static let positionUnavailable = "Position unavailable. Wait for tracking to recover, then ask me again."

    static func number(_ n: Int) -> String {
        let words = ["zero", "one", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", "eleven", "twelve"]
        return n >= 0 && n < words.count ? words[n] : String(n)
    }

    /// Clock directions, the way orientation and mobility training says them.
    static func direction(clock c: Int) -> String {
        switch c {
        case 12: return "straight ahead"
        case 6: return "behind you"
        case 3: return "on your right"
        case 9: return "on your left"
        default: return "at \(number(c)) o'clock"
        }
    }

    /// §7 step 2: "Polo! Behind you, two steps, on the table."
    static func polo(relAzimuthDeg: Double, distanceM: Double, surface: String?) -> String {
        let dir = direction(clock: Geo.clockPosition(relAzimuthDeg))
        let on = surface.map { ", on the \($0)" } ?? ""
        if distanceM <= Guidance.withinReachM {
            return "Polo! Within reach, \(dir)\(on)."
        }
        let n = Geo.steps(distanceM)
        return "Polo! \(capitalized(dir)), \(number(n)) \(n == 1 ? "step" : "steps")\(on)."
    }

    static func notFound(_ a: FindAnswer, asked: String) -> String {
        let name = a.name ?? asked
        switch a.reason {
        case "not_registered": return "I don't know your \(name) yet. Send me a photo of it."
        case "never_seen": return "I haven't seen your \(name) yet."
        case "not_where_last_seen":
            return "Your \(name) isn't where I last saw it" + (a.surface.map { ", on the \($0)." } ?? ".")
        default: return "I can't find your \(name)."
        }
    }

    /// The caretaker's words, unless they were just the name: then "That's the cumin."
    static func spokenLabel(name: String?, labelText: String?) -> String? {
        let text = labelText?.trimmingCharacters(in: .whitespacesAndNewlines)
        if let text, !text.isEmpty, text.lowercased() != name?.lowercased() { return text }
        return name.map { "That's the \($0)." }
    }

    static func whatIsThis(_ a: WhatAnswer) -> String? {
        switch a.status {
        case "known": return spokenLabel(name: a.name, labelText: a.label_text)
        case "unknown": return "I don't know this one yet. I've sent a photo to your helper."
        case "no_touch": return "Touch it first, then ask me what it is."
        default: return nil
        }
    }

    static func touchedKnown(name: String?, labelText: String?) -> String? {
        spokenLabel(name: name, labelText: labelText)
    }

    static func labelReady(_ m: LabelReadyMsg) -> String { "Your helper says that's the \(m.name)." }

    static func leftBehind(_ e: WorldEventMsg) -> String {
        "You left your \(e.name)" + (e.surface.map { " on the \($0)." } ?? ".")
    }

    static func registration(_ r: RegistrationReply, name: String) -> String {
        r.quality == "ok" ? "Saved your \(name)." : "I can't see the \(name) clearly, try again."
    }

    private static func capitalized(_ s: String) -> String { s.prefix(1).uppercased() + s.dropFirst() }
}

enum Intent: Equatable {
    case find(String)
    case whatIsThis
    case setDoor
    case stop
}

/// Turns what the user said into an intent. "Marco, where are my keys?" -> .find("keys"). With the registered items
/// (ItemVocabulary), the name is the item's own: "Marco, have you seen my car keys?" -> .find("keys").
enum Speech {
    /// "Marco" and the ways speech recognition writes it (the recognizer is also given "Marco" as a hint).
    static let wakeWords = ["marco", "marko", "mark o", "marc o", "mark oh"]

    static func normalize(_ s: String) -> String {
        let t = s.lowercased().replacingOccurrences(of: "\u{2019}", with: "'")
        let kept = t.unicodeScalars.map { CharacterSet.letters.contains($0) || CharacterSet.decimalDigits.contains($0) || $0 == "'" ? Character($0) : " " }
        return String(kept).split(separator: " ").joined(separator: " ")
    }

    /// The words after the last wake word, or nil if no wake word was said. "" is the wake word alone.
    static func command(after transcript: String) -> String? {
        let t = " " + normalize(transcript) + " "
        var best: Range<String.Index>?
        for w in wakeWords {
            if let r = t.range(of: " \(w) ", options: .backwards), best == nil || r.lowerBound > best!.lowerBound {
                best = r
            }
        }
        guard let r = best else { return nil }
        return String(t[r.upperBound...]).trimmingCharacters(in: .whitespaces)
    }

    /// Said before the request itself: "Marco Polo, ...", "Marco, hey, could you ...".
    private static let leadIns = ["hey", "hi", "ok", "okay", "um", "uh", "so", "oh", "and", "polo", "please",
                                  "can you", "could you", "would you", "will you", "can u"]
    /// How people ask for a thing, longest first so "where did i put" wins over "where".
    private static let findOpeners = [
        "where did i put", "where did i leave", "where have i put", "where have i left", "where'd i put", "where'd i leave",
        "where can i find", "do you know where", "you know where", "where did", "where'd",
        "where are", "where is", "where's", "wheres", "where", "have you seen", "did you see", "you seen",
        "help me find", "find", "locate", "look for", "looking for", "i'm looking for", "im looking for", "i am looking for",
        "i can't find", "i cant find", "i cannot find", "can't find", "cant find", "i lost", "i've lost", "ive lost",
        "i misplaced", "take me to", "guide me to", "lead me to", "show me", "get me",
    ].sorted { $0.count > $1.count }
    /// Said after the thing: "where my keys at", "do you know where my wallet is", "where did my keys go".
    private static let tails: Set<String> = ["please", "at", "now", "again", "go", "went", "gone", "is", "are", "for", "me",
                                             "then", "today", "right"]
    private static let determiners: Set<String> = ["my", "the", "a", "an", "our", "your", "his", "her", "their", "some"]
    private static let pronouns: Set<String> = ["it", "them", "that", "this", "those", "these", "they", "thing", "something", "stuff"]

    struct Parsed: Equatable {
        let intent: Intent?
        let match: ItemMatch?        // the registered item a find resolved to, if any
    }

    static func intent(_ command: String, items: ItemVocabulary = ItemVocabulary()) -> Intent? {
        parse(command, items: items).intent
    }

    /// Nothing more is needed to act on it: a stop, a what-is-this, or a find that names all of a registered item.
    /// The listener then answers after a shorter pause.
    static func isComplete(_ command: String, items: ItemVocabulary) -> Bool {
        let p = parse(command, items: items)
        switch p.intent {
        case .find?: return p.match?.complete == true
        case nil: return false
        default: return true
        }
    }

    static func parse(_ command: String, items: ItemVocabulary = ItemVocabulary()) -> Parsed {
        let t = strip(normalize(command), leading: leadIns)
        guard !t.isEmpty else { return Parsed(intent: nil, match: nil) }
        if ["stop", "cancel", "never mind", "nevermind", "quiet", "be quiet", "shut up"].contains(where: { t == $0 || t.hasPrefix($0 + " ") }) {
            return Parsed(intent: .stop, match: nil)
        }
        if ["what is this", "what's this", "whats this", "what is it", "what am i touching", "what am i holding"].contains(where: { t.contains($0) }) {
            return Parsed(intent: .whatIsThis, match: nil)
        }
        if ["this is the door", "mark the door", "set the door", "here is the door", "this is the front door"].contains(where: { t.contains($0) }) {
            return Parsed(intent: .setDoor, match: nil)
        }
        if let opener = findOpeners.first(where: { t == $0 || t.hasPrefix($0 + " ") }) {
            return find(thing(String(t.dropFirst(opener.count))), items: items)
        }
        // Just the thing ("Marco, keys?"), only when it is all of a registered item's name.
        if let m = items.resolve(t), m.complete { return Parsed(intent: .find(m.name), match: m) }
        return Parsed(intent: nil, match: nil)
    }

    /// "my keys are" -> "keys".
    private static func thing(_ s: String) -> String {
        var w = s.split(separator: " ").map(String.init)
        while let last = w.last, tails.contains(last) { w.removeLast() }
        while let first = w.first, determiners.contains(first) { w.removeFirst() }
        return w.joined(separator: " ")
    }

    private static func find(_ said: String, items: ItemVocabulary) -> Parsed {
        guard !said.isEmpty, !pronouns.contains(said) else { return Parsed(intent: nil, match: nil) }
        if let m = items.resolve(said) { return Parsed(intent: .find(m.name), match: m) }
        // "my keys and my wallet": one thing at a time, the first.
        if let r = said.range(of: " and "), let m = items.resolve(String(said[..<r.lowerBound])) {
            return Parsed(intent: .find(m.name), match: m)
        }
        return Parsed(intent: .find(said), match: nil)        // not registered here: the server decides
    }

    private static func strip(_ t: String, leading: [String]) -> String {
        var s = t
        var changed = true
        while changed {
            changed = false
            for w in leading where s == w || s.hasPrefix(w + " ") {
                s = String(s.dropFirst(w.count)).trimmingCharacters(in: .whitespaces)
                changed = true
            }
        }
        return s
    }
}
