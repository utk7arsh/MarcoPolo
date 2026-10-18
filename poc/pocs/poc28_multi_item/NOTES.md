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
