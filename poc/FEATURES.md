# Marco Polo: the helpful features, specified and checked

Each feature gets four things:
1. **The interaction** (Apple-style: one sentence, one sound, one gesture).
2. **How it works** (real APIs).
3. **What we verified** (POCs on the validated emulators or real data).
4. **Effort for the 36-hour build.**

---

## 0. The headline: "Other finders find your mug. Marco tells your hand which jar is cumin."

**The problem.** Blind people rarely *lose* spice jars; they can't *tell them apart*. Spice jars, pill bottles, cans, and shampoo vs conditioner all feel identical. Today's fixes:
- **PenFriend 3 voice labeller: $160–180** (LS&S $159.95, Braille Institute $170, MaxiAids $179.95).
- **NFC tags: about $1.30 each** (WayAround: 25 stickers for $31.99, 60 for $74.99).
- Either way, someone has to tag every single object.

### Feature A: Reach and hear, hands-free

**Interaction.**
- The chest camera tracks your hand. Labelled objects say their own name from their spot as you reach.
- "Marco, cumin": the cumin calls "Polo".
- **The moment your fingers touch the wrong jar: "that's cinnamon", before you pick it up.** The right one gets a soft "cumin ✓".

**What each piece is, and how it was checked:**

| Piece | Check | Result |
|---|---|---|
| Hand tracking from the chest camera | Apple Vision `VNDetectHumanHandPoseRequest` on real photos (POC 17) | Hand + all 21 joints found in 6 of 7 hand-and-object photos, including a reach to a jar on a shelf. **4.5 ms per frame** (220 fps) on a Mac, so 30 fps on iPhone is easy |
| Which jar the hand is on | Same photo, visual check | The single fingertip point landed *between* two jars. **Use all 21 joints (the jar the hand wraps) + LiDAR depth + the moment the fingers close**, not the fingertip alone |
| Which jar is which (identical jars) | POC 13, row matching vs map drift | **97–100%** correct at 2–16 cm drift when the row's ends are in view (point anchors: 37–68%) |
| Jar names it can read on its own | Apple Vision text recognition on real photos (POC 17) | Read CUMIN, PAPRIKA, CAYENNE PEPPER, NUTMEG, CORIANDER, DRIED BASIL/ROSEMARY on real shelves, "Nateglinide 60 mg, 90 tablets" and "HYDROCO/APAP 5-500" on pill bottles, ROAST BEEF / APPLE SAUCE / CORN on cans. Same-shaped jars from one brand are told apart by their printed names. Misses: tiny labels, labels facing away, partly handwriting ("CURRY" read as "CUREY") |
| The label speaks from the jar | Apple's real spatial engine, POC 18 | Rendered from a jar 30° right, 0.5 m away; heard on the right |
| "That's cinnamon" timing | Reach simulation, POC 16 (minimum-jerk human reaches, 30 fps tracking, 1 cm noise, 100–250 ms latency) | **Before the hand arrives: not feasible.** Only 1–6% of wrong reaches can be flagged ≥200 ms before contact (the time a person needs to stop a reach), and 7% of correct reaches get false warnings. **At touch, before lifting: feasible.** The name is heard 117–267 ms after the fingers stop, so design it as "touch, listen, take" |

**Say it this way:** "The moment your fingers touch the wrong jar, Marco says 'that's cinnamon', before you pick it up." Not "before your hand gets there".

### Feature B: Labels from anyone, with no tags

**Interaction.**
- Put your hand on a jar and say "Marco, this is cumin."
- Or, when you touch something unknown, Marco texts a photo to your guardian through Photon. Their voice-memo reply becomes that jar's voice.

**How it was checked:**

| Piece | Check | Result |
|---|---|---|
| "This is cumin" speech | Apple Speech API docs | On-device recognition (iOS 13+). `contextualStrings` (iOS 10+) adds your label words (turmeric, garam masala…) so they aren't misheard. Custom vocabulary since iOS 17 |
| Photo out, voice memo back | Photon SDK docs (`research/photon/`) | **Advanced iMessage Kit:** send images (several in one message), send/receive audio messages, real-time new-message events, download received attachments. **Free iMessage Kit:** runs on a teammate's Mac signed into Messages, sends images, watches replies; needs Full Disk Access. Not run end to end here (needs an account/line) |
| Voice memo → the jar's voice | POC 18 on Apple's audio stack | An iMessage-style Opus CAF memo decodes with `AVAudioFile` and plays spatialised from the jar's position |

### More to add (each with how sure we are)

1. **Read it once, remember it forever.** Most products print their name. Marco reads it the first time the camera sees it, so the guardian is only needed for homemade, refilled or unreadable items. *Verified on real photos (POC 17).*
2. **Label a whole shelf in one message.** One photo with numbered jars goes to the guardian, who replies "1 cumin, 2 paprika, 3 turmeric…". Eight labels, one text. *Photon sends multi-image messages; parsing the reply is easy.*
3. **Shelf screen reader.** Slide your fingers along the jars and each says its name, like VoiceOver for real objects. *Same hand tracking + row matching as A.*
4. **"What's this?"** Hold any item in front of your chest and ask. This covers wall cabinets the chest camera can't see (above ~1.5 m) and any item away from its shelf. *Camera + text recognition + appearance match.*
5. **Medicine: never guess.** For pills, speak only on high-confidence reads ("Nateglinide, 60 milligrams"); otherwise "I can't read this one, turn it slowly." Add schedules: "It's 8 pm. Your blood-pressure pills are the round bottle on the left." *Text recognition verified on pill bottles; the schedule logic is new.*
6. **Expiry dates** read off the label when visible: "Milk, expires tomorrow."
7. **Voices you love.** A mom's or partner's voice memo *is* the label. Labels can be in any language (text recognition auto-detects language on iOS 16+).
8. **"Cumin's empty"** adds it to the shopping list (Reminders via App Intents).
9. **Putting groceries away:** Marco reads each item as it passes the camera and remembers where it went ("beans: pantry, second shelf"). This connects back to the original "where is it?" memory.

### Known limits (be upfront with judges)

- **Swapped identical jars:** if two jars look identical and get swapped, Marco can't know. Re-label them, or make sure their printed labels are readable.
- **Labels facing away:** turn the jar. **High wall racks:** use "What's this?".
- **Photon:** the free route needs a Mac relay with Full Disk Access; the managed route needs an account. Guardian replies arrive whenever they reply, so Marco says "I asked Sam; I'll tell you when they answer."

---

## 0b. Finding: "Marco, where are my keys?", and how the phone finds them

**Tested (POC 20):** an open-vocabulary detector (YOLO-World; you type "keys" and it looks for keys) on 7 real photos of keys.

| Model | Result |
|---|---|
| Small (`s`, fast enough for every frame) | Found the keys in 2–3/7 photos, and only while they filled 200–400 px of its input, i.e. close-ups. **Useless from the chest at a distance.** |
| Extra-large (`x`, 140 MB) | Found keys in 4/7, **including two realistic table scenes**: a car key and fob on a café table (85 px boxes) and one key beside a light bulb. Confidence was low (0.1–0.3), and it missed the other three photos. |

**Design that follows from this (most finds never need a search):**

1. **Remember, don't search.** Marco sees the keys when you put them down. Your hand is at ~0.5 m, so the keys are large in the frame. Crop around the hand (as in POC 19) and the keys fill much of the crop, which is the size where detection works. Walk-by sightings refresh the memory. The answer then comes from memory in under 0.5 s.
2. **Search mode, only when they're "not where I last saw them":**
   - Marco asks you to turn slowly (under ~48°/s), and the phone sends a frame a second to the server, which runs OWLv2 with your registered photo (§0c).
   - **Verify candidates against *your* keys**, enrolled from all sides (Vision feature prints: 98–99% at close range in POC 6), and accumulate evidence over several frames (POC 2's logic).
   - **Jev is the second opinion** on promising tiles about once a second: "Box: the keys in `tile`" plus a yes/no "are keys in `tile`?". Its probabilities decide when to say "found them".
   - Once found: LiDAR depth at the box centre gives the 3D spot; the memory updates and the Polo plays from there.
3. **Range is about 1–2 m** (keys need ≈85+ px in the detector input). Search room by room, guided by which surfaces haven't been seen recently.

**For the demo:** use a keychain with a big, distinctive fob, and enrol it. **Stretch / veri.studio prize:** fine-tune the detector on photos of keys, wallets and glasses cases to lift the hit rate.

**Honest status:** finding small items by camera works close up and from memory, and is hit-or-miss beyond ~2 m. Pitch it as "Marco saw where you put them", not "Marco scans the room for them".

---

## 0c. Which model finds a REGISTERED item (runs on a server, not the phone)

**Benchmark (POC 22).** Charts: `reports/figures/poc22_find_registered_items.png` (which model) and `poc22_one_shot_photo_quality.png` (which photo).
- **Data:** ORBIT, 18 real items filmed by blind and low-vision users (keys ×4, remotes, wallets, sunglasses, phones, watches, headphones, cane, purse). Registration photos come from their clean videos; testing uses their cluttered videos, with human-drawn boxes.
- **Registration = one photo + the name** ("these are my keys"), encoded once on the server.
- **Task 1:** find my item in my own clutter. **Task 2:** find *my* item when three other people's look-alikes are in view.
- **Caveat:** frames are only 224 px, so every score is pessimistic.

| Approach (one-shot) | Task 1 | Task 2 | ms per phone frame (M3 Mac) |
|---|---|---|---|
| **OWLv2 image-guided, 1 photo** | **97%** | **58%** | 392 (276 in fp16) |
| OWLv2, 1 photo + name | 97% | 53% | 390 |
| OWLv2, name only | 86% | 36% | 390 |
| YOLOE-26x, 1 photo | 86% | 50% | 82 |
| YOLOE-26x, name only | 83% | 35% | 87 |
| YOLOE-26l, 1 photo | 80% | 49% | 40 |
| YOLOE-26l, name only | 81% | 37% | 44 |
| YOLOE-26s, 1 photo | 74% | 45% | 14 |
| Name finds candidates, DINOv2 matches the photo | 70% | 51% | 58 |
| Box everything, DINOv2 matches the photo ("option A") | 57% | 51% | 300 |

Times are for one 1440×1920 frame with the registration already encoded (`server_latency.py`). The first chart's 1.8 s for OWLv2 was a benchmark artifact: it re-encoded the photo every frame and used a slow Python NMS. The fast path picks the same box (checked).

**Decision (server-side):**
1. **OWLv2 image-guided with the one registered photo.** It is best on both tasks.
   - Speed: 1.1 TFLOP per frame (counted), so roughly 20–70 ms on a T4/L4-class cloud GPU. That is an estimate, not a measurement. At 1 fps even this Mac keeps up.
2. **The photo makes or breaks it** (`registration_study.py`). The first good photo from each user's video scored 97% / 58%. Other photos the name detector could box averaged 80% / 46%, and photos it couldn't box (blurry, cut off, empty) averaged 46% / 32%. App rules:
   - **Take it like this:** the whole item in view, on a plain surface, 30–60 cm away, sharp, hand off it.
   - **Check it:** the server runs the name detector on the photo. If it can't box the item, say "I can't see the keys clearly, try again".
   - **Fall back:** if the photo still fails, register the name only. That scores 86% in your own clutter, which beats a bad photo.
3. **Box the item with its name, not the hand.** The automatic "most prominent object" box landed on hands.
   - YOLOE learns whatever is inside the box: it scored 0% on the watch and the purse, whose boxes were loose. OWLv2 got 100% on both.
   - The way the query region is picked inside the crop was also checked (`query_modes.py`): the transformers default beats the older rules.
4. **Bigger YOLOE is better** (26x 86% vs 26l 80% vs 26s 74%) but still behind OWLv2. YOLO-World takes words only, so it can't use the photo at all.
5. **More photos only help if averaged** (6 photos averaged: 94% / 64%; "best match of any photo": 83% / 54%). Not needed for the hackathon.
6. **Look-alikes stay hard** (58% with one photo). Lean on memory ("Marco saw where you put it") and a "this one?" confirmation.
7. **Jev:** put the registered photo *in* the Box question rather than sending every box for it to choose from (Jev itself untested).
8. **Server practicalities:**
   - **1 fps.** POC 11 sweep: 0.5 / 1 / 2 / 3 fps catch 32 / 45 / 46 / 47% of put-downs at the moment of release. 57% of put-downs happen outside the chest camera's view, so more frames don't help, and about 100% are seen again within 60 s of walking around.
   - **Search:** a sweep has no gaps up to 48°/s of turning at 1 fps, but only 24°/s at 0.5 fps.
   - **Frames:** 960-px JPEG, about 135 KB, so about 490 MB/hour.
   - **Latency per frame doesn't depend on fps.** At 0.5 fps the wait for the next frame (up to 2 s) dominates.
   - **Hosting:** put the server close, either a laptop at the table or a cloud GPU (e.g. Vultr, an MLH prize in 2026).
   - **Keep cached labels on the phone,** so "that's cinnamon" at touch doesn't wait for the network.

**Appendix (only if you ever go on-device):** YOLOE-11s with the item names built in exports to Core ML and runs at 11 ms on the M3's GPU. YOLOE-26's Core ML export failed with PyTorch 2.14 (coremltools is tested only to 2.7).

---

## 1. Spatial voice labels: "Marco, this is the cumin"

**Interaction.**
- *Label:* touch a jar and say "Marco, this is the cumin." A soft tick plus "Cumin, saved" confirms it.
- *Later:* when your fingertip comes within about 3 cm of that jar, Marco whispers "cumin" from the jar's position. Move to the next jar and it says "paprika".
- No NFC tags, no braille stickers, nothing to buy. The same works for medicine bottles, shampoo vs conditioner, light switches, thermostat buttons and drawers ("this drawer is batteries").

**How it works.**
- *Fingertip:* Vision's `VNDetectHumanHandPoseRequest` finds the index fingertip in the chest camera frame, and LiDAR depth turns it into a 3D point.
- *Label anchor:* the label is stored on the jar nearest the fingertip (detected box + LiDAR) as an `ARAnchor` in the saved `ARWorldMap`.
- *Row structure:* it also stores the jar's place in its row (the neighbours' offsets).
- *Recall:* each frame, the jars in view are matched to the stored row, and the jar under the fingertip speaks.

**Verified (POC 13).** Eight identical jars 5.5 cm apart, the worst case.

| Anchor error after relocalising (ARKit drifts 3–8 cm, older versions up to 16–18 cm) | Position only | Row matching |
|---|---|---|
| 1 cm | 99% | 99.9% |
| 3 cm | 68% | **97%** |
| 5 cm | 49% | **99%** |
| 8 cm | 37% | **99.9%** |
| 16 cm | 24% | **100%** |

- **Point anchors fail for identical jars. Row matching works**, provided the camera sees the ends of the row or a distinctive neighbour such as the rack edge or a different bottle. If it can't, accuracy falls back to position-only.
- *Fallbacks:* jars usually look different, and Vision feature prints tell objects apart at 98–99% close up (POC 6). Or Marco says "step back a little so I can see the whole shelf".
- **Height limit:** the chest camera (30° tilt) sees counter (0.92 m) and shelf (1.2 m) height, but not a wall rack at 1.5 m. The glasses camera covers that, because you look at it.
- If you rearrange identical jars, re-label them. Marco can't tell identical jars apart once they've been swapped.

**Effort:** medium (6–8 h). Hand pose + LiDAR + anchors + row matching. **Wow:** very high. It's tactile, it's magic, and no other app does it.

---

## 2. Drop detection: "Sounds like something fell. Polo!"

**Interaction.**
1. You hear keys hit the floor, and so does Marco.
2. Within about a second, "Polo" plays from the floor where they landed, plus "by your left foot, half a step back."
3. If it's unsure: "Something fell. Hold still, I'll look."

**How it works, two-stage:**
1. *Sound:* `SNClassifySoundRequest` (Apple's on-device classifier, 303 classes) watches for `keys_jangling` / `coin_dropping` / `thump_thud` ≥ 0.7, vetoed while it also hears cutlery, dishes, typing or footsteps.
2. *Camera:* the tilted chest phone (30°) sees the floor from about 0.7 m. LiDAR looks for a *new* bump on the floor compared with a moment ago, and the detector names it.

**Verified (POC 14):** 32 real recordings.
- **Every clean key-drop clip scored 0.90–0.98.**
- At the 0.7 threshold: 6 of 8 key/coin drops caught, 1 false alarm in 18 everyday clips (dishes). With the veto: **0 false alarms in 18**.
- Soft drops (a phone on carpet, generic thuds) are mostly *missed* by sound, so stage 2 is what catches those.
- Caveat: these were studio-ish recordings. A phone mic on the chest in a real room will have more noise, so test it.

**Effort:** medium (4–6 h for stage 1; floor change detection +4 h). **Wow:** the top demo moment.

---

## 3. Item homes and tidy check

**Interaction.**
- "Marco, my keys live here," said with your hand on the hook.
- Later, on its own: "Your keys aren't home. Last seen on the sofa at 9:40."
- At night, or when you leave: a single soft tidy-check line.

**How it works:** a home anchor per item, plus the move-aware memory (POC 2). It triggers when the item is seen away from home, at a set time, or at the door anchor. **Verified:** reuses POC 2 (moves and "not there" detected 100% in testing). **Effort:** low (2–3 h). **Why it matters:** a fixed home for everything is *the* core coping strategy blind users already rely on. This reinforces it instead of replacing it.

---

## 4. Guided search when something is truly lost

**Interaction.** "Marco, I can't find my wallet." "I haven't seen it since 8:10 this morning. Let's check the likely places: the entry table first, then the sofa." Polo plays from each place in turn, and the camera checks as you arrive. "Not here… next, the sofa."

**How it works:**
- *Candidate places:* the item's home, the last-seen surface, and surfaces where the item *usually* ends up (from the timeline).
- *Order:* places are checked in order of probability ÷ walking time. That's the classic optimal-search rule: check the place with the best chance per second first.
- *Skipped places:* surfaces the camera has clearly seen since the item went missing (POC 2's "seen, not there" logic) are crossed off automatically.
- *Navigation:* breadcrumb routing between places (POC 12).

**Verified:** parts only (POC 2 negative evidence, POC 12 routing). The ordering itself is standard search theory. **Effort:** medium (4–6 h). **Why:** it replaces the 20-minute hands-and-knees searches blind users describe.

---

## 5. "Take me back to my seat" (or the door, or the car)

**Interaction.** Standing up at a café or a conference: "Marco, remember my seat." Later: "Marco, take me back." Breadcrumb Polos lead you back along the way you came.

**How it works:** an `ARAnchor` at the seat, plus your recorded walking path (ARKit pose). Guidance plays the beacon from waypoints along the reversed path (POC 5 beacon, POC 12 breadcrumbs).

**Verified:**
- ARKit drift while walking is 0.2–0.5% of distance (research), so after a 20–50 m round trip you're within about 4–25 cm, which is plenty for a chair.
- If the app was closed in between, relocalization is needed (the hour-one test).

**Effort:** low (2–3 h on top of guidance). **Wow:** high. It works outside the home, at hackathons too, so you can demo it in the hall.

---

## 6. Hotel / new place: "Marco, what's around me?"

**Interaction.**
1. Walk the room once.
2. "Marco, what's around me?" gives a clockwise sweep: "Door behind you. Bed, two o'clock. Desk, three o'clock. Bathroom, eight o'clock."
3. Each item pings from its spot, spread out so the pings are distinguishable.
4. Then: "Polo, bathroom."

**How it works:** RoomPlan (furniture categories, doors, windows) or the LiDAR mesh labels, then a spoken clock-face list plus pings.

**Verified (POC 9):**
- Pings alone at true positions convey layout poorly: 31–39% get the order right for items 20–30 cm apart.
- Spreading the pings 3× gives 69–87%.
- **Speech carries the layout; the pings carry where each thing is.**
- Caveat: RoomPlan expects the device to be swept around the room. Doing it from the chest vest while walking is untested; a quick scan by a sighted helper is the fallback.

**Effort:** medium (4–6 h). **Who it helps most:** blind travellers.

---

## 7. Timeline: "When did I last have my wallet?"

**Interaction.** "When did I last have my wallet?" "At 2:14, you put it on the dining table." / "What did I put on the counter this morning?"

**How it works:** the memory already logs every event (seen, moved, not there). Queries go through on-device `NLEmbedding` matching (POC 8: 9/10 on held-out phrasings) or the on-device LLM where Apple Intelligence is available. **Effort:** low (2 h). **Wow:** medium, but it's what makes the memory feel real.

---

## Build order for these (on top of the core loop)

1. **Item homes** (low effort; reinforces the memory story).
2. **Spatial voice labels** (the signature moment).
3. **Drop detection stage 1** (keys).
4. **"Take me back"**, which you can demo in the hall.
5. **Timeline** queries.
6. **Guided search.**
7. **Hotel sweep** (vision slide if time runs out).

POC sources: `pocs/poc13_voice_labels`, `pocs/poc14_drop_audio` (real clips, Apple SoundAnalysis), plus POC 2, 5, 6, 8, 9 and 12. Results are in `reports/*.json`.
