# VoiceOver support for the control panel

Researched and implemented October 17, 2026.

## Decision

Use iPhone **VoiceOver** (Settings → Accessibility → VoiceOver) for reading and operating the app. SwiftUI already exposes native text, buttons, fields and sheets to assistive technology. Our job is to provide accurate labels, grouped status values, recovery instructions and announcements for important asynchronous changes. An additional in-app accessibility mode or text-to-speech service is unnecessary for this panel. No new entitlement, SDK, package or permission was added.

VoiceOver speech is separate from microphone and speech-recognition permission. Denying those permissions disables the app's spoken commands, not VoiceOver navigation or status reading. The existing positional speech and beacon renderer continues to handle object guidance.

## Implemented

- Camera, LiDAR, Audio, Server and Voice commands are individually readable elements with labels and current values. Decorative artwork and separators are hidden. The camera preview itself is not represented as an interpreted description of the room.
- **Read status**, shown automatically while VoiceOver is enabled, reads a fresh summary including failures and recovery steps. It remains usable when capture or navigation audio cannot start because it uses the system accessibility announcement API.
- Start/Stop is a native button with its current action, state and hint. VoiceOver's two-finger double-tap (Magic Tap) invokes the same action. Permission-pending and unsupported states cannot be bypassed by this gesture.
- Meaningful changes announce camera start/stop/failure, server connection/loss, headphone output changes, navigation-audio startup failure, speech permission/startup failure, and lost/restored position tracking. A server that has not connected gets one reminder after 12 seconds while the panel is visible.
- Updates settle for 400 ms before announcement; identical status and changes between tracking limitation reasons stay quiet. Automatic announcements queue behind current VoiceOver speech and preserve focus. Pending failures are retained while an OS permission dialog or app sheet covers the panel. Read status uses the latest information on demand.
- Microphone/speech denial appears visibly, with a route to iPhone Settings. Opening connection settings and dismissing settings/preview use native sheet behavior; the preview also has a labelled Close control and the VoiceOver escape action.
- The OS spatial-audio flag stays informational: changing that flag alone is not announced as failure of our separate HRTF renderer. VoiceOver does not speak distance, yaw or camera telemetry on every update.

## Verification and remaining device checks

`sh ios/check.sh` tests status wording, recovery guidance, changes, disconnections, suppression of duplicate announcements, and the conditions for a connection reminder. Xcode compiles the actual SwiftUI/UIKit implementation. See [VERIFICATION.md](VERIFICATION.md) for current results.

Build success and pure-logic tests do not verify spoken output, actual gesture routing, audio mixing, modal focus or screen-reader usability. No iOS Simulator runtime is installed on this Mac. Before claiming full VoiceOver support, run these tasks on the iPhone, with VoiceOver on, without looking at the screen:

1. Read each hardware row and the full summary; start and stop using both the button and Magic Tap. Test an unsupported device as well.
2. Deny camera access, hear the recovery instructions, open Settings and return. Deny microphone/speech access separately and confirm VoiceOver still reads the panel.
3. Leave the server offline for 12 seconds, connect it, disconnect it, and reconnect. Confirm one useful warning per meaningful change and no stale announcements after stopping or opening a sheet.
4. Disconnect/reconnect the AirPods; read the output route and spatial flag. Check that VoiceOver remains audible alongside object guidance and that spoken UI is not accidentally interpreted as a wake-word command, particularly through the speaker.
5. Open and dismiss both sheets, including the escape gesture; verify focus enters the sheet, cannot reach background controls, and returns sensibly. Check every control with large Dynamic Type.

## Apple references

- [SwiftUI accessibility fundamentals](https://developer.apple.com/documentation/swiftui/accessibility-fundamentals): built-in accessibility, labels, values and grouping.
- [VoiceOver evaluation criteria](https://developer.apple.com/help/app-store-connect/manage-app-accessibility/voiceover-evaluation-criteria): operable common tasks, concise labels, state changes, logical navigation and real VoiceOver testing.
- [VoiceOver environment value](https://developer.apple.com/documentation/swiftui/environmentvalues/accessibilityvoiceoverenabled): follows the user's system setting, including changes while the app is open.
- [Accessibility announcements](https://developer.apple.com/documentation/uikit/uiaccessibility/notification/announcement) and [queuing announcements](https://developer.apple.com/documentation/uikit/uiaccessibilityspeechattributequeueannouncement): system-managed status speech.
- [Supporting accessibility gestures](https://developer.apple.com/library/archive/featuredarticles/ViewControllerPGforiPhoneOS/SupportingAccessibility.html): Magic Tap invokes the primary action; escape dismisses modal content.
