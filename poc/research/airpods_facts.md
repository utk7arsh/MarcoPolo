# AirPods facts for the Marco Polo emulator

Compiled 2026-10-14. Confidence tags:
- MEASURED: an instrumented measurement (ours, or a paper or log with numbers).
- DOCUMENTED: Apple docs, SDK headers or Apple support pages.
- ANECDOTAL: a forum post, blog or third-party site with no published method.
- INFERENCE: our own reasoning, not checked on a device.
- UNKNOWN: no source found.

Local evidence lived under `poc/research/` (saved sources are not in the repository). Paths below are relative to that directory.
- SDK headers: `sdk_headers/iPhoneOS27.0.sdk/` (also 14.0 through 26.5)
- Apple doc text: `apple_docs/batch1.txt`, `batch2.txt`, `batch3_personalizing_spatial_audio.txt`, `supported-capabilities-ios.html`
- Forum tag pages: `forums/`
- RTINGS pages: `papers/latency_fork/` (the numbers are locked behind a paywall in the saved HTML)
- Papers: `papers/daga2025_m2s/`, `papers/headacoustics_m2s/`, `papers/airpods/` (two arXiv 2609.* earbud-IMU papers, saved here)

---

## Numbers for the emulator

| Parameter | Value / range | Confidence | Source |
|---|---|---|---|
| Headphone motion update rate | 25 Hz (40 ms period). AirPods Pro 1 and Pro 2 confirmed; other models assumed the same | MEASURED (3 independent reports) and ANECDOTAL | EarDA (arXiv 2406.16943, AirPods Pro 2): "set to the highest value allowed by API, which is 25 Hz". SO 71612270: "sample at 25Hz using AirPod Pros v1". airtracker README: "~25 Hz" |
| Can the app set the rate? | No. There is no `deviceMotionUpdateInterval` on CMHeadphoneMotionManager | DOCUMENTED (absent from the header) | `CMHeadphoneMotionManager.h` (iOS 27 SDK) |
| Sample jitter or drops | Not measured. For the emulator, assume 40 ms ±5 ms with occasional Bluetooth gaps of 100–500 ms | UNKNOWN (the jitter figure is our guess) | none |
| Sensor-to-callback latency | Not measured. For the emulator, assume 20–50 ms (Bluetooth link plus fusion) | UNKNOWN | none |
| Populated fields | attitude (quaternion, rotation matrix, Euler angles), rotationRate, gravity, userAcceleration, sensorLocation, timestamp. `magneticField` is effectively absent (see the magnetometer row) | DOCUMENTED (CMDeviceMotion fields) and MEASURED (papers use the fused attitude, device-frame acceleration and gyroscope) | arXiv 2609.34978 §3: "fused attitude, device-frame acceleration, and gyroscope"; `CMDeviceMotion.h` |
| Attitude reference frame | Arbitrary yaw with Z vertical (gravity-referenced pitch and roll). Yaw zero is wherever the stream started, and the app cannot choose a reference frame | DOCUMENTED (there is no `...UsingReferenceFrame:` start method) and ANECDOTAL | `CMHeadphoneMotionManager.h`; `CMAttitude.h` |
| Yaw re-zeroing by the OS | Yaw re-centres abruptly when another Spatial Audio playback starts (reported on macOS) | ANECDOTAL | Apple forums thread 844940 (quoted in Q1) |
| Magnetometer | None listed on AirPods Pro 3, so there is no absolute heading and yaw drifts freely | DOCUMENTED (spec sheet) | apple.com/airpods-pro/specs lists "Motion-detecting accelerometer, Speech-detecting accelerometer ..." and no magnetometer |
| Yaw drift rate | No number found. Several apps ship a slow "pull yaw back to centre" correction. For the emulator, model a random walk of about 0.5–2°/min plus a 5–20° step at each re-centre or reconnect event | UNKNOWN (the drift numbers are our guess); the existence of drift is ANECDOTAL | airtracker README; Anand Chowdhary note lists "yaw drift"; pods-head-tracker reports "0.2° of noise when the head is still" and "3–4° of unwanted roll during pure yaw or pitch movement" |
| Accuracy against optical mocap | No published AirPods-against-Vicon or OptiTrack study found. The DAGA 2025 paper's DUT was a Pixel 7 Pro (under 2° error), not AirPods. For the emulator, use 2–5° static error | UNKNOWN | `papers/daga2025_m2s/daga2025_94.pdf` p.3 |
| Perceptual motion-to-sound (M2S) latency threshold | About 60–100 ms | DOCUMENTED (a citation in a peer-reviewed paper) | DAGA 2025 (Kentgens et al.), citing Brungart 2005: "Perceptual thresholds for M2S latencies found in literature are in the order of about 60…100 ms" |
| Reference M2S for a non-Apple head-tracked renderer | 93.4 ms mean (Wi-Fi phone sensor, wired headphones). Renderer updates every 20 ms | MEASURED | DAGA 2025 p.3 |
| AirPods output latency, normal A2DP/AAC | Pro 2: 126 ms (keyboard-tap-to-sound on iPad; built-in speaker 83 ms). Pro 1: 144–167 ms. `outputLatency` reports about 163 ms (Pro 1). macOS `kAudioDevicePropertyLatency` reports 160 ms. The log shows 151 ms "in-ear latency" | MEASURED (Coyle) and ANECDOTAL (forums, logs) | stephencoyle.net/airpods-pro-2; discussions.apple.com/thread/256097737; Apple forums thread 764070 |
| AirPods output latency, Game Mode | About 60 ms (log: "In ear-Latency change ... latency 60MSec"). Only for apps the system treats as games | ANECDOTAL (system log) | Apple forums thread 764070 |
| AirPods SBC latency (Android/PC) | Pro 2: 160 ms. Pro 3: 183 ms | MEASURED (RTINGS) | `papers/latency_fork/rtings_pro2_vs_pro3.html` |
| HFP (call profile) output latency | About 9 ms reported, but HFP is mono narrowband, which breaks binaural audio. Do not use it | ANECDOTAL | discussions.apple.com/thread/256097737 |
| Apple engine listener smoothing | About 40 ms lag. 25 Hz step updates are click-free | MEASURED (ours) | prior PoC measurement |
| AVAudioEnvironmentNode yaw sign | Positive listener yaw means the head turns right (clockwise seen from above) | MEASURED (ours) | prior PoC measurement |
| Estimated total motion-to-sound, app renders on iPhone with its own CMHeadphoneMotionManager loop | 0–40 ms (sample wait, mean 20) + 20–50 ms (sensor link) + about 40 ms (engine smoothing) + 5–20 ms (I/O buffer) + 120–165 ms (A2DP). Total about 200–300 ms. In Game Mode, about 140–200 ms | INFERENCE | built from the rows above |

Emulator defaults: 25 Hz step updates, 250 ms total motion-to-sound with ±30 ms spread, yaw random walk of 1°/min plus re-centre steps, 3° static error. Sweep total latency from 150 to 350 ms to test robustness.

---

## Entitlements (already established; repeated for completeness)

- **Head Pose** (`com.apple.developer.coremotion.head-pose`) is required for `AVAudioEnvironmentNode.isListenerHeadTrackingEnabled`, `PHASEListener.automaticHeadTrackingFlags` and `kAudioUnitProperty_SpatialMixerEnableHeadTracking`. The capability table marks it available to ADP and ADEP only, not free "Apple Developer" accounts. DOCUMENTED: `apple_docs/supported-capabilities-ios.html` (the row has check marks in the ADP and ADEP columns only) and `apple_docs/batch3_personalizing_spatial_audio.txt`.
- **Spatial Audio Profile** (`com.apple.developer.spatial-audio.profile-access`) is also ADP and ADEP only. DOCUMENTED: same table, same row pattern.
- **CMHeadphoneMotionManager** needs only `NSMotionUsageDescription`. DOCUMENTED: `apple_docs/batch1.txt`: "If this key is absent, the system crashes your app when you start device-motion updates."
- macOS anecdote: atmos-control reports that personalized HRTF and head tracking work "inside an app-hosted AUSpatialMixer for an unentitled/self-signed binary" on macOS. ANECDOTAL (github.com/yukij3/atmos-control). Do not assume this holds on iOS.

---

## Q1. CMHeadphoneMotionManager

**API surface.** DOCUMENTED in `CMHeadphoneMotionManager.h`, `CMHeadphoneMotionManagerDelegate.h` and `CMHeadphoneActivityManager.h` (iOS 27 SDK):
- Available from iOS 14.
- Start, stop and status: `startDeviceMotionUpdates`, `startDeviceMotionUpdatesToQueue:withHandler:`, `stopDeviceMotionUpdates`, `deviceMotion` (latest sample, pull model), `isDeviceMotionAvailable`, `isDeviceMotionActive` and `authorizationStatus`.
- Connection status: `startConnectionStatusUpdates` / `stopConnectionStatusUpdates`, `isConnectionStatusActive`, and the delegate callbacks `headphoneMotionManagerDidConnect:` / `headphoneMotionManagerDidDisconnect:`. The header says connection status "can be used to register for delegate updates before requesting device motion data."
- There is no update-interval property and no reference-frame selector.
- `CMHeadphoneActivityManager` (iOS 18) adds headphone activity (walking, running and so on; "automotive and cycling are not supported") plus Connected/Disconnected status.

**sensorLocation.** DOCUMENTED: `CMDeviceMotion.sensorLocation` takes the values `Default`, `HeadphoneLeft` and `HeadphoneRight` ("the location of the sensors used to compute the device motion data").
- The EarDA paper says "IMU signals from each earbud in a pair are fused together automatically in API". arXiv 2609.34978 says the AirPods are "exposed by iOS as a single fused head-motion stream". MEASURED/ANECDOTAL.
- So the app gets one stream, whose source bud is reported per sample. We assume it switches when a bud is removed (UNKNOWN). The emulator should model a possible attitude discontinuity when the source switches.

**Update rate.** 25 Hz. Sources are in the table: EarDA (Pro 2), Stack Overflow (Pro 1), airtracker and the Chowdhary note ("at around 25 Hz"). Two SO answers independently agree. No per-model differences have been reported. For AirPods 3/4, Pro 3 and Max we assume 25 Hz (UNKNOWN).

**Jitter and latency.** No published measurement found. UNKNOWN. Recommendation: log `CMLogItem.timestamp` against the arrival time on the PoC device.

**Reference frame and drift.**
- Yaw is relative to an arbitrary start heading.
- There is no magnetometer (DOCUMENTED spec sheet, and the class offers no reference-frame option), so there is no absolute heading and no compass correction.
- Drift exists (airtracker: "pull yaw back to center at a slow, adjustable rate" to absorb sensor drift). Re-centre happens on reconnect (airtracker) and when another app's Spatial Audio starts (forums thread 844940, macOS, unanswered). The OP of 844940 wrote: "when I start playing audio with Spatial Audio set to either Head Tracked or Fixed, the yaw appears to recenter as soon as I press play ... Is AirPods head-motion data designed so that the application currently using Spatial Audio takes precedence ...?" (https://developer.apple.com/forums/thread/844940).
- Implication: never trust absolute AirPods yaw. Use only short-term yaw deltas, or fuse with the phone's heading.

**Accuracy against mocap.**
- No AirPods-specific validation study found. Searched OpenAlex and DDG: AirPods accuracy, mocap, cervical ROM.
- "On the Effect of User Tracking on Perceived Source Positions in Mobile Audio AR" (2023, AirPods Pro plus iPad ARKit) is perceptual only: "participants tend to prefer more stable tracking solutions".
- The local DAGA 2025 and HEAD acoustics abstracts (AES Headphone Conf 2025, ISEAT 2025) measure M2S on "various commercial off-the-shelf spatial audio devices", but only the abstracts are saved, with no AirPods numbers. The full AES 2025 paper is a gap: it probably contains AirPods M2S values. UNKNOWN.

**Background delivery.**
- No Apple doc covers background delivery for headphone motion. UNKNOWN.
- Related ANECDOTAL evidence (forum thread 841001 in `forums/tag_core-motion_1.html`, iOS 26.5.2, CMMotionManager): background device motion keeps flowing only while a Core Location session is active. Location on: "received 1366 / expected ~1373 (99.5%)". Location off: "received 2 / expected ~1286 (0.16%)".
- Marco Polo plays audio continuously, so the `audio` background mode will probably keep it alive. Untested.

**Single stream and multi-app.** One fused stream per headset (above). Multiple apps appear to share one orientation reference, which the system Spatial Audio owner can reset (thread 844940). ANECDOTAL.

**Raw IMU.** Apple DTS (forums thread 814483, Feb 2026) only points to CMDeviceMotion: "I am pretty sure you can use CMHeadphoneMotionManager to gather CMDeviceMotion data from a paired + connected AirPods Pro 3". There is no raw accelerometer or gyroscope API, though the papers say rotationRate is "clean raw gyroscope"-like.

**Supported models.** DOCUMENTED (support.apple.com/en-us/102469): "AirPods 3, AirPods 4, AirPods 5, AirPods Pro, and AirPods Max use Spatial Audio and head tracking". Beats Fit Pro is also reported to work (tukuyo sampler README).

**iOS gotcha.** ANECDOTAL (SO 79779924): `isDeviceMotionAvailable` is true but no samples arrive on iOS 18/26 with AirPods 2. The authorization status was 1, i.e. restricted. AirPods 2 have no head tracking. Check the model and `authorizationStatus`.

## Q2. Apple automatic head tracking semantics

**What the APIs say.** DOCUMENTED:
- `AVAudioEnvironmentNode.listenerHeadTrackingEnabled`: "On capable devices, listener orientation will be automatically rotated based on user's head-orientation if enabled." (header, iOS 18 and later)
- PHASE `PHASEAutomaticHeadTrackingFlagOrientation`: "listener orientation will be automatically rotated based on user's head-orientation". `...FlagPosition`: "listener position will be automatically set based on user's position". iOS 18, and the Position flag is presumably meaningful only on visionOS.
- `kAudioUnitProperty_SpatialMixerEnableHeadTracking` (`AudioUnitProperties.h`, iOS 18, macOS 12.3): "Enables or disables head-tracking using AirPods motion sensors. **This tracking will apply a second rotation on top of head yaw, pitch, and roll parameters.**"
  - This is the only explicit statement on composition. On AUSpatialMixer, the app-set head yaw, pitch and roll and the AirPods rotation are composed.
  - INFERENCE: AVAudioEnvironmentNode (built on the same mixer) composes the app-set `listenerAngularOrientation` with head pose in the same way. Our earlier engine measurements are consistent with an app-set listener orientation being honoured. Verify with Head Pose on.
- Apple guide text (`batch3_personalizing_spatial_audio.txt`): head tracking "works by simulating the effect of detaching the left and right speakers from the person's head and virtually placing them in stationary positions in the physical environment". This states the intent (world-stationary) but not the reference.

**Device-anchored or world/initial reference: not documented for the app APIs (UNKNOWN).**
- The system media mode is documented as device-anchored. iPhone Control Center "Head Tracked: The audio you're listening to will sound like it's coming from your iPhone or Mac" (support.apple.com/guide/airpods/dev00eb7e0a3). DOCUMENTED.
- Settings > Accessibility > AirPods has a "Follow iPhone" toggle. With it on (the default), the soundstage follows the phone. Its exact wording was not retrievable from Apple.
- Community descriptions (akulab.io) say the system is "continuously nudging the reference ... a reference that follows your average orientation slowly enough to go unnoticed". ANECDOTAL.
- For the app-level APIs, no doc says whether the iPhone's IMU is included. Both hypotheses are plausible:
  - (a) Head relative to the phone. Then a chest-mounted phone gives head-relative-to-torso, and the scene rotates with the body when the user turns their whole body. Good for "item is 30° to your right" relative to the torso, bad for world-fixed items unless the app counter-rotates the sources by the phone's world yaw from ARKit or CMMotionManager.
  - (b) Head relative to a slowly re-centring initial reference. Then the scene drifts toward the user's average facing.
- **This is the top on-device test.** Rotate the whole body 90° with the phone on the chest and the head fixed relative to the torso, and check whether a source at 0° stays straight ahead.

**Robust design for Marco Polo (INFERENCE).**
- Do not depend on the automatic mode's reference.
- Compute the world-to-head rotation yourself as phone world yaw (ARKit or CMMotionManager `xMagneticNorthZVertical`, chest-mounted, so this is torso yaw) plus head-relative-to-torso yaw. Get the second term from CMHeadphoneMotionManager deltas, and re-zero it whenever the head is still and roughly aligned with the torso. People look roughly forward on average.
- Then set the listener orientation manually, with automatic tracking off. This needs no Head Pose entitlement, so it works on a free account.

**Other gotchas found.** ANECDOTAL (forums thread 772475, Apple engineer, Feb 2025):
- AVAudioEnvironmentNode does not light up the Control Center Spatial Audio UI, "but that doesn't mean audio is not spatial".
- Inputs must be connected in **mono** format, or there is no positioning. Use `renderingAlgorithm = .HRTFHQ`.
- One user only got real binaural output after setting the App Store category to "Games - Music Games" (Nov 2025, macOS). INFERENCE: this ties in with the iOS 18 game-category system spatialisation (`AVGameBypassSystemSpatialAudio`) and Game Mode.

**visionOS only.** `AVAudioSessionSpatialExperience` with anchoring strategies `Scene` and `Front` ("the user's concept of 'front' which the user can move with an intentional gesture") is marked `API_UNAVAILABLE(ios)` in `AVAudioSessionTypes.h`. It is not available to us.

## Q3. Personalized Spatial Audio HRTF for third-party apps

Yes, on iOS 18 and later, with the paid-only Spatial Audio Profile entitlement. DOCUMENTED:
- `com.apple.developer.spatial-audio.profile-access` "applies the personalized spatial audio profile someone makes in Settings to your app's audio output for ... AVAudioEngine, AUSpatialMixer ..., PHASE". (`apple_docs/batch3_personalizing_spatial_audio.txt`)
- AUSpatialMixer has `kAudioUnitProperty_SpatialMixerPersonalizedHRTFMode` (iOS 18): `Off` = "Use generic HRTF", `On` = "Use personalized HRTF, if available", `Auto` = "Follow system preferences".
- `kAudioUnitProperty_SpatialMixerAnyInputIsUsingPersonalizedHRTF` (read-only) "should be queried after AU is initialized" because "the value of ...PersonalizedHRTFMode alone does not guarantee that personalized HRTF is being used". It requires `kSpatializationAlgorithm_UseOutputType` with `kSpatialMixerOutputType_Headphones`.
- PHASE and AVAudioEngine apply the profile automatically when the entitlement is present (no per-node switch in the headers).
- Gotcha (ANECDOTAL, forums thread 772104): an Xcode Cloud build rejected the key with "not supported on iOS". The thread is unanswered, and the poster suspected an iOS 17 deployment target.
- Profile-capable headphones: support.apple.com/en-us/102596 lists "AirPods Pro 1, AirPods Pro 2, AirPods Pro 3, AirPods Max, AirPods 3 or later" and some Beats.
- Hackathon impact: a free account gets the generic HRTF only. That is fine; personalisation is a nice-to-have.

## Q4. System spatial audio re-centring when walking

- Apple documents no time constant. UNKNOWN.
- ANECDOTAL evidence of continuous slow re-centring:
  - Reddit r/airpods "Spatial audio recenters after a few seconds" (fetch blocked; title and search snippet only).
  - Apple Community threads 252977727 and 252325635 ("Spatial Audio 'center' moves" when the user works off to the side of the iPad).
  - akulab.io describes a test: "hold about thirty degrees for half a minute, and the scene should gradually treat the new heading as forward".
  - pods-head-tracker (its own algorithm on the AirPods' private stream): "A stop shorter than approximately 3 seconds does not cause a re-center".
- No source covers walking specifically. With "Follow iPhone", the soundstage follows the phone's heading as you walk. With the phone on a chest lanyard, that means it follows the torso.
- Emulator model: re-centre toward the device or average heading with a time constant of about 5–30 s. Treat this as a tunable parameter (UNKNOWN). Our own manual-orientation design avoids the re-centring entirely, because we do not use the system mode.

## Q5. Head gestures and stem press

- **Head gestures (nod/shake) are not exposed to third-party apps.** DOCUMENTED as Siri-only and ABSENT from the headers.
  - Apple support says "To use head gestures to respond to Siri, Announce Calls and Announce Notifications must be on". Models: AirPods 4, AirPods 5, AirPods Pro 2, Pro 3, Max 2.
  - The WWDC24 newsroom post describes them only as "Siri Interactions".
  - No gesture API appears in the CoreMotion headers (`CMHeadphoneMotionManager.h`, `CMHeadphoneActivityManager.h`) or in `AVAudioApplication.h` (iOS 27 SDK).
  - Workaround: detect nod and shake ourselves from CMHeadphoneMotionManager pitch and yaw rates at 25 Hz. A nod is about 1–2 Hz and well within Nyquist.
- **Stem press.** DOCUMENTED (support.apple.com/guide/airpods/devb2c431317), same on Pro 2/3 and AirPods 4:
  - Press = play/pause.
  - Double-press = next track.
  - Triple-press = previous track.
  - Press-and-hold = noise-control mode or Siri. This is system-owned and not delivered to apps.
  - INFERENCE (standard iOS behaviour, not re-verified here): these reach the Now Playing app as MPRemoteCommandCenter `togglePlayPauseCommand`/`playCommand`/`pauseCommand`, `nextTrackCommand` and `previousTrackCommand`. The app must hold an active playback audio session and be the Now Playing app (set `MPNowPlayingInfoCenter`).
  - Usable vocabulary: 3 discrete commands, for example "where is X", "next item" and "repeat".
- `AVAudioApplication` input-mute gesture: the header says the mute state can change "due to a Bluetooth audio accessory gesture (certain AirPods / Beats headphones)". The handler `setInputMuteStateChangeHandler` is macOS only. On iOS, `AVAudioApplicationInputMuteStateChangeNotification` exists, and it only applies while the app records audio. DOCUMENTED.

## Q6. AirPods Bluetooth output latency

Per model, MEASURED where noted:
- **AirPods Pro 2: 126 ms average.** MEASURED, end-to-end tap to sound on iPad. The built-in speaker was 83 ms on the same test, so Bluetooth adds about 43 ms on top of the app/OS path. Source: https://stephencoyle.net/airpods-pro-2 ("average latency of 126ms vs the original's 167ms ... only 43ms worse than the built-in speakers (at 83ms)").
- **AirPods Pro 1: 144–167 ms.** Same source; the two values come from different iOS versions.
- AVAudioSession `outputLatency` with AirPods Pro on iPhone 13: "A2DP: ~163ms", "HFP: ~9ms". ANECDOTAL (https://discussions.apple.com/thread/256097737). The 9 ms HFP figure is the reported value, not measured, and HFP is mono 16 kHz, which is unusable for binaural audio.
- macOS:
  - `kAudioDevicePropertyLatency` "seems to always report 160ms for AirPods".
  - Game Mode log: "In ear-Latency change received from BTServer, latency 151MSec" then "latency 60MSec". The poster called it "a full 100ms reduction".
  - ANECDOTAL (system log, Apple forums thread 764070).
- RTINGS SBC (non-Apple source device): Pro 2 160 ms, Pro 3 183 ms. MEASURED (`papers/latency_fork/rtings_pro2_vs_pro3.html`). RTINGS iOS-latency values are locked in the saved HTML.
- soundlatencytest.com: AirPods 3 and Pro 1 at 150–180 ms, Pro 2 and Max at 120–150 ms, "~20ms" in Low Latency mode. ANECDOTAL, no method given. Treat as low quality.
- AirPods 4 and Pro 3 on iOS: no measured number found. UNKNOWN. Assume Pro 2-like (120–160 ms).
- Apple says AirPods Pro deliver "the best wireless audio latency Apple has ever delivered for mobile gaming" in Game Mode (WWDC24 newsroom), with no number. DOCUMENTED claim only.

**Implications for Marco Polo (INFERENCE).**
- When the phone renders the binaural audio, every head turn reaches the ears only after the full output path: about 200–300 ms motion-to-sound, versus a perceptual threshold of 60–100 ms. Sources will audibly "swim" during fast turns.
- Mitigations:
  1. Short, repeating chimes. Localisation happens mostly when the head stops.
  2. Predict head yaw about 100–150 ms ahead from `rotationRate` (gyro extrapolation). Clamp the prediction to avoid overshoot.
  3. Encourage slow head sweeps of 30–60°/s.
  4. Game Mode (about 60 ms) would cut the total to about 140–200 ms, but it appears only for game-category apps. Untested for our app category.
- Using Apple's automatic head tracking does not avoid the Bluetooth latency either: rendering still happens on the phone. Apple may use internal prediction. UNKNOWN.

---

## Open unknowns, in priority order for on-device tests

1. Automatic head-tracking reference (device-anchored or initial/world). Do the whole-body-turn test with the phone on the chest.
2. CMHeadphoneMotionManager arrival jitter and sensor-to-callback latency. Log timestamp against arrival time at 25 Hz.
3. AirPods yaw drift in °/min over 10 minutes with the head still, and the re-centre triggers (playback start, bud removal, sensorLocation switch).
4. End-to-end motion-to-sound on our pipeline. Use a turntable or tap test: a click through AirPods recorded with the phone mic, plus a gyro step.
5. Whether MPRemoteCommandCenter stem events arrive while AVAudioEngine plays chimes in the background.
6. AirPods M2S values in Kentgens et al., AES Headphone Technology 2025 (full paper not retrieved).
