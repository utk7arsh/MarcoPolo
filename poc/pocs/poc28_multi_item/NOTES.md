# POC 28: several registered items: are they all checked, and why are items 2, 3, … missed?

**Question (user, 2026-10-18):** "for multiple registered objects does it check for all of them: like moving ones (that are already found and might move) and new ones … currently it is not able to detect the objects beyond the first one."

## How inference runs (code: `server/marco/perception/detector.py`, `brain.py`, `world/memory.py`)
- **Every frame checks every registered item.** There's one OWLv2 image pass with one query per item, so found and unfound items are treated the same; the guidance target isn't special.
  - For each item, the best-scoring box is put through the presence check: photo + name logit, DINOv2 similarity of the box crop to the registration crop, and "looks more like this item than my other items".
- **The world model then splits by state** (`World.sighting`):
  - an unplaced item is placed on its first sighting;
  - a sighting within 25 cm refreshes it;
  - a sighting elsewhere moves it only after 2 agreeing sightings within 10 s;
  - its spot in view with no detection for 3 frames makes it `missing`.

## Measured (`check.py`, `sweep.py`, `restart.py`; real OwlDetector on rec1/rec2/rec3, the user's photos loaded the way the server does)
- **Order and count don't matter.** Each item's scores and boxes are identical whether it's registered alone, with the others, or in reverse order. The "other items" margin never blocked an item here.
- **The DINOv2 crop check is what rejects correct boxes.** Across 19 frames where the item's box was on the item:
  - 5 were accepted;
  - in 13 the DINOv2 similarity was 0.06–0.37, under the 0.38 threshold;
  - the OWLv2 photo + name score passed in 17.
  - The wallet was boxed correctly 3 times and never accepted. "Beyond the first one" is the small, flat, black items failing more often than the bottle.
  - The threshold was calibrated on ORBIT's handheld photos. The vest sees items from 1–2 m at an angle; the photos are close-up and top-down.
- **Threshold sweep** (all items together; 37 frames; a false alarm is "present" with the box elsewhere or the item out of view):

  | registration query | DINO ≥ 0.38 (today) | 0.33 | 0.30 | 0.25 | 0.20 |
  |---|---|---|---|---|---|
  | crop (first registration) | 5 hits, 1 FA | 8, 1 | 8, 1 | 11, 4 | 13, 9 |
  | whole photo (after a restart) | 9, 1 | 10, 1 | 10, 1 | 10, 4 | 13, 4 |
- **Restart inconsistency.** The first registration queries with the crop around the item. After a server restart, `_reload` re-registers with `gate=False`, which uses the whole saved photo. So detection changes after every redeploy.
  - Here the whole photo did better: 9 hits against 5. That's likely because the photos were taken on the same wooden tables as the venue (background match), so don't generalise it.
- **Moving items.** Two agreeing sightings within 10 s are needed to move an item. At 25–50 % per-frame recall that often doesn't happen, so the item stays at its old spot or goes missing. Better recall fixes this too.

## Recommendation (not applied yet; waiting on the user)
1. `TH_DINO` 0.38 → 0.30. On these clips, crop queries go from 5 to 8 hits with no extra false alarms. It's an env var, so it can be set on the box today in `/etc/marco/local.env`.
2. Make restarts register exactly like the first registration: re-crop with the name check, and fall back to the whole photo.
3. Next: registration photos from the vest's own angle, which the user suggested earlier.
4. Caveat: 3 clips, 10–14 s each. Re-run `eval_detection.py` on a longer walk with more clutter before settling on 0.25 or lower.

## 2026-10-18 later: "the brain can't find anything" (user, live test)
- **The full server path works on the recorded iPhone clips.**
  - Real mode, run locally on loopback, fed by `tools/live_check.py` the way the phone streams: frames over HTTP, poses over the socket, the three photos registered over HTTP.
  - All 14 frames were accepted, with no errors in the server log.
  - The bottle and the power bank were found and located; the wallet wasn't (`never_seen`).
  - The 140 unit tests pass. So it isn't a general code break; something about the live session (photos, frames, the box) differs.
- **float16 isn't it.** The A16 runs OWLv2 in float16 (`detector.py`), and every threshold was set in float32. On MPS in float16, scores moved by 0.05 on average, and 1 present/absent decision flipped out of 68 (`fp16.py`).
- **The one consistent failure is the DINOv2 crop check.** The new debug route showed it on the replay, e.g. "wallet: not present: DINOv2 crop similarity 0.37 < 0.38".
  - **Applied: `TH_DINO` 0.38 → 0.30.** Same clips: rec2 now finds all 3 items, the wallet included (1.9 cm placement error), and rec3 finds both.
  - **Rotation-tolerant matching** (`turns.py`, `MARCO_DINO_TURNS=4`) compares the crop against the registration crop at 4 quarter turns. It finds 7 of 18 at 0.38 and 10 at 0.33, but false alarms rise to 2–3. Opt-in only.
- **New for live debugging:** `GET /v1/debug/detection` and a per-frame log line (see `server/README.md`). For each item and recent frame they show the scores and whether it was placed, or which check failed.
  - Every live session is also recorded on the box under `MARCO_DATA/sessions/<session_id>/` and can be replayed here exactly.

## Live debug log, 2026-10-18 10:58 UTC (the box: CUDA float16, TH_DINO 0.30)
- **Setup:** 5 detector items (Pringles, Diet coke, Sparkling water, coffee ×2), all "reloaded after a restart", which means whole-photo references.
- **OWLv2 is finding things.** Photo + name scores were 5–9 on the boxes that look right (coffee 7–9, Diet coke 7–8, Pringles 3–5).
- **DINOv2 rejects nearly all of them,** at 0.0–0.25 where 0.30 is needed. One sighting passed (Diet coke, 0.303, placed 0.54 m away).
- **Cause:** a reference made from the whole photo describes the photo's background, not the item. Fix: re-crop phone photos on reload (brain._reload), the same as the first registration. This also fits "earlier we could tag things": before a restart, references were crops.
- **Look-alike cans:** Diet coke and Sparkling water fall on the same box. OWLv2's image query prefers Diet coke, while DINOv2 prefers Sparkling water (0.49 against 0.30), so the margin check hands it to Diet coke. Crop queries should separate them better; re-check after redeploy.
- **"coffee" is still registered twice** (identical scores). It's harmless since Utkarsh's twin fix, but one could be removed.

## Live false positives, 2026-10-18 (a clear plastic coffee mug detected as the registered black bottle)
- **Why it can get through (from the code; the live case itself is not replayed yet):**
  - The photo + name score adds the text score for "a photo of {name}", which every object of that kind shares.
  - DINOv2 similarity is weak evidence at these crop sizes: the clips' one false alarm, a look-alike black bottle, scored 0.59. Lowering `TH_DINO` from 0.38 to 0.30 raised hits from 5 to 8 with the same 1 false alarm on the clips.
  - Nothing looked at colour or size.
- **Added (`appearance_eval.py`, uncommitted):** a colour check. The detection crop's lightness and colourfulness (CIELAB L*, chroma, median of the middle 60 %) must be within 40 / 30 of the registration crop's.
  - On the venue clips it gives the same result as before (8 hits, 1 false alarm), with margin: the right item was at most 28.5 lightness and 19 colourfulness away.
  - By construction, a light or colourful object taken for a dark item fails it. Not yet measured on the live mug.
- **Tried and dropped:**
  - **Elongation check:** seen from the chest, a standing bottle looks squat, so the real bottle failed it.
  - **Top 3 boxes per item:** 9 hits but 3 false alarms, against 8 and 1.
  - **Descriptive names** (`names_eval.py`, `poc/reports/poc28_names.json`): "black metal water bottle", "black and blue power bank" and "black leather wallet" gave 8 hits / **3** false alarms against 8 / 1 with plain names. They don't help; keep short names. Calling is unaffected: the phone's matcher resolves "bottle" or "black bottle" to either name.
- **Still unsolved:** a true look-alike, such as another black bottle (the clips' one false alarm: same colour, DINOv2 0.59).

### Live log, per session (journalctl 10:54–13:17 UTC, `an/sessions.py`, `an/cooccur.py` in /tmp/poc27 on the Mac)
- **10:54–11:11 and 11:48–12:10 (cans, Pringles, coffee):** each item stayed in 2–5 half-metre spots. Clean.
- **12:51–13:17 (Bottle, Coffee, Pringles, Can of soda):**
  - Bottle placed 149 times at 59 different spots (14 + 45 across the two server sessions), heights −1.53 to 0.01 m, plus 66 "present" detections 7.6–8.3 m away (beyond the 4 m range, so ignored).
  - Coffee placed 390 times at 29 spots. Pringles stayed at 1–4 spots.
  - Bottle and Coffee were never placed on the same spot in the same frame (closest 0.16 m). But in 59 frames where Bottle was placed, Coffee was refused for "margin over the other items": another item outscored it on its own best box. That fits the mug being taken for the bottle; which item won isn't in the log.
  - Caveat: positions are per AR session; the phone restarting AR moves the origin, so spot counts over 23 minutes overstate the scatter.
- **To prove it:** replay that session's frames and the Bottle and Coffee registrations locally. They're on the box under /var/lib/marco/data; not copied (needs the user's OK).

## State at 2026-10-18 ~13:55 UTC (kept current for context compaction)
- **Pushed today:**
  - `5242509`: a hand held on the guided item is a touch.
  - `502a26e`: `POST /v1/reset`, and the server half of the preview relay.
  - Earlier: `174e78f`, `a064c72`, `6f88881`, `651edc7`.
  - The box runs `b11519b`, deployed by Sandeep. **`5242509` and `502a26e` are NOT deployed yet.**
- **Colour check: PUSHED as `6cd9dff` (13:35 UTC), not deployed.** I wrongly told the user it was local only; corrected at ~14:30.
  - Only measured on the venue clips: 37 frames, 3 dark items. Same 8 hits / 1 FA with or without it.
  - Unmeasured on cans, Pringles and clear items. A clear mug's colour is mostly what's behind it.
  - Off without a code change: `TH_LIGHT=inf TH_CHROMA=inf`. Recommended: deploy it off until the replay on the user's data shows it helps.
- **Measured and rejected:**
  - top 3 boxes: 9 hits / 3 FA;
  - elongation check: the real bottle fails it from the chest;
  - **descriptive names: 8 hits / 3 FA against 1 with plain names** (`names_eval.py`, `poc/reports/poc28_names.json`). So "register with a descriptive name" was a WRONG guess; the user needs that corrected.
- **Name matching (measured with the phone's real `ItemVocabulary`):** "bottle", "black bottle" and "water bottle" all resolve to "black metal water bottle". With two bottles registered, plain "bottle" is a tie and goes to the server as said.
- **Live log (read-only SSH, journalctl, 10:54–13:17 UTC, 1,814 frame lines; `/tmp/poc27/live_frames.log` on this Mac):**
  - "Bottle" was placed in 149 frames across 51 different 50 cm spots, 34 of them more than 2.5 m away, heights −1.53 to 0.01. These are scattered false positives.
  - Other items cluster in 2–17 spots: Coffee 390 frames / 17 spots, Fanta 71 / 3, Diet coke 51 / 6, Pringles 90 / 7.
  - Caveat: the coordinate frame changes between sessions (new map ids), so clusters across sessions mix.
- **SSH:** the user gave the root password in chat (don't write it anywhere; advise rotating it). The auto-mode classifier allowed `journalctl` reads and refused a broader command that read `registry/items.json` ("credential leakage"). Askpass helper `/tmp/poc27/askpass.sh` reads `$MARCO_SSH_PW`; ControlPath `/tmp/poc27/ssh-%r@%h`.
- **Running:** a background audit agent (read-only) for accuracy, false-positive and blocking bugs. When it reports, verify each finding against code and data, then confirm with the user before changing anything.
- **Next:**
  - verify the audit findings;
  - analyse the live log per session;
  - get the "Bottle" frames (the false positives) to replay here;
  - then decide the colour check;
  - the preview feature's phone and dashboard halves are still to do (server relay done).

## 2026-10-18 ~14:30: the user fetches data, I don't touch the server
- **The user said: "dont access the server, I will get you what you want".** SSH master closed. Don't SSH again; the classifier also refused it ("production reads").
- **Asked the user for:**
  - today's sessions (/var/lib/marco/data/sessions, frames since 10:50 UTC);
  - registry items.json, photos/ and templates/;
  - the original texted photos for removed items;
  - ground truth: where each item was, what moved, which item is the clear mug.
- **Morning jumps (`an/jumps.py`, `an/jumps2.py`: the logged placements through the real World.sighting):**
  - Typical placement within 4–13 cm of the item's usual spot, but 10–35 % of placements land 0.3–0.8 m off.
  - The dashboard dot moved 1–10 times per item in 15–20 min, by 0.3–1.0 m.
  - Only 5 of 49 jumps were shared by two items at once (a map shift). The rest flip back and forth within 1–2 s (Fanta: 13 jumps, 12:07–12:10), so they're not real moves.
  - So it's a wrong box or a wrong depth surface under the box (`locate_footprint` samples the surface just past the box's lowest edge). The frames will tell which.
