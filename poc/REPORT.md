# Marco Polo: feasibility report (emulator-based POCs)

- **Date:** 2026-10-14
- **Scope:** checks the ideas in `../marco-polo.md` before the hackathon.
- **What was run:** everything ran locally on emulators of the iPhone (ARKit + LiDAR), the AirPods (head motion), and Apple's own spatial-audio engine. A simulated blind listener was calibrated to published human data. Each emulator was checked against real-device data or published measurements first; there are 19 automated fidelity tests and all pass.
- **What was not run:** nothing was run on a real iPhone or AirPods. The things only hardware can settle are listed in §8 as hour-one tests.

---

## 1. Verdict

**Feasible. Pursue it, with five design changes.** The core loop works in simulation end to end, with numbers well inside what guidance needs:

1. **Remember** where items are: 1–10 cm fused position error.
2. **Notice moves**: 100% of scripted moves and look-alikes handled (90 runs), and 0 false "gone" across 90 adversarial runs (occlusion, far views, motion blur).
3. **Guide**: a beacon gets 99% of simulated blind users to the item within 15 s.

The five design changes:

1. **Tilt the chest mount 25–35° down.** A vertical lanyard cannot see a table closer than 0.96 m, so "the camera guides your hand" is impossible as written. It also misses most key sightings.
2. **Don't rely on Apple's automatic head tracking with a chest phone until hour one proves its reference frame.** If it is not phone-relative, the sound swings by about 84°. Use our free fusion (ARKit torso + AirPods deltas) as the baseline. Head Pose also needs a paid Apple Developer account, not a free one.
3. **Replace "a call once a second" with a Soundscape-style beacon.** It plays ~2.5 Hz with distinct "facing it" and "behind you" variants, gets faster as you approach, ends on a "within reach" chime, and then says where the item is relative to your body.
4. **Code distance and height explicitly.** By default Apple's engine stops getting louder inside 1 m, and humans can't hear height. Use tempo, plus speech such as "waist height, at your left hand".
5. **Lead the pitch with memory, not spatial audio.** ARKit + LiDAR + head-tracked AirPods object finders already exist (research since 2018, Seeing AI since 2020, several 2026 hackathon projects; see `research/landscape/`).
   - They search only when asked, and remember for one session at most.
   - Our edge: passive capture that notices without being asked, memory that survives relaunch, and events (moved, dropped, "you're leaving without your keys"). This is a narrow gap, so build it, don't just claim it.

---

## 2. What we can and can't do

**Can do (verified in simulation, emulators validated against real data):**

| Capability | Result | Where |
|---|---|---|
| 3D position of items from chest-camera detections + LiDAR + ARKit | 4–10 cm per sighting (p90 10–17 cm); 1–10 cm fused; holds with depth noise at 2× the measured value | POC 1 |
| Clear and glass bottles (LiDAR sees through them) | "Footprint" method (raycast onto the supporting surface) 10.7 cm vs 18–22 cm for depth-at-box; height ±2 cm | POC 1 |
| Item moved in view → memory updates | 100%, 0.5 s | POC 2 |
| Item moved out of view → "not where I left it" when you look back | 100%, 1.5 s after looking; found at the new spot 1.5 s after seeing it | POC 2 |
| No false "gone" when occluded, far/marginal, or motion-blurred | 0/90 runs | POC 2 |
| A look-alike bottle on the old spot isn't taken as yours | 100% correctly "not there", 1 s | POC 2 |
| Distance and direction update correctly while walking to the item | direction 2.6° median (p90 4.8°), distance 7 cm, never jumps backwards | POC 3 |
| Head-tracked, world-fixed sound with a chest phone and a free developer account | ARKit + AirPods fusion: 1.9° median, <5° 87% of the time, robust to 10°/min AirPods drift | POC 4 |
| Guiding a blindfolded person to an item | beacon design: 99% within 15 s, median 6.8 s, 98.7% path efficiency; still 90% at 500 ms latency | POC 5 |
| "Only your bottle answers" (Apple Vision feature prints, real iPhone footage of 8 bottles) | pick-the-right-one-of-3: 98–99% at ~2 m, ~93% at ~3.3 m, with all-sides enrolment | POC 6 |
| Fuzzy requests ("the thing I drink from", "my specs") fully offline | Apple NLEmbedding: 12/12 tuned, 9/10 held-out | POC 8 |
| Drop trigger | Apple's on-device SoundAnalysis has `thump_thud`, `keys_jangling`, `coin_dropping`, `glass_breaking` (accuracy untested) | POC 10 |

**Can't do (or not as described):**

| Claim in marco-polo.md | Reality | Fix |
|---|---|---|
| "A free Apple developer account is enough" | Head Pose (automatic head tracking) and Personalized Spatial Audio entitlements are paid-program only (Apple's capability table) | Use CMHeadphoneMotionManager + our fusion (no entitlement), or one teammate buys ADP ($99) |
| "Chest phone matches Apple's automatic head tracking" | The reference frame is undocumented. If it's start-relative, combining it with ARKit double-counts body turns and the error is ~84°. If it's phone-relative, it's the best option (1.6°) | Hour-one whole-body-turn test (§8); fusion is the fallback |
| "Camera sees your hand and the object together" (last 30 cm) | A vertical chest camera can't see a table top closer than 0.96 m (portrait VFOV 62°, HFOV 48°) | Mount tilted 25–35° down. At 25° the table is visible from 0.39 m and the floor from 0.92 m; you lose high shelves |
| "Index at the moment of release" | Same geometry: hands at a table in front are out of frame at 0° tilt | Same tilt |
| "Distance: calls get louder as you get closer" | Apple's default inverse-distance model is flat inside 1 m (reference distance = 1 m). Absolute loudness is a poor distance cue anyway | Tempo vs distance + "within reach" chime + speech. Set `referenceDistance` to ~0.3 m if loudness is used |
| "Repeat the call ~1/s; turn until it's dead ahead" | Works most of the time (71% within 15 s), but too sparse and front/back-ambiguous | Beacon with on-axis/behind variants (99%), §5 |
| "What's on the table? Each item pings from its spot" | Items 20–30 cm apart at 2 m: correct left-to-right order only 31–39% (chance 17%) | Spread the pings 3× (69–87%) and speak the labels left to right; or "head-scan": the item you face says its name |
| Detecting keys / wallets / glasses with an on-device YOLO | COCO-trained detectors have no keys, wallet or glasses classes (bottle, cup, remote, phone and backpack are fine). Small keys need ~40 px; at a 0° mount they were sighted only 5 times in two room loops | Open-vocabulary detector (e.g. YOLO-World exported to Core ML) or Gemini boxes, feature-print matching, a tilted mount, and "put-down" indexing up close |
| On-device LLM for fuzzy queries | Needs Apple Intelligence enabled + iPhone 15 Pro or newer (couldn't run here: not enabled on this Mac) | NLEmbedding fallback works offline on any iPhone (POC 8) |

---

## 3. How it was tested, and why the emulators can be trusted

| Emulator | Built from | Fidelity evidence |
|---|---|---|
| **Apple spatial audio** | HRIRs extracted from Apple's real `AVAudioEnvironmentNode` (HRTFHQ, offline render), 721 directions, 6 distances | ITD 760 µs at 90°, inside the human range of 656–776 µs (12 measured heads); matches Woodworth within ~5%; real front/back spectral cue (+4–13 dB at 8–16 kHz); linear and time-invariant; `.auto` is identical to HRTFHQ in offline mode |
| **Apple engine dynamics** | Real engine rendering while the listener yaw changes (10 ms and 25 Hz updates) | Running ITD tracks the expected value (RMS 36–47 µs); **positive listener yaw = head turns RIGHT**, the opposite of ARKit/CoreMotion's right-hand rule, so negate when converting; ~40 ms internal smoothing; no clicks |
| **iPhone ARKit + LiDAR** | Ray-cast furnished room; ARFrame-like output (256×192 float32 z-depth, confidence 0/1/2, 1920×1440 intrinsics fx=1600) | 14 tests: noise vs distance within 25% of our **own measurement of real iPad LiDAR vs Faro laser GT** (ARKitScenes, 1.85 M pixels) × 1.5 iPhone factor; confidence mix; edge flying pixels; small-object bleed; portrait FOV 48.4°×61.9°; VIO drift 0.3%/m |
| **Detector** | Detection probability vs pixel size, visibility, blur; bbox jitter; false positives; look-alike confusion | Parameterised; recognition numbers come from the real Vision API (POC 6) |
| **AirPods motion** | 25 Hz, no magnetometer, start-relative yaw, gyro drift, latency, dropouts | Rate and frame from research; drift and latency unpublished, so swept over 1–10°/min and 50–150 ms |
| **Simulated blind listener** | Bayesian localization: Apple-rendered cues interpreted with a real person's ears (12 ARI HRTFs); human head-turn kinematics; 0.6 m/s gait | Calibrated: generic-HRTF front/back confusions 33% (lit. 20–59%), own-HRTF 10%, lateral error 12°. **Out-of-sample:** head movement drops confusions to 5.2% (Oberem 2020 measured 6.3–7.1%) |

---

## 4. POC results in detail

- **POC 1, mapping** (`pocs/poc1_mapping`): two loops of a furnished room at 0.8 m/s, ARKit drift on, three methods.
  - Median depth over the box gives the best horizontal error (fused 1–8 cm).
  - The footprint method gives the best height (±2 cm) and is the only one that survives a clear bottle.
  - **Recommend:** footprint for height and glass; median depth for horizontal; fuse the last 5 sightings.
- **POC 2, moved items** (`pocs/poc2_moved`): six scenarios × 30 seeds, all pass. The memory accumulates evidence (log-odds). It never decides from one frame, and negative evidence counts only when LiDAR shows the bare spot in view.
  - Three bugs were found and fixed on the way. These are exactly the bugs a naive implementation ships with:
    - a single misrecognised look-alike resets "present";
    - a table seen at a grazing angle looks like an occluder;
    - one outlier depth estimate becomes a confident "miss".
- **POC 3, walking to the item** (`pocs/poc3_walk`): 30 approach walks through the full chain.
  - The ear offset (ears ~30 cm above and ~10 cm behind the phone) matters. Without it, distance error rises to 17 cm and height error to 5°.
  - "Within reach" fires ~65 cm from the chest, so set the threshold relative to the phone.
- **POC 4, head tracking** (`pocs/poc4_headtracking`): five pipelines over 5-minute realistic sessions (median error, % under 5°):
  - phone only: 3.3°, but p90 45° (doesn't follow head turns)
  - AirPods only: 7.5°, drifting
  - **fusion: 1.9° / 87%**
  - Apple automatic, phone-relative: 1.6° / 95%
  - Apple automatic, start-relative: 84° (unusable)
  - Fusion tuning: τ = 5 s, gated when the head is within 15° of the torso.
- **POC 5, guidance strategies** (`pocs/poc5_guidance`): 12 listeners × 24 targets, plus sensitivity runs.

  | Strategy | Within 15 s | Median |
  |---|---|---|
  | single call | 25% | — |
  | 1 Hz call (doc) | 71% | 6.7 s |
  | 1 Hz call, tempo by distance | 81% | — |
  | 4 Hz clicks | 87% | — |
  | continuous | 83% | — |
  | 1 Hz + lock/behind | 93% | — |
  | **2.5 Hz beacon + lock/behind** | **99%** | **6.8 s** |
  | clock-face speech then beacon | 99% | 8.5 s |
  | 1.5× supernormal azimuth | 98% (no gain) | — |
  | speech only | 53% | — |

  - **Ranking robustness:** the ranking holds with latency (50–500 ms), walking speed (0.4–0.9 m/s) and poorer listeners.
  - **Tracking error matters most:** with ≤5° error users still always reach the item. At 10° they arrive from the side; at 20° only ~60% arrive. Hence the <5° requirement for POC 4.
- **POC 6, recognition** (`pocs/poc6_recognition`): Apple Vision `VNGenerateImageFeaturePrintRequest` on 8 real Objectron iPhone bottle videos.
  - One-sided enrolment: 3-bottle ID at native, 200, 120 and 80 px is 99 / 97.8 / 91.7 / 86%.
  - All-sides enrolment: 99.3 / 93.6 / 92% at 200 / 120 / 80 px.
  - Saying "not mine" to an unknown bottle is weaker (77–87% accept at 1% false-accept, at 2 m). So pick among the candidates in view and accumulate evidence.
  - Vision's foreground mask removes background bias (the same table in the demo) at a small accuracy cost.
  - **Caveat:** these bottles differ in type. Three near-identical water bottles would be harder, so pick visually distinct props.
- **POC 7, reach geometry** (`pocs/poc7_reach_fov`): nearest visible table / floor / highest point at 2 m, by tilt:
  - 0°: 0.96 / 2.26 / 2.39 m
  - 25°: 0.39 / 0.92 / 1.43 m
  - 35°: 0.26 / 0.61 / 1.08 m
- **POC 8, queries** (`pocs/poc8_query`): see §2.
- **POC 9, layout** (`pocs/poc9_layout`): see §2.
- **POC 10, drops** (`pocs/poc10_drop`): see §2.

---

## 5. How to tell the user where it is (recommended interaction)

The answer to "is *repeat the call once a second and turn until it's dead ahead* a good idea?" is **mostly yes, with three upgrades**:

1. **Faster.** About 2.5 Hz (Soundscape's 0.4 s beat), so you hear it during the ~1 s head turn.
2. **Categorical cues.** A distinct "facing it" variant within ±10–15° and a muffled "behind you" variant past ~110°.
3. **Explicit distance and height.**

Turning to face the sound is the right strategy because hearing is sharpest straight ahead (~1° minimum audible angle). But with a generic HRTF "dead ahead" and "dead behind" sound alike. The app knows the true angle, so it should simply *tell* you with the variant.

**The flow (one sound, one voice, one gesture):**

1. "Marco, where are my keys?"
2. The calm voice answers first, in words, relative to your body (the chest phone's heading, the O&M convention): *"Keys. Coffee table, two o'clock, three steps, low."* If the item is behind you, the speech resolves it instantly.
3. The beacon plays from the keys. It changes to the bright "facing it" double-ding when you're aligned; the phone on your chest gives a haptic tap at the same moment, which is free, with no Watch needed. If you've turned the wrong way you hear the muffled "behind" variant.
4. As you walk it speeds up (period 1.0 s far → 0.4 s near), and re-aims you every step.
5. At ~65 cm from the chest a three-note "within reach" chime plays. Then a body-relative hand cue: *"At your left hand, knee height."* That uses ARKit's torso frame, which doesn't drift, so a residual AirPods error doesn't matter here.
6. With the tilted mount the camera sees your hand. *"Left… got it."* Nod to confirm.
7. If the item isn't where it was last seen, Marco never sends you to an empty spot: *"Your keys were on the coffee table at 2:14, but they're not there now. Last seen moving toward the hallway. Want me to look?"*

Listen to it: `reports/audio/` has binaural renders through Apple's HRTF (use headphones, with macOS "Spatialize Stereo" off).
- `01_direction_tour.wav`: hear the generic HRTF's front/back ambiguity yourselves.
- `02_doc_design_1hz.wav` vs `03_recommended_beacon.wav`.

---

## 6. Features that make it better (ranked for a 36-hour build)

Pain points come from `research/pain_points_and_landscape.md`. Stars mark demo "wow" moments.

**Must (core loop):**
- Passive memory + "Marco, where's my X?" + beacon + "within reach" + body-relative hand cue.
- Put-down confirmation, spoken softly ("keys: coffee table"). It builds trust and doubles as the memory write.
- Nod to confirm / shake to cancel. There is no public API, but CMHeadphoneMotionManager pitch/yaw rates are enough.
- Phone-on-chest haptic lock tap, for noisy halls and DeafBlind users.
- Transparency mode, and a beacon that plays only on demand. Blind users' top complaints are constant beacons and blocked ears.

**Demo moments:**
- ★ "**Someone moved it**": "Your mug was moved from the desk at 3:12 to the shelf." Already proven in POC 2. Moved items are a top blind-user pain point (etiquette guides; hotel housekeeping).
- ★ "**You're leaving without your keys**", heard from behind at the door.
- ★ **Drop detection**: SoundAnalysis `thump_thud`/`keys_jangling` + the last frames before the drop + the floor in view with the tilted mount. "Sounds like something fell — Polo," from the floor.
- ★ **Only your bottle answers**: proven at ≤2 m with all-sides enrolment. Use visually distinct bottles.

**Polish / stretch:**
- Siri / App Intents / Action button.
- Item homes ("keys aren't home").
- Find your cane, which is cluster #4 in ORBIT.
- Label reading at pickup for medicines.
- Hotel "hear the room": one sweep, then clockwise callouts.
- "What's on the table" (spread pings + spoken order).
- Timeline queries ("when did I last have my wallet?").

**Curb cut:**
- The same app finds a sighted person's TV remote. 45% lose it weekly (Pixie 2017).
- The Polo plus an on-screen arrow suits sighted users.
- A caregiver / shared family memory goes on the vision slide.

---

## 7. Apple-quality bar: acceptance criteria to carry into the build

| Area | Ship criterion (measure on device, as in the POCs) |
|---|---|
| World-fixed sound | Whole-body 90° turn with the phone on the chest: rendered source moves < 5°; head-only turn: < 5° |
| Yaw sign | Turn right: a source straight ahead moves to your LEFT ear. Write a unit test: AVAudio yaw = −(right-hand yaw) |
| Guidance | Blindfold test: ≥ 9 of 10 trials reach within 15 s, median < 10 s (sim: 99% / 6.8 s) |
| Memory | Never "present" for an empty spot. Moved item: update ≤ 2 s after seeing it. No false "gone" when occluded or far |
| Position | Fused item error ≤ 10 cm horizontal, ≤ 5 cm height |
| Latency | Motion-to-sound ≤ 300 ms (keep calls short, re-aim each call) |
| Failure is never silent | Every query gets a spoken answer, including "I haven't seen them since 8:10 at the entry table" |
| Battery and heat | ~45–50%/h measured for continuous ARKit: MagSafe pack; throttling after ~2 h. Detector at 2 Hz only when moving |

---

## 8. Hour-one hardware tests (things the emulators cannot settle)

Ordered by risk.

1. **Apple automatic head tracking's reference frame.** Phone on the chest, a chime straight ahead. Turn your whole body 90°.
   - The chime should now be on your left.
   - If it stays in front, or swings past, the reference is not phone-relative. Use the fusion.
   - This needs a paid account for Head Pose. On a free account, go straight to the fusion.
2. **CMHeadphoneMotionManager.** Log the timestamp against the arrival time at 25 Hz. Measure jitter, latency, and yaw drift over 10 minutes with the head still. Note what makes it re-centre.
3. **End-to-end motion-to-sound latency.** Tap the AirPod, record the click with another phone. Budget ≤ 300 ms.
4. **Mount tilt.** Set the chest vest's phone mount to 25–35° and lock it. Check that the table, the hand and the floor near the feet are in frame.
5. **Detector on real props** at 1–3 m: keys, wallet, glasses case. The open-vocabulary choice decides keys and glasses.
6. **LiDAR on the actual demo bottles.** Glass or clear plastic reads the background, so use the footprint method.
7. **Blindfold test** with the beacon design. Compare it against the 1 Hz call on the same people.

---

## 9. Known unknowns and honest limits

- **Unmeasured AirPods numbers:** latency, drift and jitter aren't published, so they were swept rather than fixed.
- **Apple's head-tracking reference:** undocumented. It is the #1 hardware test.
- **Listener model:** calibrated to group data, but real blind users differ. They are often better at sound and slower walkers, and they learn fast. Treat the strategy *ranking* as robust and the absolute times as estimates.
- **Detector behaviour:** parameterised from general small-object behaviour, not measured on keys. Recognition (POC 6) is real-API, real-data, but on bottles of different types.
- **LiDAR source:** the noise model comes from iPad Pro LiDAR (the same 576-point emitter) × 1.5 for iPhone, per ScanNet++.
- **Untested here:** the on-device LLM (Apple Intelligence was off) and drop-sound accuracy.

---

## 10. Files

```
poc/
  REPORT.md                  this file
  README.md                  how to run everything
  research/                  four research reports with sources (+ raw papers and pages)
  emulators/apple_audio/     Swift: HRIR extraction and dynamic render on Apple's real engine
  emulators/audio, listener/ HRTF I/O, auditory features, Bayesian listener + calibration
  emulators/arkit/           room ray-caster, iPhone ARFrame/LiDAR/VIO emulator, detector
  emulators/motion/          AirPods CMHeadphoneMotionManager emulator, human head/body sessions
  core/mapping.py            the app logic under test (position methods + move-aware memory)
  pocs/poc1..poc10/          each POC (run.py / sim.py) - results in reports/*.json
  validation/                19 fidelity tests (pytest) + Apple-engine and listener validations
  reports/                   JSON results, figure, binaural demo WAVs
  data/                      extracted Apple HRIRs, downloaded HRTFs/ARKitScenes/Objectron samples, tmp
```
