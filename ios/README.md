# Marco iPhone app (Utkarsh)

The default screen is now the approved Paper V3 control panel: Instrument Sans, open Camera / LiDAR / Audio / Server rows, a Voice commands status, and a circular Start/Stop control. It uses this app's existing ARKit, upload, speech, head tracking and spatial-audio engine. There is one app source tree, `Marco/`; the earlier standalone AVFoundation panel is not compiled alongside it.

Optional Mac spatial-audio experiments are kept locally in `ios/spatial/` and
ignored by Git. The app's spatial-audio implementation is in `Marco/Audio/`.

Open **`MarcoPolo.xcodeproj`**, select the **MarcoPolo** scheme and your signing team, then Run. This checked-in project uses the same `Marco/` sources as the XcodeGen option below, so XcodeGen is optional. Both projects use Swift 5 and iOS 17+. The three bundled Instrument Sans fonts and licence are in `Marco/Design/Fonts/`; font names are registered in `Marco/Info.plist` and `project.yml`.

Use the gear to set the server's Tailscale address. Start waits for camera permission, and **Running** appears after the first real AR frame. The Server row reflects the actual phone WebSocket, so it is **Not connected** before starting. The Audio row reports the active route and its OS spatial-audio flag; this does not identify a headphone model or certify active head tracking. This ARKit pipeline requires a LiDAR-capable phone.

Stop cancels listening/guidance, pauses capture, closes the phone socket and releases the audio session. Backgrounding performs the same stop and saves the world map; returning does not auto-start. The running screen offers **Open LiDAR view** (`LiDAR/`): the live LiDAR depth, full screen (red near, blue far, dim camera past 5 m), with only a close button. It only reads the existing AR session's frames. Debug builds retain the original tools under Connection → Developer tools; the main panel does not expose analytics or item setup.

See [VERIFICATION.md](VERIFICATION.md) for build/test results and device checks still required.

The six reproducible iOS audit findings are fixed; see [AUDIT-FIXES.md](AUDIT-FIXES.md). Guidance cancels on tracking loss, a stale pose or a coordinate reset; ask Find again after tracking recovers. Voice Stop also cancels pending Find replies. The portable suite now passes 204 checks.

With iPhone **VoiceOver** enabled, the panel exposes hardware status and recovery instructions through native accessibility. **Read status** replays the current summary; two-finger double-tap starts/stops capture. Important failures and connection changes are announced without moving focus. No separate app mode or new permission is needed for screen-reader speech. See [ACCESSIBILITY.md](ACCESSIBILITY.md) for Apple research and the required hands-on VoiceOver checks.

The phone half of [docs/INTERFACES.md](../docs/INTERFACES.md):
- **Sensors in:** ARKit + LiDAR, Vision hands, AirPods head motion, speech.
- **To the server:** frames, poses, hands and queries.
- **Back out:** spatial audio, Marco's voice and haptics, driven by what the server says.

Everything the contract needs is wired. What's left is the hour-one tuning on the real phone.

## Set up (once)
You need:
- a Mac with Xcode 26 and its iOS platform (Xcode > Settings > Components);
- the **iPhone 16 Pro** (LiDAR), with Developer Mode on (Settings > Privacy & Security);
- AirPods Pro 3;
- the Tailscale app on the phone, signed in to the team tailnet.

A free Apple ID works. Apps signed with a free Personal Team expire after 7 days: just run again from Xcode.

**Option A (one command):** `brew install xcodegen && cd ios && xcodegen && open Marco.xcodeproj`. Then plug in the phone and Run.
- `project.yml` already signs with Utkarsh's Personal Team (`7764XWK2G5`) as `com.utkarshlal.marco`. Anyone else: change both there and run `xcodegen` again.
- `xcodegen` also writes `Marco/Info.plist` (generated, git-ignored) for the one key Xcode can't generate: file sharing, so Finder shows the app's recordings.

**Option B (by hand):**
1. Xcode > New > Project > iOS App. Name it `MarcoApp`, interface SwiftUI, language Swift. Save it in `ios/xcode/` (that folder is ignored by git).
2. Delete the template's `ContentView.swift` and `MarcoAppApp.swift`.
3. Drag the folders in `ios/Marco/` into the project. Pick "Reference files in place" and tick the app target.
4. Target > Build Settings:
   - Swift Language Version = **Swift 5**;
   - Default Actor Isolation = **nonisolated** (Xcode 26 defaults new projects to MainActor; this code uses its own queues);
   - iOS Deployment Target = 17.0.
5. Target > Info: add these four keys (the strings are in `project.yml`):
   - `NSCameraUsageDescription`
   - `NSMicrophoneUsageDescription`
   - `NSSpeechRecognitionUsageDescription`
   - `NSMotionUsageDescription`
6. Signing: pick your Personal Team. On first run, trust the profile on the phone under Settings > General > VPN & Device Management.

**Then:**
1. Keep **Spatialize Stereo off** for the AirPods (Control Center > hold volume). The app renders HRTF itself, and system spatialisation would apply it twice.
2. **Put the phone on the tailnet:** install the Tailscale app and sign in with a login that's on the server's allow-list (`TAILSCALE_ALLOWED_LOGINS`). Keep it connected while Marco runs.
3. **Point the app at the server and press Start.** All processing runs on the server; the phone only captures, sends and plays sound.
   - **Primary: the Vultr GPU box** (`deploy/vultr/`): `https://marco-gpu.<tailnet>.ts.net`.
   - **Fallback: a Mac at the venue.** Start the server there, then publish it on the tailnet:
     ```
     cd server
     MARCO_AUTH=tailscale TAILSCALE_ALLOWED_LOGINS=<your tailnet login> ../poc/.venv/bin/python -m marco.app
     tailscale serve --bg 8000
     ```
     and enter `https://<server-mac>.<tailnet>.ts.net`. The stub needs no models. See [server/README.md](../server/README.md).
   - Right after Start, the log says "Server OK: n items, ms", or what to fix (Tailscale off, refused by the allow-list, unreachable), from `Net/ServerCheck.swift`.

## Files
| File | What it does | Builds on macOS? |
|---|---|---|
| `App/MarcoApp.swift`, `App/ContentView.swift` | app entry, V3 control panel, connection settings and camera preview | no (UIKit/SwiftUI iOS) |
| `App/DiagnosticsView.swift` | original sensor and voice-command tools, accessible in Debug builds | no (UIKit/SwiftUI iOS) |
| `App/AppModel.swift` | wiring: AR frames to uploads/poses/hands, server messages to audio, voice to queries, the 60 Hz guidance tick | no (ARKit) |
| `Capture/ARSessionManager.swift` | ARKit + LiDAR (`smoothedSceneDepth`), ARWorldMap save every 30 s, relocalize on launch, fresh map after 30 s | no (ARKit) |
| `Capture/FrameEncoder.swift` | sensor JPEG 960x720 (no rotation, no EXIF tag), depth/confidence maps as arrays (handles padded rows) | yes, tested |
| `Capture/HandTracker.swift` | Vision hand pose (orientation `.up`), 21 joints in the server's order, the 9x9 depth patches | yes, contract-tested |
| `Net/Uploader.swift` | `POST /v1/frames` multipart, latest frame wins; `POST /v1/items`; label audio fetch | yes, contract-tested |
| `LiDAR/LiDARScreen.swift`, `LiDAR/LiDARRenderer.swift` | the LiDAR view: the live depth map, full screen, from the shared AR session (read-only). The renderer can also draw a room point cloud and item labels; the screen doesn't use them | no (ARKit, MetalKit) |
| `Core/DepthVision.swift`, `Core/LiDARShaderSource.swift` | its maths (colour scale, depth probe, projection, item labels) and its shaders, compiled at runtime so the build needs no Metal Toolchain | yes, tested (shaders run on the Mac's GPU) |
| `Net/ServerCheck.swift` | one `GET /v1/items` at Start, turned into a sentence that says what to fix | yes, unit-tested |
| `Net/PhoneSocket.swift` | `/v1/phone` WebSocket: JSON both ways, reconnect with backoff, pings, holds map/query messages until connected | yes |
| `Audio/SpatialAudio.swift` | `AVAudioEnvironmentNode` HRTF: beeps, ding, steady tone, spatial speech, label playback. The audio route: stereo out to the AirPods, speech in from the AirPods' mic (iOS 26 Bluetooth high-quality recording) or the iPhone's | yes |
| `Audio/HeadTracker.swift` | `CMHeadphoneMotionManager` (AirPods yaw), plus its rate, jitter and latency for the debug screen | yes |
| `Voice/Listener.swift` | on-device speech: always listening for "Marco ..." (or "Marco", a blip, then the request), plus hold-to-talk; registered item names as recognizer hints; restarts on route changes | yes |
| `Core/Vocabulary.swift` | what was said to a registered item: "car keys" to keys, "specs" to glasses case, "walet" to wallet; ambiguous ("jar") goes to the server as said | yes, unit-tested |
| `Core/Guidance.swift` | the §7 sequence as pure logic (`Guidance`) and the POC 4 head fusion (`HeadFusion`) | yes, unit-tested |
| `Core/Messages.swift`, `Wire.swift`, `Geometry.swift` | every message of the contract, the byte formats, the server's angle conventions | yes, contract-tested |
| `Core/Lines.swift` | everything Marco says, and voice-to-intent parsing | yes, unit-tested |
| `Core/Config.swift` | rates and tunables | yes |
| `Core/Recorder.swift` | records what the phone sends, on the phone, in the server's own layout (`server/marco/recorder.py`) | yes, contract-tested |
| `Core/Health.swift` | AirPods stream stats and the rate meters on the debug screen | yes, unit-tested |

Threads:
- **ARKit queue (60 Hz):** poses at 10/s, frames at 1/s and hands at 15/s are picked here.
- **Encode queue:** the JPEG and depth for each frame.
- **Hand queue:** Vision (frames are dropped while it's busy).
- **Socket queue:** the WebSocket.
- **Main thread:** the guidance tick at 60 Hz and the UI.

ARFrames are only held while their data is copied out; ARKit stalls if they pile up.

## Test
```
sh ios/check.sh                                     # type-checks the macOS-buildable files, runs 286 checks
cd server && ../poc/.venv/bin/python -m pytest -q tests/test_ios_contract.py
```
The second command builds the Swift core and feeds the exact bytes it produces to the real server:
- the frame upload;
- pose, hand, map, query and guidance messages;
- hand patches, checked byte for byte against the server's reference.

It also checks the angles against the server's geometry.

The contract test also records a short walk with `Core/Recorder.swift` and checks it with the server's own `Session` reader and `tools/check_recording.py`.

The ARKit/UIKit files need the iOS SDK. The whole app builds with no errors or warnings:
```
cd ios && xcodegen && xcodebuild -project Marco.xcodeproj -scheme Marco -destination 'generic/platform=iOS' CODE_SIGNING_ALLOWED=NO build
```
Add tests in `Tests/main.swift` for any logic you add to `Core/`.

## Hour-one tests on the phone (record what you find in STATUS.md)
1. **Start.** Expect socket connected, tracking normal, and "frames accepted" going up once a second. A 422 in the log says exactly what the server didn't like.
2. **"Where are my keys?" against the stub.** You should hear "Polo! Behind you, two steps..." coming from 2 m behind where you first stood. Then:
   - muffled beeps;
   - a ding when you face it;
   - the stub's fake hand counts down and "touches" after about 8 s.
3. **AirPods.** Put them in and watch the `airpods` row: expect about 25 Hz; note the jitter, the latency, and how far the raw yaw drifts in 10 minutes with your head still.
   - **Yaw sign:** turn your head right: "head yaw" must go up. Or turn your whole body a few times and read `sign check`. If it's inverted, flip the toggle.
   - Then check that the beacon stays put in the room while you turn your head.
   - The fusion keeps its alignment through Bluetooth gaps under 2 s, re-aligns at once when the AirPods re-zero (a jump faster than any head turn), and re-aligns after 8 s if it was set while your head was turned. `sign check` also shows how often it re-aligned.
4. **Hand stream.** Point at a counter-height jar lid and watch `hand` messages arrive (server log or dashboard). Vision orientation `.up` is the default; if fingertips are poor, try `.right` and tell Vedant.
5. **Relaunch.** Kill the app and start it in the same room. The log should show "map relocalized" within 30 s; otherwise "Getting my bearings" and a new map.
6. **Record 5 minutes from the vest.** Either way gives the same files:
   - **With the server:** it records everything under `server/data/sessions/<session_id>/`.
   - **On the phone, no server or network needed:** leave the server URL empty (or keep it), press Start, then Record. Stop, then Export (AirDrop a zip) or Finder > iPhone > Files > Marco > `sessions/<session_id>/`. The layout is the server's own, so every server tool reads it.

   Check it with `python tools/check_recording.py <session folder>` (in `server/`) and hand it to Vedant.
7. **AirPods mic.** With the AirPods in, read the `mic` row under Ask. Expect `mic AirPods Pro (..., high quality)` and `out AirPods Pro, 2 ch`.
   - **2 ch is the one that matters:** if the output drops to 1 channel in this mode, the beacon loses its direction. Flip "Use the iPhone mic" and tell the team.
   - "HQ off" or "no HQ": the route didn't take the mode (check iOS 26 and the AirPods firmware). The iPhone mic is used instead.
   - Say "Marco, where are my keys?" from 3 m away with the phone in the vest. Note how long it takes from your last word to "Polo!". The mode can add input latency; the listener answers 0.45 s after a whole registered name, 0.9 s otherwise.
   - Say "Marco", wait for the blip, then "where's my wallet". The window is 5 s.
   - Put the AirPods in after Start: the `mic` row should switch to them within a second or two.

Without the app, you can still feed the pipeline real iPhone data: record with the free Stray Scanner app and convert it with `server/tools/stray_session.py`.
