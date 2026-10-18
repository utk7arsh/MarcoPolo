# Photon integration audit and Vultr handoff

2026-10-18. Code/configuration audit requested by Sandeep. The wearer phone is
unavailable for a live retest. The fixes were subsequently deployed with the
user's authorization; the deployment evidence is recorded below.

**Environment follow-up:** the user subsequently authorized direct environment
files on Vultr. ElevenLabs TTS settings are in `/etc/marco/local.env`;
Photon settings are in `/etc/marco/photon.env`. Both are root-owned `0600`,
verified without exposing credentials, and outside Git. Existing settings were
preserved. The running Photon service loads its file explicitly with
`EnvironmentFile=/etc/marco/photon.env`; the running server loads `local.env`.

## Deployment verified on Vultr

- Pulled latest teammate commit `dc985e6`, then deployed the reviewed server and
  bridge source. Original remote source was backed up; no environment, registry,
  recording, model cache or existing dashboard build was overwritten.
- Restarted `marco.service`; all 9 backend item IDs survived. Installed Node
  24.22.0 and enabled `marco-photon.service`, running as the unprivileged `marco`
  user with automatic restart and private persistent state.
- Stopped the Mac bridge before starting Vultr. Preserved the original Mac state
  at `/private/tmp/marco-photon-handoff-20261018T091213Z/original-data.tar.gz`.
  Migrated one caretaker link, five bridge-local items, media and cursor 12245.
  The old unsent request `req_a2e7216234` remains recorded as `failed` in the
  migrated copy; it was not sent, and no backend items were deleted.
- Vultr `/health` reports `ok=true`, server connected, zero pending/open
  questions. Photon cloud subscription and all read-only doctor checks pass.
- Private items, timeline, dashboard/API snapshots, installed dashboard and all
  feed handshakes pass. Missing media and disabled docs return 404; invalid writes
  are rejected. Unauthenticated loopback returns 403. No public app listener.
- Real ElevenLabs output via private `/v1/speech` passes WAV validation: mono,
  24 kHz, 16-bit; 0.369 s generation, 0.002 s cached response. No audible playback
  or physical unknown-object/iMessage round trip was performed.
- Active GitHub workflows are under repository-root `.github/workflows/`.
  They run frontend and server/Photon/Swift contract checks with isolated data,
  without production credentials or automatic deployment.
- Isolated tests on the deployed Node/Linux runtime: 51 passed, one skipped
  because its HEIC fixture generator requires macOS `sips`. Generated that
  synthetic fixture on the Mac and separately verified HEIC-to-JPEG conversion
  using the deployed bridge on Vultr. No backend item or message was created.

The audit-time findings and test scope below describe the original failure.

## What is implemented

| Flow | Path | Evidence and limit |
|---|---|---|
| Caretaker teaches an item | iMessage photo + typed name → bridge → `POST /v1/items` with `source=photon` | Local actual-server integration passes; earlier live registrations exist in bridge state. |
| Wearer asks about an unknown item | iOS query → real brain's recent fingertip + camera crop → `WS /v1/photon` → bridge → caretaker photo + prompt | Synthetic real-brain inputs and isolated server/bridge integration pass. Fresh physical unknown-object/iMessage delivery is not verified. |
| Caretaker answers | Typed reply → bridge → `POST /v1/labels` with `touch_id` → phone `label_ready` | Local integration passes; reply must be matched to the outgoing photo/question. |
| Marco speaks | Phone selects text → private `POST /v1/speech` → ElevenLabs TTS → iOS audio graph, with Apple fallback | Separate output-only implementation. No ElevenLabs credential is needed in the bridge. Deployment/device checks are in `SPEECH-OUTPUT-PLAN.md`. |

The `MarcoAgent` class is conversation routing code, not a conversational LLM.
Voice messages are not transcribed or used as labels. Neither the phone nor the
dashboard connects directly to the bridge. Wire details: `INTERFACES.md` §5.

## What the current failure proves

- The wearer heard “I've sent a photo to your helper.” That line was selected
  from the server's `unknown` response, before any iMessage delivery result.
  It did not prove that Photon sent anything. The local copy now says “I'm
  asking your helper.” No new delivery-acknowledgement protocol was added.
- Saved bridge state contains one incomplete identification request from
  2026-10-18 06:50:45 UTC, with its cached crop but **no accepted photo message
  ID**. Four setup/name questions were answered. Private state and crop files
  remain ignored and were not cleared or replayed.
- Read-only Photon history for the surrounding time window showed a received
  text and delivered agent text, but no photo. The original provider exception
  is absent from the available process log, so its exact cause is unconfirmed.
- Credentials, iMessage platform, line assignment, event subscription and the
  private server connection pass read-only diagnostics. Caretaker sender ends
  **7418**; Marco's assigned line is **+1 628-316-7976**. These roles are correct.
  No new key is required for the handoff.

## Reproduced bugs and local fixes

| Failure | Fix and regression coverage |
|---|---|
| A transient outgoing request failure was logged and dropped | Up to three attempts per server request; permanent server errors stop retries; subsequent requests still run. |
| Photo succeeds but prompt fails: photo ID was never saved | Persist each accepted send immediately; recover the reply link across a bridge restart and skip the already-sent photo. |
| Same attachment retry key could carry different multipart bytes | Derive the boundary from the key; the upload body is stable across retries. This is retry hardening, not a confirmed historic provider error. |
| Bridge offline when the server generated the request | Keep up to 128 unanswered requests for 10 minutes; replay on authenticated reconnect and resolve after a label is saved. Memory-only, matching touch crops. |
| iOS queries omit `t_device`; the real brain compared zero with device uptime | Estimate query time from the latest sensor timestamp and monotonic elapsed time. Fresh fingertips work; old fingers/known touches expire, including when streaming stops. |
| Retrying an accepted label after losing its HTTP response created another item | Reuse the existing item for the same retained touch in both real and stub brains. |
| Healthy socket hid saved incomplete sends | Health reports `pending_questions`; `ok` also requires a linked allowed caretaker and no incomplete identification sends. Doctor surfaces pending records and no longer promises delivery from a socket handshake. |

Requests replay at least once. The bridge uses stable touch/question IDs to
avoid re-asking questions already sent. This is bounded recovery, not a durable
message broker: server restarts lose unanswered touches; exhausted retries
need investigation. Health and doctor are diagnostics, not proof that a real
caretaker received a photo. There is still no delivery receipt to the wearer.

## Verification

- Photon typecheck and **52 tests pass**, zero skips. Includes partial-send
  recovery, identical retry uploads, bounded retry behavior and an actual isolated
  stub-server/bridge process restart during an unanswered request.
- Full server suite: **120 passed, one external dataset skipped**. Includes the
  real brain's identification gate with synthetic sensor inputs, replay bounds/
  expiry, late bridge connection, resolved requests and lost-response retries.
- Swift portable checks: **387 passed** after the spoken-copy correction.
- Before the deployment, read-only doctor reported the old incomplete request as
  a failure. The handoff above preserved it as failed and stopped the old Mac
  process; Vultr now runs the fixes and passes doctor.
- During the initial audit, no real caretaker message, shared item creation/
  deletion, remote deployment, commit or push was performed. The later deployment
  is recorded above. Synthetic tests use isolated data.
  No new model-accuracy, physical touch, AirPods or live iMessage claim is made.

## Demo runtime: Vultr, operated by a teammate

1. Review and integrate these changes with the teammate's latest branch before
   deployment. Coordinate one deployer at a time. Deploy compatible server and
   bridge code; a bridge-only update cannot add server replay or the clock fix.
2. Use Node 22 or newer and `npm ci` inside `photon/`. The pinned image converter
   needs its install-time binary download. Keep configuration private with
   `PHOTON_MODE=photon`, the existing project/key, `CARETAKERS`,
   `PRIMARY_CARETAKER`, and `MARCO_SERVER_URL`. Do not put ElevenLabs in Photon.
3. Keep `MARCO_SERVER_URL` on the private Tailscale Serve HTTPS hostname even
   when both processes share Vultr. Verify the **Vultr host's** Tailscale identity
   is in the active server allow-list; preserve other allowed users. Keep the
   FastAPI and bridge listeners on loopback. Do not add public ingress.
4. Give the bridge a stable, private, writable absolute `DATA_DIR`, such as
   `/var/lib/marco-photon`. Preserve the chosen live instance's JSON state,
   conversation link, event cursor and media when migrating. Do not merge JSON
   state from two running instances. Inspect the existing pending test request
   before any retry; this audit does not authorize replaying it to the caretaker.
5. Run `npm run doctor` from the configured bridge directory. Verify the assigned
   sender/Marco roles and private access. The caretaker must first text Marco
   to establish a conversation if that link is not preserved in migrated state.
6. Arrange a controlled handoff: stop the old Mac bridge before starting the
   Vultr bridge with the same project. Check other terminals/agents too. The
   loopback port guard detects duplicates only on one machine. Keep one active
   bridge so two instances do not send conflicting replies. Use the teammate's
   existing service supervisor and restart policy; no deployment was added here.
7. Inspect the new process logs and loopback `/health`. A server socket alone
   is insufficient. Do not use caretaker `/restart` to check connectivity: it
   deletes Photon-sourced registrations.

## Live acceptance test, when the phone is available

1. Caretaker sends a clear photo plus a unique typed name to Marco. Confirm the
   backend item, its `source=photon`, and the caretaker confirmation.
2. Wearer streams a fresh frame/hand pose, touches an unregistered object and
   asks “Marco, what is this?” Correlate its `touch_id` through server request,
   crop fetch and bridge logs. Confirm the photo arrives on the real caretaker
   phone; a provider message ID alone proves acceptance, not receipt.
3. Caretaker replies to that photo with a typed name. Confirm `POST /v1/labels`
   returns an item ID, phone receives `label_ready`, and wearer hears the name.
   Ask again while touching it to check the known-item path.

Vultr configuration and the single-bridge handoff are complete. Still needed:
wearer and caretaker phones for the live acceptance test. No more API keys are
needed. The unavailable wearer phone limits physical validation, not the local
audit, automated tests or verified service connections.
