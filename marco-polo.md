# Marco Polo: LA Hacks project notes

> "Marco, where are my keys?" … and your keys answer **"Polo!"** from where they actually are.

- **Last updated:** 2026-10-14
- **Event:** LA Hacks 2027, UCLA Pauley Pavilion, 36 hours, mid-April 2027
- **Status:** chosen idea; core loop scoped, hardware list ready, open decisions in §20

---

## 1. The idea

Marco Polo is an AI memory of where your things are, played back as spatial audio.

1. A camera (an iPhone with LiDAR, or a privacy cap) notices where you put things down.
2. AI recognizes *your* items (not just "keys" in general) and saves "item · place · time".
3. When you ask, a "Polo" sound plays from the object's real position.
4. AirPods head tracking keeps the sound fixed in the room as you turn your head, so you can walk straight to it.

It's built for blind and low-vision users first. It's also useful for anyone who loses things, the same way curb cuts help everyone.

**Pitch lines**
- "In the pool game you find people with your eyes closed. We made that work for everything you own." (In Marco Polo the seeker keeps their eyes closed and finds people by sound, so the name *is* the product.)
- "AirPods were built for movies. LiDAR was built for photos. We turned them into a sixth sense."
- "We remember *where* things are, never *what the camera saw*."
- "Ask. Listen. Reach."

---

## 2. Why this can win (patterns from past winners)

| Pattern | Evidence |
|---|---|
| A hidden sensor in something people already own, used for something new | **Aircade** (Hack the North): AirPods head-tracking API used as a Wii remote. **SPECTRA** (LA Hacks '26 track and Zetic winner): iPhone LiDAR turned into dense depth maps. **Concerto** (HTN '26): audience phones as optical beacons. |
| AI that acts in the physical world, not just chat | **Reflex** (HTN '26): Claude drives exoskeleton-glove servos over MCP, plus a SmolVLA model learns from demonstrations. **Aircade**: the AI picks one of 5 legal shots and the game engine does the physics. |
| A one-line hook or inversion | Reflex: "We write skills for AI; what if AI wrote skills for us?" Drip: "every prompt generates water". |
| A 5-second demo the judge takes part in, plus a visible "AI brain" panel | Aircade had an "AI shot decisions" panel. Reflex showed live telemetry. |
| Accessibility hardware does well at LA Hacks | **Bridge** (a low-cost braille display) won Best Hardware '26. **Dots** (tactile maps) won 2 tracks. **Accent** won a track. |
| Winning several prizes with one project | **RIIS** (a Pi 5 rover, 4 Fetch.ai agents and a Gaussian-splat VR scene) took 2nd overall plus Fetch.ai. Fetch.ai-related prizes went to 11 teams in '26. Devin projects took 1st and 3rd overall. |

---

## 3. How it works

```
camera sees your keys ─► AI recognizes them ─► LiDAR gives the exact 3D spot ─► memory: "keys · coffee table · 2:14 pm"
"Marco, where are my keys?" ─► AI finds them in memory ─► "Polo" sound placed at that 3D spot
AirPods head tracking ─► the sound stays put as you turn ─► you walk to it ─► the camera guides your hand
```

1. **Remember.** As you move around, the camera spots your things.
   - Recognition runs on-device (Vision feature prints plus a small detector), or through Gemini.
   - LiDAR depth at the object's pixel, plus the camera's position from ARKit, gives a 3D point in the room.
   - It saves only item, position, surface ("table"/"seat"), time and confidence. **No images.**
2. **Ask.** "Marco, where are my keys?" goes through on-device speech-to-text, then an LLM matches the request to the memory. It handles fuzzy requests like "the thing I drink from".
3. **Hear.** A 3D audio source plays at the object's position. Apple's audio engine applies AirPods head tracking automatically, so the sound stays fixed in the room.
4. **Reach.** In the last arm's length, the camera sees your hand and the object together and talks you in: "left… down… got it", with optional Apple Watch taps.

---

## 4. Spatial audio: what's realistic

**A single "I'm here" won't let someone pinpoint the object.** One call tells you roughly which direction. A repeating call while you turn your head gets you walking straight to it. The final grab still needs help.

| | With generic 3D audio over headphones | What to do about it |
|---|---|---|
| Left vs. right | Good, but roughly 10–20° off. At 2 m that's about half a meter. | Fine for walking toward it. Use the camera for the last 30 cm. |
| Front vs. back | Often confused when the sound is static | **Head tracking fixes most of it** (Wightman & Kistler 1999; Begault, Wenzel & Anderson 2001, NASA Ames). That's why the AirPods matter. |
| Up vs. down | Poor | Say the height out loud: "waist height, on the table" |
| Distance | Poor | Tempo and loudness: the calls speed up as you get closer, like a parking sensor |

**Design rules**
- Repeat the call about once a second, so the user can turn until it's dead ahead. Turning to face the sound is the most accurate strategy.
- Use broadband sounds: jingles, clicks, a short noise burst under the voice. Pure beeps are hard to locate.
- Add a "lock-on" cue: the sound changes when you're facing it within about 10°.
- Give clock-face directions ("two o'clock, four steps"). This is standard in orientation and mobility training for blind people.
- Default to **Transparency mode** in real use, because blind users rely on hearing traffic and people. Use noise cancellation only for the loud hall.
- Keep the sound design tasteful: one signature chime and a calm voice. No silly object voices.

**Evidence it works at walking scale:** UCSB's Personal Guidance System (Loomis, Golledge, Klatzky) found spatial audio beat spoken directions for blind navigation. Microsoft Soundscape (2018–2023) guided blind users with 3D audio beacons.

---

## 5. Architecture options

### A. iPhone on a chest lanyard (the demo default)
- ARKit world tracking plus LiDAR depth give 3D positions. Detection runs 1–2 times a second, and only when the camera has moved.
- Apple's automatic head tracking expects the phone to be in front of you, and a chest-mounted phone matches that.
- **Downsides:**
  - Continuous ARKit plus camera drains the battery within hours. Add a MagSafe battery pack.
  - iOS stops the camera when the app goes to the background, so the memory has gaps whenever you use your phone.
  - Fix: use a **spare or old iPhone Pro** as a dedicated lanyard device.
- **Listener position:** raise it about 30 cm above the phone, to head height.

### B. Privacy cap (the product direction; optional for the hackathon)
- **Hardware:** a Seeed XIAO ESP32S3 Sense (camera, mic, Wi-Fi), a BNO085 motion sensor and a small LiPo battery, under the cap brim.
- **It captures only when you look down,** meaning the head is tilted down and still. It sees hands and surfaces and rarely faces. A few frames a minute makes all-day battery realistic; continuous video would last about 2 hours.
- **Frames go to a local hub** (phone or Mac). A local vision model turns them into events like "keys → coffee table, 2:14 pm", then the frames are deleted. This is the same model as HomeKit Secure Video, where analysis runs on the home hub.
- **No 3D tracking on the cap.** A one-time RoomPlan scan gives furniture positions, so the cap only needs to know *what* it saw and *which furniture* it's on.
- **Guidance:** hold the phone like Find My's Precision Finding for about 30 seconds. ARKit locates the phone in the saved scan, the AirPods chime plays from the furniture, and a camera finds the item for the last meter.
- Fits the Espressif prize ("creative, meaningful").

### C. Room cameras (old iPhones on shelves over the spots where things get put down)
- Plugged in and always on. Looking down from above gives great last-inch guidance, with your hand and the object in the same frame.
- **Caveat:** Apple's automatic head tracking assumes the device is in front of you. With a static shelf phone, use the user's handheld phone for guidance instead.
- **Aligning devices:** an ARKit collaborative session or a shared ARWorldMap. For the demo, a printed Marco Polo logo card works as the shared reference.

### D. Phone-free v2
- A depth camera that runs AI on the camera itself (e.g. OAK-D Lite) plus tracking software on the cap. The cap then knows the head's position directly, so audio renders from that and AirPods are just headphones. Heavier and riskier to build in 36 hours.

### E. Ruled out
- **Wi-Fi sensing (esp-csi):** it senses large moving bodies, not where a stationary set of keys sits. Its only possible role is an optional motion wake-up trigger.
- **UWB/BLE tags:** precise and camera-free, but that's AirTags' job, and third-party apps can't read AirTags. Don't compete there; items that leave the house belong to Find My.

---

## 6. Apple APIs (checked in Apple's docs, Oct 2026)

| API | Use | Since |
|---|---|---|
| `CMHeadphoneMotionManager` | Raw AirPods head motion (fallback, nod/shake detection) | iOS 14 / macOS 14 |
| `AVAudioEnvironmentNode.isListenerHeadTrackingEnabled` | Automatic head tracking for 3D audio | iOS 18 |
| `PHASEListener.automaticHeadTrackingFlags` | Same, in the PHASE engine | iOS 18 |
| `AVAudio3DMixing` `occlusion` / `obstruction` | Muffle a sound "behind" a real object | — |
| ARKit `sceneDepth`, `sceneReconstruction = .meshWithClassification` | LiDAR depth; surface labels: table, seat, floor, wall, door, window | — |
| ARKit `ARWorldMap` / collaborative sessions | Save and relocalize the room map; share it across devices | — |
| RoomPlan `CapturedRoom.Object.Category` | Furniture: bathtub, bed, chair, dishwasher, fireplace, oven, refrigerator, sink, sofa, stairs, storage, stove, table, television, toilet, washerDryer | iOS 16 |
| Vision `VNGenerateImageFeaturePrintRequest` | Match your enrolled items ("only your bottle answers") | — |
| Vision `VNDetectHumanHandPoseRequest` | Last-inch hand guidance | iOS 14 |
| Vision `VNDetectHumanBodyPose3DRequest` | 3D body position relative to the camera (room-camera variant) | iOS 17 |
| Vision face/text detection | Blur faces and text before any frame leaves the device | — |
| Foundation Models (on-device LLM) | Parse requests, tool calls into the memory. **Image attachments since iOS 27.** Needs an Apple Intelligence iPhone (15 Pro or newer) | iOS 26 |
| `SFSpeechRecognizer` (on-device) | Speech to text | — |
| App Intents / App Shortcuts | "Hey Siri, Marco…" and the Action button | — |
| WatchConnectivity | Send haptic taps to the Watch | — |

---

## 7. Memory logic (the "smart" part)

- **Enrollment ("Introduce your things"):** hold an item up for about 3 seconds, like setting up Face ID. The app computes feature prints and from then on recognizes *your* keys.
- **Index at the moment of release:** watch for "hand lets go, object stays". The object is close up then, so it's more accurate and cheaper than scanning everything.
- **What's stored:** item, 3D position, surface label, room, time, confidence. Never images.
- **Moved-item logic:** if the camera looks at the last known spot and the item isn't there, mark it **unknown**. Never send someone to an empty table.
- **"It noticed the move":** overwrite the position whenever the item is seen again.
- **Containment (stretch):** it saw the keys go into the backpack, so it answers "in your backpack, on the chair" and the chime plays from the bag.
- **Item homes:** learn each item's usual spot and nudge you to return it ("your keys usually live on the hook"). Keeping a consistent place for everything is a core strategy taught to blind users.
- **Time memory:** "Where were my glasses last night?" → "Sofa, 10:41 pm."
- **Fuzzy requests:** "the thing I drink from" → your blue bottle (LLM plus a tool call into the memory).
- **Never silent on failure:** "Haven't seen your keys since 8:10 am, at the entry table. Want me to look?" → search mode.

---

## 8. Features, by priority

### Must (the core loop)
- [ ] Enroll 4–5 items
- [ ] Detect, compute 3D positions, write to memory (including the moved-item logic)
- [ ] Voice query, then a lookup in memory
- [ ] Head-tracked spatial chime with tempo for distance and a spoken height/clock-face hint
- [ ] Last-arm's-length hand guidance and a "Got it" confirmation
- [ ] Map screen showing the objects, the user's direction and the AI's decisions (the "AI brain" panel)

### Demo moments (pick 3)
- [ ] **Only your bottle answers.** Three different bottles on the table; only the judge's says "Polo".
- [ ] **It noticed the move.** A teammate moves the item in view of the camera, and the "Polo" moves with it. This proves nothing is hardcoded.
- [ ] **"You're leaving without your keys,"** heard from behind as the judge walks away.
- [ ] **"What's on the table?"** Each item pings in turn from its spot, so you hear the layout in 3 seconds.

### Product polish
- Siri or Action button trigger. Nod or shake to confirm (from AirPods motion data).
- Apple Watch "warmer/colder" taps, plus a tap when the object is grabbed.
- Transparency mode by default.
- A Find My-style room map for family and caregivers, and a memory the whole household shares.
- Multi-room guidance: "It's in the bedroom. Follow me." The chime plays from each doorway in turn, like breadcrumbs.
- Label reading: "Which bottle is my allergy medicine?" and the right bottle answers.

### Stretch
- Containment, item homes, the privacy cap, room cameras
- Fetch.ai remote agent ("where's my passport?" from anywhere)
- Photon: text "where are my keys?" over iMessage

### Parked
- **Remote helper places a sound.** A live helper can already talk someone there for one-off finds. The sound only helps when spoken directions get ambiguous or stale, or for labeling many items in one call, and the camera memory covers most of that. Skip it.

---

## 9. Privacy design
- Store item names, positions and times only. **"0 images stored"** shown on screen.
- Process on the device or a local hub. No cloud in the core loop. Gemini is optional, and if it's used, blur faces and text on the device first and send crops, not full frames.
- Cap variant: capture only when looking down, with a recording LED and a slide-over lens cover. Skip any frame that contains a face. Never track or identify people.
- Keep the memory on the device, encrypted, with old entries expiring.
- Remote queries: require Face ID for sensitive items and give coarse answers ("bedroom"), never the map.
- "Marco, forget this room" wipes everything for that room.

---

## 10. Reliability and gotchas
- **Bluetooth:** turn off the AirPods "Automatically switch" setting so they don't jump to a teammate's Mac mid-demo.
- **Spares:** bring 2 pairs of AirPods, charged. Use noise cancellation in the hall.
- **Battery and heat:** detect 1–2 times a second, only when the camera moved. Use a MagSafe battery pack.
- **Small objects far away:** keys are tiny in the frame beyond about 2 m. Index at the moment of release, or run the detector on cropped sections.
- **Offline-first:** keep the core loop on-device so venue Wi-Fi can't break the demo.
- **Backup:** record a demo video in a quiet room.
- **Hygiene:** disposable sleep masks, plus spare ear tips or disinfecting wipes between judges.

---

## 11. Demo script (90 seconds)
1. Put the lanyard (and Watch) on the judge. The phone hangs where their hackathon badge does. They introduce their water bottle in 3 seconds.
2. They set it down among two other bottles and put on a sleep mask.
3. They ask "Marco, where's my bottle?" and **only their bottle answers.** They turn their head and the sound stays put. The Watch taps, they grab it, and it says "Got it."
4. Meanwhile a teammate has moved a keychain you handed the judge at the start, keeping it in the camera's view. The judge takes off the mask and walks away. The AirPods say **"You're leaving your keys"** from behind them, at the new spot.
5. End on the map screen and "0 images stored."

---

## 12. Answers for judges
- **"Doesn't Seeing AI or Lookout do this?"** Those only work while you sweep the camera around, and the cues come from the phone. Google Lookout's Find mode only searches preset categories (seating and tables, doors and windows, cups, bottles and cans, utensils and tableware, vehicles, bathroom). Marco Polo remembers *your* items, the sound comes from the object itself, and it works when the object is off-camera.
- **"Why not AirTags?"** You'd need a tag on every item, and you can't easily tag a mug, glasses or medicine. AirTags are good for keys that leave the house, so the two complement each other.
- **"How accurate is it?"** Direction is within about 10–20°. Homing in works because the call repeats and you turn your head. The camera handles the last 30 cm.
- **"What about privacy?"** It stores events, not footage. Everything is on-device, 0 images are stored, and it never tracks people.
- **"What about battery?"** For the demo, a dedicated phone with a MagSafe pack. For the product, the cap or room cameras.
- **"Is it only for blind users?"** No, the curb-cut effect applies: it also helps people with ADHD, older adults, and anyone in a rush.

---

## 13. First-hour tests (de-risk before building the rest)
1. **Blindfold test:** place a fixed virtual sound, blindfold a teammate and time how long they take to touch it. Aim for consistently under about 15 seconds.
2. **Head tracking test:** check that Apple's automatic head tracking keeps the sound fixed in the room while walking and turning with the phone on your chest. Fallback: drive the listener orientation yourself from `CMHeadphoneMotionManager`.
3. **Recognition test:** check that feature prints can tell 3 different bottles apart from 1–2 m away.

---

## 14. Team split (4 people)
1. ARKit capture and 3D positioning
2. Recognition, enrollment and the memory (including the moved-item logic)
3. Spatial audio, head tracking and final-inch guidance (runs the blindfold test in hour one)
4. Voice and LLM, the map screen, the demo script and prize add-ons (Fetch.ai agent, Sentry tracing)

---

## 15. Hardware checklist

**Core**
- [ ] iPhone Pro with LiDAR (12 Pro or newer) ×1, ideally ×2. iOS 18+ for automatic head tracking. iPhone 15 Pro or newer for Apple's on-device model; otherwise use Gemini.
- [ ] AirPods Pro ×2 pairs (AirPods Max and AirPods 3/4 also do head tracking)
- [ ] Mac with Xcode (a free Apple developer account is enough)
- [ ] Chest mount or lanyard phone holder with the camera facing out
- [ ] MagSafe battery pack

**Demo props**
- [ ] 3 visually different water bottles
- [ ] A distinctive keychain, a wallet, a glasses case, a backpack
- [ ] An empty, labeled medicine bottle (label-reading demo)
- [ ] Disposable sleep masks, spare ear tips or disinfecting wipes
- [ ] A small tripod and phone clamp (backup video)

**Nice to have**
- [ ] Apple Watch (any recent model) for haptics

**Privacy cap (optional, about $60–80)**

| Part | Qty | ~Cost |
|---|---|---|
| Seeed XIAO ESP32S3 Sense | 2 (1 spare) | $14 each |
| Adafruit BNO085 motion sensor | 1 | $25 |
| 3.7 V LiPo, 500–1000 mAh | 1–2 | $8 |
| Red status LED and a slide switch | 1 each | $2 |
| Cap and a 3D-printed brim case with a sliding lens cover | 1 | — |
| Wires, heat shrink, Velcro, zip ties | — | — |

**Power and tools:** power strip and extension cord, USB-C chargers and cables, soldering iron, multimeter, hot glue, tape measure, painter's tape, 3D printer access.

**Accounts (set up before the event):** Apple Developer, Gemini API, ElevenLabs, Fetch.ai Agentverse, Sentry.

---

## 16. Prize map

| Prize | How Marco Polo qualifies |
|---|---|
| **Applied Intelligence** (main track) | Accessibility for blind and low-vision users |
| Beyond the Digital (alternative track) | Spatial audio and AR in the physical world |
| Paper: Best Designed Hack | Craft in the sound, haptics and map design ("personal craft, human touch") |
| veri.studio | Fine-tune an open model (the item detector or a placement-event vision model) using Veri |
| MLH Gemini | Recognition and descriptions (or opt-in only, if the core runs on-device) |
| MLH ElevenLabs | The voice and the chime/sound-effect design |
| Fetch.ai (ASI:One) | A uAgent on Agentverse using the Chat Protocol: "Where's my passport?" from anywhere |
| Espressif | The privacy cap |
| Sentry | Tracing on the sense → decide → audio loop, plus Logs or Session Replay. Cite a real bug or slowdown you found with it. |
| Cognition (Devin) | Build parts with Devin and document it |
| Photon | Text "where are my keys?" over iMessage |
| MLH GoDaddy | A domain for the project |

*Check the rules: you can probably submit to only one track, plus any number of company challenges.*

---

## 17. Other uses for the same tech

**The four building blocks:** (1) spatial memory, (2) sound pinned to a place, (3) hand guidance, (4) event understanding.

**At home**
- Leaving-home check (everyone, especially people with ADHD)
- Blind kitchens: find spices by ear, and know where the knife is and which way the blade points before reaching
- Night trip hazards: "Bag on the hallway floor ahead" (falls are the leading cause of injury death for adults 65+)
- Packing checks: "Is my charger in my bag?"
- Dementia care: misplaced items and gentle reminders
- Hotel rooms and airport gates for blind travelers: a "hear the room" sweep

**Beyond the home**
- Moving: "Which box has the HDMI cables?"
- Warehouse picking by sound: the right bin calls the worker, hands and eyes free
- Factory assembly: "Next: the 10 mm bolt", the bin chimes, the camera confirms the pick
- Home inventory for insurance claims
- A memory layer for home robots ("Robot, bring my keys"), which fits Fetch.ai agents
- Smoke-filled buildings: exits and teammates as sound beacons (needs a pre-mapped building)
- Job sites: hard hats are already head-mounted, so "where did I leave the drill?" fits naturally
- Games: scavenger hunts and escape rooms played by ear

**For the pitch:** keep blind users as the core story, then add one breadth slide.

---

## 18. Other ideas considered (backups)

**Spatial audio ideas**
- **Look to Listen:** face whoever you want to hear in a loud room and their voice comes through clearly. The loud hall is the demo.
- **Their Voice:** each person's speech is translated and played from their seat, in a clone of their own voice. Fine-tune for mixed-language speech (Spanglish, Hinglish). Strong ElevenLabs fit.
- **Memory Palace:** AI turns any list into scenes pinned to spots in your room.
- **Story Room:** an AI story set in your actual room.
- **Eyes-Closed Arcade:** Aircade, but playable by blind players.
- **The Council:** AI agents placed around you; look at one to talk to it.

**Other ideas**
- **Margin:** an AI tutor that writes hints in your paper's margin with a pen plotter. Eedi's misconception dataset could be used for fine-tuning.
- **Tip of the Tongue:** the Even G2 glasses show the word you're stuck on. Needs a G2 loaner.
- **Knock Knock:** a piezo sensor turns any surface into a touch interface.
- **Anything Arcade:** an IMU clipped to any object, and AI invents a game for it.
- **Backbeat:** a QNX desk drummer.
- **What's in the cup?:** Wi-Fi identifies liquids inside a foil-lined box.
- **4D Anything, Courtside, Jenga with a pulse:** rejected as gimmicky, with too little AI.

**Rejected and why**
- Textbook esp-csi presence or fall detection
- Hardware gimmicks where the AI does little
- Anything that overlaps Even G2's built-in features (AI Cues, translation, teleprompter, conversation summaries)

---

## 19. References gathered
- Hack the North museum: <https://museum.hackthenorth.com>. Reflex, Orbis Engine, Combadge (QNX 8.0 on a Pi 5, conductive thread), S-KBD67 (Nerf gun turned into an FPS controller with ESP32 and gyros), Concerto, Keymaeleon, TakeOne, punching-face, bingbong.
- Aircade: <https://devpost.com/software/aircade-m4n6zv>. Swift, SceneKit, Core Motion. Only one AirPods motion stream can be active at a time.
- LA Hacks 2026 winners: <https://la-hacks-2026.devpost.com/project-gallery>
- Even G2 starter pack: <https://evenrealities-lahacks.vercel.app/starterpack>. No camera or speaker; display, mic and touch only; one loaner per team.
- QNX open-source ports: <https://oss.qnx.com> and <https://github.com/qnx-ports> (onnxruntime, tflite-micro, whisper.cpp, llama.cpp, opencv, mediapipe, executorch, ROS 2)
- Google Lookout Find mode: Google accessibility help page (preset categories only, hold the device steady and move slowly)
- Spatial audio research: Wightman & Kistler (1999); Begault, Wenzel & Anderson (2001); Loomis et al., Personal Guidance System; Microsoft Soundscape

---

## 20. Open decisions
- [ ] Demo capture device: chest iPhone (simplest) or the privacy cap (better story, plus the Espressif prize)
- [ ] Recognition: on-device (Foundation Models needs an iPhone 15 Pro or newer) or Gemini
- [ ] Include the Apple Watch in the demo?
- [ ] Main track: Applied Intelligence or Beyond the Digital
- [ ] Final name and domain
