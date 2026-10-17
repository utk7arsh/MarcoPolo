# Marco Polo, everyday edition: ideas, features and avenues to explore

Everything here is backed by research (`research/`) or emulator POCs (`pocs/`, results in `reports/`). Detailed feature specs with evidence are in `FEATURES.md`; positioning is in `POSITIONING.md`.

---

## The idea in one line

**A memory you wear.** Marco saw where you put them; it doesn't scan the room for them. It notices where your things go without being asked, keeps that memory across days, speaks up when something changes, and guides you with sound that comes from the thing itself.

Search apps make you hold the phone, ask, wait for a cloud model, and follow the sound. Marco is ambient: nothing to hold, nothing to point at, and the answer is already known when you ask.

**Headline pitch (current):** "Other finders find your mug. Marco tells your hand which jar is cumin." Blind people rarely lose spice jars; they can't tell identical-feeling jars, pill bottles and cans apart. The verified spec (reach-and-hear, labels from anyone via Photon, read-it-once, plus nine additions and the known limits) is in `FEATURES.md` §0.

---

## 1. The wearable: one system, three parts, each doing what it's best at

| Part | Role | Why this part (evidence) |
|---|---|---|
| **Body: iPhone Pro in an off-the-shelf phone chest vest/harness** (e.g. Ulanzi CM028 or STUNTMAN from Amazon), tilted ~30° down, plus a MagSafe battery | The mapper. ARKit pose + LiDAR depth give 3D item positions and the room map, and its heading is the drift-free anchor for head tracking | Body-fixed camera: re-sees items **100%** within 60 s of walking, regardless of head behaviour (POC 11; this model ignores occlusion, and POC 1's ray-cast walk found small keys far less often). Positions 1–10 cm (POC 1). **The 30° tilt is required:** at 0° the phone sees a table only from 0.96 m and catches **7.5%** of put-downs, vs **49%** at 30° (POC 7, 11) |
| **Face: AirPods Pro, or Ray-Ban Meta glasses** (Meta Wearables Device Access Toolkit) | Ears + head motion (+ an eye-level camera, if glasses) | Glasses: the eye-level camera catches **87%** of put-downs when you look at your hands. Open-ear speakers keep the room audible. "Hey Meta" can launch the app. Blind users already wear them (official Be My Eyes integration). Caveat: the glasses compass alone gives a 12° median error indoors (POC 4), so head yaw still comes from gyro + ARKit fusion (1.9°) |
| **Wrist: Apple Watch** (optional) | Silent trigger + haptic "you're facing it" taps | watchOS 11 Double Tap works in third-party apps (`handGestureShortcut`), so you can trigger with one hand while holding a cane. Haptics help in loud places and for DeafBlind users |

**Why the hybrid instead of glasses alone:**
- Blind users often don't point their heads at their hands. With "blind-typical" head behaviour, glasses catch 39–52% of put-downs, and the chest camera still catches 49% because it doesn't depend on the head.
- Together they cover **71%** (93% for people who look at their hands), and re-sightings fill the rest (POC 11).
- Glasses have no depth sensor and no reliable indoor heading, so the phone stays the brain and the mapper.

**Vest setup (off-the-shelf; see the shopping list in section 6):**
- **Harness, not lanyard.** The phone must turn exactly with your torso: its heading is what keeps the sound fixed in the room. A lanyard swings and twists; a vest with shoulder and back straps doesn't.
- **Position:** phone in the vest's clamp on the upper sternum (~1.25–1.40 m). Screen faces the chest; cameras and LiDAR face out. The clamp should grip the side edges at mid-height, so the top-corner camera stays clear.
- **Tilt:** set the mount's joint to ~30° down and tighten it. Friction joints can slip while walking, so add a small printed lock shim, or check the angle in-app.
- **In-app tilt check:** the phone measures its own angle from gravity. Marco can say "camera is at 22°, tilt it down a bit", and it also catches a loosened or rotated mount.
- **Power:** continuous ARKit uses ~45–50% of the battery per hour. Run the detector at 2 Hz and only while the wearer moves, and attach a MagSafe battery to the outward back, below the cameras.
- **Screen:** iOS stops the camera when the app is in the background or locked. Keep Marco in the foreground with the screen dimmed, under Guided Access.
- **Starting and asking:**
  - put an NFC sticker on the clamp, with a Shortcuts automation, so docking the phone opens Marco;
  - "Hey Siri / Hey Meta, ask Marco…";
  - the Action button (iPhone 15 Pro+) if the clamp leaves it exposed;
  - Apple Watch Double Tap.
- **Heat:** leave airflow behind the phone. Don't sandwich it against the body with padding.
- **Feel:** a tactile marker on the clamp's top edge, so it's mounted the right way up without looking.

**Stretch / vision, "Marco Home":** old iPhones plugged in on shelves watch the main surfaces around the clock. They track you with Vision 3D body pose, so at home nothing needs to be worn; you just ask. This is the most work: multi-device alignment via a shared ARWorldMap.

---

## 2. Faster and more seamless than search-on-ask finders (measured or sourced)

| | Search-on-ask finder | Marco Polo |
|---|---|---|
| Time from asking to first sound | A cloud model call, and only if the item is in the camera's view | **< 0.5 s**: the answer comes from local memory; speech starts immediately |
| End-to-end find time | Aim the camera, wait for the model, then follow the cue | **6.8 s median** guidance in simulation (POC 5). Not measured on people, so verify with the blindfold test |
| Works offline / no quota | Usually a cloud model call per search | Memory answers and cached labels work offline; new sightings need our own server (no third-party quota) |
| Item out of view | Only if it was searched for earlier in the same session | Yes, across days (ARWorldMap persistence) |
| Hands-free start | Hold the phone and touch the screen | "Hey Siri" / "Hey Meta" / Action button / Watch Double Tap / dock with NFC |
| Who speaks first | Always you | Marco: "moved", "dropped", "you're leaving without your keys" |
| Guidance | A spatial cue toward the item | Spoken body-relative answer first, then a beacon with "facing it" and "behind you" variants (99% within 15 s in POC 5), routed around furniture, ending on a hand-level cue |
| Identity | "a mug" | *your* mug (98–99% picking yours out of 3 at 2 m, real iPhone footage) |

---

## 3. Features and avenues to explore

### Mapping

1. **Breadcrumb routing around furniture.** In a furnished room, the straight line to the item passes through furniture **35%** of the time (POC 12). With the LiDAR/RoomPlan map, plan a path and play the Polo from the next waypoint: median 3 waypoints, +22% path length. *Demo moment: "Polo leads you around the coffee table."*
2. **Whole-home map.** RoomPlan's StructureBuilder (iOS 17) merges room scans. "Your keys are in the bedroom": the Polo plays from each doorway, then from the item.
3. **Floor-hazard heads-up.** LiDAR sees objects on the floor ahead: "Bag on the floor, two steps ahead, slightly left." Bags, shoes and boxes are caught about 3 m ahead with no false alarms; clutter under ~8 cm is not (POC 15). The 30° tilt shrinks the blind zone from 2.2 m to ~0.7 m, which the cane covers.
4. **Spatial voice labels.** "Marco, this is the cumin"; later the jar speaks when your hand comes near. With row matching it's **97–100%** right on identical jars even with 2–16 cm of map drift, vs 37–68% for point anchors (POC 13). See `FEATURES.md` §1.
5. **Item homes and tidy check.** "Keys live on the hook." Later: "Your keys aren't home; last seen on the sofa."
6. **Guided search when it's genuinely lost.** Checks the likeliest places first (probability ÷ walking time) and skips surfaces the camera has already seen empty.
7. **Retrace / back to my seat.** "Take me back to where I was sitting." The breadcrumbs end within about 4–25 cm after a 20–50 m trip (ARKit drift is 0.2–0.5% of distance walked).
8. **"Hear the room"** in a hotel or new place. A clockwise spoken sweep plus spread-out pings. Speech carries the layout; pings alone can't (POC 9: 31–39%; spread + speech 69–87%).
9. **Timeline:** "When did I last have my wallet?" / "What was on the counter at noon?"
10. **Shared family map** (vision slide): a housemate's phone also logs sightings via a collaborative session.

### Proactive, and other

- "**Someone moved it**" (proven, POC 2).
- **Put-down confirmation**, spoken softly: "Keys, entry table."
- "**You're leaving without your keys**", triggered by a door anchor.
- **Drop detection** (POC 14, real recordings): Apple's on-device sound classifier scored **0.90–0.98 on every clean key-drop clip**, with 0 false alarms in 18 everyday sounds after a context veto. Soft drops need the camera's floor check.
- **Medicine label check at pickup.**
- **Find your cane** (cluster #4 in ORBIT, the dataset of things blind people search for).
- **Nod to confirm**, from AirPods or glasses IMU.

### Also helps older adults stay on their feet

**Why it's credible:**
- **Trips and slips cause 59% of falls** among independent older adults living at home (Berg et al. 1997, *Age and Ageing*).
- More than **1 in 4 adults 65+ fall each year**, and about **43,000 die** from falls (CDC STEADI).
- CDC's home checklist asks people to keep objects off floors and stairs, light the path from bed to bathroom, and keep often-used things on low shelves. Several Marco features do exactly that.

**What Marco does about it:**
- **Trip-hazard heads-up** (POC 15, LiDAR emulator walk):
  - "Bag on the floor, two steps ahead, slightly left."
  - Bags, shoes and boxes (10 cm tall or more) were caught **every time, about 3 m ahead (3–5 s of warning)**, with **0 false alarms** in 10 bare-floor walks.
  - **Limit:** low clutter under ~8 cm (cords, rug edges, flat books) is *not* reliably caught, so CDC's "tape down cords" advice still applies.
- **No crawling to find what you dropped.** Drop detection plus "Polo" from the floor and a hand-level cue means no bending and sweeping the floor on hands and knees, which is risky for older adults.
- **No searching in the dark.** "Marco, where are my glasses?" at night gives an answer without walking around looking, on the dark bed-to-bathroom path CDC flags.
- **Tidy nudges.** "Your bag is still on the hallway floor." Item homes keep things off the walking path, and Marco can suggest moving often-used things lower.
- **Falls themselves:** use the Apple Watch's built-in fall detection; don't build our own.

**How to say it:** "Marco helps people stay on their feet: it warns you about the bag in the hallway and finds what you dropped, so you never have to crawl for it." Don't claim it *prevents falls*; that needs a clinical study.

**Overlap with the core audience:** age-related vision loss (macular degeneration, glaucoma, cataract) means many older adults are also low-vision, so it's the same users.

---

## 4. What to build in 36 hours

**Core:**
- Phone chest vest (30° tilt) + AirPods.
- Passive capture.
- Move-aware memory saved with ARWorldMap.
- Spoken answer + beacon + reach cue.
- Breadcrumb routing in one room.

**Wow:**
- "Someone moved it", "leaving without your keys", and "relaunch, it still remembers" (see `POSITIONING.md`).
- Spatial voice labels on a spice row.
- Breadcrumbs around the coffee table.

**Stretch:**
- Drop detection (keys).
- "Take me back to my seat" in the hall.
- Ray-Ban Meta as the face (if the team owns a pair; Motion data is beta and dev-channel only).
- Watch Double Tap.

**Vision slide:** Marco Home ambient cameras and the shared family map.

---

## 5. Risks

- **Vest joint slipping off 30°:** lock it with a shim, and use the in-app tilt check.
- **Weight and heat of the phone + battery on the chest:** wear-test it for an hour.
- **Persistence:** relocalization time and accuracy need the hour-one test (`POSITIONING.md`).
- **Meta DAT is a developer preview:**
  - the Motion API is beta;
  - camera streaming over Bluetooth Classic is compressed and auto-degrades;
  - battery drain while streaming is unpublished.
- **Head-pointing behaviour of blind users with glasses:** unmeasured. It decides how much a glasses camera adds.

---

## 6. Shopping list (vest setup)

- **Phone chest vest/harness with phone clamp:**
  - Ulanzi CM028 (phone version): https://www.amazon.com/clp/B0D3DRXLN9
  - STUNTMAN High Stability Chest Mount for Smartphones (most stable in reviews): https://stuntmancameramounts.com/shop
- **MagSafe battery** (any).
- **NFC sticker** (NTAG215) for "dock to open Marco".
- **Optional:** a small printed lock shim for the tilt joint.
