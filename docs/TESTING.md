# Testing Marco on real video

How to tell whether the camera, LiDAR and poses are right, and whether detection finds our items, on real recordings from the iPhone 16 Pro. Every command runs from `server/`.

## 1. Record (about 15 minutes, no app needed yet)
Use the free **Stray Scanner** app on the iPhone 16 Pro. It records the video, the LiDAR depth and the ARKit poses, which is the same data our app will send.

1. **Props:**
   - the demo items: keys, wallet, mug, a bottle;
   - two or three identical spice jars with different contents.

   Put them where they'll be in the demo (jar lids at counter height, for touch).
2. **Registration, from the vest's view.** Register the way the product will: with the phone in the harness, about 1 m from the item, at the angle the vest sees it.
   - Record a few seconds per item with Stray Scanner, and use a frame of that clip: `eval_detection.py --register-frame "wallet=data/sessions/reg-place-a:3:1005,1065"` (frame 3, sensor pixel on the item).
   - Photos from the Camera app also work (`--register`). On the first recordings, top-down close-ups matched video crops badly. The server reads JPEG, not HEIC: set Camera > Formats > Most Compatible.
   - **Register in a different place from the tests:** a different table or room, other light, another time. Registering and testing at the same table makes the item look the same in both (same light, angle and background), and the score comes out higher than it will be in the demo.
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

## 5. Tune, then confirm (never on the video you score)
- If recall is low or false alarms are high, the report's `operating_points` give the best thresholds from that recording, within 0.5, 1 and 2 false alarms per minute.
- Set them with `TH_PHOTO_NAME`, `TH_DINO` and `TH_VS_OTHERS`.
- **Confirm on a recording from a different place:** thresholds tuned and scored on the same video, or the same table, look better than they are.
- Nothing in the code is tuned to a particular recording. Only `TH_*` changes, and only after it holds on held-out places.
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

## First iPhone 16 Pro recordings (2026-10-17, three clips, 34 s, all at one venue)
- **The recordings are good:**
  - frame-to-frame agreement of 1.5–2.4 cm;
  - depth lines up with the image;
  - Stray Scanner's OpenCV pose convention was detected automatically.
- **When found, items are placed 1.7–6.7 cm from the truth.** Every frame takes 0.37–0.40 s.
- **Recall with top-down photos is low:** 4 of 9 passes, and the wallet never. Most misses had the right box, rejected by the DINOv2 crop check: sharp top-down photos don't resemble blurred, angled video crops.
- **Registering from a vest-camera frame** of another clip caught 7 of 10 passes (the wallet 5 of 6 frames), with more false alarms. Those clips were taken at the same table minutes apart, so this is an upper bound. The test across places above decides it.
- **False alarms are real look-alikes:**
  - the iPhone, taken for the power bank;
  - other people's black bottles, one 3.5 m away.
- **Fixed after these recordings:**
  - surfaces are named from the floor seen in the LiDAR map (ARKit's origin is where the phone started);
  - sightings beyond 4 m don't place items;
  - large photos are shrunk, with their EXIF rotation applied.

## What we already know
- **Synthetic room:**
  - items placed within 0.7–5.6 cm;
  - the jar touch detected 67 ms after contact;
  - no false events.
- **Real iPad video (ARKitScenes, real OWLv2):**
  - the oven was found in both frames where it is in view, and placed 11 cm from the truth;
  - with "table" registered, three other tables and a chair came up as false alarms, and moved the stored table 3.2 m. That's the look-alike problem; the thresholds need tuning on our own props.
- **Blind users' own videos (ORBIT, POC 25/26):** the presence check catches the item in about half of the individual frames where it is present (50.6%), with 1–4% false alarms per frame. That is why per-pass recall is the measure that matters.
