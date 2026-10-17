// POC 8b: offline fuzzy matching with Apple's NaturalLanguage sentence embeddings (no Apple
// Intelligence needed; works on every iPhone). Each item gets a few descriptive phrases at
// enrolment ("keys: keys, keyring, house keys"); a request picks the closest phrase.
import Foundation
import NaturalLanguage

let items: [String: [String]] = [
    "keys": ["keys", "house keys", "car keys", "keyring"],
    "wallet": ["wallet", "purse", "cards and cash", "the thing I pay with"],
    "blue water bottle": ["water bottle", "bottle", "something to drink from", "my drink"],
    "glasses case": ["glasses", "spectacles", "specs", "reading glasses"],
    "coffee mug": ["mug", "coffee cup", "my coffee", "tea cup"],
    "TV remote": ["TV remote", "remote control", "clicker", "the remote for the television"],
    "allergy medicine": ["medicine", "pills", "tablets", "allergy medication"],
    "phone charger": ["charger", "charging cable", "phone cable"],
    "white cane": ["cane", "white cane", "walking stick", "my stick"],
]
let queries: [(String, String)] = [
    ("where are my keys", "keys"), ("where's the thing I drink from", "blue water bottle"),
    ("I can't find my specs", "glasses case"), ("where did I leave my pills", "allergy medicine"),
    ("where's the clicker for the telly", "TV remote"), ("where's my stick", "white cane"),
    ("find the thing I pay with", "wallet"), ("my coffee", "coffee mug"),
    ("where is my passport", "none"), ("I need to charge my phone", "phone charger"),
    ("have you seen my car keys", "keys"), ("where did I put my reading glasses", "glasses case"),
]
let heldOut: [(String, String)] = [
    ("where's my keychain", "keys"), ("my cup of tea", "coffee mug"), ("the drink bottle", "blue water bottle"),
    ("where's my medication", "allergy medicine"), ("where's the remote", "TV remote"), ("where's my billfold", "wallet"),
    ("where's my USB cable", "phone charger"), ("my walking cane", "white cane"), ("where's my laptop", "none"),
    ("where are my sunglasses", "glasses case"),
]
let useHeldOut = CommandLine.arguments.count > 1
guard let emb = NLEmbedding.sentenceEmbedding(for: .english) else { print("no sentence embedding"); exit(0) }
var phrases: [(String, String)] = []
for (k, v) in items { for p in v { phrases.append((k, p)) } }
var correct = 0
for (q, exp) in (useHeldOut ? heldOut : queries) {
    // Keep only the object phrase: drop the "where are my ..." scaffolding.
    let stop: Set<String> = ["marco", "where", "where's", "wheres", "is", "are", "my", "the", "did", "i", "leave", "put",
                             "find", "can't", "cant", "have", "you", "seen", "for", "a", "an", "need", "to", "of", "it", "me", "please"]
    let toks = q.lowercased().components(separatedBy: CharacterSet.alphanumerics.union(CharacterSet(charactersIn: "'")).inverted).filter { !$0.isEmpty && !stop.contains($0) }
    let cleaned = toks.joined(separator: " ")
    var best = ("none", Double.infinity)
    for (k, p) in phrases {
        let d = emb.distance(between: cleaned, and: p)
        if d < best.1 { best = (k, d) }
    }
    let pick = best.1 < 0.95 ? best.0 : "none"
    let ok = pick == exp
    correct += ok ? 1 : 0
    print(String(format: "%@ %-40@ -> %-18@ d=%.2f", ok ? "OK " : "BAD", q as NSString, pick as NSString, best.1))
}
print("accuracy \(correct)/\((useHeldOut ? heldOut : queries).count)")
