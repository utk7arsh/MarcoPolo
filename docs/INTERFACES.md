# Marco: who builds what, and the interfaces between us (v0.4, 2026-10-18)

Three owners, one contract. Change a message format only by updating this file, the code and tests on both sides, and telling the others. Changes are listed in §11–13.

## 1. Owners

**Vedant: perception and world (`server/`, Python).** The brain.
- **Item identity:** registration from one photo plus a name, with the retake check (POC 22, 25, 26).
- **Detection at 1 frame/s,** with the "is my item in this frame?" decision (POC 25).
- **2D boxes to 3D world positions,** using the frame's own pose and depth (POC 23); footprint method for glass.
- **Room map:** a voxel point cloud built from the depth frames, plus named surfaces (floor, seat, table, counter, shelf, by height).
- **World model:** items, user position track, and a sightings timeline. Events: seen, put down, moved, picked up, missing, left behind (POC 2 logic).
- **Touch detection** from the hand stream (POC 24: 3D, fingertip visible only).
- **Answers:** "where are my keys?" and "what is this?".
- **Data feeds:** for the phone, Photon and the dashboard.

**Utkarsh: the iPhone app (`ios/`, Xcode) and Photon (`photon/`).** Sensors in, sound and voice out.
- **ARKit session:** world tracking, LiDAR scene depth, plane detection; saving and loading the ARWorldMap and relocalizing.
- **Sending:** frames at 1/s, pose at 10/s, and the hand stream at 15/s while a hand is in view (formats below).
- **Spatial audio:**
  - AVAudioEnvironmentNode HRTF;
  - AirPods + ARKit head-tracking fusion, with the phone-only fallback;
  - the guidance sequence (§7);
  - label playback.
- **Voice:** "Marco" plus speech recognition, turned into queries; Marco's spoken lines.
- **Photon:** sends the caretaker the photo of an unknown item, receives its typed name, and posts it to the server. Voice recordings are not labels.

**Dashboard (web, `frontend/`).** Reads the server's feeds only (§6):
- the live chest view with boxes;
- the 3D map with items and the user;
- a radar of where the sound is coming from;
- the "what / when / where / last seen" timeline;
- the setup view (items and labels).

## 2. Shared conventions (everyone, no exceptions)

- **World frame:** ARKit's world coordinates for the current `map_id`. Metres, +y up (gravity), right-handed.
  - Every position in every message is in this frame.
  - A new `map_id` means a new coordinate frame, so positions from other maps don't apply.
- **Heading and azimuth:**
  - heading 0 = world −z, +90 = world +x (turning right);
  - a relative azimuth of 0 means ahead, +90 right, −90 left, ±180 behind;
  - clock positions round half to even, as Python's `round` does.
- **Matrices:** send `simd_float4x4` / `simd_float3x3` as flat float arrays in **column-major** order, exactly as the columns sit in memory: `[c0.x, c0.y, c0.z, c0.w, c1.x, ...]`.
  - `camera_transform` = `ARFrame.camera.transform` (camera to world).
  - `intrinsics` = `ARFrame.camera.intrinsics`, for `image_resolution` = `ARFrame.camera.imageResolution`, normally 1920×1440.
- **Images:** the camera image in the **sensor's own orientation**, which is landscape even though the phone is portrait in the vest.
  - Do not rotate, and do not write an EXIF orientation tag.
  - The server rotates for detection and maps boxes back (POC 23).
- **Depth:**
  - `ARFrame.smoothedSceneDepth.depthMap`: 256×192 Float32 metres, sent as float16 little-endian, then DEFLATE-compressed;
  - its `confidenceMap`: UInt8 0/1/2, DEFLATE-compressed;
  - both in the sensor orientation, row 0 = top of the sensor image.
  - **Compression:** Apple's `NSData.compressed(using: .zlib)` writes raw DEFLATE (no zlib header). The server accepts raw DEFLATE or zlib.
- **Time:**
  - `t_device` = `ARFrame.timestamp`, in seconds on the device's uptime clock, for ordering;
  - `t_wall` = ISO-8601 UTC, for the dashboard.
- **Ids:**
  - `session_id` (UUID, per app launch). It is on **every** phone-to-server message, so the server files everything into one recording.
  - `map_id` (UUID per ARWorldMap, kept across launches when relocalized);
  - `frame_id` (increasing per session).

## 3. Phone to server (Utkarsh sends, Vedant receives)

### 3.1 Frames: `POST /v1/frames`, about 1 per second (multipart)

| Part | Content |
|---|---|
| `meta` | JSON, below |
| `image` | JPEG, 960×720 (the 1920×1440 sensor image scaled 0.5), sensor orientation, quality 0.8, about 100–150 KB |
| `depth` | DEFLATE(float16 little-endian 256×192) |
| `confidence` | DEFLATE(uint8 256×192) |

```json
{"session_id": "…", "map_id": "…", "frame_id": 1234, "t_device": 81234.567, "t_wall": "2026-10-17T15:04:05.123Z",
 "tracking": "normal", "camera_transform": [16 floats], "intrinsics": [9 floats], "image_resolution": [1920, 1440],
 "jpeg_scale": 0.5}
```
- **Reply:** `202` straight away. Detections and events come back over the WebSocket.
- **When the server is busy:** it keeps only the newest frame from each phone (latest frame wins). The phone does the same: one upload in flight, and only the newest frame waits behind it.
- **A `422` reply** carries the reason (for example "the JPEG has an EXIF orientation tag", or "JPEG is 720x960 but image_resolution x jpeg_scale is 960x720").
- **Don't send frames** while `tracking` isn't `normal`, or before relocalization finishes (§3.4). The same goes for poses and hands.

### 3.2 WebSocket `wss://…/v1/phone` (JSON, phone to server)

**Pose, 10 per second:**
```json
{"type": "pose", "session_id": "…", "map_id": "…", "t_device": 81234.6, "camera_transform": [16 floats],
 "head_yaw_deg": 12.3, "head_source": "fusion"}
```
`head_yaw_deg` is the listener yaw the audio engine uses, in the world frame. `head_source` is `fusion` or `phone`.

**Hand, 15 per second, only while Vision sees a hand:**
```json
{"type": "hand", "session_id": "…", "map_id": "…", "t_device": 81234.62, "camera_transform": [16 floats],
 "vision_orientation": "up", "chirality": "right",
 "joints": [{"name": "indexTip", "x": 0.512, "y": 0.431, "conf": 0.88}, … 21 joints, Vision's order],
 "depth_patches_f16_b64": "…", "conf_patches_u8_b64": "…", "patch": 9}
```
- **Run Vision on `capturedImage` with orientation `.up`,** so joint coordinates are in the sensor frame. If accuracy suffers in hour-one tests, switch to `.right` and tell Vedant; the server will convert.
- **Joint order and names:** `wrist`, then `thumbCMC/MP/IP/Tip`, then `index`, `middle`, `ring` and `little`, each as `MCP/PIP/DIP/Tip`. That's Vision's joint names, in `server/marco/touch.py` `JOINTS` order.
  - A joint Vision didn't find is sent as x 0, y 0, conf 0.
- **Patches:** for each joint, in order, a 9×9 window of the depth map (and of the confidence map) centred on depth pixel `u = floor(x·256)`, `v = floor((1 − y)·192)`. Vision's origin is bottom-left; the depth map's is top-left.
  - Pad outside the map with NaN for depth and 0 for confidence.
  - That's 21 × 81 values each, about 5 KB per message.
- **Intrinsics:** the hand message carries none. The server unprojects with the latest frame's `intrinsics`, which don't change during a session.

**Guidance state, 10 per second while guiding,** so the dashboard radar shows what the user hears. Send one last message with phase `off` when guidance ends:
```json
{"type": "guidance", "session_id": "…", "item_id": "…", "phase": "behind|turning|facing|approach|reach|touched|off",
 "rel_azimuth_deg": -140, "distance_m": 1.6}
```
`rel_azimuth_deg` is relative to the head; `distance_m` is horizontal, chest to item.

**Queries:**
```json
{"type": "query", "session_id": "…", "query_id": "…", "kind": "find", "name": "keys"}
{"type": "query", "session_id": "…", "query_id": "…", "kind": "what_is_this"}
{"type": "query", "session_id": "…", "query_id": "…", "kind": "set_place", "name": "door"}
```
`set_place door` ("Marco, this is the door") remembers where the user stands. Leaving through there with a carry item (keys, wallet, phone) still in the room triggers `left_behind`. It needs a pose first.

**Map lifecycle:**
```json
{"type": "map", "session_id": "…", "event": "relocalized|new_map|saved", "map_id": "…"}
```

**Errors:** a message the server can't use gets `{"type": "error", "detail": "…", "for_type": "hand"}` back. The socket stays open.

**Command acknowledgement** (the answer to a dashboard `command`, §4):
```json
{"type": "command_ack", "session_id": "…", "command_id": "…", "status": "accepted|applied|rejected", "reason": "…"}
```
- Send `accepted` when you take the command, then `applied` once guidance has started (Find) or stopped (Stop).
- Or send `rejected` with a reason, such as `session_mismatch`, `expired` or `position_unavailable`.
- The server ignores acks for unknown, other-session or already-finished commands, and never replies to them.

### 3.3 Registration: `POST /v1/items` (multipart `photo` + `name`), from the app's setup flow or from Photon
- **Photo:** any normal upright photo; EXIF is fine here, and the server applies it. Send JPEG (convert HEIC on the phone).
- **`source`** (optional form field): who registers it, `app` (the default: the app's setup flow) or `photon` (a caretaker). It lets one source's items be removed together (§5).
- **Reply:** `{item_id, quality: "ok"|"retake", reason}`. On `retake`, say *"I can't see the {name} clearly, try again."*
- **`GET /v1/items`** lists every item, with these fields (labels made before an app launch come from here):
  - `item_id`, `name`, `position`, `surface`, `state`;
  - `last_seen_wall`;
  - `label_text`, `label_audio_url`, `size_m`;
  - `source`: `app`, `photon`, or `seed` (the stub's built-in fake items).
- **Saved across server restarts:** every registration and label, with its photo (or touch crop) and voice note, under `MARCO_DATA/registry/`.
  - On start, the server reloads them and registers the photos with the detector again, so detection works at once.
  - Positions are not saved: an item is placed again when the camera next sees it. Until then it reads `state: "registered"`.

### 3.4 ARWorldMap rules (Utkarsh), so positions survive relaunch
1. Save `getCurrentWorldMap` about every 30 s and when the app goes to the background.
2. On launch, load it as `initialWorldMap`. Wait until tracking is `normal` after relocalizing, then send `map: relocalized` and resume frames.
3. If relocalizing hasn't worked after 30 s of walking:
   - start a fresh map;
   - send `map: new_map`;
   - say *"Getting my bearings."* (Marco never says its own wake word: the mic would hear it.)

   The server keeps the items but marks their positions stale until they're seen again.

### 3.5 Spoken replies: `POST /v1/speech` (JSON)

The phone's existing `Lines` and guidance logic decide what to say. This route
converts that exact text to speech; it does not generate an answer or recognize
speech. It uses the same fail-closed Tailscale authentication as every other route.

```json
{"text": "Polo! On your left, two steps, on the table."}
```

- `text`: 1–360 characters; whitespace is trimmed. Blank text and NUL are rejected (422).
- **200:** `Content-Type: audio/wav`, mono 24 kHz signed 16-bit PCM in a WAV
  container, at most 20 seconds. The server uses the standard 44-byte PCM RIFF
  header followed by sample data; the phone validates format and lengths before
  caching. `Cache-Control: private, no-store` prevents HTTP
  caching; `X-Marco-Speech-Provider: elevenlabs` identifies the provider and
  `X-Marco-Speech-Cache: hit|miss` identifies reuse of a cached/pending request.
- **503:** unconfigured key, provider failure, invalid audio, saturation or
  timeout. The phone falls back to Apple's `AVSpeechSynthesizer`. The server's
  deadline is 2.5 s and the phone's is 3 s; after failure the phone uses Apple for
  uncached lines for 15 s before trying again. **403:** caller not authorized.
- Server cache: at most 128 entries / 8 MiB, keyed by voice, model and text;
  duplicate pending lines share generation. Phone cache: 64 entries / 8 MiB,
  cleared when the configured server changes. Caches are memory-only.
- A newer line, wake blip, Stop or stopped session cancels pending playback.
  Late replies cannot speak an old instruction. The phone converts the WAV to
  its existing mono spatial voice node; world anchors, beeps, head fusion and
  the 60 Hz guidance loop remain on the phone. No TTS request per sensor tick.
- Key and stock voice/model configuration stay on the server. Defaults:
  `ELEVENLABS_VOICE_ID=JBFqnCBsd6RMkjVDRZzb`,
  `ELEVENLABS_TTS_MODEL=eleven_flash_v2_5`. See `server/.env.example`.

## 4. Server to phone (Vedant sends over `/v1/phone`)

```json
{"type": "answer", "query_id": "…", "kind": "find", "found": true, "item_id": "…", "name": "keys",
 "position": [x, y, z], "surface": "table", "seen_ago_s": 600, "confidence": 0.82, "state": "present"}
{"type": "answer", "query_id": "…", "kind": "find", "found": false, "reason": "not_registered", "name": "cat"}
{"type": "answer", "query_id": "…", "kind": "find", "found": false, "reason": "never_seen", "item_id": "…", "name": "wallet"}
{"type": "answer", "query_id": "…", "kind": "find", "found": false, "reason": "not_where_last_seen", "item_id": "…",
 "name": "mug", "last_position": [x, y, z], "surface": "shelf"}
{"type": "answer", "query_id": "…", "kind": "what_is_this", "status": "known|unknown|no_touch", "item_id": "…",
 "name": "cumin", "label_text": "That's the cumin, love", "label_audio_url": "/v1/audio/…", "touch_id": "…"}
{"type": "answer", "query_id": "…", "kind": "set_place", "name": "door", "ok": true}
{"type": "touch", "touch_id": "…", "item_id": "…" , "name": "cumin", "position": [x, y, z], "t_device": 81235.1}
{"type": "touch_end", "touch_id": "…"}
{"type": "hand_proximity", "item_id": "…", "distance_m": 0.27}
{"type": "event", "kind": "seen|put_down|moved|picked_up|missing|left_behind|label_added", "item_id": "…", "name": "mug",
 "position": [x, y, z], "from_position": [x, y, z], "surface": "shelf", "t_wall": "…"}
{"type": "label_ready", "item_id": "…", "name": "cumin", "label_text": "…", "label_audio_url": "/v1/audio/…"}
```
- `seen_ago_s` may be `null`.
- `touch.item_id` is `null` for an unknown thing being touched.
- `hand_proximity` is sent 15 times a second while guiding: the fingertip's distance to the target, which drives the steady tone in §7.
- **Touching a known item** while not being guided to it names it: the phone says its label text, or "That's the {name}," through §3.5 with Apple fallback.
- `label_audio_url` and `GET /v1/audio/{id}` remain for stored-data and older-client compatibility. The current iOS app does not download or prefer caretaker recordings; it caches synthesized replies instead.

**Dashboard command** (Find or Stop pressed on the dashboard, §6), sent only to the socket bound to the current session:
```json
{"type": "command", "command_id": "…", "session_id": "…", "action": "find|stop",
 "item_id": "…", "name": "keys", "position": [x, y, z], "surface": "table", "expires_wall": "2026-10-17T22:00:10.000Z"}
```
- **Ignore and reject:**
  - drop a repeated `command_id`;
  - reject a command for another `session_id`;
  - reject one that arrives after `expires_wall` (with about 2 s of clock slack): never start it late.
- **Find:** guide to exactly `item_id` at `position`, the same way as a voice Find; don't look the item up by name. Reject with `position_unavailable` when tracking isn't usable.
- **Stop:** stop guidance only; the camera and streams stay on.
- **Ack:** send `command_ack` (§3.2) for every command you act on or refuse.

## 5. Photon to server (Utkarsh's Photon service)
- **Connect through the `tailscale serve` URL,** even on the server Mac, so the allow-list sees the bridge's tailnet login.
- **Requests:** listen on WebSocket `/v1/photon` for `{"type": "label_request", "touch_id": "…", "crop_url": "/v1/touch/…/crop.jpg", "question": "What is this?"}`. These are sent when the user asks "what is this?" about an unknown item.
- **Asking:** send the crop (the touched item boxed) to the caretaker over iMessage.
- **Replying:** post the answer to `POST /v1/labels` as multipart:
  - `touch_id`, `name` (short, e.g. "cumin"), and `text` (the caretaker's words, which the phone speaks);
  - no `audio` is sent by the current bridge. The optional legacy upload field remains compatible with older clients and saved data.

  The server:
  - registers the item from the crop;
  - anchors it where it was touched;
  - sends `label_ready` to the phone;
  - replies `{"status": "ok", "item_id": "…"}`.
- **Corrections:** post again with that `item_id` (instead of `touch_id`), the corrected `name` and typed `text`. A standalone recording gets a request to type the name; it is not downloaded, transcribed or uploaded as a label.
- **Caretaker-initiated setup:** the caretaker sends a photo with a caption. Post it to `POST /v1/items` with `name` = the caption.
- **`source=photon`** goes on every Photon `POST /v1/items` and `POST /v1/labels` (an item a label creates gets this source).
- **Starting over (testing):** when a caretaker texts `/restart`, the bridge calls `DELETE /v1/items?source=photon`.
  - The server forgets every Photon item, with its label, voice note and saved files.
  - The app's own setup items (`source=app`) are untouched.
  - The reply is `{"status": "ok", "removed": [{"item_id": "…", "name": "…"}]}`.
  - `source` is required (422 without it), so nothing is ever removed by accident. The route sits behind the same auth gate.

## 6. Server to dashboard

**The dashboard's API** (`server/marco/dashboard.py`). Its payload is `frontend/src/lib/schema.ts`, exported as `frontend/docs/dashboard.snapshot.schema.json`; the behaviour is in `frontend/docs/fastapi-handoff.md`. Every route also answers under `/api/…`, the browser's base path, and every route is behind the auth gate.

| Route | What it does |
|---|---|
| `GET /dashboard/snapshot` | one complete `dashboard.snapshot` envelope: `schemaVersion` 1, `streamId`, a strictly increasing `sequence` shared with `/events`, and `sentAt` |
| `WS /events` | a snapshot at once, then after each change (at most 5 per second) and at least once a second |
| `POST /dashboard/commands` | Find (`{commandId, deviceId, type: "find", itemId}`) or Stop (`{commandId, deviceId, type: "stop"}`) |
| `GET /media/frames/<token>.jpg`, `/media/items/<item_id>.jpg`, `/media/audio/<id>`, `/media/touch/<touch_id>.jpg` | the recent upright frames (the last 30), item photos, label audio and touch crops |
| `GET /app/…` | the built dashboard, when `MARCO_DASHBOARD_DIR` points at `frontend/dist` (one origin with the API) |

- **`deviceId`** is the phone's current `session_id`.
- **Commands:** they go to the bound phone as `command` (§4) and come back as `command_ack` (§3.2).
  - **Success:** HTTP 202 `{commandId, status: "pending"}` means only that the command was sent.
  - **Status:** the snapshot's `lastCommand` follows the phone: `accepted`, then `completed` (guidance started or stopped) or `rejected` with a reason.
  - **No answer:** after 10 s the command is `rejected` with `no_answer`, which means the outcome is unknown.
  - **Retries:** a retry with the same `commandId` and body sends nothing again; reusing an ID for a different command gets 409.
  - **Errors:** 400 `invalid_request`; 404 `unknown_item`; 409 `phone_disconnected`, `session_mismatch`, `busy`, `location_unavailable` or `command_conflict`, each with a body `{"error": {"code", "message"}}`.
- **Mapping:**
  - **Items:** the core's world items; `lastSeen.position` is null when the item's position is stale (a new map).
  - **Wearer:** the latest pose in the current map.
  - **Navigation:** the phone's guidance telemetry:
    - behind, turning, facing or approach become `guiding`;
    - reach becomes `within_reach`;
    - touched becomes `found`;
    - after 3 s of silence it's `idle` (or `unavailable` if the phone is gone).
  - **Devices:** the phone is `connected` while a message arrived in the last 5 s. AirPods are `connected` while poses are AirPods-fused, and `unknown` otherwise.
  - **Registrations:** `label_request` and `label_ready`, plus `POST /v1/items` results.
  - **recentMemory:** `seen`, `moved`/`put_down` and `label_added` timeline events.
- **Room name:** `MARCO_ROOM_ID` and `MARCO_ROOM_NAME`.

**The raw feed**, WebSocket `/v1/dashboard` (read-only), which the adapter itself is built from:

| Message | Rate | Content |
|---|---|---|
| `frame` | every frame (about 1/s) | upright JPEG for display, plus boxes in its pixels: `[{item_id, name, box, score, present}]` |
| `world` | 2/s | items `[{item_id, name, position, surface, last_seen_wall, state}]`, user `{position, heading_deg}`, trajectory of the last 5 min |
| `map_points` | every 5 s | new voxel points `[[x, y, z, r, g, b], …]` (2–5 cm voxels) |
| `guidance` | 10/s | the phone's guidance state (§3.2), plus target and user positions, for the radar |
| `timeline` | on change | events and sightings: what, when, where |

Also `GET /v1/timeline?item_id=…` and `GET /v1/items`. The pre-recorded outside-view 3D video can be rendered from `map_points` plus `world`.

## 7. The spatial-audio sequence: who computes what

The phone runs this loop at 60 Hz for low latency (`ios/Marco/Core/Guidance.swift`). The server supplies the target and the touch.

1. **"Marco, where are my keys?"** The phone sends `query find`.
2. **The answer arrives.** The phone speaks *"Polo! Behind you, two steps, on the table,"* spatialised at `position`:
   - the direction is relative to the **body** (chest heading), because "behind you" means behind your body;
   - clock position = round(relative azimuth / 30°), where 12 o'clock means ahead; 12, 3, 6 and 9 are said as "straight ahead", "on your right", "behind you" and "on your left";
   - steps = round(horizontal distance / 0.7 m), at least one;
   - within 0.6 m it says *"Polo! Within reach, …"* instead.
3. **Beacon:** beeps from `position`, rendered relative to the **head** (fused yaw). They're muffled and lower while the item is behind the head (|relative azimuth| more than 90°).
4. **Facing** (|relative azimuth| 12° or less): a double ding plus a haptic, once per lock. The lock releases past 20°.
5. **Walking:** the gap between beeps = clamp(0.15 + 0.35 × distance, 0.15, 1.0) s. *"Within reach, on the {surface}"* is said once at 0.6 m (POC 5).
6. **Steady tone** once `hand_proximity.distance_m` is 0.30 or less. It releases above 0.40, or when proximity is older than 0.5 s.
7. **On `touch` for that item:** silence, then the item's typed label or *"Got it."* through §3.5. The phone's guidance sequence does not wait for cloud speech.

If an `event moved` (or `put_down`) arrives for the target, retarget to its new `position`.

## 8. What each person needs from the others

**Vedant needs from Utkarsh:**
1. The frame upload (§3.1).
2. The pose stream and the hand stream (§3.2).
3. The `map` messages (§3.4).
4. A 5-minute recorded session saved to disk in exactly these formats (frames, poses, hands), so Vedant can build against real data before the app is finished.
   - The server records every session it receives under `server/data/sessions/<session_id>/`. Running the app against the server is enough.
   - Until then, a Stray Scanner recording converts with `server/tools/stray_session.py`.

**Utkarsh needs from Vedant:**
1. A stub server that accepts everything above and returns fake `answer` / `touch` / `event` messages (`MARCO_MODE=stub`, the default).
2. Then the real ones (`MARCO_MODE=real`).
3. Typed labels and the speech route (§3.5). Legacy label audio URLs remain optional compatibility fields.
4. `label_request` events for Photon.

**The dashboard needs from Vedant:**
- the `/v1/dashboard` feed with recorded or fake data first (`server/tools/replay.py`), then live.

**Everyone:** the server is private:
- it binds 127.0.0.1 only and is reached through `tailscale serve`;
- every route goes through the fail-closed auth gate (`server/marco/auth.py`), which admits only `TAILSCALE_ALLOWED_LOGINS`.

## 9. Integration order
1. **Hour 0–2:** agree this file. Vedant ships the stub server; Utkarsh gets the ARKit session and frame upload working; the dashboard renders fake feeds.
2. **Then:** the recorded 5-minute session from the vest. Vedant runs the real pipeline on it offline; the dashboard replays it.
3. **First live path:** register keys, put them down, ask "where are my keys?", and follow the sound to them, end to end.
4. **Then:**
   - touch and "what is this?" with Photon labeling;
   - moved and left-behind events;
   - relaunch persistence.

## 10. Open questions (decide together)
- **Vision orientation:** `.up` versus `.right` for the hand pose. Test in hour one.
- **Where the server runs: decided (2026-10-17).** The Vultr GPU box (`deploy/vultr/`, `marco-gpu`) is the primary server; a laptop at the venue is the fallback. Nothing in this contract changes: clients only change the base URL.
- **Who names places** ("entry table"): the server names them by height, or the user names them during setup.
- **Photon and dashboard routes.** `photon/` and `frontend/` were built against the earlier requirements and POC 26 paths. Status of each:
  - **Photon: decided (2026-10-17).** `photon/` adopted §5 as written, on Photon 2.0, with no format changes. The phone never talks to `photon/`. Two optional additions are proposed in `STATUS.md` (`label_request_seen`, `label_unknown`); they are not part of this contract.
  - **Dashboard: decided (2026-10-18).** The server serves `frontend/`'s own contract (§6, `marco/dashboard.py`). The phone gained `command` and `command_ack` for Find and Stop.

## 11. Changes since v0.1
- **Compression:** DEFLATE, where raw DEFLATE (Apple's `.zlib`) and zlib are both accepted.
- **`session_id`** is on every phone message (hand, guidance, query and map too).
- **Hand message:** gains `map_id`. The server uses the latest frame's intrinsics, and the joint names are spelled out.
- **New query** `set_place door`, with its answer.
- **Find answers:**
  - `reason` adds `not_registered`;
  - `not_where_last_seen` carries `last_position` and `surface`;
  - found answers carry `state`.
- **Event kinds:** added `seen`, `missing` and `label_added`.
- **`POST /v1/labels`:** takes `text`, and `item_id` for a follow-up voice note; it returns `item_id`.
- **`GET /v1/items` fields** are listed.
- **§7:** directions are relative to the body and sound to the head; there is a "within reach" line, the facing lock releases past 20°, and the steady tone releases above 40 cm.
- **"Getting my bearings."** replaces "Marco is getting its bearings."

## 12. Changes since v0.2
- **Registrations and labels persist** across server restarts (§3.3), under `MARCO_DATA/registry/`.
- **`source`:**
  - optional on `POST /v1/items` (default `app`) and `POST /v1/labels` (default `photon`);
  - listed in `GET /v1/items`.
- **New route** `DELETE /v1/items?source=…`, which forgets one source's items. Photon's `/restart` command uses it (§5).
- **Dashboard API** (§6): `GET /dashboard/snapshot`, `WS /events`, `POST /dashboard/commands`, `GET /media/…` and `/app/…`, each also under `/api/…`, all behind the auth gate.
- **New phone messages for dashboard Find and Stop:** `command` (server to phone, §4) and `command_ack` (phone to server, §3.2).

## 13. Changes since v0.3
- **Output-only ElevenLabs:** authenticated `POST /v1/speech` (§3.5), short exact text to mono WAV, bounded caching/timeouts and Apple fallback. iOS plays it through the existing spatial voice node.
- **Typed Photon labels:** no Scribe, transcription or new caregiver audio labels. Photos and typed names, retries, corrections and source attribution stay. Stored legacy media and optional wire fields remain compatible.
