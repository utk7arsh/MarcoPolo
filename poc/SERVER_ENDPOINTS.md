# Marco server: every endpoint

> **Test every endpoint whenever you change the server.** Before you push or deploy a server change:
>
> 1. **Run the full suite:** `cd server && .venv/bin/python -m pytest -q tests`. All of it must pass.
>    - It exercises every route below, including that each one refuses a caller without a login.
>    - It also runs both client contract tests (the iPhone app's exact bytes, and the Photon bridge).
> 2. **New or changed route:**
>    - add a test, including its no-login check;
>    - put it behind `require_caller` / `ws_caller`;
>    - add it to this list and to `docs/INTERFACES.md`.
> 3. **After deploying to Vultr:**
>    - run `deploy/vultr/marco-vultr.sh status`. The local call without a login must give 403, and yours through the tailnet must give 200;
>    - run an end-to-end pass with `server/tools/live_check.py --server https://marco-gpu.taild6d426.ts.net ...`.
>
> No route may ever answer without a login. `/docs`, `/redoc` and `/openapi.json` stay switched off.

Checked against `server/marco/app.py` and the Photon replay fixes (2026-10-18). The source of truth is `server/marco/app.py` and `docs/INTERFACES.md`; if this list disagrees with them, they win, so fix this list.

## Base URL and login

- **On Vultr:** `https://marco-gpu.taild6d426.ts.net`. Reachable only from the tailnet.
- **On a laptop, for development:** `http://127.0.0.1:8000` with `AUTH_TEST_BYPASS=1`. Never set that bypass while `tailscale serve` points at the port.
- **Login:** every route requires a tailnet login on `TAILSCALE_ALLOWED_LOGINS`. `tailscale serve` adds the caller's identity.
  - HTTP calls without it get **403**.
  - WebSockets without it are closed straight away.

## Status

| Method | Path | Called by | Request | Success | Errors |
|---|---|---|---|---|---|
| GET | `/` | a browser, `status` | none | 200 `{service, ok, signed_in_as, mode, items, api}` | 403 |

## Phone

| Method | Path | Called by | Request | Success | Errors |
|---|---|---|---|---|---|
| POST | `/v1/frames` | iPhone, 1 per second | multipart (see below) | 202 `{frame_id, status: "accepted" \| "superseded"}` | 422 with the reason |
| POST | `/v1/speech` | iPhone | JSON `{"text": "..."}`, 1 to 360 characters | 200 `audio/wav` (see below) | 422 bad text; 503 speech unavailable |
| WS | `/v1/phone` | iPhone | JSON messages both ways (see below) | | `error` message; the socket stays open |

**`POST /v1/frames`** takes four multipart parts:
- **`meta`:** a JSON form field with:
  - `session_id`, `map_id`, `frame_id`, `t_device`, `t_wall`, `tracking`;
  - `camera_transform` (16 floats, column-major);
  - `intrinsics` (9 floats);
  - `image_resolution`, `jpeg_scale`.
- **`image`:** JPEG in the sensor's orientation, with no EXIF orientation tag.
- **`depth`:** float16, 256x192, zlib or raw DEFLATE.
- **`confidence`:** uint8, same size and encoding as `depth`.

It replies "superseded" when a newer frame from the same session arrived while this one waited. A 422 names the problem:
- missing meta keys;
- a row-major matrix;
- odd intrinsics;
- a rotated or wrongly scaled JPEG;
- an EXIF orientation tag;
- undecodable depth.

**`POST /v1/speech`** returns mono 24 kHz 16-bit audio.
- **Headers:** `X-Marco-Speech-Provider: elevenlabs` and `X-Marco-Speech-Cache: hit|miss`.
- **503:** no `ELEVENLABS_API_KEY` on the server, a provider failure or a timeout. The phone then falls back to Apple speech.
- **Config:** `ELEVENLABS_API_KEY`, `ELEVENLABS_VOICE_ID`, `ELEVENLABS_TTS_MODEL`.

**`WS /v1/phone`, phone to server:**
- `pose`, 10 per second;
- `hand`, 15 per second while Vision sees a hand;
- `guidance`, 10 per second while guiding;
- `query`: `find`, `what_is_this` or `set_place`;
- `map`: `relocalized`, `new_map` or `saved`;
- `command_ack`.

**`WS /v1/phone`, server to phone:**
- `answer`, `touch`, `touch_end`, `hand_proximity`, `label_ready`;
- `event`: `seen`, `put_down`, `moved`, `picked_up`, `missing`, `left_behind` or `label_added`;
- `command`: a dashboard Find or Stop;
- `error`: `{detail, for_type}`.

The formats are in `docs/INTERFACES.md` §3.2 and §4.

## Items, labels and the timeline

| Method | Path | Called by | Request | Success | Errors |
|---|---|---|---|---|---|
| POST | `/v1/items` | the app's setup flow, Photon | multipart `photo`, `name`, `source` (see below) | 200 `{item_id, quality: "ok" \| "retake", reason}` | 422 unreadable photo or bad `source` |
| GET | `/v1/items` | iPhone, Photon, dashboard | none | 200 list (see below) | 403 |
| DELETE | `/v1/items?source=photon` | Photon (`/restart`) | `source` is required | 200 `{status, removed: [{item_id, name}]}` | 422 missing or bad `source` |
| POST | `/v1/labels` | Photon | multipart (see below) | 200 `{status: "ok", item_id}` | 422 neither id given, or bad `source`; 404 unknown `touch_id` / `item_id` |
| GET | `/v1/timeline?item_id=` | dashboard, tools | `item_id` is optional | 200 list of events | 403 |
| GET | `/v1/touch/{touch_id}/crop.jpg` | Photon | none | 200 `image/jpeg`: the touched thing, boxed | 404 unknown touch |
| GET | `/v1/audio/{audio_id}` | older clients | none | 200 audio | 404 unknown id |

- **`POST /v1/items`:** `source` defaults to `app`; Photon sends `photon`. It must match `[a-z0-9_-]{1,32}`. `item_id` is null on a retake.
- **`GET /v1/items`** fields: `item_id`, `name`, `position`, `surface`, `state`, `last_seen_wall`, `label_text`, `label_audio_url`, `size_m`, `source`.
- **`DELETE /v1/items`** removes only the items of the `source` you name.
- **`POST /v1/labels`** takes `name`, then `touch_id` (label what was touched) or `item_id` (a correction), plus `text` and `source=photon`. The `audio` part is optional and legacy.

Registrations and labels survive a server restart (under `MARCO_DATA/registry/`). Positions don't: an item reads `state: "registered"` until the camera sees it again.

## Photon

| Method | Path | Called by | Request | Success | Errors |
|---|---|---|---|---|---|
| WS | `/v1/photon` | the Photon bridge | listen only; anything it sends is ignored | server sends `label_request` `{touch_id, crop_url, question}` | closed without a login |

The server retains up to 128 unanswered requests for 10 minutes and replays them
when the bridge connects. Deduplicate by `touch_id`; a saved label resolves its
request. The buffer and touch crops are memory-only and do not survive a server
restart. Reposting the same retained touch label reuses its item ID.

## Dashboard

Every route here except `/app` also answers under `/api/...`, e.g. `/api/dashboard/snapshot` and `/api/events`.

| Method | Path | Called by | Request | Success | Errors |
|---|---|---|---|---|---|
| GET | `/dashboard/snapshot` | dashboard | none | 200 snapshot envelope (see below) | 403 |
| WS | `/events` | dashboard | none | a snapshot at once, then after each change (at most 5 per second) and at least once a second | closed without a login |
| POST | `/dashboard/commands` | dashboard | Find or Stop (see below) | 202 `{commandId, status: "pending"}` | 400, 404 or 409 (see below) |
| GET | `/media/frames/{token}.jpg` | dashboard | none | 200 JPEG: one of the last 30 upright frames | 404 expired |
| GET | `/media/items/{item_id}.jpg` | dashboard | none | 200 JPEG: the registration photo | 404 |
| GET | `/media/audio/{audio_id}` | dashboard | none | 200 audio | 404 |
| GET | `/media/touch/{touch_id}.jpg` | dashboard | none | 200 JPEG: the touch crop | 404 |
| GET | `/app` | a browser | none | 307 to `/app/` | 403 |
| GET | `/app/{path}` | a browser | none | 200: the built dashboard (see below) | 404 when not installed, or for a path that leaves the folder |
| WS | `/v1/dashboard` | the adapter, tools | none | the raw feed (see below) | closed without a login |

- **The snapshot envelope:** `{type, schemaVersion: 1, streamId, sequence, sentAt, data}`. Its schema is `frontend/docs/dashboard.snapshot.schema.json`.
- **Commands:**
  - Find is `{commandId, deviceId, type: "find", itemId}`; Stop is `{commandId, deviceId, type: "stop"}`.
  - 202 means only that the command was sent. The snapshot's `lastCommand` then follows the phone's answer.
  - Errors come as `{"error": {"code", "message"}}`: 400 `invalid_request`; 404 `unknown_item`; 409 `phone_disconnected`, `session_mismatch`, `busy`, `location_unavailable` or `command_conflict`.
- **`/app/{path}`:** serves `frontend/dist` from the folder in `MARCO_DASHBOARD_DIR`. Build it with `VITE_DATA_SOURCE=api npm run build -- --base=/app/`. Unknown paths get `index.html`.
- **`WS /v1/dashboard`:** on connect it sends a `world` snapshot and the last 200 `timeline` events, then `frame`, `world`, `map_points`, `guidance` and `timeline` as they happen.

## Switched off on purpose

| Path | Answer | Why |
|---|---|---|
| `/docs`, `/redoc`, `/openapi.json` | 404 | FastAPI's built-in pages would answer without the login check |

## Count

- **HTTP:** 18 routes, plus `/api/...` aliases for 6 of the dashboard ones (the snapshot, commands and the 4 media routes).
- **WebSocket:** 4 (`/v1/phone`, `/v1/photon`, `/v1/dashboard`, `/events`), plus the `/api/events` alias.
