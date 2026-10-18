# Marco: project status (read this first)

Last updated: 2026-10-17. Keep this file current: update it whenever a decision is made or a piece lands.

**Primary roadmap:** the user's approved whole-system diagram is recorded in
[`docs/HACKATHON-ROADMAP.md`](docs/HACKATHON-ROADMAP.md). Read it and `AGENTS.md`
before future edits; this status file records implementation evidence and remaining gaps.

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
  - **Vultr (`deploy/vultr/`):** the A16 16 GB in `sjc` ($0.47/h) is live. The only plan deployable in `lax` was the A40 48 GB at $1.71/h. Billing stops only when the box is destroyed.
- **Wire details:**
  - depth and confidence may be zlib or raw DEFLATE (Apple's `.zlib` is raw DEFLATE; the server accepts both);
  - every phone message carries `session_id`, so the server files it into the same recording.
- **Repo hygiene:**
  - no references to other teams' projects;
  - no secrets;
  - large and third-party data stay out (`.gitignore`);
  - push only when the user says so.

## Where it runs and who can get in (2026-10-17)
- **Vultr GPU box `marco-gpu`** (NVIDIA A16, 16 GB), deployed by Utkarsh:
  - `marco.service` runs under its own `marco` user from `/opt/marco/server`, with `MARCO_MODE=real` and the hardened systemd settings in `/opt/marco/deploy/`;
  - `/opt/marco/deploy/remote-setup.sh` re-runs after each code sync; his `marco-vultr.sh deploy` does both.
- **URL:** `https://marco-gpu.taild6d426.ts.net`, through `tailscale serve`, tailnet only. The bare URL answers with a status; the API is `/v1/...`.
- **Login is Tailscale itself:**
  1. A device must be signed in to Utkarsh's tailnet even to reach the URL.
  2. `tailscale serve` adds that user's login, and the server admits only `TAILSCALE_ALLOWED_LOGINS` (now `utk7arsh@github`).
  3. Everyone else gets 403 (WebSocket close 1008).
- **From the internet:** ports 80, 443 and 8000 are closed (probed 2026-10-17). The app listens on 127.0.0.1, and ufw allows only SSH.
- **Remaining risk:** root SSH with a password. Anyone with SSH can call 127.0.0.1:8000 directly. Change the password (it was shared in chat) and switch to keys only.
- **To add a teammate:** invite them to the tailnet, add their login to `ALLOWED`, and redeploy.

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
  - **First iPhone 16 Pro recordings** (3 clips, 34 s, one venue; details in `docs/TESTING.md`):
    - good capture: 1.5–2.4 cm agreement between frames;
    - placement 1.7–6.7 cm when found;
    - 0.37–0.40 s per frame;
    - recall with top-down photos only 4 of 9 passes (the wallet never), because the DINOv2 check rejects blurred, angled crops;
    - registering from a vest frame caught 7 of 10, but the clips share a table, so that's an upper bound.
    - False alarms are look-alikes: the iPhone taken for the power bank, other black bottles.
    - Fixed: floor-relative surface names, a 4 m range gate, large-photo handling.
    - Next: register at place A, test at place B.
  - **Bigger models** (same recordings, photo registration; `MARCO_OWL_MODEL` / `MARCO_DINO_MODEL` pick them):
    - **DINOv2 base or large:** no better separation than small (AUC 0.87–0.90 against 0.895), and +30 ms or +130 ms per frame.
    - **OWLv2-large:** boxes land on the item more often (17 of 20 visible frames against 15), and it catches 67% of passes with zero false alarms. But it needs 1.8 s per frame on this M3 Pro (1.3 s in half precision), so it's too slow for 1 frame/s here. Try it on a CUDA GPU (the Vultr box) with `bench_frame.py`.
    - **Half precision on the Mac** speeds up OWLv2-base from 363 to 235 ms per image pass (not yet switched on).
    - **On the team's Vultr GPU (NVIDIA A16, 16 GB, CUDA 13; `tools/gpu_check.py`, then `bench_frame.py`)**, full pipeline in half precision:
      - **OWLv2-base:** 0.20 s per frame with 3 items, 0.27 s with 10 and 0.38 s with 20 (p95 0.47 s). Comfortable at 1 frame/s.
      - **OWLv2-large:** 0.74 s with 3 items, 0.84 s with 10 (p95 1.08 s) and 0.98 s with 20 (p95 1.40 s). Only a few items fit, with no room for the upload.
      - The per-item cost is mostly DINOv2 preprocessing on the CPU; moving it to the GPU would help large.
      - Memory peaks at 1 GB.
      - Setup on the box: `~/marco-bench`, a venv with pip run from `pip.pyz` (no system packages), and models in `~/.cache/huggingface`. Nothing listens on any port.
    - All of this is from 34 s of video at one venue: suggestive, not settled.
  - **Live path tested:** recording 2, streamed into the real server on loopback at real-time pace.
    - The server kept up, announced "seen" events, and answered "where's my bottle?" with "on the table", 1.7 cm from the truth.
    - It recorded the stream as a session.
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
  - the Paper V3 control panel, with the original diagnostics available in Debug builds.

  Verification:
  - `sh ios/check.sh` type-checks every file that builds on macOS and runs 204 Swift checks (102 original, 24 control-panel, 44 accessibility and 34 audit regression checks).
  - `server/tests/test_ios_contract.py` builds the Swift core and feeds the exact bytes it sends to the server: the frame multipart, the poses, the hand patches (byte-exact against the server's reference) and the queries. It also checks the geometry angle for angle against `marco/geometry.py`.
  - **Xcode compiled:** the complete app, including ARKit/UIKit glue, builds for an iOS device (Debug and Release) and Simulator (Debug). Device/runtime checks remain; see `ios/VERIFICATION.md`.
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
- **Verification totals:** server 79 passed on Vedant's Mac (with the ARKitScenes sample; 76 + 1 skipped where it's absent), Swift 204, Photon scaffold 8; `photon/` 39 (Utkarsh's run).
  - `photon-scaffold`'s `npm test` now runs `node --test test/*.test.js`, which works on Node 22 (thanks, Utkarsh).
- **Teammates' code on `main`:** `frontend/` (Sandeep, the dashboard) was built against the earlier requirements, not this contract. See the next steps.
- **`deploy/vultr/` (Utkarsh): the Vultr GPU deployment kit.**
  - `marco-vultr.sh` has `plans`, `up`, `deploy`, `status`, `logs`, `bench`, `ssh` and `down`.
  - The box has no inbound ports. It joins the tailnet at first boot (cloud-init) and is reached by Tailscale SSH.
  - The server runs as a hardened systemd unit with `MARCO_MODE=real` and `MARCO_AUTH=tailscale`. `tailscale serve` publishes it only after the gate is checked to return 403.
  - PyTorch is a CUDA build matched to the driver.
  - **Live since 2026-10-18:** `marco-gpu` (A16 16 GB, `sjc`, driver 580 / CUDA 13.0, torch `cu130`) at `https://marco-gpu.taild6d426.ts.net`, with `TAILSCALE_ALLOWED_LOGINS=utk7arsh@github`.
    - **Checked with `status`:** an unauthenticated local call gets 403; an allowed tailnet call gets 200.
    - **`bench` on the box (full per-frame pipeline):**

      | Items | Mean | p95 |
      |---|---|---|
      | 1 | 0.18 s | 0.19 s |
      | 10 | 0.28 s | 0.32 s |
      | 20 | 0.40 s | 0.49 s |

      That is about 2x faster than this Mac.
  - **Fixed on the way:** a YAML quoting bug in `cloud-init.yaml` kept the first box from installing Tailscale. That box was finished by hand from the Vultr console. The check now asserts that every `runcmd` entry is a string.
- **`server/requirements.txt` gains `scipy`.** A fresh install (what Vultr runs) couldn't load the detector without it: transformers 5's default OWLv2 image processor needs it.
  - With it, a clean venv from `requirements.txt` runs `bench_frame.py` with real OWLv2 on MPS: 0.41 s/frame with 1 item, 0.56 s with 10.
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
   - run the compiled `ios/` app on the actual iPhone;
   - run the hour-one tests in `ios/README.md`;
   - point `photon/` at the server: set `MARCO_SERVER_URL` to its tailscale serve URL, add the bridge machine's login to `TAILSCALE_ALLOWED_LOGINS`, then `npm run doctor`. Photon 2.0 itself is live and was tested.
4. **Vedant:** the real-video test in `docs/TESTING.md`.
   - Record recordings A–D with Stray Scanner, plus one registration photo per prop.
   - Inspect each recording, label it, and score it.
   - Tune `TH_*` on one recording and confirm on another; refit the touch `CONTACT_M`.
   - Re-run `bench_frame.py` on the venue machine.
5. **Dashboard:** live data through the adapter (step 1); until then, the stub plus `tools/replay.py` give real feeds on `/v1/dashboard`.
6. **Proposed, waiting for a go-ahead:**
   - two agreeing sightings before an item's first placement, so one false-alarm frame can't place it;
   - "Marco, remember this as my wallet": registration from the vest camera's live frame (server, contract and app);
   - OWLv2-large on a CUDA GPU (Vultr);
   - half precision on the Mac.
7. **Caretaker voice notes:** `photon/` already sends them as m4a. Server-side conversion is only needed for other clients that post `.caf`.
   - **Possible §5 additions (proposals, not built):** `label_request_seen` (the caretaker opened the photo: "Mom is looking at it") and `label_unknown` ("Mom isn't sure either"). `photon/` already detects both and only logs them.
   - **Today the server doesn't queue `label_request`** for a disconnected bridge. `photon/` reconnects with backoff and shows the socket state on `/health`.

8. **Vultr (Utkarsh): the box is up** (see "Built and verified"). Left to do:
   - point the phone's Server field and `photon/`'s `MARCO_SERVER_URL` at `https://marco-gpu.taild6d426.ts.net`;
   - invite teammates to the `utk7arsh` tailnet, add their logins to `TAILSCALE_ALLOWED_LOGINS`, and re-run `deploy`;
   - measure the phone-to-Vultr round trip on venue Wi-Fi (`tailscale ping marco-gpu`);
   - try OWLv2-large on it with `bench_frame.py` (step 6).

   It bills $0.47/h until `marco-vultr.sh down`; stopping it doesn't stop billing.

## Open questions / hour-one tests (need the real phone)
- **iPhone runtime checks** of the compiled ARKit/UIKit app; no installed simulator runtime is available on this Mac yet.
- **Relocalization** after an app relaunch: time and anchor error.
- **AirPods motion:** rate, drift, latency, and the yaw sign (there's a toggle on the debug screen).
- **Vision fingertip confidence** when the fingertip is hidden (on low tables and behind objects).
- **Thresholds on the real props and room:** presence, and touch `CONTACT_M`.
- **Vision orientation** `.up` versus `.right` for the hand pose.
- **Caretaker voice notes** (`.caf`) playing on the phone through `AVAudioFile`.
- **Remote teammate eligibility** for prizes. Ask the organisers.

## Frontend and iOS V3 integration (October 17, 2026)

- Pulled main through `755ee6b` before implementation. The uncommitted standalone iOS panel was backed up and its design/project assets reconciled into the canonical `ios/Marco/` app. There is one compiled sensor pipeline and one app entry point.
- Implemented approved Paper V3 in React and native SwiftUI: bundled Instrument Sans, shared palette, open status/guidance layouts, underlined web navigation, larger distance and direction, larger selected-object image, circular native Start/Stop. The iOS gear retains connection settings; original diagnostics stay available in Debug builds.
- Added explicit camera permission and first-frame state, Stop/background cleanup, stale-callback invalidation, and live route/spatial-audio status. Kept the existing ARKit capture, world maps, uploads, speech, and HRTF guidance. The phone's Server row follows its actual `/v1/phone` socket.
- Build setup: checked-in `ios/MarcoPolo.xcodeproj` compiles `Marco/`, using Swift 5 / iOS 17 like `project.yml`. The generator remains optional. Font registration is in both configurations.
- Verification: web formatting/lint/schema/build passed, 22 unit tests and 19 browser tests passed (accessibility and 1440/768/390 widths). Swift 126 checks passed; Debug/Release device and Debug Simulator builds passed. No installed simulator runtime; physical camera/LiDAR/audio and runtime UI checks still require an iPhone.
- Existing integration gap remains explicit: the web snapshot/command contract is not implemented by the new `/v1` server. The API mode needs the adapter and phone command forwarding described above; the dashboard remains runnable in Demo mode. This UI change modifies no wire formats or server authentication.

## iOS VoiceOver support (October 17, 2026)

- Researched Apple's native VoiceOver guidance; the system screen reader supplies panel speech and gestures without a separate in-app accessibility mode, speech service, package or new permission. References and rationale are in `ios/ACCESSIBILITY.md`.
- The panel exposes current hardware values, specific camera failure reasons and recovery actions. Added Voice commands status and visible microphone/speech/audio startup failures; these had previously appeared only in diagnostics. Speech-recognition startup now rejects an unavailable recognizer and cleans up its tap if its audio engine cannot start.
- With VoiceOver on, Read status replays the current summary. Magic Tap shares Start/Stop behavior, including unsupported/pending-permission guards. Native sheet escape/close actions remain available; decorative camera preview content is hidden from the accessibility tree.
- Important camera, server, headphone, voice/audio failure and tracking changes use system announcements. Updates coalesce for 400 ms, identical updates stay quiet, automatic messages queue behind VoiceOver speech, and no focus movement is forced. A disconnected server gets a reminder after 12 seconds on the visible panel. A spatial-audio flag change alone is informational, not an HRTF failure.
- Verification: 170 Swift checks passed (44 new accessibility checks); Xcode device and Simulator builds passed. No installed Simulator runtime; actual VoiceOver speech, gestures, modal focus, permission recovery, AirPods routing and coexistence with guidance still require the real iPhone. No wire formats or backend code changed.

## Frontend audit fixes (October 17, 2026)

- Fixed all four actionable findings from the supplied frontend audit. Existing V3 styling and iOS changes were preserved.
- Live map position now requires matching session/map/wearer coordinate IDs in addition to connection, tracking and freshness; stale or mismatched data cannot enable the wearer marker, target line, live badge or Recenter. Remembered descriptions remain available.
- Find/Stop command state and its timer are invalidated on phone/session replacement. Same-scope uncertain retries keep their ID; new-scope actions get a new ID. Late old errors/acknowledgements are ignored.
- Silent WebSockets now close and reconnect/refetch through the existing backoff after more than 10 seconds without valid snapshot progress, including no first snapshot. Duplicate recovery, old socket messages, disposal and authorization failures are guarded.
- A missing camera now shows Waiting for camera; actual image failure and disconnection remain distinct, and a new frame recovers normally.
- Verification: complete `npm run check` passed formatting, lint, schema consistency, TypeScript/production build, **52 unit tests and 22 browser tests** (including automatic silent-stream recovery, reset maps and camera failure/recovery). `git diff --check` passed. Details: `frontend/docs/audit-fixes.md`.
- The separate server dashboard adapter and phone command forwarding remain open integration work; these fixes change no backend wire format or authentication. Browser API tests use mocked endpoints.

## Dashboard API preparation (October 17, 2026)

- Added `frontend/docs/backend-integration-plan.md` for potentially taking on the API layer after the backend team's core is ready. Ownership remains undecided; no API implementation started.
- Grounded the plan in the current FastAPI/core, browser schema and Swift decoder. It covers the three browser routes, media, world/map identity, health, Photon results, targeted Find/Stop delivery, phone acknowledgements, uncertain retries, rollout and live integration checks.
- Flagged the older frontend contract's superseded ownership diagram. Proposed session IDs on browser commands and new phone command/health messages require a coordinated team-interface/code/test update when implemented; no existing wire format changed here.
- Documentation-only change; implementation tests are specified in the plan and are not evidence that live integration already works.
- Verification: Prettier passed for the four touched frontend documentation files; all 28 local links resolved; `git diff --check` passed. No application tests were rerun for this documentation-only change.

## iOS audit fixes and main integration (October 17, 2026)

- Fixed all six reproducible iOS audit findings: fresh normal pose/coordinate scope gates guidance; Stop and supersession invalidate pending Find replies; unsaved capture starts allocate new map IDs; queued save completion checks lifecycle before disk writes; movement updates spoken surfaces; new labels update active touch feedback with text fallback.
- Tracking loss or a pose older than 0.5 seconds cancels guidance and gives a non-positional recovery message. A fresh Find is required after recovery. No device/server message formats changed. Details: `ios/AUDIT-FIXES.md`.
- Verification: 204 portable Swift checks passed, plus 23 AppModel and 11 ARSessionManager controlled regressions using current code and deterministic doubles. Xcode Debug Simulator build passed. AirPods route interruption, physical LiDAR and VoiceOver runtime checks remain open.
- Pulled the team's Photon 2.0 changes at `71268c6` and rebased onto the newer backend findings at `8aa0ae1`. The only conflicts were verification totals in this status file; preserved the newer backend/Photon work and our frontend/iOS progress.
- Pre-push checks in this checkout: frontend formatting/lint/schema/build, **52 unit tests and 22 browser tests**, **204 Swift checks**, unsigned Xcode Debug Simulator and Release device builds, and **8 Photon scaffold tests** passed. A temporary backend test environment ran **4 Swift/server contract tests plus 72 remaining server tests** successfully; one optional ARKitScenes-sample test was skipped because its dataset is absent. Hardware and live dashboard-adapter integration remain open.

## Approved roadmap and AirPods spatial verification (October 17, 2026)

- Recorded the user's primary system diagram in `docs/HACKATHON-ROADMAP.md`; added repository and parent-workspace `AGENTS.md` instructions and linked the roadmap from this status and `CLAUDE.md`. Future edits must preserve the architecture, minimal accessible iOS controls, shared visual theme, component contracts and private deployment. Proposed features remain distinct from working integrations.
- Fixed immediate spatial voice placement: both speech and label playback now use the last item position immediately, instead of waiting for the next guidance tick after switching from a general announcement.
- Added `spatial/check-render.sh`: actual Apple offline HRTF rendering through the app's voice-file path. Six reproduced failures before the fix; **17 checks pass** after it, including left/right placement, front/back filtering and simulated head turns. Existing **204 Swift checks** and the full Debug Simulator Xcode build pass.
- Confirmed connected AirPods Pro stereo output at **48 kHz / two channels** on this Mac. The app's HeadTracker received **308 samples at about 34.1 Hz**, spanning **77.46 degrees** of yaw. Generation, physical yaw sign and motion-to-audio latency are not established by that measurement.
- Added `spatial/check-airpods.sh` for real motion and spatial speech checks using the production classes. Completed the five-position/live-head-turn voice run, with **1,029 motion samples at about 36.8 Hz**; perceived localization feedback and chest-mounted iPhone world anchoring remain pending. Detailed procedure and boundaries: `spatial/VERIFICATION.md`. No protocol changes or push.
- Wearer feedback: **left/right sounded correct; front/back need improvement**. World anchoring was not independently confirmed. Rechecked the approved roadmap: spatial rendering/head fusion belong on the iPhone; the server supplies world positions and touch. The Mac helper exercises that existing phone code for development. No additional audio behavior changed after this feedback.
- Rechecked Apple documentation and primary spatial-hearing research. The current mono/HRTF/manual-head-tracking architecture fits the plan. Apple's separate automatic listener-tracking API requires a head-pose entitlement; do not stack it with manual source rotation. The initial tour tracked head turns only during its final phrase and omitted the production beacon sequence, so a sustained front/back head-turn test is still needed. Sources and concrete next checks are in `spatial/VERIFICATION.md`; this review made no runtime changes or new localization claims.
- Completed a focused **46-second** AirPods retest with live head compensation in every stage, repeated identical beacons for front/back A/B comparisons, and a separate spoken/muffled rear-cue demonstration. The helper waits for fresh motion and pauses on loss. **1,755 samples at about 38.2 Hz; zero missing-motion ticks**. Extended offline rendering tests: **21 passed**, including ±30° front/back head-turn checks. Perceived A/B localization and anchoring responses remain pending. Only test-helper/test/documentation behavior changed for this retest; no further production audio changes or push.
- Replayed the same test at the user's request: **1,641 motion samples at about 36.6 Hz**. A/B ran with motion; a loss in the final rear-cue stage triggered the audio pause (65 missing-motion update ticks). Listening feedback remains pending; no further code changes.
- Latest requested replay: **1,376 samples at about 33.2 Hz**, with three motion-loss pauses during B and the final segment (483 missing-motion update ticks). This run does not establish uninterrupted B/head-anchoring performance. No code changes; feedback pending.
- Latest wearer feedback confirms left/right, but front/back, distance and movement instructions remain unclear. The Mac tours use a fixed 2 m target and 0.65 s beep interval, bypassing production distance/facing/reach logic. Documented a focused guidance proposal: spoken turn/distance, chest-heading validation before any forward-walk instruction, separate alignment cue, existing distance cadence and fingertip-based reach. A head-facing ding alone does not establish body alignment or a clear path. No runtime changes based on the supplied comparison; details in `spatial/VERIFICATION.md`.
- Implemented requested `--guidance` test mode using production Guidance/SpatialAudio with real head yaw and explicitly simulated approach/reach. It includes alignment ding, 3 m→0.5 m distance cadence and speech, fingertip-proximity tone, touch confirmation, and honest alignment timeout. Motion loss freezes audio and simulated progress; no physical walking or Mac haptics are claimed. **18 new demo checks and 204 portable Swift checks passed**; helper compiled. Initial playback was rejected because AirPods disappeared and output reverted to Mac speakers. Awaiting reconnection; no successful new live run yet. The shell wrapper now requires a helper completion record instead of assuming LaunchServices success means playback. Details in `spatial/VERIFICATION.md`.
- After reconnection, a second start timed out before audio because no motion sample arrived within five seconds. Corrected test startup: immediate ding/spoken preparation, 30-second motion window, spoken timeout reason and live logs. The corrected launch now reports **audio started, motion ready, intro running**. The 18 demo checks passed again; completion and user feedback still pending at this point.
- Historical automatic guidance run executed: its internal alignment flag was set; **2,210 motion samples, zero missing-motion ticks, 34 scheduled beeps, three facing dings and one steady-tone entry**. Physical alignment is not confirmed. The wearer reported staying still while all stages ran, rejecting the automatic approach/reach/touch as an interaction test. Sample availability and an internal lock do not prove physical movement; startup yaw stability, drift and sign remain open. No production guidance changes.
- At the user's request, moved the new Mac spatial tools, renderer/simulation tests and verification notes into top-level `spatial/`, with build output ignored. Scripts compile the canonical iOS audio/core sources, preserving the iPhone's runtime ownership and Xcode layout. The old `--guidance` entry now refuses to play; the scripted sequence is retained only as explicit `--simulate-approach`, documented as simulation. Latest device check showed Mac speakers as output, no AirPods audio route and no developer iPhone. No new listening or physical navigation pass is claimed.
- Packaging validation: **21 offline renderer checks, 18 scripted-simulator checks, two withdrawn-option checks and 204 production Swift checks passed**. The relocated Mac helper compiles/signs, and the full unsigned iOS Debug Simulator build succeeds. Shell syntax and whitespace checks pass. Simulator checks describe generated input only; front/back localization and actual movement-dependent guidance remain unverified on the wearer/device.
