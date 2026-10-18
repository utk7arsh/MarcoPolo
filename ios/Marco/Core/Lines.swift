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

/// Turns what the user said into an intent. "Marco, where are my keys?" -> .find("keys").
enum Speech {
    static let wakeWords = ["marco", "marko", "mark o"]

    static func normalize(_ s: String) -> String {
        let t = s.lowercased().replacingOccurrences(of: "\u{2019}", with: "'")
        let kept = t.unicodeScalars.map { CharacterSet.letters.contains($0) || CharacterSet.decimalDigits.contains($0) || $0 == "'" ? Character($0) : " " }
        return String(kept).split(separator: " ").joined(separator: " ")
    }

    /// The words after the last wake word, or nil if no wake word was said.
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

    private static let findPattern = try! NSRegularExpression(
        pattern: "^(?:where(?:'s| is| are| did i (?:put|leave)| have i (?:put|left))|find|locate|look for)\\s+(?:my |the |a |an )?(.+?)(?: please)?$")

    static func intent(_ command: String) -> Intent? {
        let t = normalize(command)
        guard !t.isEmpty else { return nil }
        if ["stop", "cancel", "never mind", "nevermind", "quiet", "be quiet"].contains(where: { t == $0 || t.hasPrefix($0 + " ") }) {
            return .stop
        }
        if ["what is this", "what's this", "whats this", "what is it", "what am i touching", "what am i holding"].contains(where: { t.contains($0) }) {
            return .whatIsThis
        }
        if ["this is the door", "mark the door", "set the door", "here is the door", "this is the front door"].contains(where: { t.contains($0) }) {
            return .setDoor
        }
        let ns = t as NSString
        if let m = findPattern.firstMatch(in: t, range: NSRange(location: 0, length: ns.length)) {
            let name = ns.substring(with: m.range(at: 1)).trimmingCharacters(in: .whitespaces)
            return name.isEmpty ? nil : .find(name)
        }
        return nil
    }
}
