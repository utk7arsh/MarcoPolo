// POC 8: can Apple's on-device Foundation Model map fuzzy requests to remembered items?
// Uses guided generation so the answer is always one of the remembered item names (or "none").
import Foundation
import FoundationModels

// (Guided generation via @Generable needs Xcode's macro plugin; with Command Line Tools we ask for
// plain text and validate it against the list, which an app should do anyway.)

let items = ["keys", "wallet", "blue water bottle", "glasses case", "coffee mug", "TV remote", "allergy medicine", "phone charger", "white cane"]
let queries: [(String, String)] = [
    ("Marco, where are my keys?", "keys"),
    ("where's the thing I drink from", "blue water bottle"),
    ("I can't find my specs", "glasses case"),
    ("where did I leave my pills", "allergy medicine"),
    ("where's the clicker for the telly", "TV remote"),
    ("where's my stick", "white cane"),
    ("find the thing I pay with", "wallet"),
    ("my coffee", "coffee mug"),
    ("where is my passport", "none"),
    ("I need to charge my phone", "phone charger"),
]

let model = SystemLanguageModel.default
print("availability: \(model.availability)")
guard case .available = model.availability else { exit(0) }
var correct = 0
let t0 = Date()
for (q, expected) in queries {
    let session = LanguageModelSession(instructions: "You match a person's spoken request to one of their remembered belongings. Items: \(items.joined(separator: ", ")). Reply with exactly one item name copied from the list, or the word none if the request is not about any of these items. Reply with the name only.")
    let s = Date()
    let r = try await session.respond(to: q)
    let raw = r.content.trimmingCharacters(in: .whitespacesAndNewlines.union(.punctuationCharacters)).lowercased()
    let picked = items.first { raw == $0.lowercased() } ?? items.first { raw.contains($0.lowercased()) } ?? (raw.contains("none") ? "none" : "?\(raw)")
    let ok = picked.lowercased() == expected.lowercased()
    correct += ok ? 1 : 0
    print(String(format: "%@  %-45@ -> %-20@ (%.2f s)", ok ? "OK " : "BAD", q as NSString, picked as NSString, Date().timeIntervalSince(s)))
}
print("accuracy \(correct)/\(queries.count), total \(Date().timeIntervalSince(t0)) s")
