# Marco Polo: positioning, demo script, build priorities

## One line

**Other finders find what you ask for. Marco Polo remembers what you didn't.**

**How we say finding works:** "Marco saw where you put them", not "Marco scans the room". Search mode is only the fallback (see `FEATURES.md` §0b).

| | Typical finder app (ask, then search) | Marco Polo |
|---|---|---|
| When it looks | Only when you ask; you point the phone and an AI model searches the frame | All the time, passively (tilted chest phone; the cap is a stretch goal) |
| What it remembers | At most what it found during the current session | Every sighting of your enrolled items, saved with ARWorldMap and anchors, surviving app relaunch |
| Who speaks first | You | **Marco**: "your mug was moved", "something fell", "you're leaving without your keys" |
| Item identity | Generic labels ("mug") | *Your* items (one registration photo; OWLv2 on the server, 97% in own clutter): only your bottle answers |
| Identical items | Can't tell them apart | Tells your hand which identical jar it's touching, by remembering which one was put where; labels come from family over iMessage |
| Memory | Little or none | Memory is the product: timeline queries ("when did I last have my wallet?") |

Remembering across sessions and rooms is the hard part. Don't claim it; build it and show it.

## Prior art: cite it, it protects you (sweep 2026-10-16, `research/landscape/`)

"Objects that call out from where they are" is an eight-year-old idea:
- CARA (Caltech, eLife 2018, HoloLens) had objects speak their names from their 3D positions to blind users.
- Microsoft Seeing AI's "World" channel (2020) does it on LiDAR iPhones, with beacons, AirPods head tracking (2023) and "Find My Things" for taught items (2024).
- In 2026: "Making Objects Speak" (AirPods Pro head-tracked object sound), Touvigation (a chest-harness LiDAR iPhone with hand guidance; 48/48 with 12 blind users), and TouchScribe (CHI 2026: describes what you grab by reading its label).

Both halves of our idea are crowded at hackathons:
- **Live finders with LiDAR and sound:** Solaura, StepSight (OWLv2 + depth), Reach, Proprio, Cyclops, InsightAI, EchoAI.
- **"AI memory finds lost items", mostly for dementia, answering in words:** Mira (TreeHacks 2026 winner), Project Memoria (winner), SIGHTLINE, AURIC, Vigil, Senova, GEM.

Not found anywhere in products, papers or ~1,500 harvested hackathon projects:
1. Passive put-down memory that lasts across days and guides a blind user back with head-tracked spatial audio.
2. Telling identical, unlabeled items apart at the moment of touch, by tracking which one was put where.
3. Family photo labels pinned to positions in a saved 3D room map.
4. Proactive "you dropped it, it's here" or "leaving without your keys" without tags.

**Say:** "Seeing AI and other finder apps find what's in front of the camera when you ask. We built on that. Marco remembers what you never asked about, and tells your hand which identical jar it's touching." Put a "Prior work" paragraph in the Devpost naming CARA, Seeing AI, Touvigation and Mira. Judges who know the field will see the lineage; judges who don't will see the rigor.

**Don't:**
- open with "find objects with spatial audio" (that's the crowded part);
- say "first";
- pitch "register your items and find them" (Seeing AI shipped it in 2024; it's plumbing for us, not the product).

## Demo and test items

- **Demo:**
  - keys on a bright, distinctive keychain (distinctive bunches 80–100% among look-alikes; plain ones 20–40%);
  - TV remote (the most-lost item: 45% of people lose it weekly);
  - sunglasses or a glasses case, and headphones (90–100% in both tests);
  - a water bottle or mug (the "other apps find your mug" contrast);
  - three identical spice jars (cumin, cinnamon, paprika) for the touch beat;
  - a wallet only for "where is it", not "mine vs yours" (black wallets 0–17% among look-alikes).
- **Avoid on stage:** the phone itself, clear glass (LiDAR can't measure it), tiny things (rings, pills), medication (a wrong answer is dangerous), two plain black look-alikes.
- **Test set:** the 9 ORBIT categories already benchmarked plus the demo items, in your own space:
  - at 1, 2 and 3 m;
  - plain vs cluttered surfaces;
  - dim light;
  - half-covered;
  - one look-alike pair;
  - moved by a teammate;
  - after an app relaunch.

## 90-second demo (every beat is something search-on-ask finders can't do)

1. **Put-down confirmation (passive memory write).** The judge walks in wearing the lanyard and sets down keys and a water bottle without saying anything. Marco, softly: *"Keys, entry table."*
2. **Masked; a teammate moves the mug.** *"Your mug was moved, from the desk to the shelf."* Proven logic: POC 2, updates in 0.5 s.
3. **Item out of view.** The bottle is behind the judge, and the camera can't see it now. *"Marco, where's my bottle?"* → *"Bottle. Behind you, five o'clock, two steps, waist height."* Then the beacon: a "behind you" sound, turn, the "facing it" double-ding plus a chest haptic, the "within reach" chime, *"at your right hand"*, *"got it."*
4. **Which jar?** Three identical spice jars, labeled earlier by a "family member" from a photo over iMessage (show the thread for one second). The judge reaches for one: *"Cumin."* No tags, no labels on the jars.
5. **Drop** (scripted fallback: "Marco, I dropped something"). A teammate drops keys on the floor. *"Sounds like something fell. Polo,"* played from the floor.
6. **Leaving.** The judge walks to the door. From behind: *"You're leaving without your keys. They're on the floor by the table."*
7. **Relaunch.** Kill and relaunch the app in front of the judges. *"Where's my bottle?"* still works: the memory survives because the map relocalizes. This is the beat that ends the "isn't this just another finder?" question.
8. End on the memory timeline screen.

**Q&A line:** "Search-on-ask finders are great when the item is in front of the camera; their memory is short and only covers things you searched for. Marco Polo builds memory passively, keeps it across launches, and tells you when something changes."

## Build priorities (36 h), reordered by the new positioning

**Must:**
1. Passive capture on a 25–35° tilted chest mount: 1 frame/s to the server (OWLv2 with each item's registered photo), footprint positioning.
2. **Persistence:** save the ARWorldMap with item anchors, then relocalize on launch (newly critical; untested in the POCs).
3. Move-aware memory (POC 2 logic).
4. "Where's my X" with spoken body-relative answer, beacon, reach cue (POC 5 design).
5. Head tracking via ARKit + AirPods fusion (POC 4).

**Demo moments:** moved alert, leaving-without-keys, put-down confirmation, relaunch.

**Stretch:** drop detection (SoundAnalysis `thump_thud`/`keys_jangling`), spatial voice labels, label reading, nod to confirm.

**Cut or postpone:** the Gemini dependency in the core loop (keep it for open-vocabulary detection only), "What's on the table", Fetch.ai.

## New hour-one test (because of persistence)

Map the room and place 3 items. Kill the app, relaunch, and walk in. Measure:
- time to relocalize with the chest camera only, with no deliberate scanning (a blind user can't aim);
- anchor error after relocalization. Research expectation: about 3–8 cm for saved anchors, 16–18 cm on older ARKit.

If relocalization is slow, add a guided "walk once around the room" step ("Marco is getting its bearings…").
