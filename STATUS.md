# Marco: project status (read this first)

Last updated: 2026-10-17. Keep this file current: update it whenever a decision is made or a piece lands.

**Hardware (final):** iPhone 16 Pro (LiDAR) in a chest vest, and AirPods Pro 3. Until the phone recordings exist, iPad LiDAR data (ARKitScenes) is used for checking.

## What this repo is
Marco is a wearable for blind and low-vision people. An iPhone in a chest vest (LiDAR + camera) and AirPods (spatial audio) work with a server that remembers where things are. It:
- answers "where are my keys?" with sound that comes from the item;
- tells your hand which identical jar it is touching;
- lets family label things over iMessage.

| Folder | What | Owner |
|---|---|---|
| `server/` | perception and world model (Python): ingest, recording, geometry, detection, world model, touch, API | Vedant |
| `ios/` | the iPhone app (Swift, Xcode): ARKit capture, uploads, WebSocket, spatial audio, voice | Utkarsh |
| `photon/` | the team's Photon bridge (TypeScript, **Photon 2.0**): caretaker labelling over iMessage, speaking `docs/INTERFACES.md` §5 | Utkarsh |
| `photon-scaffold/` | reference wiring for Photon that speaks `docs/INTERFACES.md` §5 exactly, tested against the server | Vedant (for Utkarsh to use or copy) |
| `frontend/` | the dashboard (React + Vite), with its backend contract in `frontend/docs/` | Sandeep |
| `docs/INTERFACES.md` | **the contract** between the three parts: message formats, coordinates, who sends what | everyone |
| `poc/` | research, emulators and the 26 POCs behind every decision (`poc/REPORT.md`, `poc/FEATURES.md`, `poc/REQUIREMENTS.md`) | reference |

## Decisions (and the evidence)
- **Models run on a server, not the phone.** OWLv2 image-guided search with **one registration photo**: 97% on blind users' own items (ORBIT, POC 22).
  - **Retake check:** OWLv2's score for the item's name in the photo, at least 0.05 (POC 25: kept photos 75.5%, rejected 20%).
- **Frames to the server at 1 per second.** 0.5 fps loses about a third of put-downs; 2–3 fps adds almost nothing (POC 11 sweep).
- **"Is my item in this frame?" needs a combined check.** Raw OWLv2 scores are about 0.99 even when the item is absent. The check is photo + name, a DINOv2 crop check, and "looks more like this item than my other items" (POC 25/26).
  - Move an item only after two agreeing sightings.
- **Geometry rules (POC 23; all unit-tested in `server/tests/test_geometry.py`):**
  - The phone sends the raw sensor-orientation image, no EXIF orientation tag.
  - The server turns it upright from gravity.
  - Boxes become 3D with the pose and depth *of their own frame*. The stale pose put items 50 cm to 2 m off.
- **Touch (POC 24 + `server/marco/touch.py`):**
  - **Identity:** the fingertip's 3D point from LiDAR, matched to the nearest stored item within 15 cm.
  - **Contact:** the live depth just past the fingertip continues the fingertip's depth, voted over 5 messages.
  - **Visible fingertip only:** a hidden fingertip never counts.
  - **2D box overlap is useless:** 100% false touches.
  - **Finding:** from the chest, the back of the hand hides the fingertip on low tables and when poking things straight ahead. **Demo touches go on counter-height lids.**
- **Head tracking:** ARKit torso + AirPods fusion (POC 4, ported to `ios/Marco/Core/Guidance.swift` `HeadFusion`); phone-only fallback ("turn your body").
- **Guidance sequence (POC 5; `docs/INTERFACES.md` §7):** spoken direction, then a beacon (muffled when behind you), a double ding when facing, faster beeps, a steady tone in the last 30 cm, silence and "Got it" at touch.
  - Spoken directions are relative to the body (chest); sound placement and the beacon phases are relative to the head.
- **Audio route:** AirPods stay in A2DP (stereo, so HRTF spatial audio works); the iPhone's own mic does speech. Bluetooth HFP would make the AirPods a mono headset.
- **Where it runs:** a teammate's Mac at the venue for the demo, and/or a Vultr GPU (sponsor prize).
  - **1 frame/s inference holds:** the full per-frame pipeline on this Apple Silicon Mac (MPS), on real iPad frames, takes 0.33 s with 1 item, 0.37 s with 10 and 0.42 s with 20 (p95 0.43 s). That is `tools/bench_frame.py`; run it on the venue machine too.
  - Slower frames are dropped (latest frame wins), never queued. Touch uses the 15/s hand stream and no model, so it is independent of this.
  - Everything is reached through **Tailscale**; the server binds 127.0.0.1 only, behind a fail-closed auth gate.
- **Wire details:**
  - depth and confidence may be zlib or raw DEFLATE (Apple's `.zlib` is raw DEFLATE; the server accepts both);
  - every phone message carries `session_id`, so the server files it into the same recording.
- **Repo hygiene:**
  - no references to other teams' projects;
  - no secrets;
  - large and third-party data stay out (`.gitignore`);
  - push only when the user says so.

## Built and verified
- **`server/`** (`cd server && ../poc/.venv/bin/python -m pytest -q tests`):
  - geometry, wire codecs, recorder, session reader, world model, room map, touch detector;
  - stub brain (fake perception, real geometry; answers `find`, `what_is_this`, `set_place`) and real brain;
  - OWLv2 + DINOv2 detector, plus a ground-truth detector for synthetic sessions;
  - the FastAPI app (all routes and WebSockets of `INTERFACES.md`), with the fail-closed auth gate and Tailscale allow-list mode.
- **Sample sessions (`server/tools/`):**
  - `fake_session.py`: a synthetic session from the ARKit/LiDAR emulator (38 frames, poses, a rendered hand touching a jar).
  - `fetch_arkitscenes.py` + `arkitscenes_session.py --root`: real iPad LiDAR, video and ARKit poses (ARKitScenes, about 50 MB from Apple, kept out of git). The pose conversion is verified by cross-frame LiDAR overlap.
  - `stray_session.py`: real **iPhone** recordings from the free Stray Scanner app (LiDAR, video and ARKit poses). It picks the pose axis convention by LiDAR overlap; tested on a synthetic export in both conventions.
- **Tools:**
  - `run_offline.py`: runs the real brain on any session; writes `report.json` (with per-frame timing), `frames.jpg` and `map.png`.
  - `bench_frame.py`: per-frame time for 1–20 registered items, against the 1 s budget.
  - `replay.py`: streams a session into a running server, as if the phone were live (for the dashboard and Photon).
  - `check_recording.py`: validates a phone recording against the contract.
  - **Real-video testing ([docs/TESTING.md](docs/TESTING.md)):**
    - `inspect_session.py`: blur, LiDAR coverage, and frame-to-frame pose and depth consistency (real ARKit 1.5 cm; above 8 cm means something is wrong), with a picture of the depth over the image;
    - `label_truth.py`: one click per item, made into 3D truth with LiDAR;
    - `eval_detection.py`: per-item hits, misses, false alarms per minute, passes caught, placement error, time per frame, a threshold sweep and `sheet.jpg`.
- **Results so far:**
  - **Synthetic:** 6 items placed within 0.7–5.6 cm of ground truth; the jar touch detected 67 ms after contact; no false events.
  - **Real iPad data, real OWLv2:**
    - the oven was found only in the 2 frames where it is in view, and placed 11 cm from truth;
    - the table was rejected by the DINOv2 check (large objects);
    - thresholds must be refit on the real demo props.
  - **1 frame/s:** the full pipeline takes 0.33 s per frame with 1 item and 0.42 s with 20 (p95 0.43 s), on MPS on this Mac.
  - **Real iPad video scored with `eval_detection.py`:**
    - the oven was hit in 2 of its 2 visible frames, 11 cm from the truth;
    - with "table" registered, three other tables and a chair were false alarms, which moved the stored table 3.2 m. That's the look-alike problem: thresholds need tuning on our props.
- **`ios/` (Swift, for Utkarsh):** the full app scaffold:
  - ARKit + LiDAR capture, with ARWorldMap save and relocalize;
  - frame upload (latest wins), pose and hand streams, and the WebSocket;
  - Vision hand pose with depth patches;
  - HRTF spatial audio and the §7 guidance loop;
  - AirPods head fusion;
  - "Marco" wake word and push-to-talk;
  - labels primed from `GET /v1/items`, with audio cached;
  - a debug screen.

  Verification:
  - `sh ios/check.sh` type-checks every file that builds on macOS and runs 102 Swift unit tests.
  - `server/tests/test_ios_contract.py` builds the Swift core and feeds the exact bytes it sends to the server: the frame multipart, the poses, the hand patches (byte-exact against the server's reference) and the queries. It also checks the geometry angle for angle against `marco/geometry.py`.
  - **Not compiled here:** the ARKit/UIKit glue (`App/`, `Capture/ARSessionManager.swift`), because this Mac has no iOS SDK. Build it in Xcode first.
  - Setup: `ios/README.md`; project generation: `ios/project.yml` (XcodeGen).
- **`photon-scaffold/` (JavaScript ESM with JSDoc types, reference for Utkarsh):** an iMessage caretaker bridge on `@photon-ai/imessage-kit` 3.x that speaks §5 exactly. Utkarsh's `photon/` is the team's bridge; this one shows the server wiring.
  - It handles label requests, text replies (name plus spoken words), voice notes before or after the name, setup photos with or without a caption, a caretaker allow-list, and expiry.
  - Plain JS because this Mac's npm registry needs a login. It runs with no build step, and its tests need no install.
  - Verification:
    - `npm test` runs 8 tests;
    - `server/tests/test_photon_contract.py` runs its HTTP client against a live loopback server: crop, label, voice note and registration, then `label_ready` with playable audio.
- **Docs:**
  - `docs/INTERFACES.md` v0.2 (+ `.docx`), with a changelog in §11;
  - top-level `README.md`, `server/README.md`, `server/requirements.txt`;
  - `.gitignore` covers recordings, datasets, build output and `node_modules`.
- **`photon/` (Utkarsh, TypeScript): the team's caretaker bridge, on Photon 2.0, speaking §5 exactly** (2026-10-17).
  - **iMessage:** the official Photon 2.0 client (`@photon-ai/api` 0.5.0) for sends and attachments, and the project's Socket.IO event stream with a saved cursor. The LA Hacks track requires Photon 2.0, so Spectrum was removed.
  - **Server side (§5):** it listens on `/v1/photon` for `label_request`, fetches the crop, texts it to the caretaker and posts the answer to `POST /v1/labels` (`touch_id` first, then `item_id`). A voice memo sent after a typed name is added to that `item_id`. Setup photos go to `POST /v1/items` as JPEG (HEIC converted). Voice memos are sent as m4a (CAF converted), which the phone and the dashboard can both play.
  - **Resilience:** at-least-once handling, with stable ids and idempotency keys, so a replayed event never double-posts or double-texts. If the server has forgotten a touch (a `404` after a restart), the item is registered from its crop, then labelled.
  - **Status port:** 127.0.0.1 only (`/health`, plus `/dev/*` in sim mode). The phone never talks to `photon/`.
  - **Checks:** `npm run doctor` checks the Photon 2.0 key, line and event stream, plus `MARCO_SERVER_URL` (`GET /v1/items`, the `/v1/photon` socket and the allow-list), read-only.
  - **Verification:** `cd photon && npm test` runs 39 tests. One of them is end to end against the real `server/` (stub, loopback): `what_is_this` → `label_request` → iMessage → text then voice memo → `label_ready` with m4a audio → `what_is_this` known → setup photo → `GET /v1/items`. It runs when `server/.venv` (or `MARCO_SERVER_PYTHON`) has the stub dependencies.
- **Totals (all passing):** server 74 tests (including both client contract tests and the real-video tools), Swift 102, Photon scaffold 8, `photon/` 39.
  - `photon-scaffold`'s `npm test` script (`node --test test/`) fails to start on Node 22.21, which treats the directory as a module. `node --test test/*.test.js` runs all 8.
- **Teammates' code on `main`:** `frontend/` (Sandeep, the dashboard) was built against the earlier requirements, not this contract. See the next steps.
- **Security sweep:**
  - no wildcard binds, tunnels or tokens in the repo;
  - POC 26's server now refuses non-loopback binds too.
  - The GitHub token from the first push sits in `.git/credentials`: never committed, and it goes when the folder is deleted. Revoke it after the hackathon.

## In progress / next
1. **Reconcile the routes** (`docs/INTERFACES.md` §10) with Sandeep:
   - **Photon: done.** `photon/` adopted §5 unchanged; no server change was needed.
   - **Dashboard:** `frontend/` expects `GET /dashboard/snapshot`, `WS /events` and `POST /dashboard/commands` (`frontend/docs/fastapi-handoff.md`). Likely a server adapter, plus a phone message for dashboard Find/Stop.
2. **Security fix for `photon/`: applied.** Its HTTP port binds 127.0.0.1 and serves only `/health` (and `/dev/*` in sim mode). The phone-facing routes and `BRIDGE_TOKEN` are gone; caretaker media is never served.
3. **Utkarsh:**
   - build `ios/` in Xcode;
   - run the hour-one tests in `ios/README.md`;
   - point `photon/` at the server: set `MARCO_SERVER_URL` to its tailscale serve URL, add the bridge machine's login to `TAILSCALE_ALLOWED_LOGINS`, then `npm run doctor`. Photon 2.0 itself is live and was tested.
4. **Vedant:** the real-video test in `docs/TESTING.md`.
   - Record recordings A–D with Stray Scanner, plus one registration photo per prop.
   - Inspect each recording, label it, and score it.
   - Tune `TH_*` on one recording and confirm on another; refit the touch `CONTACT_M`.
   - Re-run `bench_frame.py` on the venue machine.
5. **Dashboard:** live data through the adapter (step 1); until then, the stub plus `tools/replay.py` give real feeds on `/v1/dashboard`.
6. **Caretaker voice notes:** `photon/` already sends them as m4a. Server-side conversion is only needed for other clients that post `.caf`.
   - **Possible §5 additions (proposals, not built):** `label_request_seen` (the caretaker opened the photo: "Mom is looking at it") and `label_unknown` ("Mom isn't sure either"). `photon/` already detects both and only logs them.
   - **Today the server doesn't queue `label_request`** for a disconnected bridge. `photon/` reconnects with backoff and shows the socket state on `/health`.

## Open questions / hour-one tests (need the real phone)
- **Xcode build** of `App/` and `ARSessionManager.swift`: the first compile of the ARKit glue.
- **Relocalization** after an app relaunch: time and anchor error.
- **AirPods motion:** rate, drift, latency, and the yaw sign (there's a toggle on the debug screen).
- **Vision fingertip confidence** when the fingertip is hidden (on low tables and behind objects).
- **Thresholds on the real props and room:** presence, and touch `CONTACT_M`.
- **Vision orientation** `.up` versus `.right` for the hand pose.
- **Caretaker voice notes** (`.caf`) playing on the phone through `AVAudioFile`.
- **Remote teammate eligibility** for prizes. Ask the organisers.
