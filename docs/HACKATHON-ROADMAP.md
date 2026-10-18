# Marco Polo: approved hackathon roadmap

The user designated their whole-system diagram as the primary roadmap on
October 17, 2026. This document records that diagram for future agents and edits.
It defines the intended system, not a claim that every connection is already working.
Read `../STATUS.md` for implementation evidence and `INTERFACES.md` for wire formats.

**Revised speech scope:** the user dropped caretaker voice labelling and Scribe
from the demo. Photos and typed names remain; ElevenLabs is intended for Marco's
spoken responses (TTS). The output route and iOS spatial playback are implemented
and deployed, with live backend and silent Swift-rendering checks passed; physical
playback checks remain. See [`SPEECH-OUTPUT-PLAN.md`](SPEECH-OUTPUT-PLAN.md). This supersedes
the corresponding part of the original diagram.

## Demo outcome

A blind or low-vision wearer asks where a registered object is. A voice and beacon
come from its remembered position as the wearer turns and approaches. A visible
fingertip identifies the touched item; a caretaker can supply its typed name
through iMessage. The dashboard lets the team observe and explain this flow.

## Components and responsibilities

| Component | Agreed role |
| --- | --- |
| AirPods Pro 3 | Head motion through `CMHeadphoneMotionManager`; stereo HRTF output. Diagram also proposes iOS 26 high-quality Bluetooth microphone recording, with the phone microphone as fallback. Actual hardware generation and mic mode must be checked, not inferred from its name. |
| Chest-mounted iPhone 16 Pro, `ios/` | ARKit world tracking, smoothed LiDAR depth, saved/relocalized ARWorldMaps; Vision hand pose with 21 joints and 9×9 depth patches; local wake/push-to-talk speech; 60 Hz head-fused guidance and haptics; cached synthesized replies and offline session recording. |
| Private Marco server, `server/` | Python/FastAPI ingest and recording under `data/sessions/`; OWLv2 image-guided detection and DINOv2 verification at 1 fps; frame-specific pose/depth projection; items, wearer track and seen/moved/missing/left-behind timeline; voxel room map and named surfaces; fingertip proximity within 15 cm and five-message touch vote; `find`, `what_is_this`, `set_place`; phone, Photon and dashboard feeds; label storage. |
| Photon bridge, `photon/` | Node/TypeScript Photon 2.0 `@photon-ai/api`, Socket.IO events with saved cursor; caretaker allow-list; idempotent posting; HEIC/PNG→JPEG conversion; typed labels only; loopback health endpoint and doctor checks. Phone never calls the bridge directly. |
| Dashboard, `frontend/` | React/Vite observer and setup view: live chest video with boxes, map, sound radar and timeline. Use `VITE_DATA_SOURCE=api` and the Vite `API_PROXY_TARGET`. The server now implements the snapshot/event/command adapter, with phone acknowledgements for Find/Stop. Live snapshot, events and camera were verified in Chrome; physical command execution is not proved by this read-only check. |
| Photon cloud and caretaker Messages | Managed iMessage line; REST sends and attachments plus incoming events. Revised demo uses typed names and captioned registration photos. Recordings are not used as labels. |
| ElevenLabs speech output | Generate Marco's spoken responses server-side, then play them through the existing iOS spatial graph. Cache common phrases; retain Apple speech as fallback. No caretaker transcription is required by the revised demo. The authenticated `/v1/speech` route returns WAV for the existing iOS voice node. Deployed live generation, caretaker-reply integration and silent Swift rendering pass; physical playback checks remain. |

## Connections and deployment

1. AirPods ↔ iPhone: Bluetooth stereo and headphone motion.
2. iPhone → private server: HTTPS camera/depth upload, 1 fps, latest frame wins,
   five-second give-up; never build a backlog.
3. iPhone ↔ private server: WSS phone messages, poses, hands, answers and events.
4. iPhone ← server: private `/v1/speech` WAV replies, locally cached with Apple fallback.
5. Dashboard ↔ server: private proxied snapshot/event feed and command adapter.
   `/dashboard/snapshot`, `/events`, `/dashboard/commands` and their `/api` aliases
   are implemented; see `INTERFACES.md` §6. The earlier local raw `/v1` frontend
   adapter is superseded by this server adapter.
6. Photon bridge ↔ server: authenticated private events and label/registration posts.
7. Photon bridge ↔ Photon cloud: client REST and Socket.IO event stream.
8. Photon cloud ↔ caretaker: iMessage photos and typed names.
9. Private server → ElevenLabs TTS; iPhone retrieves the audio privately
   and renders it locally. Keep the ElevenLabs key out of the phone and browser.

The brain stays inside the private Tailscale network. Tailscale Serve terminates
HTTPS and forwards to `127.0.0.1`; `auth.py` fails closed with an allow-list.
The Vultr A16 GPU is the primary server, with the venue Apple Silicon Mac as
fallback, as recorded in current `STATUS.md`. Both use private Tailscale access
with no public inbound ports. The diagram's
0.33–0.42 s/frame Mac and 0.18–0.40 s/frame GPU figures are reference measurements,
not guaranteed latency. Recheck the actual model, item count and deployment.

## Constraints to preserve in future edits

- One coherent world coordinate system with session/map identity. A box uses its
  own frame's pose and depth. Retain tracking/freshness checks and relocalization.
- Keep user guidance local and responsive; network inference does not control
  every audio tick. AirPods motion supplements torso tracking with phone fallback.
- Keep wearer controls simple and VoiceOver accessible. The dashboard serves
  observers; analytics do not become requirements for the blind wearer.
- Preserve the Apple-inspired minimal visual theme shared by web and iOS.
- Backend contracts change together with their consumers and tests.
- Build the smallest complete demo path before adding optional features. Do not
  add a second mapping, audio, networking or UI pipeline to bypass integration.

## Known decisions still requiring evidence

- The diagram proposes a high-quality AirPods microphone path. The current app's
  documented baseline uses the iPhone microphone and Bluetooth stereo output.
  Keep that fallback until the iOS availability, selected route and simultaneous
  recording/spatial output are verified on the physical phone.
- An AirPods connection or OS spatial-audio badge does not prove head motion,
  correct yaw sign, world-fixed audio, or perceived front/back localization.
- Dashboard adapters, speech output and deployment readiness must each
  be checked against current code and credentials; a box in this roadmap does not
  make an integration complete.
- Room memory cannot detect an unseen object's movement. Update remembered
  positions when the camera observes them; distinguish remembered from live data.

## How future edits should be assessed

For a proposed change, identify the demo step it improves, its owning component,
affected interfaces and fallback, then run the relevant tests. Measure performance
where relevant and record remaining physical-device checks in `../STATUS.md`.
If it changes this architecture or adds substantial scope, explain the tradeoff
to the user before implementing it. Otherwise complete the authorized work and
report the result directly.
