# iOS V3 and VoiceOver verification

Latest audit regression run, October 17: **204 Swift checks passed**, plus **23 AppModel and 11 ARSessionManager controlled reproduction checks**. Unsigned Xcode Debug Simulator and Release device builds passed. See [AUDIT-FIXES.md](AUDIT-FIXES.md) for fixes, recovery policy and hardware limits. The results below document the earlier V3/VoiceOver build baseline.

October 17, 2026, after pulling main through `755ee6b`.

- The checked-in `MarcoPolo.xcodeproj` compiles the canonical `Marco/` app. No second app entry point or parallel AVFoundation capture session is included. It matches the teammate Swift 5 / iOS 17 build settings.
- Xcode Debug device build: passed, unsigned.
- Xcode Release device build: passed, unsigned.
- Xcode Debug Simulator build: passed, unsigned.
- `sh ios/check.sh`: **170 passed, 0 failed**. This includes the existing 102 checks, 24 control-panel checks and 44 accessibility checks covering status summaries, specific failure/recovery instructions, camera action hints, server/headphone disconnection, voice/audio startup failures, tracking recovery, and suppression of repetitive announcements.
- Built app contains all three Instrument Sans faces and UIAppFonts registrations. Permission declarations cover camera, microphone, speech, motion and local networking.

Device Release and Simulator Debug builds were rerun after adding the VoiceOver implementation. No simulator runtime is installed on this Mac (rechecked October 17), so the compiled app has not been launched in Simulator. The Paper image in `design/` is not a runtime screenshot.

The VoiceOver implementation uses SwiftUI labels/values/hints, a native Read status button, Magic Tap, escape actions, and queued UIKit announcements. It requests no new permissions. Apple research and the hands-on VoiceOver test procedure are in [ACCESSIBILITY.md](ACCESSIBILITY.md). Compilation and pure-logic tests do not establish that speech, focus, gestures, or guidance/VoiceOver audio coexist correctly on hardware; those checks remain open.

Still requires the iPhone: visual/Dynamic Type/VoiceOver checks, allow/deny camera permission and recover through Settings, start/preview/stop/restart, lock/background stop, actual LiDAR capture and upload, Bluetooth route changes, head motion, speech permission callbacks, server reconnection and map relocalization. Confirm real audio and camera resources are released after Stop. Use the existing hour-one checklist in README.md.

## Audit regression fixes: latest verification

The V3/VoiceOver results above describe the earlier implementation. The current audit fixes additionally passed:

- `sh ios/check.sh`: **204 passed, 0 failed**, including 34 new checks for pose validity, Find cancellation/correlation, map-save lifetime, moved surfaces and live label updates.
- Full unsigned Xcode Debug build for generic iOS Simulator: passed after the AppModel, guidance, map lifecycle and audio fallback fixes.

Directional guidance now requires a fresh pose in the current capture/map scope. Tracking loss and map changes cancel searches; late or stale Find answers cannot restart them. Fresh tracking runs receive fresh map IDs, and obsolete/overlapping saves cannot overwrite the current world map. Moved surfaces and new labels update the active target, including text fallback when label audio cannot play.

These checks do not establish physical iPhone, AirPods or VoiceOver runtime behavior. Audio interruption and route-change recovery still require a device check; this change does not add that recovery flow. Server/iOS Python contract tests were not rerun in this checkout because its Python environment and dependencies are unavailable.
