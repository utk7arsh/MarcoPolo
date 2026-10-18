# iOS audit fixes — October 17, 2026

All six reproducible findings in the supplied iOS audit are addressed. These changes preserve the existing device/server wire formats.

| Finding | Correction |
| --- | --- |
| Invalid tracking, stale pose or discarded map keeps guidance running | Only a normal, relocalized pose less than 0.5 seconds old is eligible. Every pose/Find/target is scoped to capture generation, map ID and coordinate revision. Tracking loss invalidates that revision immediately on the AR queue, cancels the search, silences cues and gives a non-positional recovery message. Tracking recovery requires a new Find. Explicit stale/missing/picked-up/registered locations cannot start guidance. |
| Delayed Find overrides voice Stop | A single pending Find must match its query ID and current coordinate scope. Stop, newer Find and capture/map replacement invalidate earlier replies. Unsolicited and duplicate replies are ignored. Other query kinds remain independent. |
| Unsaved restart reuses map ID | Each capture start without a successfully loaded world map allocates a fresh UUID and resets mapping/relocalization/save timing state. Restoring a saved map retains its ID and waits for normal tracking. |
| Async save resurrects discarded map | Save completion returns to the serial AR queue and checks its captured map/capture/save ticket before any disk write or saved event. Reset/restart invalidates old callbacks; an older overlapping save cannot overwrite a newer one. A final save may complete after pause if no reset/restart occurred. |
| Moved item speaks obsolete surface | Retargeting updates position and surface, including clearing an unknown surface. Movement discards old hand proximity/facing lock; duplicate sightings do not repeat the within-reach line. |
| New label ignored at touch | Label updates refresh the active target as well as the registry. Touch uses the latest text/audio, with the latest text as fallback if the file is missing or playback fails. Unreadable audio conversion throws instead of appearing to succeed silently. |

## Verification

- `sh ios/check.sh`: **204 passed, 0 failed**. The 34 new portable assertions cover scoped/fresh poses, cancellation and supersession, map/save generations, movement and duplicate sightings, updated labels and audio fallback cues.
- The audit's controlled reproductions were regenerated from the current app methods and ARSessionManager source: **23 AppModel checks and 11 ARSessionManager checks passed**. Output recorders substitute audio/network, and ARKit/storage doubles control callback timing. These demonstrate the reported control-flow fixes, not physical sensor behavior.
- Unsigned Xcode Debug Simulator and Release device builds passed. The complete ARKit/UIKit app is compiled by these checks; the portable suite alone does not compile it.
- All four Swift/server contract tests passed against rebased backend `8aa0ae1`. The remaining backend suite passed 72 tests, with one optional ARKitScenes sample check skipped because that dataset is absent locally. Eight Photon scaffold checks also passed. Test dependencies were installed in temporary environments outside the repository.

The temporary reproduction harnesses are under `<local-evidence>/marco-ios-fix-regressions/`; the maintained pure-state regressions are in `Tests/main.swift`.

## Hardware checks remain

AirPods route/engine-configuration changes and audio-session interruptions still need a physical test. The audit did not reproduce a route failure, so this change adds no speculative audio recovery subsystem. Also check VoiceOver speech/focus/Magic Tap, real LiDAR, permission recovery, relocalization and HRTF on the iPhone. See [ACCESSIBILITY.md](ACCESSIBILITY.md), [VERIFICATION.md](VERIFICATION.md) and the hour-one checklist in [README.md](README.md).
