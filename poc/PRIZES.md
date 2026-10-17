# Prize stack: touch as many tracks as possible, each one genuine

**Basis.** The LA Hacks 2026 prize list, read from Devpost (`research/lahacks/devpost2026.html`). The 2027 list isn't out yet, so re-check it when it is. Rule of thumb from the 2026 page: one main track plus any number of company challenges.

**Judging criteria (2026):** technical depth, product thinking & impact, execution & polish, originality & insight.

**The trap:** shallow "sponsor soup" hurts the main judging. Every integration below does a real job in the product, and the core loop stays on-device so a flaky API can't break the demo.

---

## Architecture: on-device core, sponsors at the edges

```
iPhone (chest vest): ARKit + LiDAR + Vision hand pose + text recognition + spatial audio    <- always on-device (Zetic)
   ├─ unknown or uncertain item ──► Jev (TypeSafe): "which enrolled jar is this?" (Choice with photo options),
   │                                Box for the crop, Noul "is the label readable?"
   │        └─ still unsure ─────► Photon (iMessage): photo to the guardian; voice-memo reply = the label
   ├─ labels / timeline sync ────► MongoDB Atlas (household memory; caregiver view)
   ├─ voices ─────────────────────► ElevenLabs (Marco's voice; typed guardian replies in the guardian's own voice)
   ├─ remote questions ──────────► Fetch.ai agent on Agentverse / ASI:One ("did Dad take his pills?")
   └─ caregiver web app ─────────► Auth0 login, GoDaddy domain (optionally Cloudinary media)
```

---

## Tier 1: build these (high fit, real value)

| Sponsor / track | What it does in Marco | Why it's genuine | Effort | Demo moment |
|---|---|---|---|---|
| **Photon** (iMessage) | 1) Guardian labelling: touch an unknown jar, a photo goes to the guardian, and their voice-memo reply becomes the jar's voice. 2) Heads-up texts: "Mom's blood-pressure pills were moved to the counter", "Dad left without keys". 3) Batch: one shelf photo with numbered jars; the reply "1 cumin, 2 paprika…" labels the whole row. 4) Text Marco "which bottle is my allergy medicine?" and get the answer back | The people around a blind user already live in iMessage, so no new app to install. SDK supports images, multi-image, audio messages, events and attachment download (verified in the docs) | 4–6 h | A judge's phone buzzes with the photo; they reply by voice; the jar speaks in their voice |
| **Jev** (TypeSafe) | 1) **"Which jar is this?"** as a Choice whose options are the enrolled photos of each jar. Returns probabilities, which suits look-alike items. 2) **Box** for the crop of a new item at labelling time ("the jar under the hand in `frame`"), paired with a Noul "is a jar there?" since Box always answers. 3) **Confidence-gated routing:** high confidence, Marco speaks; low, ask the guardian via Photon; medicine below a high bar, "I can't be sure" | Typed answers with probabilities are exactly what a safety gate needs. Keep it *off* the per-frame loop: preview quality ("dreamer-ready"), one box per question, network latency (TypeSafe claims 70–500 ms, text-only, untested here). Use it at labelling time and on uncertain items | 4–6 h | The "AI brain" panel shows Jev's probabilities ("cumin 0.91 / paprika 0.06") before Marco speaks |
| **Zetic** (on-device AI, $1,000 1st in 2026) | Deploy one model through Melange on the iPhone NPU: the open-vocabulary detector, or a jar-embedding model. Show the on-device vs cloud split clearly | Their rule, "primary functionality on-device; cloud only for fallback", is already Marco's architecture | 4–6 h | A live latency counter: touch → name in ~150 ms, airplane mode on |
| **ElevenLabs** (MLH) | Marco's calm voice; labels in any language; typed guardian replies spoken in the guardian's own cloned voice (with consent) | Labels in a loved one's voice are the emotional core of feature B | 2 h | "Cumin," in the judge's own voice, from the jar |
| **Fetch.ai** (Agentverse 1st $2,500; OmegaClaw skill $1,500; ASI:One) | Marco agent registered on Agentverse: caregivers ask through ASI:One "Did Dad take his 8 pm pills?", "Where are Mom's glasses?", "What's on her spice shelf?". Built as an OmegaClaw skill too | A real remote use: family checks without calling | 4–6 h | Ask ASI:One on a laptop; get the answer from the live home memory |
| **Main track** | **Catalyst for Care** (health: medication safety, fall prevention, independent living), or **Light the Way** if 2027's text emphasises accessibility | — | — | — |
| **Best Social Impact / Organizers' Choice / Best UI-UX / Sponsormaxxing** | Automatic candidates: blind-first and older-adult impact; audio-first UX with an accessible caregiver UI; many genuine sponsor integrations | — | — | — |

## Tier 2: cheap adds (an hour or two each)

| Sponsor | Use | Effort |
|---|---|---|
| **MongoDB Atlas** (MLH) | Household memory: labels, item homes, timeline, synced to the caregiver view | 1–2 h |
| **GoDaddy** (MLH) | A domain for the caregiver page / demo site | 15 min |
| **Auth0** (MLH, AI agents) | Who can see whose memory: caregiver login, and scoped access for the Fetch agent | 1–2 h |
| **Figma Make** | Prototype the caregiver dashboard and onboarding in Make, and show the process (the challenge judges process, not polish) | 1 h |
| **Gemma** (MLH) | On-device language model for fuzzy requests ("the thing I drink from") and turning label text into a spoken summary (drug, dose) | 2–3 h |

## Tier 3: only if time is left

- **Best Hardware Hack / Espressif:** a tactile "Marco button" on the vest strap (ESP32, Bluetooth). Press to ask, or to repeat; good in noisy kitchens. A vibration motor can give the "facing it" tick.
- **Cloudinary:** host label photos in the caregiver web app (the challenge requires their React starter kit).
- **Arista** ("connect people to resources"): the guardian network angle. Weak fit; only if its 2027 text matches.

## Skip (no honest fit)

Solana, World (proof of human), Roblox, HHKB, Cognition (2026 asked for tooling that makes AI coding agents better, not a product built with Devin), ASUS GX10 (unless hardware is lent and you run Marco Home on it).

---

## Make each integration count with judges

1. **Show it in the demo**, not just in the README: the Jev probabilities panel, the judge's phone getting the Photon text, airplane mode for Zetic.
2. **One sentence per sponsor on the Devpost page:** what it does and why that sponsor.
3. **Fallbacks:** if Jev, Photon or the cloud are down, the on-device core still finds and names things.
4. **Note on Jev naming:** use TypeSafe's official API (`api.typesafe.ai`, docs at docs.typesafe.ai). Several look-alike "Jev AI" sites (thejevai.com, ai-jev.pro, jevai.info) say they are independent and not affiliated.

## Build plan (4 people, 36 h)

1. **Core (on-device):** vest capture, hand pose, row matching, text recognition, spatial labels, Zetic model.
2. **Labels:** Jev decisions + Photon loop + ElevenLabs voices.
3. **Memory and the people around the user:** Atlas sync, Fetch agent, Auth0, caregiver page (Figma Make → web) + GoDaddy.
4. **Demo, polish, Devpost write-up:** the sponsor sentences, the blindfold test, the video backup.
