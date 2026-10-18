# Testing Marco on real video

How to tell whether the camera, LiDAR and poses are right, and whether detection finds our items, on real recordings from the iPhone 16 Pro. Every command runs from `server/`.

## 1. Record (about 15 minutes, no app needed yet)
Use the free **Stray Scanner** app on the iPhone 16 Pro. It records the video, the LiDAR depth and the ARKit poses, which is the same data our app will send.

1. **Props:**
   - the demo items: keys, wallet, mug, a bottle;
   - two or three identical spice jars with different contents.

   Put them where they'll be in the demo (jar lids at counter height, for touch).
2. **Registration photos:** one ordinary photo per item with the Camera app, as a user would take it, with the item filling about a third of the frame.
   - The server reads JPEG, not HEIC: set Camera > Formats > Most Compatible, or convert with `sips -s format jpeg in.heic --out out.jpg`.
3. **Recording A, "find" (2–3 min):**
   - the phone at chest height, portrait (in the vest if you can);
   - walk slowly through the room, passing each item at 1–3 m;
   - turn around and walk back;
   - include stretches with no items in view.
4. **Recording B, "look-alikes" (1–2 min):** the identical jars side by side, plus similar objects (two mugs, two bottles).
5. **Recording C, "moved" (2 min):** walk, pick up the keys, put them somewhere else, keep walking. This tests the moved, picked up and put down events.
6. **Recording D, "hard":** dim light, and items 3–4 m away.

Export each recording from Stray Scanner to the Mac (AirDrop or Files). The folder holds `rgb.mp4`, `depth/`, `confidence/` and `odometry.csv`.

## 2. Is the recording itself good?
```
python tools/stray_session.py <export folder> --out data/sessions/kitchen-a
python tools/check_recording.py data/sessions/kitchen-a       # the format, against the contract
python tools/inspect_session.py data/sessions/kitchen-a       # blur, LiDAR coverage, pose consistency
```
Open `data/sessions/kitchen-a/inspect/inspect.jpg`. The depth colours (near red, far blue) must sit on the objects; shifted or mirrored colours mean the image and depth don't line up.

**Consistency** checks that the poses, depth and intrinsics agree: each frame's LiDAR points are moved into the next frame and compared with what that frame sees.
- Real ARKit data agrees to about 1.5 cm.
- Above 8 cm, something is wrong: a pose convention, row-major matrices, or intrinsics for another resolution.

## 3. Ground truth (2 minutes per recording)
```
python tools/label_truth.py data/sessions/kitchen-a
```
1. Step through the frames with `n` and `p`.
2. Click the **middle of each item** in a frame where it's 1–2 m away with nothing in front of it.
3. Type its name, the same name as its registration photo.

LiDAR turns each click into the item's 3D position. Projecting that point into every frame, with an occlusion check, says when each item should be seen. Items must stay put during the recording: for recording C, label only the items that don't move.

## 4. Score detection
```
python tools/eval_detection.py data/sessions/kitchen-a --register keys=photos/keys.jpg wallet=photos/wallet.jpg mug=photos/mug.jpg
```
It writes two files under `data/sessions/kitchen-a/eval/`:
- **`sheet.jpg`:** green = hit; red = a miss or a false alarm; grey = don't care (at the image edge, beyond 4 m, or partly hidden).
- **`report.json`:** per item, how often it was found, the false alarms, the placement error and the time per frame.

**What "working" means for the demo:**

| Measure | Target | Why |
|---|---|---|
| passes caught: the item was in view within 3 m, and was found at least once | 90% or more | "where are my keys?" needs one good sighting per pass |
| false alarms | at most 0.5 per minute | two agreeing false alarms move an item |
| placement error of hits (horizontal) | 15 cm or less | the beacon and the hand guidance aim at it |
| time per frame, p95 | under 1 s | 1 frame per second |

Frame recall (the share of individual frames with a hit) is reported too. It can be well below 100% while every pass is caught.

## 5. Tune, then confirm
- If recall is low or false alarms are high, the report's `operating_points` give the best thresholds from that recording, within 0.5, 1 and 2 false alarms per minute.
- Set them with `TH_PHOTO_NAME`, `TH_DINO` and `TH_VS_OTHERS`.
- **Confirm on a different recording:** thresholds tuned and scored on the same video look better than they are.
- Retake the registration photos that the retake check rejects.

## 6. The whole pipeline on a recording
```
python tools/run_offline.py data/sessions/kitchen-a --detector owl --register keys=photos/keys.jpg ...
python tools/replay.py data/sessions/kitchen-a --server http://127.0.0.1:8000      # the dashboard, as if live
python tools/bench_frame.py data/sessions/kitchen-a --items 1 10 20                # the 1 frame/s budget on this machine
```
`run_offline.py` reports events (seen, moved, picked up, put down), answers and touches, and draws `frames.jpg` and `map.png`.

## 7. With our app
The server records everything the phone sends under `data/sessions/<session_id>/`, so steps 2–6 work the same on a live session. For touch, record touches on the counter-height jar lids; `run_offline.py` lists the detected touches with their times.

## What we already know
- **Synthetic room:**
  - items placed within 0.7–5.6 cm;
  - the jar touch detected 67 ms after contact;
  - no false events.
- **Real iPad video (ARKitScenes, real OWLv2):**
  - the oven was found in both frames where it is in view, and placed 11 cm from the truth;
  - with "table" registered, three other tables and a chair came up as false alarms, and moved the stored table 3.2 m. That's the look-alike problem; the thresholds need tuning on our own props.
- **Blind users' own videos (ORBIT, POC 25/26):** the presence check catches the item in about half of the individual frames where it is present (50.6%), with 1–4% false alarms per frame. That is why per-pass recall is the measure that matters.
