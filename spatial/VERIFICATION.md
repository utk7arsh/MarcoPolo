# Spatial voice and AirPods verification

Checked October 17, 2026 on the development Mac. The app uses Apple's
[`AVAudioEnvironmentNode`](https://developer.apple.com/documentation/avfaudio/avaudioenvironmentnode)
for HRTF audio and
[`CMHeadphoneMotionManager`](https://developer.apple.com/documentation/coremotion/cmheadphonemotionmanager)
for head motion, rather than a separate AirPods SDK. Item positions come from the
phone/server world map; headphone motion does not locate the objects themselves.

## Bug fixed

`place()` previously positioned the voice straight ahead while `voiceAtItem` was
false. `say(atItem: true)` and `playFile(atItem: true)` only changed that flag,
leaving the voice centered until another guidance tick arrived. The first spatial
voice could therefore use an old or centered position.

`SpatialAudio` now remembers the latest item position and sets the voice position
immediately when either playback entry point selects an item voice. General
announcements continue to originate ahead. No wire formats changed.

## Automated results

- `sh spatial/check-render.sh`: **21 passed**, using the app's actual `SpatialAudio`
  class and Apple's offline HRTF renderer. It exercises mono content through the
  voice-file path, immediate left/right placement, centered front/back positions,
  distinct front/back filtering, returning from a general announcement to an item
  voice, moving a target, and left/right ear changes after simulated head turns.
  Four additional checks verify that ±30° head turns shift front and rear sources
  toward opposite ears, with the expected signs.
- Before the fix: **6 failures**; initial left/right/front/back voices all had
  the same 0.54 dB right/left energy bias.
- After the fix: right **+14.40 dB**, left **−15.01 dB**, front **+0.54 dB**,
  back **−0.73 dB**. These are rendered channel-energy differences for the test
  signal, not measured localization accuracy or a promised volume at the ear.
- `sh ios/check.sh`: **204 passed**.
- After relocation into `spatial/`, all **21 renderer and 18 scripted-simulator
  checks** passed again; **two withdrawn-option checks** verify both the script
  and helper executable reject `--guidance`. The relocated helper builds/signs.
- Xcode Debug build for generic iOS Simulator: **BUILD SUCCEEDED**. This is a build,
  not an iPhone or simulator runtime test.

## Connected hardware observations

The first device query showed only the Mac speakers; a subsequent query confirmed
the connected AirPods Pro as the default Bluetooth output with **two channels at
48 kHz**. Their display name does not establish the AirPods generation.

The bundled macOS probe, using the app's own `HeadTracker`, received **308 distinct
motion samples at approximately 34.1 Hz**, with a **77.46° yaw range** during its
12-second window. This proves a motion stream on this Mac and connection. It does
not independently calibrate the physical right-turn sign, drift, or end-to-end
motion-to-sound latency.

## Repeat the physical check

Use the Mac's Sound settings to select the AirPods as output. Wear both earbuds.
For this test, turn macOS Spatialize Stereo off so it does not add another
spatialization layer to the app's already binaural output.

```sh
sh spatial/check-airpods.sh           # 12-second motion check; no microphone capture
sh spatial/check-airpods.sh --listen  # 28-second spatial voice and head-turn check
sh spatial/check-airpods.sh --front-back # 46-second tracked voice/beacon retest
sh spatial/check-airpods.sh --simulate-approach # explicit scripted sound demo only
```

The helper is compiled from the app's existing audio and head-tracker classes.
It launches as an ad-hoc-signed macOS app with its own Motion usage description.
Allow its Motion request if prompted. Listening mode checks that the default
output is Bluetooth before playing, uses 35% mixer gain, and does not record
the microphone or access a server.

The first four identical phrases come from left, right, front and behind at
five-second intervals. Keep the head facing forward for these. At 20 seconds,
the final phrase uses live head yaw relative to the initial orientation and asks
the listener to turn their head. The perceived source should stay in its original
direction. This checks yaw-only anchoring in a stationary Mac test; the production
phone app additionally fuses ARKit torso/world motion.

## Remaining evidence

The 28-second listening run completed, with **1,029 motion samples at about
36.8 Hz**, spanning **42.74°** of yaw. Motion was available for positions 2–5;
the first phrase ran before the initial motion sample, as expected for the static
left-hand source. The helper sent all five phrases to the live audio engine.
The wearer reported that **left and right were clear**, while the other directions
needed improvement. Front/back localization therefore remains unresolved; perceived
world anchoring was not separately confirmed. This feedback does not identify the
cause or establish a complete localization pass. No microphone or acoustic loopback
measurement was made. The macOS Spatialize Stereo
setting was requested but not independently verified. Front/back filtering being different does not
prove that a particular listener distinguishes the directions.

Still verify on the physical chest-mounted iPhone: real object positions,
right-turn sign, whole-body turns, walking, motion loss/reconnection, audio-route
changes, simultaneous speech recognition, and VoiceOver coexistence. The current
phone-microphone fallback remains the baseline; this check does not validate the
roadmap's proposed iOS 26 high-quality Bluetooth microphone mode.

## Documentation review after wearer feedback

Rechecked the production code against Apple documentation and the approved roadmap.
This review changes no runtime behavior.

- **Ownership:** `docs/INTERFACES.md` §1 and §7 place audio rendering and head fusion
  on the phone. The server supplies world-space object positions and touch events.
  Local rendering avoids a network round trip for each head movement. The Mac
  helper reuses these classes for development; it is not a server implementation.
- **Audio graph:** mono player → `AVAudioEnvironmentNode` → stereo output is the
  appropriate graph. The code explicitly selects `.HRTFHQ` and `.pointSource`;
  default equal-power panning would not provide the same spatial filtering.
  Apple says available algorithms depend on the output format; checking
  `applicableRenderingAlgorithms` would improve route validation. It is not an
  established fix for this listener's front/back difficulty.
  Sources: [environment node](https://developer.apple.com/documentation/avfaudio/avaudioenvironmentnode),
  [renderingAlgorithm](https://developer.apple.com/documentation/avfaudio/avaudio3dmixing/renderingalgorithm).
- **Manual head tracking:** Apple's WWDC23 example reads headphone device motion,
  records a starting attitude and computes relative motion. Our app uses yaw and
  an ARKit-aligned offset, then transforms the item into listener coordinates;
  the environment listener stays unrotated. This is a coherent horizontal
  tracking implementation. Verify the physical yaw sign and starting alignment;
  it is not full pitch/roll compensation.
  Source: [What's new in Core Motion, headphone section](https://developer.apple.com/videos/play/wwdc2023/10179/).
- **Automatic tracking is a different path:** Apple's
  [`isListenerHeadTrackingEnabled`](https://developer.apple.com/documentation/avfaudio/avaudioenvironmentnode/islistenerheadtrackingenabled)
  requires `com.apple.developer.coremotion.head-pose`. It is not currently enabled.
  Do not enable it on top of our listener-relative source correction: that would
  apply head rotation twice. Switching requires a deliberate coordinate/reference
  design; an additional API flag alone does not improve this architecture.
- **Front/back:** interaural timing and level cues can be ambiguous; controlled
  listener head movement can help disambiguate them. The wearer's result is
  consistent with that phenomenon, but we have not established its cause here.
  Source: [Wightman and Kistler, 1999](https://pubmed.ncbi.nlm.nih.gov/10335634/).

### Next focused test and implementation priorities

1. Improve the test before changing HRTF settings. In the existing tour, positions
   1–4 deliberately use yaw zero; only position 5 compensates for head motion.
   The short final utterance also does not exercise a continuing guidance beacon.
2. Use a repeated broadband beacon for separate fixed front and back sources,
   with live head compensation throughout. First verify the sign: for a source
   ahead, turning the head right should move the source left relative to the ears;
   for a source directly behind, that same turn should shift it toward the right.
   Measure perceived front/back choices with unlabeled trials before supplying
   spoken answers. This is a proposed next test, not a completed result.
3. Retain the production spoken direction (`Lines.polo`) and muffled rear beacon.
   These already implement the roadmap's front/back assistance, but the first
   listening tour used identical phrases and did not exercise the beacon sequence.
4. Verify startup alignment, then torso/world anchoring on the chest-mounted
   iPhone. Do not move rendering to the backend or promise that a filter change
   will resolve the perceptual ambiguity.

### Focused retest

Added `--front-back` to the existing helper. It waits up to five seconds for a
fresh motion sample before starting audio, uses live head compensation in every
stage, and pauses audio if samples become stale. The production app's audio and
motion classes are unchanged for this retest.

The sequence is left (5 s), right (5 s), A (12 s), B (12 s), then spoken rear
guidance plus a muffled beacon (12 s). A and B use the same unmuffled broadband
beep, so rear muffling does not supply the answer during those comparisons.
For reproducibility, A is behind and B is ahead in the initial head reference.
The final rear segment separately demonstrates the existing assistance cues.

This is a stationary yaw test, not an iPhone walking test or a statistically
validated localization study. Per-stage yaw ranges and missing-motion ticks are
logged. Record wearer responses separately from rendering and motion results.

The focused retest completed: **1,755 distinct motion samples at about 38.2 Hz**,
**2,612 tracked render-update ticks**, and **zero missing-motion ticks**. All five
audio stages ran with fresh motion. The extended offline suite passed all **21**
checks. Wearer A/B direction and anchoring responses are pending. Logged yaw min/max
ranges cross the ±180° boundary, so their numerical difference must not be read
as a physical head-turn angle or an accuracy measurement.

Requested replay: **1,641 samples at about 36.6 Hz**. A/B both ran with motion;
the final rear-cue stage logged a motion loss and correctly paused audio, with
65 missing-motion update ticks across the run. Do not treat the final stage as
uninterrupted playback. Wearer direction/anchoring feedback is still pending.

## Guidance clarity feedback and proposed next check

The wearer subsequently confirmed left/right but could not reliably infer
front/back, distance, or how to move. The supplied comparison describes another
implementation; its source files were not independently inspected.

The Mac tours do not test walking distance: the ear position stays at the origin,
targets remain 2 m away, and the focused beacon interval is a constant 0.65 s.
Head turns rotate the relative position without changing its length. These tours
bypass `Guidance.tick`, so they do not exercise the app's existing distance cadence,
facing ding, within-reach announcement, or fingertip-proximity transition.

Current production behavior is different: `Guidance.beepInterval` decreases from
1 s at 3 m to 0.5 s at 1 m and 0.325 s at 0.5 m; the normal beep has an 880 Hz
fundamental, six harmonics and some noise. The distance attenuation reference
is 1 m with rolloff 0.5. Apple's curve therefore provides no attenuation change
inside 1 m of the ears. More beeps per second and a higher acoustic pitch are
different design choices; increasing pitch alone is not an established solution.

Proposed smallest improvement, not yet implemented:

- Use spoken direction/approximate distance to explain the initial turn.
- Check chest/body heading before issuing any instruction to walk forward;
  the current facing lock is head-relative, which does not establish body alignment.
  A clear-path decision is separate from target direction and is not established
  by the sound beacon.
- Retain a distinct alignment cue and reserve pulse speed for approach distance,
  rather than having the same pulse speed encode both angle and distance.
- Retain hand-to-item proximity for the last reach. The phone stays on the chest;
  a phone-distance bubble or frozen ear position is not an appropriate substitute.
- Exercise the real Guidance state machine in a clearly labelled simulated
  approach before physical chest-mounted iPhone testing. Do not ask the wearer
  to walk toward a Mac-only virtual target as though its position were mapped.

The comparison's steeper attenuation is supported by
[Apple's inverse-distance formula](https://developer.apple.com/documentation/avfaudio/avaudioenvironmentdistanceattenuationmodel/inverse),
but can substantially reduce far-target volume; do not copy the values without
listening tests. Front/back uncertainty remains a perceptual test issue, supported
by [head-movement localization research](https://pubmed.ncbi.nlm.nih.gov/25161605/).

## Withdrawn automatic guidance demonstration

The original `--guidance` mode described below was rejected by the wearer:
they reported staying still while the whole approach and touch sequence ran.
The automatic sequence cannot validate action-dependent feedback. The public
`--guidance` option now exits before initializing motion or audio. The sequence
is retained only under the explicit `--simulate-approach` option, for controlled
sound demonstrations, not as a working navigation test.

The historical implementation used the existing Mac helper.
It uses the production `Guidance`, `SpatialAudio`, `Lines` and `HeadTracker`
classes. A test-only trajectory simulates chest translation and fingertip reach;
there is no iPhone capture, server, real object or physical walking measurement.

The wearer stays seated. The voice explains simulation, then asks for a slow
head turn toward a source 30° right at 3 m. An internal head-facing lock plays the
production double ding. Alignment must remain within the production threshold
for 0.6 seconds. If not confirmed within 25 seconds, the voice explicitly says
so before continuing the distance-only demonstration. This continuation is part
of the rejected behavior. A measured yaw crossing a threshold alone also does
not establish that the wearer physically turned; startup stability, drift and
the physical yaw sign still need checking.

After another reminder to stay seated, the virtual body approaches from 3 m to
0.5 m over 18 seconds. Production pulse timing gets faster, narration says two
meters and one meter, and production guidance announces within reach. The
simulated hand then moves from 0.5 m to 0.05 m over seven seconds, triggering
the production steady tone at 0.3 m and the touch silence/"Got it" sequence.
There are no physical haptics in this Mac helper. It does not issue an instruction
to physically walk, and it does not implement the proposed production body-heading gate.

Head motion remains real and freshness-gated. Motion loss pauses both audio and
the simulated clock. Test narration is ahead; item speech/beacons use the target
position. Beacons pause for narration. The run has a 110-second wall-time limit.

After the wearer reported another silent start, the log showed no fresh motion
within the original five-second startup window. Corrected the helper to start
audio first with a ding and spoken preparation message, wait up to **30 seconds**
for motion, and speak the failure reason on timeout. Live stdout is unbuffered
for diagnosis. These changes are in the Mac test helper, not production guidance.
The corrected launch logged audio started, motion ready and entry into the intro.
Full completion and hearing feedback are recorded separately below when available.

The historical live run **executed all scripted stages**, with an internal
alignment flag set (physical alignment is **not confirmed**),
**2,210 motion samples**, **zero missing-motion ticks**, **34 scheduled beeps**,
**three guidance dings** (repeated head-facing locks), and **one steady-tone entry**.
The simulated touch and finished stages were reached. These logs establish only
execution. The wearer then reported no movement while all stages happened, so
this run fails their requested interaction test. Body distance, hand reach and
touch were simulated; the apparent head lock needs further diagnosis.

`sh spatial/check-simulation.sh`: **18 checks passed**, exercising the scripted
sequence, fixed world target, monotonic approach, progressively faster beeps,
distance narration, near-hand tone, touch and explicit unconfirmed-alignment
timeout. These checks validate the simulator, including behavior the wearer
rejected, and are not movement/navigation acceptance tests. Full portable Swift
suite: **204 passed**. The helper compiled.

The initial live attempt did **not** play: the AirPods connection disappeared
between route checks and launch, and the default output reverted to Mac speakers.
The helper correctly rejected playback. Hardware playback/listening feedback is
pending reconnection. The shell wrapper now checks the helper's completion log,
because LaunchServices alone can return success when the helper rejects a route.

The macOS Spatial Audio menu is distinct from our own HRTF rendering. Apple's
[support guide](https://support.apple.com/en-gb/guide/airpods/dev00eb7e0a3/web)
states that availability depends on the app/content. Connected stereo output
and a working motion stream must still be verified separately; this Mac's
intermittent loss of the AirPods route is an observed additional limitation.
