# Marco: project status (read this first)

Last updated: 2026-10-18. Keep this file current: update it whenever a decision is made or a piece lands.

## Saved dashboard items: startup fix (October 18, 2026)

- User reported an empty Objects page, then confirmed the items became visible.
  Actual Chrome checks now show **12 object rows** on both the private `/app/`
  dashboard and local port 5176. No registered data was deleted or recreated.
- Reproduced a startup bug in both real and stub modes: the registry restores
  saved items, but the dashboard adapter starts empty until a world event arrives.
  Initialize its item list from the restored core. New restart regressions cover
  HTTP and WebSocket snapshots, photos, typed labels and deletion without a phone.
- Also fixed the logo's absolute root URL, which returned 404 under `/app/`.
  A browser regression checks subpath assets and a saved item with no position
  while the phone is disconnected; Find remains disabled.
- Local checks: **122 server tests passed**, one external dataset skip;
  **53 frontend unit and 23 Chromium tests passed**, plus formatting, lint,
  schema and build. User authorized pushing and deploying these follow-up fixes;
  deployment and post-restart browser verification are pending.

## Pre-mobile live integration audit (October 18, 2026)

- Rechecked GitHub, deployed source, service environments, private routes and
  authentication. Runtime files matched; synchronized a README-only difference.
  The served dashboard exactly matches a fresh build with `--base=/app/`.
- Real caretaker photo/name registration exposed another older bridge on a
  teammate's machine: two readiness mug records were saved and the older
  voice-memo prompt appeared. User confirmed that older copy is now stopped.
  No duplicate records were deleted. Threaded replies/reactions get provider
  409 on this line; the existing plain-text fallback was delivered successfully.
- **Fixed a reproduced production blocker:** outgoing Photon photo uploads used
  an unsupported `type` parameter in `Content-Type`. The provider returned 400
  `INVALID_ATTACHMENT_REQUEST`. Removed that parameter, tightened the fake
  provider's validation, observed the regression fail before the fix, and passed
  all 52 Photon tests afterward. Deployed the fix and restarted only the bridge;
  the server replayed the retained request and the real test photo/question sent.
- Current runs: 120 server tests (one dataset skip), 52 Photon tests, 53 frontend
  unit tests and 22 Chromium tests pass. Actual Swift client → private Vultr
  speech → silent HRTF rendering passes six assertions; fresh reply 1.295 s.
  Fourteen real-HTTP/local-rendering fallback, offline and cancellation checks
  also pass. Private speech invalid requests return 422; unauthenticated HTTP/WS
  return 403/1008. Live server generation: 0.406 s, cached 0.002 s, valid mono
  24 kHz WAV. Keys remain server-only and absent from tracked files.
- **Live unknown-object round trip passed:** synthetic frame/depth/hand → real
  production brain → retained Photon request → delivered test crop/question →
  caretaker's typed `Readiness beacon` reply → `/v1/labels` → phone `label_ready`
  → valid ElevenLabs WAV (0.792 s). The actual Swift client also fetched that
  exact response and rendered it silently through HRTF, with Stop verified.
  Provider confirmed delivery of the photo, question and confirmation. The reply
  had no thread ID, so this live test proves the single-open-question fallback;
  explicit reply threading with multiple open questions remains unverified.
- Controlled real server restart preserved all **12 item IDs, names and labels**,
  including the new caregiver label. Photon automatically reconnected; health is
  OK with zero pending/open questions. Synthetic positions cleared on restart.
  **93 deployed source/assets/service files** match the tested checkout exactly;
  all 85 installed Python distributions have compatible dependencies. Node's
  dependency tree is valid. Final deployed Linux Photon tests: 51 pass, one
  macOS-only HEIC fixture-generation skip (conversion separately verified).
- Fix `761e1ed` is pushed and [GitHub integration checks pass](https://github.com/utk7arsh/LAHacks-2026/actions/runs/39116085128).
  The complete unsigned iOS Release build for a generic physical iPhone passes.
  Evidence is under `/private/tmp/marco-readiness-20261018/`. The test used
  synthetic sensors and silent Mac rendering; physical iPhone capture, actual
  fingertip contact, AirPods routing/head tracking and VoiceOver still need the
  device. For the demo, handle one unknown-item question at a time.

## Vultr server and Photon activated (October 18, 2026)

- User authorized bridge setup, server restart and the GitHub workflow update.
  Pulled teammate commit `dc985e6` without conflicts, preserving all local work.
  Every remote source file matched a blob in repository history; saved the old
  server source at `/opt/marco/backups/20261018T091033Z/server-source.tar.gz`.
- Deployed the reviewed server source without syncing environments, recordings,
  model weights or the existing dashboard build. Restarted `marco`; all **9 item
  IDs survived**. The active process loads the private ElevenLabs environment.
- Installed checksum-verified **Node 24.22.0**, pinned Photon dependencies and
  `marco-photon.service`. Runs as `marco`, enabled on boot, with restart on failure,
  loopback port 8787 and state under `/var/lib/marco-photon`. Keys remain in
  root-owned `0600` files under `/etc/marco`, never GitHub.
- Stopped the Mac bridge gracefully before starting Vultr. Migrated its linked
  caretaker, 5 local items, media and cursor **12245**. Preserved the original Mac
  state privately; marked only historical unsent `req_a2e7216234` as `failed` in
  the migrated copy. It was not sent. No registered items were removed.
- Live bridge health: **ok**, server connected, 1 caretaker, 0 pending/open
  questions. Photon event subscription and read-only doctor pass on Vultr. Both
  server and bridge listen on localhost behind private Tailscale access.
- Live private route/feed checks pass, including invalid-write rejection and
  unauthenticated-loopback 403. Real `/v1/speech` returned valid mono 24 kHz WAV:
  **0.369 s** generation, **0.002 s** cache hit. No audible/device playback claimed.
- Pre-deploy checks: **120 server tests** pass (one external dataset skipped),
  including **387 Swift checks**; **52 Photon tests**, **8 reference client tests**,
  **53 frontend unit tests** and **22 Chromium tests** pass. Types, lint, schema,
  formatting, builds, shell syntax and actionlint pass.
- Added active root GitHub workflows for frontend and server/Photon/Swift
  integration. CI uses isolated data and no production keys or SSH credentials;
  it does not deploy automatically. [Frontend CI passed](https://github.com/utk7arsh/LAHacks-2026/actions/runs/39114740624)
  for `7389d7c`. The first integration run exposed an older Swift compiler's
  exhaustiveness check for `Bool?`; made its cases explicit, preserving all
  three existing status tests. [Integration CI passed](https://github.com/utk7arsh/LAHacks-2026/actions/runs/39115115948)
  for `d798c40`: **120 server tests**, **52 Photon tests**, **8 reference tests**;
  one external dataset test skipped. Deployed server/bridge source is `7389d7c`;
  the follow-up changes only iOS compiler compatibility and these audit notes.
- Isolated tests on Vultr's actual Node/Linux runtime: **51 pass, 1 skipped**.
  The skipped HEIC fixture generator needs macOS `sips`; separately generated a
  synthetic HEIC on the Mac and verified JPEG conversion on Vultr. The bundled
  PNG converter and actual server/bridge contract test also pass on Linux.
- Remaining: fresh physical wearer → caretaker photo → typed answer → spoken
  label retest. No manual caretaker test messages or synthetic shared items were
  created during deployment. The earlier local-only notes below are historical.

## Private Vultr environment files staged (October 18, 2026)

- At the user's request, added credentials directly on Vultr, outside Git:
  ElevenLabs TTS settings in `/etc/marco/local.env` and the bridge configuration
  in `/etc/marco/photon.env`. Both are root-owned, mode `0600`; read-back checks
  passed without printing credentials. Existing dashboard settings were preserved.
- No secret manager is needed for this demo. The server service already lists
  `local.env` as an environment file. The future Photon service must explicitly
  load `/etc/marco/photon.env`; it is not discovered from the bridge directory.
- No service install, restart, code deployment, provider send, commit or push was
  performed. The server PID/start time stayed unchanged. These settings are staged;
  the older running server still lacks the speech route and the bridge still needs
  installation/handoff. Prior audit findings below remain applicable.

## Photon unknown-object audit and Vultr handoff (October 18, 2026)

- User confirmed the demo bridge will run on **Vultr, operated by a teammate**.
  See [the audit and handoff plan](docs/PHOTON-INTEGRATION-AUDIT.md). Only one
  active bridge should run across the Mac and Vultr. This audit made no commit,
  push, deployment, live send or shared-data change; the old Mac process remains.
- Read-only credentials, line assignment, event stream and private server checks
  pass. One saved identify request has a cached crop but no photo message ID;
  no matching photo appears in the checked provider history window. The original
  provider error is unavailable, so the precise historical cause is unconfirmed.
- Fixed reproduced failures: bounded outgoing retries, saved partial sends and
  reply recovery, identical attachment retry bodies, server replay of recent
  unanswered requests, stale real-brain touch timestamps, and duplicate items
  after a lost label HTTP response. Health/doctor expose incomplete sends.
- iOS now says “I'm asking your helper” rather than claiming a photo was sent;
  `unknown` is not a provider-delivery acknowledgement. No wire fields changed;
  §5 documents bounded replay and retry semantics, with regenerated Word output.
- Verification: **52 Photon tests and typecheck**, **120 server tests** (one
  external-dataset skip), **387 Swift checks** pass. Both local flows include an
  isolated server/bridge restart test. Real-brain tests use synthetic sensor data.
  Updated doctor intentionally reports the saved incomplete request as a failure.
- Remaining: review/deploy server and bridge together, inspect old pending state
  before migration/retry, verify Vultr's tailnet identity and hand off the single
  bridge. Physical wearer → real caretaker photo → typed reply → spoken label
  remains unverified because the wearer phone is unavailable. No new keys needed.

## Main push verification (October 18, 2026)

- User authorized integrating and pushing the local changes. Preserved tracked
  edits and untracked source under `/private/tmp/marco-before-push-20261018T082732Z/`.
  Fetched and pulled `origin/main` with fast-forward only: already current at
  `cc38be3`, no conflicts or teammate commits to reconcile.
- Re-ran all checks: **110 server tests passed, one external dataset skipped**;
  **387 Swift checks**, **47 Photon tests**, **8 reference contract tests**,
  **53 frontend unit and 22 Chromium browser tests** passed. Formatting, lint,
  exported schema, production dashboard build and unsigned iOS Release build pass.
  Initial sandbox attempts blocked loopback sockets/compiler caches; the full
  checks passed with the required local system access, without disabling tests.
- Real local ElevenLabs → HTTP → production Swift/spatial renderer check passed
  all **14 assertions** plus HTTP 403/503/422 boundaries; fresh generation took
  **0.810 s**. Stop, late replies, cache/offline use and Apple fallback passed.
  No audible playback or physical iPhone/AirPods verification is claimed.
- Read-only live private `/dashboard/snapshot` returned 200 and passed the actual
  frontend schema. Three `/events` WebSocket snapshots also passed that schema
  with increasing sequences. `/v1/items` returned 200. `GET /v1/speech` returned 404;
  the deployed server still needs the new endpoint and private environment before
  the app can use ElevenLabs there. No shared deployment or command was sent.
- All 66 installed Python dependencies are compatible. No configured API key,
  conflict marker, tracked spatial experiment or unignored file over 10 MB was
  found. Env files stay ignored with 0600 permissions. The existing nested
  frontend workflow remains inactive on GitHub; local checks were run explicitly.
- ElevenLabs receives only exact selected text: `Lines.swift`, guidance rules
  and server item state determine the words. No conversational agent, project
  prompt, Scribe or dialogue memory is configured; caretaker text can be spoken
  verbatim. Beacons, anchors and head tracking remain local to the phone.

## Deeper pre-merge review (October 18, 2026)

- Found and fixed malformed WAV caching: validate the endpoint's PCM header,
  lengths and format before caching. Twelve new assertions reproduced rejection
  and recovery failures before the fix; all **387 Swift checks** now pass.
- Fixed a flaky Chromium reconnect test that confused StrictMode's canceled
  startup fetch with watchdog recovery. It now waits for an additional fetch and
  actual visible recovery; added an HTTP-refetch recovery unit test. Production
  transport behavior and timeouts remain unchanged.
- Final full frontend check passes: formatting, lint, schema, build, **53 unit
  tests and 22 Chromium browser tests**. The first browser attempt lacked the
  test binary; installed it outside the repository before investigating the
  actual failing test. No tests were skipped to obtain a pass.
- Rechecked **110 server tests** (one external dataset skip), **47 Photon tests**,
  **8 scaffold tests**, dependency consistency, shell syntax and secret exclusion.
  The complete app builds in **Release** for a generic iOS device without signing.
- The corrected client passed the actual loopback HTTP/spatial renderer checks
  again: 14 assertions plus 403/503/422 boundaries; real TTS **0.826 s**. Stop,
  delayed replies, Apple fallback and cache use after server shutdown passed.
- Fresh `git fetch origin`: HEAD and origin/main both `cc38be3`, zero committed
  divergence. All edits remain local; no commit, push or deployment.
- Existing integration limitation: the GitHub workflow is nested inside
  `frontend/.github/workflows/`, so GitHub will not discover it automatically
  without a repository-root workflow entry. Its placement was preserved from the
  earlier layout request. Physical iPhone/AirPods checks also remain outstanding.
  See [the pre-merge report](docs/PRE-MERGE-REVIEW.md) for evidence and limits.

## Local speech end-to-end verification (October 18, 2026)

- Started three temporary loopback-only servers with isolated data: real TTS,
  missing provider key, and closed authentication. Verified actual HTTP 403,
  503 and 422 boundaries. No deployed server or shared data was changed.
- Ran the production `SpeechOutputClient` over real URLSession HTTP against the
  local endpoint with the provided key: **1.071 s** for a fresh 2.09 s mono WAV.
  The identical line returned synchronously from the phone's cache (~0.009 ms).
- Rendered through the production `SpatialAudio` graph in AVAudioEngine offline
  mode: non-silent stereo with expected left/right energy differences. Stop
  silenced playback, and Stop before a delayed HTTP reply prevented late speech.
- Verified real HTTP 503 selects Apple fallback/cooldown, and Apple synthesis
  itself produces speech through the same spatial graph. After shutting down
  the isolated live server, cached ElevenLabs speech still worked; an uncached
  request selected fallback. **14 Swift integration assertions** passed, plus
  the three HTTP boundary checks above.
- Re-ran regressions: **110 server tests passed, 1 external-dataset skip**;
  **375 Swift checks passed**; **47 Photon tests and typecheck passed**.
- Evidence and generated audio: `/private/tmp/marco-local-speech-evidence-20261018/`
  (`report.json`, `reply.wav`, left/right renders, Apple fallback and run log).
  All temporary test servers were stopped. The Mac reported built-in speakers;
  no audible playback, physical iPhone, AirPods/head-motion, walking, front/back
  perception or device-latency check is claimed. No deployment, commit or push.

## ElevenLabs output-only migration (October 18, 2026)

- Implemented authenticated `POST /v1/speech`: exact short text to ElevenLabs
  Flash v2.5 / George, 24 kHz mono PCM wrapped in WAV. No answer generation or
  speech recognition. The key is in ignored `server/.env` (0600), removed from
  Photon configuration; `.env*` is excluded from server deployment sync.
- iOS prefers this endpoint and converts its WAV through the existing spatial
  voice node. Item anchors, head fusion, beacons and the 60 Hz guidance loop stay
  local. Bounded memory caches and 2.5 s server / 3 s phone deadlines limit cost
  and delays. Missing key, failure or decode error uses Apple synthesis. Network
  failures trigger a 15 s cooldown; cached lines remain available offline.
- New speech, wake cues, Stop and session stop invalidate pending requests and
  late callbacks. Removed caregiver recording playback/downloads from the active
  app. Apple recognition still handles wearer commands; VoiceOver handles UI.
- Deleted Photon's Scribe client, ElevenLabs config and voice-label conversion.
  Welcome/help/questions request typed names. Recordings are refused without
  downloading/transcribing/uploading them; captioned photos and typed answers,
  corrections, allow-list checks, persistence and retries remain. Existing saved
  media and optional wire fields are preserved for compatibility.
- Restarted only this repo's verified local bridge (old PID 92292 → **6703**),
  preserving state/cursor. `/health` reports live Photon mode and the private
  server connected; five local saved items and zero open questions. No deliberate
  iMessage send, shared-item reset or remote deployment occurred in this task.
- **Verification:** **110 server tests pass**, one external ARKitScenes dataset
  check skipped; **375 Swift checks pass**; **47 Photon tests pass**, zero skips,
  including the actual isolated server's typed-label/persistence/reset flow.
  iOS generic-device Debug build succeeds with signing disabled.
- **Real provided-key TTS:** endpoint HTTP 200, 1.95 s WAV, 24 kHz mono / 16-bit.
  First response **1.005 s**, cached repeat **0.001 s**. Production Swift decode
  and conversion to 48 kHz mono succeeds with non-silent samples, without playing
  sound. These are local endpoint/decoder checks, not measured iPhone latency.
- Updated canonical contract to v0.4 and generated Word copy; component setup and
  [speech implementation notes](docs/SPEECH-OUTPUT-PLAN.md) describe activation.
- **Still needed:** deploy code and configure `/etc/marco/local.env` on Vultr,
  install the updated iOS app, then check voice/beacon playback, world anchoring,
  Stop and offline fallback on the actual iPhone/AirPods. Old deployed code keeps
  its existing speech behavior. No commit or push was made.

## Latest main synchronization and dependency verification (October 17, 2026)

- Fetched GitHub and fast-forwarded local `main` from `bfe19e9` to **`cc38be3`**
  (13 commits). A second fetch after validation still reported `cc38be3`. No merge
  conflicts. The remote version is the working baseline; no local commit or push.
- Preserved every prior tracked/untracked edit in Git stash
  `Preserve local dashboard Photon and speech plan before latest main sync 2026-10-17`
  and a separate patch/archive at `/private/tmp/marco-before-main-sync-20261018T064652Z/`.
  Ignored credentials and data stayed in place. The old frontend raw-v1 adapter
  and Scribe additions were not reapplied over the new server adapter.
- Reconciled only still-needed fixes: pinned bundled `ffmpeg-static@5.3.0`,
  explicit npm install-script approvals, converter regression tests, caregiver
  allow-list checks (including previously saved caretakers), and `.env.*` ignores.
  Preserved upstream persistence, source attribution and `/restart` behavior.
  The newly added reset flow was exercised only against an isolated local stub,
  never against the shared server.
- Installed frontend/Photon from lockfiles and all `server/requirements.txt`
  dependencies into ignored `server/.venv`. `uv pip check` passed; PyTorch,
  Transformers OWLv2/AutoModel/processors, SciPy and OpenCV import successfully.
  Model weights/inference on physical demo footage were not rebenchmarked.
- Changed ignored `frontend/.env.local` from `VITE_DATA_SOURCE=v1` to `api`, keeping
  the existing private proxy target. Made Playwright's demo server explicitly
  select demo mode so a developer's API configuration cannot change those tests.
  Restarted this repo's verified local Vite process on **http://127.0.0.1:5176/**.
- **Validation:** frontend lint, format, exported-schema checks and production
  build pass; **52 frontend unit tests**, **22 Chrome browser tests**, **49 Photon
  tests** (zero skips, including actual local-server persistence/reset integration),
  **8 Photon scaffold tests**, **98 server tests** (one external ARKitScenes sample
  test skipped), and **357 Swift checks** pass. The complete iOS app builds in
  Xcode Debug for a generic iOS device with signing disabled. Initial sandbox
  socket/CoreVideo restrictions were resolved by running the relevant local
  checks with normal system-framework access, without changing app logic.
- **Live private dashboard, read-only:** `/dashboard/snapshot` and its `/api`
  alias returned 200. Real Chrome validated the snapshot against the frontend
  Zod schema, received 11 event snapshots, displayed four registered items and
  loaded a 960×720 chest-camera frame. The phone reported connected. No page
  errors, failed API responses, browser writes or commands occurred. Two Diet
  Coke registrations already exist and were left untouched. Evidence:
  `/private/tmp/marco-latest-main-live-browser.json`,
  `/private/tmp/marco-latest-main-objects.png`,
  `/private/tmp/marco-latest-main-camera.png`.
- No shared-server deployment, real iMessage send, physical iPhone install,
  Find/Stop command or AirPods test was performed in this synchronization.
  The existing live Photon process was not restarted; runtime adoption of the
  updated bridge and the planned ElevenLabs TTS migration remain separate work.

**Primary roadmap:** the user's approved whole-system diagram is recorded in
[`docs/HACKATHON-ROADMAP.md`](docs/HACKATHON-ROADMAP.md). Read it and `AGENTS.md`
before future edits; this status file records implementation evidence and remaining gaps.

**Current working baseline:** latest fetched `origin/main`, **`cc38be3`**, checked
again after local validation on October 17, 2026. Use this version and the small
local integration fixes below; do not restore the old raw-v1 frontend over it.
**Latest speech decision:** caretaker labels are photos plus typed names;
ElevenLabs is used only for Marco's spoken responses (TTS) in the local code.
Scribe/voice-label handling is removed; private TTS and iOS playback are implemented
and tested. Shared deployment and physical playback remain pending.
See [`docs/SPEECH-OUTPUT-PLAN.md`](docs/SPEECH-OUTPUT-PLAN.md).

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
- **Audio route (changed 2026-10-17):** output to the AirPods stays full-bandwidth stereo, which HRTF needs. Speech now comes from the **AirPods' mic** through iOS 26's `.bluetoothHighQualityRecording`. The SDK header says this mode enables "full-bandwidth audio in both input & output directions" on supported AirPods, unlike Bluetooth HFP, which would make them a mono 16 kHz headset (never used).
  - **Fallback:** the iPhone mic, when the route doesn't support the mode or the debug screen's "Use the iPhone mic" switch is on.
  - **Unverified on hardware:** that the output stays 2 channels in this mode (hour-one test 7).
- **Where it runs (decided 2026-10-17, Utkarsh): the Vultr GPU box `marco-gpu` is the primary server.** The phone streams LiDAR frames, poses and hands to it over the tailnet, and all processing (detection, box to 3D, world model, touch, answers, dashboard feeds) happens there. The venue Mac is the fallback: same server, and only the app's Server field changes.
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
- **Deployed 2026-10-18 03:15 UTC: commit `f778d18`.** It brings the floor-relative surfaces, the 4 m range gate, the gated status at `/` and FastAPI's docs off. It was deployed with the kit's own steps over SSH.
  - The previous code is at `/opt/marco/backup-server-20261018-031539.tgz`.
  - **Checked on the box:**
    - `/` shows the status, signed in as `utk7arsh@github`;
    - `/docs` and `/openapi.json` give 404;
    - `/v1/items` gives 200 through the URL and 403 on 127.0.0.1 without a login;
    - a forged `Tailscale-User-Login` header sent through `tailscale serve` is replaced by the real login.

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
  - `sh ios/check.sh` type-checks every file that builds on macOS and runs 286 Swift checks (Sandeep's 204, plus the phone recorder, sturdier AirPods fusion, AirPods/link health, server check, mic route and item vocabulary).
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
  - **Verification:** `cd photon && npm test` runs 45 tests. One of them is end to end against the real `server/` (stub, loopback): `what_is_this` → `label_request` → iMessage → text then voice memo → `label_ready` with m4a audio → `what_is_this` known → setup photo → `GET /v1/items` → server restart (all still there) → `/restart` (Photon's items gone, still gone after another restart). It runs when `server/.venv` (or `MARCO_SERVER_PYTHON`) has the stub dependencies.
  - **`/restart` (chat command, for testing):** a caretaker texts `/restart`; the bridge calls `DELETE /v1/items?source=photon` and forgets its own copies. Every Photon post carries `source=photon`.
  - **Fixed:** after a server restart the bridge could stop reconnecting to `/v1/photon`, because Node's WebSocket fires only `error` for a refused connection. It now retries on either event, with a connect watchdog; there's a regression test.
- **Server: registrations and labels survive a restart** (Utkarsh, 2026-10-17, contract v0.3; `marco/registry.py`).
  - **Saved:** every `POST /v1/items` and `POST /v1/labels`, with its photo (or touch crop) and voice note, under `MARCO_DATA/registry/` (on Vultr, `/var/lib/marco/data/registry/`, which deploys never overwrite). Writes are atomic.
  - **Reloaded at start** by both brains. The real brain registers each saved photo with the detector again, so detection works at once. Positions are re-learned from the camera.
  - **`source`** on items (`app` / `photon` / `seed`), and **`DELETE /v1/items?source=…`**, which removes one source's items, labels, audio and files. `source` is required, and the route is behind the gate.
  - **Tests:** `tests/test_registry.py` (7): survives a restart (stub, and the real brain with the detector re-registered), delete-by-source, idempotence, validation, the gate. Full server suite: 87 passed, 1 skipped.
  - **Deployed to `marco-gpu`** on 2026-10-18 at 05:18 UTC: commit `6f4c0ee`, from a clean checkout, with the allow-list kept as it was. Verified live: `GET /v1/items` 200, `DELETE /v1/items` without a source 422, `?source=photon` 200. The bridge runs on this Mac against it.
- **Verification totals:** server 79 passed on Vedant's Mac (with the ARKitScenes sample; 76 + 1 skipped where it's absent), Swift 314 (after merging Utkarsh's iOS work and the LiDAR view), Photon scaffold 8; `photon/` 39 (Utkarsh's run).
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

- **Voice input, end to end on the phone (2026-10-17, Utkarsh):** "Marco, where are my X?" from the AirPods' mic to a `find` query that names a registered item.
  - **Mic:** `SpatialAudio.applyRoute` (above). Route changes are handled: AirPods put in later are picked up, and both audio engines restart. Before, a route change that changed the audio format (AirPods in or out) stopped both engines, and nothing restarted them.
  - **Wake:** "Marco ..." in one breath, or "Marco", a soft blip, then the request within 5 s; hold-to-talk as before.
  - **Extraction (`Core/Lines.swift` `Speech`):** about 40 ways of asking ("have you seen my ...", "do you know where my ... are", "where my ... at", "I can't find ..."), lead-ins ("hey", "polo", "could you"), and "my keys and my wallet" (one thing at a time, the first). Just "Marco, keys?" works when it's all of a registered name.
  - **Matching (`Core/Vocabulary.swift`):** the spoken words become the registered item's own name, matched on plurals, a small synonym table (specs, clicker, billfold, cup...), one-letter recognizer slips and the shared last noun.
    - Ties ("jar" with two jars) and unknown things go to the server as said, so the server's `not_registered` answer still speaks.
    - The names come from `GET /v1/items` at start and on every reconnect, plus the names on server messages. They are also the recognizer's `contextualStrings`, so "cumin" isn't heard as "human".
  - **Faster answer:** the listener ends a command 0.45 s after a whole registered name, 0.9 s otherwise.
  - **No contract change:** `query find` still carries a `name`; it is now usually the server's own spelling.
  - **Not used:** ElevenLabs and any cloud recognizer. Apple's on-device recognizer is offline and free and takes the hints.
  - **Verified:** 60 new Swift tests (178 in all); the full app builds for iOS with no errors or warnings. Nothing has run on the phone yet.

## Dashboard adapter (2026-10-18, Vedant)
- **What:** `server/marco/dashboard.py` and `dashboard_commands.py` serve the dashboard's own contract (`frontend/docs/fastapi-handoff.md`, `frontend/src/lib/schema.ts`).
  - Routes: `GET /dashboard/snapshot`, `WS /events`, `POST /dashboard/commands`, `GET /media/...`, `/app/...` (the built dashboard via `MARCO_DASHBOARD_DIR`), each also under `/api/...`, all gated.
  - It reads only what the core already publishes; no perception changes.
- **Find/Stop:**
  1. The browser posts a command.
  2. The server sends `command` to the bound phone.
  3. The phone answers with `command_ack` (accepted, applied or rejected).
  4. The snapshot's `lastCommand` follows the answer.

  Contract §3.2, §4 and §6 are updated. The app's half is `ios/Marco/Core/DashboardCommands.swift` (pure, tested) plus `AppModel.command(_:)`, which shares the voice Find's guidance start.
- **Tests:** `server/tests/test_dashboard.py` has 8 tests:
  - schema-valid snapshots in every state, against the exported JSON Schema and its refinements;
  - socket heartbeat and ordering;
  - media;
  - the full command lifecycle, including retries, conflicts, a disconnected phone, a session mismatch, timeout and session replacement;
  - access for every new route.

  The Swift command gate has 9 tests. The contract test sends a Swift-encoded `command_ack` to the server. Totals: server 96, Swift 323.
- **Not verified here** (code-only Mac):
  - the dashboard against these routes in a browser;
  - `AppModel.command(_:)` in Xcode;
  - Find and Stop end to end with the real phone.

  Needed: Sandeep runs the browser integration (`VITE_DATA_SOURCE=api`, no mocked routes); Utkarsh builds the app and redeploys; then a real Find from the dashboard.

## Room map on the dashboard (POC 27, 2026-10-18, Vedant)
- **What:** the dashboard map now draws the room: walls, plus one stock shape per kind of furniture (table, chair, sofa, bench, bed, shelf, tree, plant) at its scanned position, size and facing. It's in the style of a car's screen, Tesla-like.
  - Geometry only, from the LiDAR the server already has: `server/marco/world/layout.py`, a 10 cm column grid inside `RoomMap`.
  - The brain sends `room_layout` every 3 frames on its own thread. The adapter fills `map.walls` and the new `map.landmarks`.
  - Frontend: `lib/roomShapes.ts`, `components/RoomShape.tsx` and `MapView`.
  - Contract: `docs/INTERFACES.md` §6 and §12.
- **Harm checks** (`poc/pocs/poc27_room_map/`, notes in `NOTES.md`):
  - Detection outputs are identical with the layout on and off: 3 sessions, real OWLv2 on two of them.
  - Mean frame latency doesn't change (noise, ±7 ms on about 380 ms frames).
  - `summarize` takes 5 ms for one room and 177 ms at the 40 m × 40 m cap, and runs off the frame thread.
  - Grid memory: 1 MB per room, 19 MB at the cap. Snapshot: 1 KB per room, 40 KB at most.
- **Accuracy** (it's display only, so it's never used for guidance or speech):
  - synthetic room: walls 95 % precision and recall; 6/6 furniture with the right kind.
  - ARKitScenes: 5/17. Cabinet runs come out as walls, and the frames are sparse.
  - iPhone venue clips: the round table, the chairs around it (facing it) and the ledge as a bench. Stepping stones show up as low tables. No trees: they're beyond LiDAR range.
  - Previews: `poc/reports/figures/poc27_dash_*.png`.
- **Not verified here:**
  - `npm run check` (vitest, Playwright, lint) in `frontend/`. The changed TS passes Prettier and a TypeScript 6 check with real zod types.
  - the live map in a browser.

  Needed: Sandeep runs `npm run check` and looks at the map with `VITE_DATA_SOURCE=api`.
- **Next, if wanted:**
  - label the shapes with the camera: OWLv2 text queries reuse the frame's image pass, an extra head call;
  - indoors, Apple RoomPlan on the phone (Utkarsh; needs a device test).

## In progress / next
0. **Several registered items (POC 28, 2026-10-18; `poc/pocs/poc28_multi_item/NOTES.md`):** every frame already checks every item, and order or count changes nothing (identical scores alone or together). Items are missed because the DINOv2 crop check (`TH_DINO` 0.38, calibrated on ORBIT's handheld photos) rejects correct boxes from the vest: it was the blocker in 13 of 19 such frames, and the wallet was never accepted.
   - **Proposed:** `TH_DINO` 0.30. On the venue clips that's 5 → 8 hits with no extra false alarms.
   - **Also proposed:** make restarts re-register like the first registration. Today the restart path queries with the whole photo, the first registration with the crop.
   - **Waiting on the user's go-ahead.**
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
   - OWLv2-large on a CUDA GPU (Vultr);
   - half precision on the Mac.
7. **Caretaker voice notes:** `photon/` already sends them as m4a. Server-side conversion is only needed for other clients that post `.caf`.
   - **Possible §5 additions (proposals, not built):** `label_request_seen` (the caretaker opened the photo: "Mom is looking at it") and `label_unknown` ("Mom isn't sure either"). `photon/` already detects both and only logs them.
   - **Local audit fix (2026-10-18):** the server buffers up to 128 unanswered `label_request` events for 10 minutes and replays on bridge reconnect; this is memory-only and not deployed yet. See the Photon audit above.
7. **Vultr (Utkarsh): the box is up** (see "Built and verified"). Left to do:
   - point the phone's Server field and `photon/`'s `MARCO_SERVER_URL` at `https://marco-gpu.taild6d426.ts.net`;
   - invite teammates to the `utk7arsh` tailnet, add their logins to `TAILSCALE_ALLOWED_LOGINS`, and re-run `deploy`;
   - measure the phone-to-Vultr round trip on venue Wi-Fi (`tailscale ping marco-gpu`).

   It bills $0.47/h until `marco-vultr.sh down`; stopping it doesn't stop billing.

8. **Phone to Vultr, and Vultr to the dashboard (decided: Vultr is primary; measured 2026-10-17):**
   - **Phone → `marco-gpu`, connected and tested from this Mac over the tailnet** (the same path the phone takes):
     - Tailscale path **direct** to the box (`via 45.32.136.225:41641`, no relay), 49–65 ms;
     - `GET /v1/items` → 200 through the allow-list (login `utk7arsh@github`);
     - `POST /v1/frames` with the Swift-encoded bytes → 202 in 83–118 ms per frame on a kept-alive connection (40 KB synthetic frame, no items registered);
     - `WSS /v1/phone` opens in about 0.4 s; message round trip median 67 ms.
   - **Expected on the phone:** about 60–100 ms network plus the A16's 0.18–0.40 s pipeline per frame, well inside 1 s. Touch: hand messages up, about a 5-message vote, `touch` down, so about 0.4 s.
   - **To connect the phone:** install the Tailscale app, sign in with the same login (`utk7arsh@github`, already on the allow-list; any other login must be added to `TAILSCALE_ALLOWED_LOGINS` and redeployed), set Server to `https://marco-gpu.<tailnet>.ts.net`, press Start. The app's log then says "Server OK", or what to fix (`ios/Marco/Net/ServerCheck.swift`).
   - **Is the phone's path direct?** `marco-vultr.sh ssh`, then `tailscale status` on the box: the iPhone's line should not say `relay`. If it does, venue Wi-Fi is blocking UDP; try the phone's cellular data.
   - **Dashboard on the Mac:** it reads `marco-gpu` over the tailnet (`API_PROXY_TARGET=https://marco-gpu.<tailnet>.ts.net`; this Mac's login is allowed).
   - **Fallback (server on the venue Mac), measured on this M2 Pro:** upload start to dashboard `frame` median 428 ms with real OWLv2 (408 ms of it detection), 16 ms in stub mode; pose to `world` 1.2 ms. Put the Mac on the iPhone's Personal Hotspot so the link stays direct.
   - **Test data on `marco-gpu`:** the connection test posted 6 copies of the Swift contract fixture frame (session `ios-contract`, map `ios-map`) on 2026-10-17. No items were registered, so item memory is untouched. Clear it before the demo by deleting that recording on the box and restarting `marco`.
   - **Phone straight to the dashboard** (no server): not useful. Boxes, positions and events come from the server, and the server-to-dashboard hop is 3 ms.
   - **Server issues found (Vedant's code):**
     - **fixed 2026-10-17 (Utkarsh, in `marco/hub.py`):** one stalled dashboard socket blocked the whole server, because `hub.send` awaited each socket in turn inside the frame route and the phone loop. Every socket now has its own outbox and writer (see the section at the end);
     - the frame `202` is returned after detection, not straight away as §3.1 says, so the phone's single upload slot is held for about 0.43 s;
     - OWLv2 runs in fp32 on MPS (POC measured 392 ms fp32 vs 276 ms fp16);
     - `map_points` goes every frame, not every 5 s as §6 says;
     - stub: guidance at 10/s starts overlapping fake guidance sequences (25 fake touches in 5 s).
   - **Dashboard (Sandeep):** `frontend/` still calls `/dashboard/snapshot`, `WS /events` and `/dashboard/commands`, so it shows nothing today. The adapter should push on every event, not on a 1 s timer, which would add 0.5 s on average. Over loopback the gate returns 403 with `MARCO_AUTH=tailscale`, so point `API_PROXY_TARGET` at the `ts.net` URL.

8. **Vultr (Utkarsh): the box is up** (see "Built and verified"). Left to do:
   - point the phone's Server field and `photon/`'s `MARCO_SERVER_URL` at `https://marco-gpu.taild6d426.ts.net`;
   - invite teammates to the `utk7arsh` tailnet, add their logins to `TAILSCALE_ALLOWED_LOGINS`, and re-run `deploy`;
   - measure the phone-to-Vultr round trip on venue Wi-Fi (`tailscale ping marco-gpu`);
   - try OWLv2-large on it with `bench_frame.py` (step 6).

   It bills $0.47/h until `marco-vultr.sh down`; stopping it doesn't stop billing.

## Open questions / hour-one tests (need the real phone)
- **iPhone runtime checks** of the compiled ARKit/UIKit app; no installed simulator runtime is available on this Mac yet.
- **LiDAR view on the phone (2026-10-17, Utkarsh; runs on the iPhone):** "Open LiDAR view" on the running panel shows the live LiDAR depth full screen (Turbo, red near to blue at 5 m, dim camera beyond), with only a close button: the user asked for no controls or overlays. `LiDARRenderer` still has the room point cloud and remembered-item labels (`Core/DepthVision.swift`, tested) if they're wanted again; with no overlay on screen it skips that work.
  - It only reads `session.currentFrame` (no second camera, never the session delegate), so frame upload is untouched.
  - Shaders are Swift source compiled on the phone at runtime: Xcode 26's Metal compiler is a separate download, and a `.metal` file would break the build without it.
  - Verified on this Mac: `check.sh` runs the point-cloud kernel and the heat-map shader on the Mac's GPU (3D points within 1 mm of `CameraMath`, the server's convention; colours match `DepthPalette`); `MarcoPolo.xcodeproj` builds for iOS.
  - Not verified: frame rate, heat and battery on the iPhone with capture running; how the overlay lines up on the real display transform.
- **iPhone app made lighter (2026-10-18, Utkarsh; built and unit-tested, not yet measured on the phone)** after it overloaded and crashed now and then:
  - **Camera stays at 60 fps** (the user's preference) and switches in place, with no tracking reset, to 1920x1440 at 30 fps only at serious heat or with Developer tools' "Camera at 30 fps" switch; back to 60 when it cools. If 30 fps ever gives no depth for 3 s it returns to 60 for the session. The log says which rate runs.
  - **No plane detection:** nothing used plane anchors.
  - **Hand detection** (Vision): one hand instead of two, the full 15/s only within 1.5 s of seeing a hand and 5/s otherwise, and the 9x9 patches read straight from the depth buffer instead of copying both whole maps per message (byte-identical, tested; the contract test still passes).
  - **No idle re-rendering:** the ~10 values only Developer tools shows (and every partial transcript of nearby speech) are published only while that screen is open, and only on change. Before, the main panel re-rendered 10 times a second.
  - **World-map saves off the ARKit queue:** archiving a large map no longer stalls frame delivery every 30 s; clearing goes through the same serial queue.
  - **WebSocket backlog cap:** at most 32 stream messages waiting; on a stalled link URLSession used to buffer poses and hands without limit.
  - **Heat policy** (`Core/ResourcePolicy.swift`): at serious heat the camera drops to 30 fps, hands to 10/2 per second and the LiDAR view to 30 fps; at critical, hands to 5/1 and the LiDAR view to 15 fps. Frames (1/s) and poses (10/s) never change.
  - **Crash evidence:** MetricKit diagnostics (crashes, CPU limit hits, hangs, with call stacks) are saved to Documents/diagnostics, visible in Finder under Files.
  - Next candidates, which need on-device profiling: the audio engine runs three HRTF players even when silent; speech recognition runs all the time.
- **Phone to Vultr:** the iPhone is on the tailnet and reaches `marco-gpu` (`GET /v1/items` from Safari); the app's streaming to it is not yet run.
- **AirPods mic (hour-one test 7):** does high-quality recording turn on with the AirPods Pro 3, does the output stay 2 channels, and how much input latency does it add from the vest?
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
- Added `ios/spatial/check-render.sh`: actual Apple offline HRTF rendering through the app's voice-file path. Six reproduced failures before the fix; **17 checks pass** after it, including left/right placement, front/back filtering and simulated head turns. Existing **204 Swift checks** and the full Debug Simulator Xcode build pass.
- Confirmed connected AirPods Pro stereo output at **48 kHz / two channels** on this Mac. The app's HeadTracker received **308 samples at about 34.1 Hz**, spanning **77.46 degrees** of yaw. Generation, physical yaw sign and motion-to-audio latency are not established by that measurement.
- Added `ios/spatial/check-airpods.sh` for real motion and spatial speech checks using the production classes. Completed the five-position/live-head-turn voice run, with **1,029 motion samples at about 36.8 Hz**; perceived localization feedback and chest-mounted iPhone world anchoring remain pending. Detailed procedure and boundaries: `ios/spatial/VERIFICATION.md`. No protocol changes or push.
- Wearer feedback: **left/right sounded correct; front/back need improvement**. World anchoring was not independently confirmed. Rechecked the approved roadmap: spatial rendering/head fusion belong on the iPhone; the server supplies world positions and touch. The Mac helper exercises that existing phone code for development. No additional audio behavior changed after this feedback.
- Rechecked Apple documentation and primary spatial-hearing research. The current mono/HRTF/manual-head-tracking architecture fits the plan. Apple's separate automatic listener-tracking API requires a head-pose entitlement; do not stack it with manual source rotation. The initial tour tracked head turns only during its final phrase and omitted the production beacon sequence, so a sustained front/back head-turn test is still needed. Sources and concrete next checks are in `ios/spatial/VERIFICATION.md`; this review made no runtime changes or new localization claims.
- Completed a focused **46-second** AirPods retest with live head compensation in every stage, repeated identical beacons for front/back A/B comparisons, and a separate spoken/muffled rear-cue demonstration. The helper waits for fresh motion and pauses on loss. **1,755 samples at about 38.2 Hz; zero missing-motion ticks**. Extended offline rendering tests: **21 passed**, including ±30° front/back head-turn checks. Perceived A/B localization and anchoring responses remain pending. Only test-helper/test/documentation behavior changed for this retest; no further production audio changes or push.
- Replayed the same test at the user's request: **1,641 motion samples at about 36.6 Hz**. A/B ran with motion; a loss in the final rear-cue stage triggered the audio pause (65 missing-motion update ticks). Listening feedback remains pending; no further code changes.
- Latest requested replay: **1,376 samples at about 33.2 Hz**, with three motion-loss pauses during B and the final segment (483 missing-motion update ticks). This run does not establish uninterrupted B/head-anchoring performance. No code changes; feedback pending.
- Latest wearer feedback confirms left/right, but front/back, distance and movement instructions remain unclear. The Mac tours use a fixed 2 m target and 0.65 s beep interval, bypassing production distance/facing/reach logic. Documented a focused guidance proposal: spoken turn/distance, chest-heading validation before any forward-walk instruction, separate alignment cue, existing distance cadence and fingertip-based reach. A head-facing ding alone does not establish body alignment or a clear path. No runtime changes based on the supplied comparison; details in `ios/spatial/VERIFICATION.md`.
- Implemented requested `--guidance` test mode using production Guidance/SpatialAudio with real head yaw and explicitly simulated approach/reach. It includes alignment ding, 3 m→0.5 m distance cadence and speech, fingertip-proximity tone, touch confirmation, and honest alignment timeout. Motion loss freezes audio and simulated progress; no physical walking or Mac haptics are claimed. **18 new demo checks and 204 portable Swift checks passed**; helper compiled. Initial playback was rejected because AirPods disappeared and output reverted to Mac speakers. Awaiting reconnection; no successful new live run yet. The shell wrapper now requires a helper completion record instead of assuming LaunchServices success means playback. Details in `ios/spatial/VERIFICATION.md`.
- After reconnection, a second start timed out before audio because no motion sample arrived within five seconds. Corrected test startup: immediate ding/spoken preparation, 30-second motion window, spoken timeout reason and live logs. The corrected launch now reports **audio started, motion ready, intro running**. The 18 demo checks passed again; completion and user feedback still pending at this point.
- Historical automatic guidance run executed: its internal alignment flag was set; **2,210 motion samples, zero missing-motion ticks, 34 scheduled beeps, three facing dings and one steady-tone entry**. Physical alignment is not confirmed. The wearer reported staying still while all stages ran, rejecting the automatic approach/reach/touch as an interaction test. Sample availability and an internal lock do not prove physical movement; startup yaw stability, drift and sign remain open. No production guidance changes.
- At the user's request, moved the new Mac spatial tools, renderer/simulation tests and verification notes into top-level `spatial/`, with build output ignored. Scripts compile the canonical iOS audio/core sources, preserving the iPhone's runtime ownership and Xcode layout. The old `--guidance` entry now refuses to play; the scripted sequence is retained only as explicit `--simulate-approach`, documented as simulation. Latest device check showed Mac speakers as output, no AirPods audio route and no developer iPhone. No new listening or physical navigation pass is claimed.
- Packaging validation: **21 offline renderer checks, 18 scripted-simulator checks, two withdrawn-option checks and 204 production Swift checks passed**. The relocated Mac helper compiles/signs, and the full unsigned iOS Debug Simulator build succeeds. Shell syntax and whitespace checks pass. Simulator checks describe generated input only; front/back localization and actual movement-dependent guidance remain unverified on the wearer/device.

## Spatial folder move and push repair

- Preserved the user's move to `ios/spatial/` and rebased it onto the team's latest work through `58f0bef`, including the server/deployment fixes and newly pushed iOS recorder, health, voice and audio changes. The original move commit is retained locally on `backup/spatial-move-de6b76f`. Rebase completed without conflicts; no force push is needed.
- Fixed the move's broken compiler paths (`../Marco/`, relative to `ios/spatial/`), updated run commands and documentation links, and verified build output remains ignored. The iPhone app sources, `ios/project.yml`, frontend and backend code were not changed by this repair.
- Verification after the latest merge: **21 renderer checks, 18 simulation checks, two withdrawn-option checks and 286 production Swift checks passed**. The Mac helper builds/signs; the unsigned iOS Debug Simulator build succeeds. Shell syntax, moved links and whitespace checks pass. No listening test was launched, and no new physical-navigation result is claimed.

## Spatial experiments kept local

- At the user's request, removed `ios/spatial/` from Git tracking while preserving its files locally. Root ignore rules cover both `/ios/spatial/` and the former `/spatial/` location; README links to the unpublished folder were removed. The iPhone's production audio remains in `ios/Marco/Audio/`.
- Incorporated the latest team work through `8cbed3c` before this removal. This is a repository-tracking/documentation change; app sources and project configuration are unchanged. Verified local file preservation, ignore rules and whitespace; no audio was played and no new device result is claimed. Existing Git history is retained.

## Architecture progress map (October 17, 2026)

- `docs/architecture.html` is now a **build map**: the target system, coloured by what actually works. Green **End to end** (integration-tested on loopback, replayed real data or from the Mac), teal **Live** (also verified with the real device or service), blue **Built** (code + unit tests only), red **Not built**. Hover any element for its evidence.
- Sections:
  - **Commands:** find, what is this, caretaker labels, touch to name, "this is the door" / left behind, and register (by a sighted helper or the caretaker). The wearer never names items themselves.
  - **The 7-stage find experience:** "Polo! Behind you, two steps", the muffled beacon, the facing ding + buzz, faster beeps, the steady tone in the last 30 cm, "Got it" at touch. Each stage is mapped to its code (`Guidance.swift` phases, `Lines.swift`, server `touch.py`).
  - **A left-to-right pipeline:** sources → pre-processing (phone capture, Photon intake) → **the brain on Vultr** (ingest, detect, box to 3D, world model, touch, answers, feeds) → post-processing (phone guidance, Photon outreach, dashboard) → destinations. 13 numbered wires.
- Snapshot at `de9aa08` (2026-10-18; adds the registry, hub fix, keep-looking, room-anchored audio, route watch, and the bridge running against marco-gpu):
  - commands 4/6 end to end;
  - find stages 0/7 (all built, none heard on the vest);
  - parts 18/36 (8 live);
  - wires 8/13 (3 live).
  - Not built: the dashboard feed and screen.
- Documentation only; no code or contract changed.

## Find: keep looking when not found, and the hub fix (October 17, 2026, Utkarsh)

- **Not found, but keep looking (phone only, no contract change):** when a Find can't guide yet, Marco says why, asks the user to turn slowly (the chest camera sweeps the room), and keeps watching for 60 s (`Lookout` in `ios/Marco/Core/NavigationContext.swift`, wired in `AppModel`).
  - **Covers:** `never_seen`, `not_where_last_seen`, and found answers whose state the phone won't guide to (`stale` after a new map, `picked_up`, `missing`). Those used to say "Position unavailable, wait for tracking", which blamed tracking.
  - **The item's next `seen`, `moved` or `put_down` event** starts guidance with "Polo! I see your keys. At two o'clock, three steps, on the table." It is held until the pose is fresh in the same scope.
  - **Ends on** a new Find, Stop, capture start or stop, or a new scope (silently). When 60 s pass with no sighting: "I still haven't spotted your keys. Ask me again any time."
  - **Not registered:** no watch ("Send me a photo of them").
  - **Verified:** 20 new Swift checks (334 in all); the MarcoPolo app builds for iOS with no errors or warnings. Not run on the phone.
- **Server hub fix (`server/marco/hub.py`, taken over while Vedant is away):** every socket has its own outbox and writer task, so `send` never waits on a socket.
  - A full outbox drops its oldest message: 1000 for the phone, 200 for Photon, 30 for a dashboard.
  - A send stuck for over 10 s drops that socket; the clients reconnect.
  - `send`'s signature is unchanged, so `app.py` needed no edit.
  - **Verified:** `tests/test_hub.py` (3 tests) includes a live uvicorn server with a dashboard that handshakes and never reads, so TCP backpressure is real. Before the fix, 1 of 40 frames got through in 3 s and the phone's `find` answer never came. After it, all 40 went through and the answer arrived. Server suite: 90 passed, 1 skipped.
- **Removed from the docs:** voice registration from the vest camera ("remember this as my wallet"). It is not being built.
- **Registration, open problem (not fixed; `brain.py` is being changed by another agent):** registering a name twice adds a second item with the same name, and `find` answers with the first, older one. Retaking a photo should replace the item, not add one.
- **Demo note:** walk the vest past each prop once before asking, so the item is placed. The watch above is the fallback, not the plan.

## Phone to AirPods: how spatial audio commands reach the ears (October 17, 2026, Utkarsh)

- **The model, now written down** (`ios/README.md`, "How the server's messages reach the AirPods"):
  - the AirPods take no commands: the phone renders everything binaurally and streams stereo; the AirPods send head motion back;
  - each server message becomes a sound plus a `SoundAnchor` (`ios/Marco/Core/SoundScene.swift`): ahead, or a point in the room;
  - room points are re-projected through the fused head yaw every tick.
- **Gaps closed (phone only; no contract change):**
  - **Labels come from the jar:** a touched known item's label (voice memo or text) and the `what_is_this` answer play from `touch.position`. Before, they played from in front of the face.
  - **Other lines from their place:** "You left your keys" plays from where the keys are; `label_ready` from where the item was last seen. Marco's own lines stay ahead.
  - **Room points outside guidance:** they are now kept in place as the head turns. Before, positions were only updated while guiding.
  - **The guided item's beacon and a line from elsewhere no longer fight over one position:** the voice has its own point (`SpatialAudio.say(_:at:)`, `playFile(_:at:)`, `moveVoice`). The older `place`, `say(_:atItem:)` and `playFile(_:atItem:)` are unchanged, which Sandeep's local spatial tools use.
  - **AirPods drop-out:** `RouteWatch` checks that the output is headphones with 2 channels, settled over 1.5 s against route flaps. If not, the beacon and tone go quiet and Marco says so; when they return, "Headphones connected." Before, beeps went to the chest speaker silently (STATUS records the AirPods falling back to the Mac speakers in a Mac test).
- **Not possible on iOS:** opting out of the system's own spatialization (`setIntendedSpatialExperience(.bypassed)` is visionOS only). Spatialize Stereo stays off by hand.
- **Checked, not built (per the user):** iPhone to Vultr and Vultr to iPhone.
  - Every §4 message is sent by the real server and decoded by the phone, contract-tested.
  - WSS round trip 67 ms and frames 202 in 83–118 ms, measured from the Mac with the app's bytes.
  - Not yet from the phone itself.
- **Verified:** 14 new Swift checks (348 in all); the MarcoPolo app builds for iOS with no errors or warnings; `test_ios_contract.py` 5 passed. Nothing here has run on the phone: hour-one test 8 in `ios/README.md`.
- **Not done (perception, other owners):** head pitch is not used (yaw only), and there is no motion prediction for the ~150 ms Bluetooth latency.
