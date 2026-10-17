# Marco Polo (working name): requirements, v0.2 for review

Status: draft v0.2 for team review before implementation (2026-10-17; adds the POC 23–26 findings). Evidence comes from the POCs in this folder; see `REPORT.md`, `FEATURES.md`, `POSITIONING.md`, and `research/landscape/` for prior art.

---

## 0. Decide in review

1. **Direction:** confirm the hybrid.
   - Lead with memory, plus family voice labels at touch.
   - "Where are my keys?" with spatial guidance is act 2.
2. **Name:** keep "Marco Polo" or rename (e.g. Touchstone, Kin, Keeper).
   - "Marco Polo" promises find-by-sound, which is what existing finders already pitch.
   - It is also the name of a large video-messaging app.
3. **Main track:**
   - **Beyond the Digital** (recommended): intelligence in the physical world through wearables and audio AR.
   - **Applied Intelligence**: names accessibility and healthcare.
4. **Remote teammate:** ask the organizers whether a remote member is eligible. The 2026 rules required in-person presence at judging.
5. **Optional sponsor items:** which ones to attempt (§7).
6. **Owners:** who owns each workstream (§8).
7. **Hardware check:**
   - LiDAR iPhone (Pro) model;
   - AirPods with head tracking (Pro, 4, 3 or Max; not 2nd gen);
   - chest vest;
   - props;
   - Vultr GPU credits.

---

## 1. What we are building

**One line:** a phone on your chest that remembers where you put your things, tells your hand which identical jar it is touching in your family's own voice, and guides you back to anything by sound. Built for blind and low-vision people first; older adults are the curb-cut audience.

**Core promise vs Seeing AI and other finders:** they find what the camera sees when you ask. Marco remembers what you never asked about, speaks first when it matters, and tells identical items apart at the moment of touch. Spatial audio is how Marco talks, not the idea.

## 2. Users and problems

- **Primary:** blind and low-vision adults at home.
  - "Where did I put my keys?"
  - "Which of these identical jars is cumin?"
  - "Did I leave without my keys?"
- **Secondary (they label things and get alerts):** family and friends, through iMessage, with no new app.
- **Curb-cut:** older adults and anyone who misplaces things. Weekly losses in a 2017 survey: TV remote 45%, phone 33%, keys 28%, glasses 27%.

## 3. Scope

**In:**
- one home space (kitchen counter, table, entry, sofa);
- registered personal items;
- identical containers on a counter or shelf;
- the family label loop;
- proactive alerts;
- memory that survives an app relaunch.

**Out:**
- **Medication decisions:** only read a printed label; never identify a medicine by its look.
- outdoor navigation;
- many rooms or whole-house mapping;
- Android;
- user accounts;
- our own on-device ML models. We use Apple's on-device frameworks, plus models on our server.

---

## 4. Features

Each feature lists what it does, then the acceptance check for the demo build, then the evidence behind it.

### Must

**M1. Register an item with one photo and its name.**
- **What:** the user says "these are my keys" with the item on a plain surface, 30–60 cm away. The phone sends the photo and the name.
- **Quality check:** the server boxes the item using its name. If it can't, Marco says "I can't see the keys clearly, try again".
- **Fallback:** after a second failure, keep the name only.
- **Accept:**
  - under 10 s per item;
  - blurry, cut-off and empty photos are rejected;
  - the hand is never boxed as the item.
- **Evidence (POC 22, ORBIT footage of blind users' own items):**
  - a good single photo scores 97% in own clutter;
  - photos the name check passes average 80%, photos it rejects average 46%;
  - the name alone scores 86%.
- **Check used by the server (POC 25, POC 26):** OWLv2's own score for the item's name in the photo, at least 0.05.
  - Across all 108 registration photos it asks for a retake 24% of the time; kept photos score 75.5%, rejected ones 20%.
  - With the server prototype, 17 of 18 items were accepted on the first photo, none needed more than 3, and accepted photos scored 88%.

**M2. Passive capture from the chest.**
- **What:**
  - the phone sits in a vest tilted 25–35° and sends 1 frame per second (960 px JPEG, about 135 KB) to the server;
  - the server returns a box for each registered item it sees;
  - the phone turns each box into a 3D position using LiDAR depth, with the footprint method for glass or clear items.
- **Accept:**
  - the server round trip is under 1 s per frame on the venue network;
  - item position error is 15 cm or less.
- **Evidence:**
  - frame-rate sweep (POC 11): 1 fps catches as many put-downs as 2–3 fps (45 vs 46–47%). The limit is where the camera points.
  - about 100% of items are seen again within 60 s of walking around.
  - POC 1: position error 5–14 cm horizontally.
- **Implementation rules (POC 23; each is a unit test):**
  - **Save each frame's pose and depth.** Keep every frame's camera pose, intrinsics and depth map with its frame_id, and place the returned boxes with *that* pose.
    - Saved pose: 7–8 cm error at any server latency.
    - Current pose instead: 50 cm off at 0.3 s and 2 m off at 1 s.
  - **Rotate and rescale boxes back.** Rotate pixels to upright portrait on the phone, then map boxes back with the inverse rotation and the 960-to-1920 scale.
    - Rotating the wrong way puts items 1.6 m off; skipping the rotation, 1.2 m; skipping the rescale, 2.5 m.
  - **No EXIF orientation tag.** The phone sends none, and the server applies the EXIF rotation once anyway. PIL ignores the tag and OpenCV applies it, so the models would see differently rotated pixels.
  - **Latest frame wins:** the server skips a frame if a newer one from the same phone is waiting (POC 26).

**M3. Memory that remembers and survives.**
- **What:**
  - per item: last-seen position, surface and time, kept on the phone;
  - moved-item logic from POC 2;
  - saved with ARWorldMap and anchors, then relocalized when the app launches.
- **Accept:**
  - a move seen in view updates within 1 s;
  - after killing and relaunching the app, Marco relocalizes within 30 s of normal walking and answers correctly.
- **Evidence:**
  - POC 2: updates in 0.5 s, and no false "not there" when an item is only hidden or blurred;
  - **relocalization is untested** (hour-one test).
- **"Is my item in this frame at all?" (POC 25, POC 26):** the hardest part of passive memory. OWLv2 always returns a best box, and its raw confidence is about 0.99 even for frames without the item.
  - **Seen only when all checks pass at the best box:**
    - the photo score plus the name score;
    - a DINOv2 check of the crop against the registration crop;
    - the box looks more like this item than like the user's other registered items.
  - **How well it works:** at about 1% false positives, this catches 50–68% of real sightings (only about 25% from the raw score). Someone else's identical keys stay hard: about 24% caught at 1%.
  - **Rules:**
    - move an item only after two sightings at the same spot (within 15 cm);
    - prefer the hand's put-down moment;
    - prefer missing a sighting to a false move.
  - **Calibration:** fit the thresholds on your own room and props in hour one, with POC 26's routine.

**M4. "Where's my X?"**
- **What:**
  1. A spoken answer relative to your body, from memory: *"Keys. Behind you, five o'clock, two steps, waist height. Seen 10 minutes ago."*
  2. Then a beacon from the item's position (2.5 Hz, "facing it" and "behind you" variants).
  3. A "within reach" chime, then *"at your right hand"*.
- **Accept:**
  - the first words come within 0.5 s;
  - blindfold test: at least 8 of 10 trials reach the item within 15 s.
- **Evidence:** POC 5 simulation: 99% reach within 15 s, 6.8 s median.

**M5. Head tracking.**
- **What:** ARKit torso heading combined with AirPods motion (CMHeadphoneMotionManager, 25 Hz; τ = 5 s, 15° gate). Phone-only fallback: tell the user to turn their body.
- **Accept:**
  - motion-to-sound latency is 300 ms or less;
  - front/back reversals are rare in the blindfold test.
- **Evidence (POC 4, listener model):**
  - fusion: 1.9° median error, vs 7.5° for AirPods alone and 3.3° median (p90 45°) for phone only;
  - head movement cuts front/back confusion from 33% to about 5%.

**M6. Touch to name, including identical items.**
- **What:** Apple Vision hand pose runs on the phone. When a fingertip reaches an item's anchor (or a jar's slot in a row), its label plays.
  - Identical jars are told apart by position, matched against the whole row.
  - A quick touch plays the short label; touch and hold plays the full memo.
  - Nothing repeats while the hand stays on the same item.
- **Accept:** the label starts 300 ms or less after touch.
- **Evidence:**
  - POC 16: 117–167 ms in simulation;
  - POC 13: row matching stays 97–100% correct even with 2–16 cm anchor error, while position alone falls to 24% at 16 cm.
- **How touch is detected (POC 24, LiDAR emulator with a rendered hand):**
  - **The test:** the fingertip lifted to 3D with LiDAR depth, within 2 cm of the jar's 3D shape, with the knuckles nearly still, for 3 frames. It ends when the fingertip is more than 5 cm away.
  - **Only when Vision can see the fingertip.** A hidden fingertip's depth is the jar in front of it.
  - **Results:**
    - 100% correct jar, including reaching over the front row to a back jar, 133–167 ms after contact;
    - 0% false touches hovering 6 cm above, or hidden 4 cm behind a jar;
    - 6.7% hovering 3.5 cm in front, which a 0.3 s touch-and-hold removes.
  - **Don't use 2D box overlap:** it fires on the wrong jar or on hovers almost every time.

**M7. Family labels through Photon.**
- **What:** the user touches an unlabeled item.
  1. Marco: *"New jar. Ask Mom?"* The user: "yes".
  2. Photon sends Mom the photo with that item boxed.
  3. Her voice memo reply (or text, spoken by Marco) becomes the label. The audio is cached on the phone, and from then on that jar answers in her voice.
- **Accept:**
  - the photo goes out within 5 s of "yes";
  - the label is playable within 10 s of her reply arriving.
- **Evidence:**
  - POC 19: touch crop and photo building, run on a real photo;
  - POC 18: an iMessage-style voice memo turned into a spatial label;
  - the Photon round trip is untested (needs access).

**M8. "You're leaving without your keys."**
- **What:** the user enters the door zone while the keys' last sighting is still on a surface. Marco says where they are and offers guidance.
- **Accept:** it fires every time in the demo, and never fires when the keys are carried.

### Should

- **S1. "Your mug was moved"** when an item is seen in a new place (POC 2 logic).
- **S2. Drop detection:** Apple SoundAnalysis classes `keys_jangling`, `coin_dropping` and `thump_thud` at 0.7 or above, ignored while dishes or cutlery sounds are present.
  - Marco says *"Sounds like something fell. Polo,"* from the floor.
  - POC 14: clean key drops 5/5, and 0/18 false triggers with the stricter rule.
- **S3. Printed labels read automatically** with Apple's text recognition: *"Label says: ground cumin,"* until a family label exists (POC 17).
- **S4. Timeline:** "When did I last have my wallet?" Every sighting is stored as time-series data in Tiger Data.
- **S5. Family web page:** labels, the timeline and alerts, designed in Paper.
- **S6. Fetch.ai ASI:One agent:** family can ask and act, for example "help Dad find his glasses" (starts guidance on his phone) or "label the new jar as cumin".
- **S7. Sentry:** tracing across phone, server and Photon, plus server profiling. The latency budget is the product.
- **S8. Basic privacy:**
  - frames are discarded after detection;
  - no faces or video are stored;
  - "Marco, pause" stops capture.

### Could

- **C1. Floor-hazard warnings.** POC 15: shoe, bag and box detected 5/5 at about 3 m, and 0/10 false alerts on a bare floor.
- **C2. ESP32 strap button and vibration motor** (Espressif): ask, repeat, and a "facing it" buzz.
- **C3. Even Realities G2:** silent glanceable cues for older sighted users, if the event lends glasses.
- **C4. StepFun Step 5 Preview** describes unknown items, with the user choosing "read it" or "ask Mom".
- **C5. veri.studio:** fine-tune for look-alikes (today 58%).
- **C6. Batch labeling:** one shelf photo and the reply "1 cumin, 2 paprika" label the whole row.

---

## 5. System design

```
iPhone Pro on a chest vest (all real-time work on-device)
  ARKit + LiDAR session, camera pose for every frame
  Capture: 1 fps, 960 px JPEG ──► Server (Vultr GPU)
  Locator: 2D box + depth ──► 3D position (raycast; footprint for glass)
  Memory: items, last seen, moves; ARWorldMap persistence
  Touch: Vision hand pose ──► nearest anchor or row slot ──► label clip
  Audio: AVAudioEnvironmentNode (HRTF), listener from ARKit + AirPods fusion
  Voice: speech commands; Marco's voice (ElevenLabs, cached)
  Alerts: leaving without keys, moved, dropped

Server (FastAPI on a Vultr GPU; Sentry tracing)
  OWLv2 image-guided find; each registration embedding computed once
  Name check at registration
  Photon agent: boxed photo out, voice memo in, heads-up texts
  Fetch.ai agent (ASI:One) ──► actions on the phone
  Tiger Data: sightings and events (time series)
  Family web page (designed in Paper), on a GoDaddy domain
```

**Key settings (from the POCs; don't rediscover them):**
- **Listener yaw sign:** listener yaw = −(ARKit right-hand yaw). Positive listener yaw means the head turned right. Unit-test this.
- **Distance attenuation:** set `referenceDistance` to about 0.3 m. Apple's default is flat inside 1 m. Distance is conveyed by tempo, the "within reach" chime and speech.
- **Head Pose entitlement:** Apple's automatic head tracking needs a paid developer account and has an undocumented reference frame. Use our fusion.
- **OWLv2 on the server:**
  - `google/owlv2-base-patch16-ensemble`, fp16 on the GPU;
  - take the top box by argmax and skip transformers' slow Python NMS post-processing;
  - this Mac takes 392 ms per frame (fp32), 276 ms (fp16);
  - 1.1 TFLOP per frame, so roughly 20–70 ms on a cloud GPU (estimate, not measured).
- **Frames:** about 135 KB each, so about 490 MB per hour at 1 fps. Fine on venue Wi-Fi.
- **Server security (prototype in `pocs/poc26_server/app.py`):**
  - **Fail-closed auth:** every route rejects requests until a real verifier is wired.
  - **Binds 127.0.0.1** by default.
  - **For the hackathon, keep it private:** phone and server on one Tailscale network, with `tailscale serve` in front, rather than a public port.
  - **If it must be public:** verify ID tokens from a real identity provider (e.g. Sign in with Apple). Never a shared key you made up.
  - **Sponsor connections:** prefer SDKs that connect outward, so no inbound port is needed. Any inbound webhook must verify the provider's signature.
- **Server latency (prototype, this Mac):** 376 ms per phone-size frame with 1 item registered, 458 ms with 18.

**API contract (draft; agree in hour 0):**
- `POST /items`: photo + name. Returns `{item_id, box, quality: ok|retake, reason}`.
- `POST /frames`: JPEG + frame_id + timestamp. Returns `{frame_id, detections: [{item_id, box_px, score}]}`. The server works only in 2D; the phone owns 3D.
- `POST /sightings`: from the phone: item_id, world position, surface, time, confidence. Writes to Tiger Data.
- `POST /labels/request`: item_id + boxed crop. Photon sends it to the family member.
- `POST /labels/reply` (Photon webhook): audio or text. Stored and pushed to the phone.
- `WS /events`: label_ready, agent_action (e.g. guide_to item_id).
- `GET /items`, `GET /timeline?item_id=`: for the family page and the agent.

**Data model:**
- **Item:** id, name, owner, registration photo, label (audio URL, transcript, author, time), last seen (position, surface, time, confidence).
- **Sighting:** item_id, time, x/y/z, surface, confidence, frame_id.
- **Event:** put_down, moved, dropped, left_behind or label_added, with item_id, time and details.

---

## 6. Demo (90 s) and props

1. **Put-down:** the judge, wearing the vest, sets down keys and a bottle without a word. Marco, softly: *"Keys, entry table."*
2. **Which jar?:** three identical, unmarked jars.
   - The judge touches one: *"New jar. Ask Mom?"*
   - A teammate's phone gets the boxed photo on iMessage and replies by voice.
   - The judge touches it again and hears that voice: *"That's the cumin, love."*
3. **Moved:** a teammate moves the mug. *"Your mug was moved, from the desk to the shelf."*
4. **Out of view:** *"Where's my bottle?"* *"Behind you, five o'clock, two steps."* The beacon leads the judge to it, ending with *"got it."*
5. **Leaving:** at the door: *"You're leaving without your keys. They're on the entry table."*
6. **Relaunch:** kill the app and reopen it. *"Where's my bottle?"* still works.
7. **End:** the family page, showing the timeline and the label Mom just recorded.

**Props:**
- keys on a bright keychain;
- TV remote;
- sunglasses or a glasses case;
- water bottle or mug;
- three identical jars;
- headphones.

**Avoid:** clear glass for LiDAR, tiny items, medication, plain black look-alikes.

---

## 7. Sponsor tracks (live list, 2026-10-17)

**Build (each does a real job):**

| Track | Job in the product | Effort |
|---|---|---|
| Photon (messaging/calling agent) | Family label loop, heads-up texts, optional call to family | 4–6 h |
| Vultr (MLH) | GPU server for OWLv2 | 1–2 h |
| ElevenLabs (MLH) | Marco's voice | 1–2 h |
| Sentry | Tracing across phone, server and Photon, plus profiling (two or more products required) | 1–2 h |
| Tiger Data (MLH) | Sightings and events time series, timeline queries | 1–2 h |
| Fetch.ai ASI:One agent | Family asks and the agent acts on the phone | 3–5 h |
| Paper (Best Designed Hack, up to $1,500) | Family page and onboarding, designed in Paper | 4–6 h |
| GoDaddy (MLH) | Domain | 15 min |

**Optional:** Espressif (C2), Even Realities (C3), StepFun (C4), veri.studio (C5).

**Skip:**
- **Wrong domain:** QNX (requires QNX OS), Workday, Visa, Intuit QuickBooks. Jev is now only in Intuit's accounting challenge, so it is dropped.
- **Builder tools, not product features:** Cognition, Base44.
- **Weak fit:** Browser Use, Creao, Snowflake, Solana.
- **Gemini:** not needed for any feature.

## 8. Team plan (4 people, 1 remote)

**1. iOS sensing and memory (on-site):** M2, M3, M6 and M8.
- ARKit and LiDAR session, frame uploads, turning boxes into 3D;
- memory, persistence and relocalization;
- hand pose and touch detection;
- the door-zone alert.

**2. iOS audio and voice (on-site):** M4 and M5, plus S2.
- spatial audio engine, head-tracking fusion and the phone-only fallback;
- beacon and spoken directions;
- label playback, voice commands, ElevenLabs;
- drop detection.

**3. Server and integrations (remote):** M1, the server side of M2 and M7, plus S4, S6 and S7.
- the API on Vultr: registration with the name check, frame detection;
- Photon, the Fetch.ai agent, Tiger Data, Sentry, the domain.
- **Ship a stub server in hour 2** so iOS isn't blocked.

**4. Design, demo and story (on-site):** S5.
- Paper design and the family page;
- vest mount and props;
- recording real vest footage for person 3;
- the demo script, rehearsals and backup video;
- the blindfold test;
- the Devpost page, with a "Prior work" section and one sentence per sponsor.

**Working rules:**
- agree the API contract and data model in hour 0;
- one repo with `ios/`, `server/`, `web/` and `docs/`;
- an always-open voice channel and a shared task board;
- a 10-minute sync every 4–6 h;
- on-site uploads real frames for the remote person to test against.

**Milestones:**
1. **About hour 12, first end-to-end path:** M1 + M2 + M3 + M4 with one item (register keys, put them down, "where are my keys?", the beacon leads there).
2. **About hour 24:**
   - M6 and M7 (the jar labeled by Mom over Photon, playing at touch);
   - M3 relaunch;
   - M8;
   - S4, S6 and S7.
3. **Last 8–12 h:**
   - polish and five demo run-throughs;
   - backup video;
   - Devpost write-up;
   - fallbacks: no network still answers from memory; phone-only head tracking.

## 9. Hour-one tests (hardware only; in risk order)

1. **Relocalization:** map the room, place 3 items, kill and relaunch, walk in. Measure the time to relocalize and the anchor error. Target: 30 s or less, 10 cm or less.
2. **AirPods motion:** CMHeadphoneMotionManager rate, jitter and drift over 10 minutes. Then the whole-body-turn test for the fusion.
3. **Motion-to-sound latency:** 300 ms or less.
4. **Vest tilt (25–35°):** the table, the hand and the floor near the feet must all be in frame.
5. **Server round trip on venue Wi-Fi** at 1 fps, and real props boxed at 1–3 m.
6. **Hand pose at touch distance** from the chest camera. LiDAR reads nothing closer than about 20 cm.
7. **Photon access:** send an image and receive a voice memo.
8. **Vision fingertip confidence when the finger is hidden** behind a jar. POC 24's no-false-touch result assumes it drops below 0.5.
9. **Presence thresholds on your real props and room:**
   - register them;
   - record 2 minutes with the items present and 2 minutes without;
   - fit the thresholds with POC 26's routine.

## 10. Risks and fallbacks

- **Relocalization is slow or wrong.** Fallback: a guided "walk once around the room" step ("Marco is getting its bearings...").
- **Identical jars get moved while unseen.** Marco says *"These jars moved while I wasn't looking. Check with Mom?"* and re-reads printed labels when possible.
- **Network drops.** Memory answers and cached labels still work. New sightings pause.
- **Photon beta or API problems.** Fall back to labeling by voice on the phone ("this is the cumin").
- **Look-alikes (58%).** Rely on memory and a "this one?" confirmation. Never guess silently.
- **Battery and heat.** Measure an hour of use. Battery pack in the vest; send frames only when the view changes.
- **Remote teammate eligibility.** Confirm with the organizers (§0).
- **False sightings move items in memory.** Use the combined presence check, two matching sightings before a move, and put-down events. Fit the thresholds in hour one.
- **Box-to-3D bugs (stale pose, rotation, scale, EXIF).** Each one is a unit test from POC 23 before any 3D work.
- **Exposing the server.** Keep it on a private network. Never open a public port without a real verifier (§5).

## 11. Judge Q&A (short)

- **"Isn't this Seeing AI?"** Seeing AI (2020) and other finder apps find what the camera sees when you ask. Marco remembers without being asked, survives a relaunch, speaks first, and tells identical jars apart in your family's voice.
- **"Does it work?"**
  - ORBIT benchmark of blind users' own items: 97%.
  - Head tracking cuts front/back confusion from 33% to about 5%.
  - Blindfold-test numbers from the event. Be honest: not yet tested with blind users.
- **"What if it's wrong?"** It says "I'm not sure. Ask Mom?" and never identifies medicine from its look.
- **"Privacy?"** Frames are thrown away and only item positions are kept. No faces or video. Pause by voice.

## 12. References

- `REPORT.md`: feasibility report and hour-one tests.
- `FEATURES.md`: feature specs, and the model decision in §0c.
- `POSITIONING.md`: prior art, demo and props.
- `PRIZES.md`: still based on the 2026 list; superseded by §7.
- POCs: `pocs/poc1`–`poc22`.
- Charts: `reports/figures/poc22_find_registered_items.png`, `poc22_one_shot_photo_quality.png`.
- Prior-art sweep: `research/landscape/products.md`, `research.md`, `hackathons.md`.
