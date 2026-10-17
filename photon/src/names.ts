// Turns a caretaker's caption or voice-note transcript into the short name the user can ask for:
// "That's the cumin, love." -> "cumin"; "these are Dad's reading glasses" -> "reading glasses".

const FILLER = /^(?:so|um+|uh+|okay|ok|oh|hey|hi|yes|yeah|yep|well|and|no|wait|sorry|actually|oops)\b[\s,]*/i;
const INTRO = /^(?:this|that|it|these|those|they|here)(?:'s|’s|'re|’re|\s+is|\s+are|\s+was)?\s+/i;
// "the one on the left is paprika": keep what follows the last "is"/"are".
const COPULA = /^.*\s(?:is|are)\s+(?:called\s+|named\s+)?(.+)$/i;
// Cut trailing clauses: "cumin, love", "cumin that grandma brought", "paprika - the smoked one".
const TAIL = /\s*(?:[,.;:!?()"“”]|\s[-–]\s|\b(?:that|which|who|from|for|in|on|with|because|love|honey|sweetie|dear)\b).*$/i;
const DETERMINER = /^(?:the|a|an|some|my|your|his|her|their|our|its)\s+/i;
const POSSESSIVE = /^\p{L}+(?:'s|’s|s'|s’)\s+/u;
const EMOJI = /[\p{Extended_Pictographic}\u{FE0F}\u{200D}]/gu;
const VAGUE = new Set(["it", "this", "that", "thing", "something", "stuff", "idk"]);

export function extractName(raw: string | null | undefined): string | null {
  if (!raw) return null;
  let s = raw.normalize("NFKC").replace(EMOJI, "").replace(/\s+/g, " ").trim();
  s = s.replace(/^["'“”‘’]+/, "").trim();
  for (let i = 0; i < 3; i++) s = s.replace(FILLER, "");
  s = s.replace(INTRO, "");
  s = s.replace(COPULA, "$1");
  s = s.replace(TAIL, "");
  for (let i = 0; i < 3; i++) s = s.replace(DETERMINER, "").replace(POSSESSIVE, "");
  s = s.replace(/["'“”‘’.!?]+$/, "").trim();
  if (!s || VAGUE.has(s.toLowerCase())) return null;
  return s.split(" ").slice(0, 4).join(" ");
}

export function isDontKnow(raw: string | null | undefined): boolean {
  return !!raw && /^(?:i\s+)?(?:don'?t|do not|dunno|no idea|not sure|idk|no clue|can'?t tell)\b/i.test(raw.trim());
}
