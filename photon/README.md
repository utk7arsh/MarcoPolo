# Marco x Photon 2.0: the caretaker bridge

This service is Marco's side of the family conversation in iMessage. It feeds the Marco server exactly as [docs/INTERFACES.md §5](../docs/INTERFACES.md) defines.

It is built on **Photon 2.0**, which the LA Hacks Photon track requires ("built on Photon 2.0 and live on at least one Photon channel"):
- the official client `@photon-ai/api` 0.5.0 for sending, uploads and downloads;
- the project's Socket.IO event stream, with a saved cursor, for incoming messages.

```
phone ──"what is this?"──► Marco server ──label_request (WS /v1/photon)──► photon/ ──crop──► caretaker's iMessage
phone ◄──label_ready──────  Marco server ◄──POST /v1/labels (touch_id / item_id)── photon/ ◄──text / voice memo──┘
                            Marco server ◄──POST /v1/items (photo + name)──────── photon/ ◄──setup photo + caption
```

The phone and the dashboard talk only to the server. Nothing talks to `photon/` except Photon itself.

## What the caretaker sees

**Ask.** The user touches something unknown and asks "Marco, what is this?". The server sends `label_request`, and the caretaker gets:

```
Marco:  [the crop, boxed]
Marco:  Dad just touched this and asked what it is. Reply with a voice memo and your voice becomes its label.
Mom:    (swipe-reply, voice memo) "That's the cumin, love."
Marco:  ❤️ on her memo, then threaded under the photo: "Got it: cumin. Dad will hear your voice next time."
```

Her answer goes to `POST /v1/labels` **before** Marco thanks her, and the server pushes `label_ready` to the phone.

**Teach.** She texts a photo with a caption ("Dad's keys"). It goes to `POST /v1/items` as `name=keys`, with the photo as JPEG. If the server asks for a retake, Marco passes that on.

## How answers map onto §5

| The caretaker sends | `photon/` posts |
|---|---|
| A text or voice memo answering a `label_request` | `POST /v1/labels` with `touch_id`, `name`, `text` and `audio` (if any). The server's `item_id` is remembered. |
| A voice memo within 2 minutes of a typed name | `POST /v1/labels` with that `item_id`, the same `name` and `text`, and the `audio` (§5 "a voice note after the name") |
| A voice memo with no name in it, and no transcript | Nothing yet. Marco asks for a name, and when it arrives the name and the voice go together. |
| A correction (swipe-reply "no wait, it's cumin") | `POST /v1/labels` with the `item_id` and the new name |
| "I don't know" | Nothing. Marco thanks her and logs it. |
| A setup photo with a caption, or a photo then its name | `POST /v1/items` with `name` and `photo`; plus `POST /v1/labels` with the `item_id` if there's a voice memo |

- **Every post carries `source=photon`**, so Photon's items can be removed together (below).
- **`name`** is the short name ("cumin", from the text or the ElevenLabs transcript).
- **`text`** is her words, which the phone speaks; for a voice memo that's the transcript.
- **Voice memos** are sent as **m4a**, converted from iMessage's CAF, so the phone (AVAudioFile) and the dashboard's browser can both play them.
- **Photos** are sent as JPEG; iPhone HEIC is converted.

## Chat commands

| The caretaker texts | Marco does |
|---|---|
| `/restart` | Removes every item and label Photon gave the server (`DELETE /v1/items?source=photon`), with their voice notes and saved files, and forgets them here too. Replies with what it removed. The app's own setup items stay. Use it between test runs. |
| `list` | Lists the names Marco knows |

The server saves Photon's labels across restarts (`MARCO_DATA/registry/`), so `/restart` is the way to clear them.

## Run it

Node 22 or newer.

```bash
cd photon && npm install
cp .env.example .env    # fill in PHOTON_*, MARCO_SERVER_URL, CARETAKERS
npm run doctor          # read-only: Photon key, line and event stream; the server's /v1/items and /v1/photon
npm start               # live: Photon 2.0 iMessage <-> the Marco server
```

| Mode | Use it for |
|---|---|
| `photon` (default when `PHOTON_API_KEY` is set) | The real thing. |
| `sim` (`npm run sim`) | No Photon credentials. You play the caretaker over the local `/dev/inbound`, against a real or stub server. |

**Against a local stub server**, the full loop without the phone or Photon:

```bash
cd server && AUTH_TEST_BYPASS=1 python -m marco.app                     # http://127.0.0.1:8000
cd photon && MARCO_SERVER_URL=http://127.0.0.1:8000 npm run sim          # status on http://127.0.0.1:8787/health
```

**Against the Vultr box (or the venue Mac):**
- **Server URL:** set `MARCO_SERVER_URL=https://marco-gpu.<tailnet>.ts.net`, its `tailscale serve` URL, even on the same machine.
- **Allow-list:** the machine running `photon/` must be on the tailnet, with its login in the server's `TAILSCALE_ALLOWED_LOGINS`.
- **Check first:** `npm run doctor` reports a refusal as "403 / closed with 1008: … not in TAILSCALE_ALLOWED_LOGINS".

## Photon 2.0 setup (once)

1. At [app.beta.photon.codes](https://app.beta.photon.codes), create a project. Copy its **Project ID** (`pho_prj_…`) into `PHOTON_PROJECT_ID`.
2. Create an **API key** with `project:read` and `project:write` (plus `platforms:read` if you want the doctor to print Marco's number), and put it in `PHOTON_API_KEY`.
3. **iMessage → add the caretaker's number → assign a number from the shared pool.** The assigned number is Marco's.
4. **The caretaker texts Marco first.** A shared line can't start a conversation. Her first text links her and gets a text-only welcome.

## Reliability

- **At least once, per Photon's event docs:**
  - a message is marked handled only after it fully succeeds;
  - if the server is unreachable (network, 5xx), the event isn't checkpointed, and Photon replays it;
  - records use ids derived from the message, sends carry idempotency keys, and the server is called once per answer, so a replay never double-posts or double-texts;
  - an event that fails 3 times is logged and skipped.
- **The server forgot the touch** (a `404` after a restart): the item is registered from its crop with `POST /v1/items`, then labelled. The caretaker's answer isn't lost.
- **`/v1/photon` reconnects with backoff,** including through a server restart or redeploy. The server doesn't queue `label_request` while the bridge is disconnected, so `GET /health` reports `marco_server.connected`.
- **Security:**
  - the status port binds 127.0.0.1;
  - it serves only `/health` (plus `/dev/*` in sim mode);
  - caretaker photos and voice memos are never served from here.
- **One copy only:** the status port is claimed before connecting to Photon, so an accidental second copy exits.

## Tests

```bash
npm test     # 45 tests
```

| File | Covers |
|---|---|
| `test/agent.test.ts` | both flows against a fake server that answers like `server/marco/stub.py`: what is posted, when, and what the caretaker is told; corrections, retakes, the 404 fallback, retries |
| `test/marco-server.test.ts` | the §5 client: exact multipart fields and filenames, error mapping (403 / 404 / 5xx), the `/v1/photon` socket's ordering and reconnect |
| `test/photon.test.ts` | the Photon 2.0 transport against a fake `api.photon.codes` (responses pass Photon's own schemas) and a real Socket.IO server: replay from the cursor |
| `test/server-contract.test.ts` | **end to end with the real `server/`** (stub, loopback), with this service as its own process: `what_is_this` → `label_request` → iMessage → text, then voice memo → `label_ready` with m4a audio → `what_is_this` known → setup photo → `GET /v1/items` → server restart (all still there) → `/restart` (Photon's items gone, and still gone after another restart) |
| `test/media.test.ts`, `test/names.test.ts` | Opus CAF to m4a, HEIC to JPEG, name extraction |

The end-to-end test runs when `server/.venv` (or `MARCO_SERVER_PYTHON`) has the server's stub dependencies.

## Files

```
src/agent.ts         the conversation: both flows, routing, confirmations, what goes to the server
src/marco-server.ts  the Marco server's §5 routes and the /v1/photon socket
src/photon.ts        Photon 2.0: REST client calls, attachment upload/download, the Socket.IO event stream
src/channel.ts       what the agent needs from a messaging channel
src/sim.ts           in-process stand-in for Photon (tests and sim mode)
src/http.ts          local status (/health) and the sim-mode /dev routes
src/store.ts         caretakers, items, questions, the event cursor (JSON file)
src/media.ts         HEIC/PNG to JPEG, CAF to m4a
src/names.ts         "That's the cumin, love." -> "cumin"
src/transcribe.ts    ElevenLabs Scribe
src/doctor.ts        npm run doctor
```

## Not covered by §5 yet (proposals for the server owner)

- **The caretaker opened the photo.** The iMessage read receipt is detected; a `label_request_seen` message would let the phone say "Mom is looking at it".
- **"I don't know."** A `label_unknown` message would let the phone say "Mom isn't sure either".
- **No queue for a disconnected bridge.** A `label_request` sent while the bridge is disconnected is lost; a pending-touches list would let it catch up.

`photon/` already detects the first two and only logs them, until they are added to `docs/INTERFACES.md`.
