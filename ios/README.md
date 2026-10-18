# Marco iPhone app (Utkarsh)

The phone half of [docs/INTERFACES.md](../docs/INTERFACES.md):
- **Sensors in:** ARKit + LiDAR, Vision hands, AirPods head motion, speech.
- **To the server:** frames, poses, hands and queries.
- **Back out:** spatial audio, Marco's voice and haptics, driven by what the server says.

Everything the contract needs is wired. What's left is the hour-one tuning on the real phone.

## Set up (once)
You need:
- a Mac with Xcode 16 or later;
- the **iPhone 16 Pro** (LiDAR), with Developer Mode on (Settings > Privacy & Security);
- AirPods Pro 3;
- the Tailscale app on the phone, signed in to the team tailnet.

A free Apple ID works. Apps signed with a free Personal Team expire after 7 days: just run again from Xcode.

**Option A (one command):** `brew install xcodegen && cd ios && xcodegen && open Marco.xcodeproj`. Then:
1. In `project.yml` (and in Xcode's Signing tab), change the bundle id to something unique to you.
2. Pick your Personal Team under Signing & Capabilities.
3. Plug in the phone and Run.

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
2. On the server Mac, start the server:
   ```
   cd server
   MARCO_AUTH=tailscale TAILSCALE_ALLOWED_LOGINS=<your tailnet login> ../poc/.venv/bin/python -m marco.app
   tailscale serve --bg 8000
   ```
   The stub needs no models. See [server/README.md](../server/README.md).
3. In the app, enter `https://<server-mac>.<tailnet>.ts.net` and press Start.

## Files
| File | What it does | Builds on macOS? |
|---|---|---|
| `App/MarcoApp.swift`, `App/ContentView.swift` | app entry, debug screen (buttons for every voice command) | no (UIKit/SwiftUI iOS) |
| `App/AppModel.swift` | wiring: AR frames to uploads/poses/hands, server messages to audio, voice to queries, the 60 Hz guidance tick | no (ARKit) |
| `Capture/ARSessionManager.swift` | ARKit + LiDAR (`smoothedSceneDepth`), ARWorldMap save every 30 s, relocalize on launch, fresh map after 30 s | no (ARKit) |
| `Capture/FrameEncoder.swift` | sensor JPEG 960x720 (no rotation, no EXIF tag), depth/confidence maps as arrays (handles padded rows) | yes, tested |
| `Capture/HandTracker.swift` | Vision hand pose (orientation `.up`), 21 joints in the server's order, the 9x9 depth patches | yes, contract-tested |
| `Net/Uploader.swift` | `POST /v1/frames` multipart, latest frame wins; `POST /v1/items`; label audio fetch | yes, contract-tested |
| `Net/PhoneSocket.swift` | `/v1/phone` WebSocket: JSON both ways, reconnect with backoff, pings, holds map/query messages until connected | yes |
| `Audio/SpatialAudio.swift` | `AVAudioEnvironmentNode` HRTF: beeps, ding, steady tone, spatial speech, label playback; AirPods stay in A2DP | yes |
| `Audio/HeadTracker.swift` | `CMHeadphoneMotionManager` (AirPods yaw) | yes |
| `Voice/Listener.swift` | on-device speech: always listening for "Marco ...", plus hold-to-talk | yes |
| `Core/Guidance.swift` | the §7 sequence as pure logic (`Guidance`) and the POC 4 head fusion (`HeadFusion`) | yes, unit-tested |
| `Core/Messages.swift`, `Wire.swift`, `Geometry.swift` | every message of the contract, the byte formats, the server's angle conventions | yes, contract-tested |
| `Core/Lines.swift` | everything Marco says, and voice-to-intent parsing | yes, unit-tested |
| `Core/Config.swift` | rates and tunables | yes |

Threads:
- **ARKit queue (60 Hz):** poses at 10/s, frames at 1/s and hands at 15/s are picked here.
- **Encode queue:** the JPEG and depth for each frame.
- **Hand queue:** Vision (frames are dropped while it's busy).
- **Socket queue:** the WebSocket.
- **Main thread:** the guidance tick at 60 Hz and the UI.

ARFrames are only held while their data is copied out; ARKit stalls if they pile up.

## Test
```
sh ios/check.sh                                     # type-checks the macOS-buildable files, runs 98 unit tests
cd server && ../poc/.venv/bin/python -m pytest -q tests/test_ios_contract.py
```
The second command builds the Swift core and feeds the exact bytes it produces to the real server:
- the frame upload;
- pose, hand, map, query and guidance messages;
- hand patches, checked byte for byte against the server's reference.

It also checks the angles against the server's geometry.

The ARKit/UIKit files don't build without the iOS SDK. **Build in Xcode before changing them**, and add tests in `Tests/main.swift` for any logic you add to `Core/`.

## Hour-one tests on the phone (record what you find in STATUS.md)
1. **Start.** Expect socket connected, tracking normal, and "frames accepted" going up once a second. A 422 in the log says exactly what the server didn't like.
2. **"Where are my keys?" against the stub.** You should hear "Polo! Behind you, two steps..." coming from 2 m behind where you first stood. Then:
   - muffled beeps;
   - a ding when you face it;
   - the stub's fake hand counts down and "touches" after about 8 s.
3. **AirPods yaw sign.** Turn your head right: "head yaw" must go up. If it goes down, flip the toggle. Then check that the beacon stays put in the room while you turn your head.
4. **Hand stream.** Point at a counter-height jar lid and watch `hand` messages arrive (server log or dashboard). Vision orientation `.up` is the default; if fingertips are poor, try `.right` and tell Vedant.
5. **Relaunch.** Kill the app and start it in the same room. The log should show "map relocalized" within 30 s; otherwise "Getting my bearings" and a new map.
6. **Record 5 minutes from the vest.** The server records everything under `server/data/sessions/<session_id>/`. Check it with `python tools/check_recording.py server/data/sessions/<id>` and hand it to Vedant.

Without the app, you can still feed the pipeline real iPhone data: record with the free Stray Scanner app and convert it with `server/tools/stray_session.py`.
