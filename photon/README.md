# Marco x Photon 2.0: caretaker labels

Photon handles object photos and **typed names** over iMessage. ElevenLabs is
used only by the Marco server for spoken replies to the wearer, never here.
The bridge contains no Scribe client, transcription or audio-label conversion.

## Two flows

- **Teach:** the caretaker sends a clear photo with a caption, such as “house
  keys.” The bridge converts HEIC/PNG to JPEG and posts `photo`, `name` and
  `source=photon` to `POST /v1/items`. A bare photo waits briefly for its caption,
  then asks for a typed name. A retake response is passed back to the caretaker.
- **Answer:** the wearer asks “what is this?” about an unknown touched object.
  The server sends a crop over `WS /v1/photon`; the bridge sends it to the primary
  caretaker. Their typed answer goes to `POST /v1/labels` with `touch_id`, `name`,
  `text` and `source=photon`. Corrections use the returned `item_id`. A voice-only
  message asks them to type the name, without downloading the recording.

The phone receives `label_ready`, chooses its reply and obtains speech through
`POST /v1/speech`. The phone and dashboard only connect to the Marco server.
See [the canonical contract, §3.5 and §5](../docs/INTERFACES.md).

## Run

Node 22 or newer:

```bash
cd photon
npm ci
cp .env.example .env
# Fill in PHOTON_*, MARCO_SERVER_URL, CARETAKERS and PRIMARY_CARETAKER privately.
npm run doctor
npm start
```

Use the project's Photon 2.0 settings for its project ID/API key. The official
`@photon-ai/api` client handles REST attachments/sends and the Socket.IO event
stream handles incoming messages with a saved cursor. Assign the caretaker to a
managed iMessage line: the assigned line is Marco's number; `CARETAKERS` contains
the sender's number. The caretaker texts Marco first to establish the conversation.

`MARCO_SERVER_URL` is the private `tailscale serve` HTTPS URL. The bridge host
must be on the team tailnet, with its login in the server's
`TAILSCALE_ALLOWED_LOGINS`, even if it shares the server's Vultr machine.
The doctor checks the key, assigned line, event stream, server access and saved
incomplete requests. A successful connection does not prove iMessage delivery.
The demo bridge runs on Vultr; see the
[audit and handoff plan](../docs/PHOTON-INTEGRATION-AUDIT.md).
It is now installed as `marco-photon.service`; deployment and restart commands
are in [the Vultr guide](../deploy/vultr/README.md#photon-bridge-on-the-same-host).
For local simulation, start an isolated loopback stub server and use
`MARCO_SERVER_URL=http://127.0.0.1:8000 npm run sim`; no Photon credentials needed.

The status service binds `127.0.0.1:8787` only (`PORT` overrides it). `/dev/*`
routes exist in sim mode only. The phone never calls this service directly.
`/health` includes `pending_questions`; `ok` requires a server connection, a
linked allowed caretaker and no saved incomplete identification sends. It is
still not proof of provider delivery. Preserve `DATA_DIR` across bridge restarts.
`npm ci` installs pinned `ffmpeg-static` in ignored `node_modules/` for image
conversion; system ffmpeg and macOS sips are fallbacks. Install-script approvals
are explicit in `package.json`. No binary, data or secret belongs in Git.

## Commands and reliability

- `list` lists known names. `/restart` explicitly deletes all Photon-sourced
  items through `DELETE /v1/items?source=photon`, then clears local records; app
  registrations remain. Do not use it just to test connectivity.
- Only configured `CARETAKERS` may register, answer or receive item photos.
  An empty allow-list admits nobody, including old saved caretakers.
- The status port is claimed before connecting, preventing a second local copy.
  Keep exactly one active bridge across all hosts; that guard cannot stop a
  second copy on a different machine.
- Events are checkpointed after handling. A failed delivery is replayed; stable
  message-derived IDs and outbound idempotency keys avoid duplicate labels and
  confirmations. Repeated failures are logged and skipped after three attempts.
- Server-originated requests also get up to three send attempts. An accepted
  photo ID is saved before the text prompt, so a failed prompt can be retried
  without losing the reply link or resending the photo. Attachment retries use
  the same idempotency key and identical multipart bytes.
- The server replays recent unanswered requests when the bridge reconnects:
  at most 128 requests, for 10 minutes, in memory only. A server restart loses
  that buffer and its touch crops. Inspect old pending bridge records before
  retrying; do not automatically resend historical test questions.
- If a touch expired (404), the bridge registers its saved crop and applies the
  typed answer. State, photos and event cursor live under ignored `DATA_DIR`.
- Existing saved records and optional server audio fields stay compatible, but
  this bridge never uploads legacy recordings as new labels.

## Verification

```bash
npm run typecheck
npm test
```

52 tests cover typed registration/answers/corrections, recording rejection,
allow-list enforcement, retakes, media conversion, reconnect/replay, idempotency
and the actual local server's persistence/reset contract, including a bridge
restart while an unknown-object request is waiting. The contract test needs
`server/.venv` or `MARCO_SERVER_PYTHON` with stub dependencies; it uses isolated
data and never touches shared items. End-to-end iMessage delivery also requires
an assigned line and a real caretaker sender; mocks do not prove that transport.

## Files

| File | Role |
|---|---|
| `src/agent.ts` | typed conversations, registration, corrections and confirmations |
| `src/marco-server.ts` | server multipart client and Photon socket |
| `src/photon.ts` | Photon 2.0 REST and cursor-based event stream |
| `src/store.ts` | local items, questions, caretakers and event cursor |
| `src/media.ts` | HEIC/PNG/JPEG image conversion |
| `src/config.ts`, `src/index.ts` | configuration and startup; no ElevenLabs key |
| `src/http.ts`, `src/sim.ts` | loopback health and simulated channel |
| `src/doctor.ts` | read-only integration diagnostics |
