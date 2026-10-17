# Marco x Photon: the family label loop over iMessage

This service is Marco's side of the family conversation. It runs Photon **Spectrum** (`spectrum-ts` 12.11.0, pinned), so caretakers use plain iMessage with no app to install. It covers M7 in the requirements.

Two flows:

| | Who starts | What happens |
|---|---|---|
| **A. Teach** | Caretaker | Texts Marco a photo plus a name ("Dad's keys") or a voice memo. Marco saves the item, and with `MARCO_SERVER_URL` set it registers the item through `POST /items`. |
| **B. Ask** | The user, by touch | Touches something unknown and asks "Marco, what is this?". The phone posts the photo here, and Marco texts it to the caretaker. Her reply, ideally a voice memo, becomes the label. The phone gets `label_ready` and plays her voice. |

What the caretaker sees (Flow B):

```
Marco:  [photo of the jar, boxed]
Marco:  Dad just touched this and asked what it is. Reply with a voice memo and your voice becomes its label.
Mom:    (swipe-reply, voice memo) "That's the cumin, love."
Marco:  ❤️ on her memo, then threaded under the photo: "Got it: cumin. Dad will hear your voice next time."
```

The phone gets `label_ready` before Marco acknowledges Mom, so the user hears her voice as early as possible.

## Run it

Node 22 or newer. Use Node, not Bun: Photon saw long-lived gRPC streams die silently under Bun.

```bash
cd photon && npm install
npm test                # 17 tests: both flows, edge cases, the /items handoff, real CAF->m4a and HEIC->JPEG
cp .env.example .env    # then fill in
```

| Mode | Command | Use it for |
|---|---|---|
| `sim` | `npm run sim` | No credentials. You play the caretaker over HTTP (`/dev/inbound`). The iOS team can build against it today. |
| `terminal` | `npm run terminal` | Spectrum's own chat TUI, where you type as the caretaker. The first run downloads a 4.8 MB binary, and Spectrum gives up after 30 s, so run it once on good Wi-Fi before the venue. |
| `imessage` | `npm start` (with `SPECTRUM_PROJECT_*` set) | The real thing: Photon cloud lines. |

Sim walkthrough (Flow B):

```bash
curl -s localhost:8787/dev/inbound -H 'content-type: application/json' -d '{"text":"hi Marco"}'       # Mom texts first
curl -s -X POST "localhost:8787/labels/request?item_id=jar-2" -H 'content-type: image/jpeg' --data-binary @jar.jpg
curl -s localhost:8787/dev/outbox                                                                     # find the photo's id
curl -s localhost:8787/dev/inbound -H 'content-type: application/json' \
  -d "{\"voice_base64\":\"$(base64 -i memo.caf)\",\"reply_to\":\"out-3\"}"                            # Mom swipe-replies by voice
```

## Photon setup (hour 0, about 30 minutes)

1. Sign up at https://app.photon.codes, create a project, and apply promo **HACKWITHPHOTON** (Pro, free for a month, 100 users).
2. Copy the project ID and secret from Settings into `.env`.
3. **Users tab: add every caretaker's handle.** Shared lines only talk to registered users ("Target not allowed for this project"). Get the real handle from https://debug.photon.codes, because some iPhones send from the Apple ID email.
4. **The caretaker must text Marco first.** A shared line cannot start a conversation. The first message from a handle links that caretaker and gets a text-only welcome plus Marco's contact card.
5. For the demo, "Mom" is a teammate's iPhone. Have it text "hi" well before judging. After 3 messages from her, Apple treats the thread as trusted.

## API for the phone (and the family page)

Base URL is `PUBLIC_BASE_URL`. If `BRIDGE_TOKEN` is set, send `Authorization: Bearer <token>` (or add `?token=` to the WebSocket URL). `/health` and `/media` are always open.

### `POST /labels/request`: the user touched something unknown

Send the photo **with the item boxed** (draw the box on the phone before uploading). Any of these forms works:

- a raw body: `Content-Type: image/jpeg`, with `?item_id=jar-2`;
- multipart: field `image`, plus optional `item_id`;
- JSON: `{"image_base64": "...", "mime_type": "image/jpeg", "item_id": "jar-2"}`.

| HTTP | `status` | Body | What the phone says |
|---|---|---|---|
| 202 | `sent` | `{request_id, item_id, caretaker}` | "I'm not sure. Asking Mom." |
| 200 | `already_asked` | same | "Still waiting on Mom." |
| 200 | `already_labeled` | `{item}` | Play the label |
| 409 | `no_caretaker` | | "No family member is connected yet." |
| 502 | `failed` | `{error}` | Fall back to labeling by voice on the phone |

### `WS /events`: pushed JSON

| `type` | Fields | Phone behavior |
|---|---|---|
| `label_request_sent` | `request_id, item_id, caretaker` | |
| `label_request_seen` | same | iMessage read receipt: "Mom is looking at it." |
| `label_ready` | `request_id` (null for Flow A), `item` | Play `item.label.audio_url` if set, else speak `item.label.text`. Cache the audio by `item.id`, so later touches play it offline. |
| `label_unknown` | `request_id, item_id, caretaker` | "Mom isn't sure either." |
| `caretaker_linked` | `caretaker` | |

`GET /events/recent` returns the last 100 events, for polling or debugging.

### Reads

- `GET /items` and `GET /items/:id` return:
  `{id, name, origin, server_item_id, photo_url, label: {name, text, transcript, audio_url, author, created_at}, created_at, updated_at}`
  - `server_item_id` is the same item's id on the FastAPI server, once `POST /items` accepted it.
- `GET /labels/requests/:id` returns `{request_id, status, seen_at, answered_at, caretaker, item}`. Use it as a polling fallback if the WebSocket drops.
- `GET /media/:file` serves photos as `jpg` and voice memos as `m4a` (AAC), which play in AVAudioPlayer and in every browser.

## Behavior worth knowing (and demoing)

- **Swipe-replies route exactly.** Every message in a question's thread (our photo, our prompt, our confirmation, her photo) maps to that question. A swipe-reply on any of them answers or corrects that item.
- **Plain replies go to the oldest open question.** The confirmation threads under the photo, so it is always clear which item got which name.
- **Corrections.** A swipe-reply on an answered item ("no wait, it's cumin") relabels it and pushes a new `label_ready`.
- **"I don't know"** pushes `label_unknown` and saves no label. Marco never guesses.
- **Photo then caption as two messages** (common on iPhone). Marco waits `PROMPT_DELAY_MS` before asking "What is this?", so the caption usually wins.
- **Voice memo but no transcript** (no ElevenLabs key, or STT failed). The label still plays, and Marco asks for a name by text, which then attaches to the same voice note.
- **Media.** iPhone HEIC becomes JPEG through Photon's `heif2jpeg`, with `sips` as a fallback. iMessage voice memos (Opus in CAF) become m4a through ffmpeg, with `afconvert` as a fallback.
- **Deliverability** follows Photon's guide:
  - inbound-first;
  - a text-only first message;
  - Marco's contact card after the first exchange;
  - tapbacks instead of extra texts for "thanks";
  - help text at most once per 10 minutes;
  - no bursts.
- **At-least-once delivery.** Inbound message ids are deduplicated, and all state lives in `data/marco-photon.json`, so it survives restarts.

## Talking to the FastAPI server

Set `MARCO_SERVER_URL` and this service calls the contract from requirements §5:

- **Flow A:** `POST /items`, multipart with `photo`, `name`, `item_id` and `source=caretaker`. This matches `poc/pocs/poc26_server/app.py`, which reads `photo` and `name`.
  - If the server answers `quality: "retake"`, Marco asks the caretaker for a closer photo.
  - Otherwise the server's `item_id` is stored as `server_item_id`.
- **Flow B:** `POST /labels/reply`, JSON `{request_id, item}` once the caretaker answers.

POC 26 puts every route behind `require_caller()`, which returns 403 until a verifier is wired, so these calls will fail until that is agreed. This service logs the failure and carries on.

Open decision for hour 0: should the phone talk to this service directly for labels (simplest, and the current design), or should everything go through FastAPI?

## Files

```
src/agent.ts         the conversation: both flows, routing, confirmations
src/http.ts          the API above, plus /dev routes in sim mode
src/messaging.ts     Spectrum wiring: cloud iMessage or terminal
src/sim.ts           in-process stand-in for a Spectrum provider (tests and sim mode)
src/store.ts         caretakers, items, questions (JSON file)
src/media.ts         HEIC->JPEG, CAF->m4a, media URLs
src/names.ts         "That's the cumin, love." -> "cumin"
src/transcribe.ts    ElevenLabs Scribe
src/marco-server.ts  calls to the FastAPI server
```

## Not verified yet

- **Nothing has run against Photon's cloud yet.** It needs the project credentials.
  - What is verified: Spectrum's real runtime through the terminal provider, and the message shapes read from the 12.11.0 iMessage provider source.
  - First real test: Mom texts, Marco sends a photo, Mom swipe-replies with a voice memo.
- **Shared-line latency is unmeasured.** Photon claims under 1 s; their July post admits past 8 s spikes. Measure photo-out and memo-in in hour 1, and keep a screen-recorded fallback of the Mom beat.
- **Apple flags 3 am sending.** Do not load-test the demo line overnight.
- **One household.** All caretakers belong to one user.
