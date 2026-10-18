# POC 29: general false alarms, on footage nothing was tuned on (2026-10-18)

The question: why does Marco take other objects for registered items, in general and not for one item? Nothing here is tuned to the live frames.

**Method:**
- The deployed detector code (`OwlDetector`, thresholds as deployed), opened up so that each variant comes from the same OWLv2 pass (`general.py`).
- **ORBIT:** 18 items of 5 blind users, 156 cluttered frames.
  - Each user registers only their own items, as at home.
  - Positives: the item's own frames, with the box on the human-drawn box.
  - Negatives: other users' frames, where the item can't be. They split into look-alikes (someone else's keys) and other objects.
- **Venue clips:** our 3 chest-camera recordings (37 frames).
- **The one fitted number** is the square-crop DINOv2 threshold. It was chosen on ORBIT, then carried unchanged to the venue clips (`analyze.py`).
- **Check that the probe matches the server:** on the venue clips it reproduces POC 28 exactly: 8 hits and 1 false alarm deployed, 5 and 1 at `TH_DINO` 0.38.
- **Reports:** `poc/reports/poc29_false_alarms.json`. The raw rows (`poc29_rows.json`, 2 MB, not committed) come from `general.py`, about 2 minutes on the Mac.

## What we were missing
1. **POC 26's false-alarm numbers don't apply to a home.**
   - POC 26 registered all 18 ORBIT items in one server. The real owner of every look-alike was registered too, and won the "looks more like my other items" margin.
   - Rebuilt here: with all 18 registered, `TH_DINO` 0.38 gives 47 % caught and 2.5 % false alarms (POC 26 reported 51 % and about 1 %, fitted and scored on the same frames).
   - With each user's own items only, the same thresholds give **7.2 % false alarms** (look-alikes 22 %, other objects 4.9 %).
   - At 1 frame/s with 4 items, that is not 0.5 false alarms a minute but about 17.
2. **`TH_DINO` 0.30 (my POC 28 change, from the 37 venue frames) doubles false alarms on held-out footage.**
   - Recall rises from 64 % to 80 %, but false alarms go from 7.2 % to **13.9 %** (look-alikes 38 %).
   - On the venue clips it showed no extra false alarm because they hold almost no look-alikes.
3. **Two sightings help less than hoped.** A false alarm repeats on the same object.
   - Both of two frames of one scene pass 7.8 % of the time, against 13.9 % for one frame.
   - On the live log, requiring two agreeing sightings before the first placement would have removed 1 of the Bottle's 8 dashboard spots and 1 of Coffee's 33 dot moves (`/tmp/poc27/an/two_sightings.py`). The wrong sightings agree with each other.

## What helps, measured
- **DINOv2 on the whole object (pad the crop to a square before DINOv2's resize and 224 centre crop):** the stock preprocessing compares only the middle of a tall or wide box.
  - AUC: ORBIT 0.886 → **0.949** (look-alikes 0.806 → 0.842); venue 0.867 → 0.886.
  - **False alarms at the same recall (ORBIT):**
    - at 80 % caught: 14.1 % → **8.6 %** (threshold 0.377);
    - at 64 % caught: 7.5 % → **3.4 %** (threshold 0.469).
  - **The 0.377 threshold carried to the venue clips, unchanged:** 9 hits and 1 false alarm, against 8 and 1 deployed. No worse anywhere.

## What doesn't help (or barely), measured
- **Colour check (in main as `6cd9dff`, not deployed):**
  - ORBIT: 80 % → **75 % caught**, false alarms 13.9 % → 12.3 %.
  - At the same 75 % recall, raising `TH_DINO` to 0.314 instead gives 12.6 % (measured; an earlier interpolated 11.8 % was wrong). So the check is a finds-for-false-alarms dial, like the threshold, adding almost nothing the threshold can't.
  - Venue: no change. It's also the check most exposed to lighting (night against day). **Turn it off.**
- **Choosing the box by image + name (audit finding 8):**
  - ORBIT false alarms 13.9 % → 15.8 % at the same recall; venue 1 → 4 false alarms.
  - POC 22 found the same (look-alike task: photo 58 %, photo + name 53 %). Keep the image query.

## Caveats
- ORBIT frames are 224 px handheld close-ups and our frames are 960 px from the chest, so the absolute rates differ. The comparisons between variants held on both sets.
- The venue clips are 37 frames at one table: a sanity check, not proof.
- The live sessions (night, 4 items) are the real test: score them with these settings fixed, never tune on them.

## State (2026-10-18 ~15:00 UTC)
- **Pushed `c7b5042`:** `server/tools/investigate_live.py` plus its test (223 server tests pass), POC 29, and the POC 28 names eval.
- **The user's friend runs the investigation on the box** (steps in server/README.md) and sends back /tmp/marco-investigation.zip. I don't access the server.
- **The colour check is off by default** (the user said "turn it off by default and push"): `TH_LIGHT`/`TH_CHROMA` default `inf`.
- **Waiting for the user to decide:**
  1. (done: colour check off)
  2. the DINOv2 square crop at `TH_DINO` 0.377 (chosen on ORBIT; to be scored, not tuned, on the live sessions);
  3. the absence and touch fixes (audit findings 1–3).
