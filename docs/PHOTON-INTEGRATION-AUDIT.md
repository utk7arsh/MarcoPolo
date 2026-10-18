# Photon integration audit and Vultr handoff

2026-10-18. Code/configuration audit requested by Sandeep. The wearer phone is
unavailable for a live retest. The fixes were subsequently deployed with the
user's authorization; the deployment evidence is recorded below.

## Reply latency: read-only diagnosis, October 18, 2026

This follow-up uses existing provider message history, bridge/server journals,
saved state and installed SDK source. The user requested existing logs only.
No outgoing messages, test registrations, configuration changes, service
restarts, push or deployment were performed for this diagnosis. The library now
contains the user's two new registrations, Pringles and Fanta, after the earlier
explicit deletion of the old five objects.

All timestamps in this table are UTC. Incoming times are the provider's recorded
receipt times, not measured socket arrival at the bridge.

| Existing exchange | Provider received | Bridge processed photo | Confirmation delivered | Elapsed |
| --- | --- | --- | --- | --- |
| First Pringles photo | 12:03:16.132 | 12:04:17.344 | 12:04:19.361 | 63.2 s |
| Fanta photo | 12:05:16.480 | 12:06:17.715 | 12:06:19.454 | 63.0 s |
| Caretaker restart | 12:04:30.282 | Command processed 12:04:30.684 | 12:04:31.971 | 1.7 s |

The two photo paths lose about 61 s before photo processing. Registration and
outgoing delivery then complete in roughly two seconds. Repeated read-only
backend item requests take 1–10 ms; the server is idle with ample RAM and GPU
capacity. Converting the same ready HEIC photos takes 52–56 ms. Provider history,
ready attachment metadata and downloads return in about 65–210 ms when checked
later. These later successful requests do not prove the attachments were ready
during the original stall. Process configuration matches the environment files,
and all 121 deployed source/schema/asset fingerprints match the release.

### Confirmed code weaknesses and remaining uncertainty

- `photon/src/photon.ts` constructs the SDK without explicit timeout/retry
  settings. Installed `@photon-ai/api` 0.5.0 defaults to a 30 s per-attempt
  timeout and up to three attempts. Retryable responses can honor Retry-After
  up to 60 s. These internal attempts happen before the bridge's own
  ATTACHMENT_NOT_READY retry loop sees an error.
- The incoming event queue awaits the complete event handler. Photo handling
  awaits the attachment download and conversion before saving the item. A slow
  attachment therefore holds subsequent captions and commands in that queue.
- An isolated test with a fake clock and a synthetic 429/Retry-After: 60 response
  confirms that the SDK can hide a 60 s wait from the bridge. **The historical
  live logs do not record the original response/status/header or actual socket
  arrival time.** Provider event delivery and attachment retrieval cannot be
  separated conclusively from these logs; the exact retry trigger is unproven.
- A separate Pringles exchange confirms a caption ordering race. Provider event
  sequence 15890 delivers the caption before photo sequence 15891, although the
  photo's recorded receipt time is slightly earlier. The caption produces
  generic help, then the photo asks for its name; the repeated name succeeds.
- This shared line rejects reactions and threaded replies with
  SPACE_NOT_SENDABLE (409). The plain reply fallback succeeds. In the inspected
  exchanges these failed calls add fractions of a second, not the minute-long
  delay. `PROMPT_DELAY_MS=2500` is also not the source of a 60 s delay.
- ElevenLabs is absent from the bridge as intended. Caretaker replies here are
  code templates, not an LLM or speech-generation request. Photon runtime source
  was unchanged by the detector crop deployment.

Proposed follow-up: add per-attempt timing and explicit bounded attachment
timeouts/retries while respecting provider rate limits; buffer a caption that
arrives just before its photo; avoid repeatedly trying unsupported reactions
and threaded replies once capability is known. Any queue restructuring must
preserve event order, durable cursor handling and idempotency. These changes are
suggestions and have not been implemented in this diagnostic pass.

Evidence: `/private/tmp/marco-full-release-20261018/slow-replies-journal.log`,
`attachment-trace.log` (passive observation received no fresh photos), and
`sdk-retry-probe.mjs` (isolated fake-clock test; no external requests).

## Detector crop persistence: fix after the audit

Implemented on top of `651edc7`, pushed and deployed as **`b11519b`** after the
full release suites passed. Both GitHub workflows pass. This supersedes
the unresolved crop finding in the historical review below; the Photon reset
and list findings were outside this change.

- Setup registrations save the exact detector crop as a lossless PNG, for both
  app and Photon sources. The detector and persistence share the same integer
  box conversion. Dashboard JPEGs remain separate.
- Touch labels save their already-cropped pixels. Reload uses the saved crop
  without another name-gate crop. Label corrections preserve the template.
- Explicit `photo_kind` metadata allows missing/corrupt templates to recover
  from full setup photos or touch crops correctly. Stub registrations record the
  same metadata so switching to real mode does not misclassify them.
- Item deletion removes its template. A reproduced stale-cache case when
  replacing a reference photo is fixed by invalidating the previous template.
- Old unlabelled setup photos are recovered and upgraded once. Legacy labelled
  records have insufficient metadata to distinguish a corrected full setup photo
  from a touch crop; preserve them whole. An ambiguous old setup item may need
  to be taught again. This limitation does not apply to new registrations.

Regression tests cover both sources, exact patterned pixels across three
reloads, EXIF orientation, touch crops, label/audio edits, legacy recovery,
missing/corrupt templates, a missing display photo, scoped deletion, retakes,
reference replacement and stub-to-real recovery. A test runs the actual
`OwlDetector.register` method with substituted model outputs to check that the
persisted pixels match what its query encoder receives. This is software
verification without downloaded model weights or hardware testing.

Final checks: **202 server tests passed, 4 skipped; 52 Photon tests and
typecheck passed**. Skips are three missing local OWLv2-processor cases and the
external ARKitScenes sample. All 27 new template tests pass. The synthetic
`bench_frame.py` run at 1/5/10 items is within budget, with p95
0.009/0.009/0.010 s; no real-model GPU benchmark was possible with the locally
cached assets. Evidence: `/private/tmp/marco-reset-audit-20261018/templates-*`.

Full release rerun also passes frontend formatting/lint/schema/build, **90 unit
and 26 Chromium tests**, **8 reference-client tests**, **461 Swift checks**, the
unsigned iOS Release build and **19 audio/ARKit emulator tests**. The missing
audio fixtures were generated offline into ignored data; they are not committed.
Release evidence: `/private/tmp/marco-full-release-20261018/`.

### Deployment verification

- Server, Photon and the `/app/` build were deployed together; all **121 deployed
  source/schema/asset files** match the tested release. Environment files remain
  unchanged. The five existing items retain their IDs/names/labels/sources and
  now have valid saved PNG templates; API, dashboard and detector IDs agree.
- On Vultr's actual cached OWLv2/DINOv2 models, isolated app and Photon setup
  registrations preserve exact crop pixels and embeddings across three reloads.
  No test records were added to the shared registry. Linux staging: **198 passed,
  8 skipped**; the Node contract then passes with `/opt/marco/node/bin` on PATH.
  macOS-only checks were run locally; the external dataset remains unavailable.
- Chrome loads five objects and their photos/logo, receives WebSocket snapshots,
  survives reload and opens the idle Live view without request or script errors.
  The read-only Photon doctor verifies credentials, assigned line, provider event
  subscription and the private server socket. No iMessage was sent in this run.
- `/v1/speech` returns non-silent ElevenLabs mono 24 kHz WAV in one measured
  0.363 s request; repeat audio is identical and reports a cache hit. HTTP/WS
  requests without identity are rejected with 403/1008. Both services are healthy
  behind private Tailscale Serve. Physical phone/audio tests remain outstanding.
- Backup: `/opt/marco/backups/release-b11519b-20261018T115513Z/` (previous code,
  dashboard, registry and bridge state). Remote evidence:
  `/opt/marco/deploy/release-b11519b/`. No environment file or credential is in Git.
- CI: [server and Photon](https://github.com/utk7arsh/LAHacks-2026/actions/runs/39124877774),
  [frontend](https://github.com/utk7arsh/LAHacks-2026/actions/runs/39124926139).
  The following documentation-only update does not change tested runtime code.

## Reset audit and latest-main review: October 18, 2026

Pulled latest `main` to **`651edc7`**, preserving the local status note and the
existing stashes. This follow-up inspected Vultr and Photon history read-only;
it did not delete records, send messages, restart services, push or deploy.
Earlier deployment counts below are historical.

| Finding | Status in `651edc7` |
| --- | --- |
| Deleted Photon objects left saved-label entries and timeline memories | Fixed by `6f88881`: snapshots filter these entries against surviving item IDs; regression coverage added. |
| Five objects remain after caretaker `/restart` | Unchanged: the command deletes `source=photon` only, as INTERFACES.md specifies. All five survivors have `source=app`. |
| Reset replies imply a completely fresh library | Unchanged: `photon/src/agent.ts` does not report the remaining app objects. |
| Photon `list` includes rejected setup photos | Unchanged and reproduced locally: a `retake` with no `serverItemId` still produces `I know 1: mug.` |
| Detector crop changes after server restart | Partly fixed by `a064c72`: app photos are cropped again, but caretaker setup photos are incorrectly treated like already-cropped touch photos. |

The live audit found five records: Pringles, Diet coke, Sparkling water and two
coffee records. Disk JSON, `/v1/items`, dashboard items and detector IDs agree;
all five saved photos exist. There is no initialization failure evident in these
records. Persistence uses JSON files, not a SQL database: server state is under
`/var/lib/marco/data/registry/`, and bridge state is
`/var/lib/marco-photon/marco-photon.json`. Their different counts are not by
themselves corruption: the bridge also keeps rejected and pending photos.

Server and Photon logs plus provider delivery history agree: `/restart` removed
7 Photon records at 10:37:05 UTC, then 0 at 10:37:42; a later reset removed the
new Chips record at 11:08:41. Those replies were delivered. Three subsequent
Vape registrations returned `retake` (scores 0.041, 0.012 and 0.008 against the
0.05 registration threshold). They were not registered in the server. The
provider rejects threaded replies/reactions on this shared line with HTTP 409;
the plain-text reply fallback delivered. No duplicate successful replies appear
in the inspected recent history; this cannot rule out another agent elsewhere.

The remaining crop issue is independent of reset: `RealBrain.register` saves a
full setup photo for both sources, but `_reload` applies the registration crop
only when `source == "app"`. A synthetic recording detector reproduced a
32×32 initial template becoming 128×128 after reload for `source=photon`; the app
template stayed 32×32. This verifies the code-path mismatch, not model accuracy.

A fresh SSH fingerprint check after the pull found Vultr's `brain.py`,
`dashboard.py` and `dashboard_commands.py` differ from latest main. Its Photon
agent matches. Do not treat the old `DEPLOYED_REVISION` marker or the historical
deployment notes as proof that these new server fixes are running.

Recommended next changes: make reset replies state their scope and remaining
count; list confirmed server registrations separately from pending/retake
photos; preserve the detector's actual crop across reloads for both setup
sources. If the demo needs an empty library, back up and deliberately clear the
five app records separately rather than silently broadening `/restart`.
Deploy the reviewed fixes together after testing.

Verification on `651edc7`: **39 focused server tests, 52 Photon tests and 90
frontend unit tests plus 26 Chromium tests pass**; Photon typecheck and the
frontend TypeScript/Vite build pass. Isolated reproductions confirm both
unresolved list and crop bugs. A second fetch still reports `651edc7` as latest
main; a second SSH read confirms Vultr still reloads all photos with `gate=False`
and the server process has not restarted since 10:48:40 UTC.
Evidence: `/private/tmp/marco-reset-audit-20261018/`.

## Dashboard visibility follow-up

The user reported zero objects after the controlled restart, then confirmed
visibility recovered. Actual Chrome checks now render all 12 objects on the
private `/app/` page and local port 5176. The earlier schema checks did not verify
that saved items were present: an empty list is schema-valid. Restart regression
tests reproduced the adapter's empty initial state in real and stub modes.
The fix seeds it from the restored core before any phone/world event.
HTTP/WS snapshots, photos and labels now pass before connecting a phone.
Also corrected the logo's root-relative asset URL for `/app/` deployment.
Pushed fix `2a07788`; preserved the subsequent iOS and room-map changes and fixed
an exact floating-point comparison in the room-map test (`f56e7d6`). Combined
verification: 134 server tests passed (one dataset skip), 61 frontend unit and
23 Chromium tests passed, plus the full frontend check. Vultr's staged dashboard
and room-layout suites passed all 22 tests. Both GitHub workflows pass:
[server/Photon](https://github.com/utk7arsh/LAHacks-2026/actions/runs/39116888768),
[frontend](https://github.com/utk7arsh/LAHacks-2026/actions/runs/39117020363).

Deployed server and dashboard together as **`f56e7d6`** with the user's approval.
All 71 release files match their hashes. The first post-restart snapshot contains
all 12 saved objects with no camera frame or connected phone; IDs, names and
typed labels are unchanged. Actual Chrome checks on private `/app/` and local
port 5176 pass, including HTTP/WS schemas, all object rows/photos, the logo and
reload. No HTTP or page errors. Find stays disabled without the phone. Photon
automatically reconnected and remains healthy with zero pending/open questions.
Loopback binding, HTTP 403 without authentication and root-owned 0600 secret
files remain intact. No new shared item or caretaker message was created.

Rollback copy: `/opt/marco/backups/dashboard-f56e7d6-20261018T095358Z`.
Evidence and browser screenshots: `/private/tmp/marco-dashboard-deploy-20261018/`.
The later `14a1d16` commit adds POC reports, without changing runtime code. Live
room-map rendering still needs a streaming phone; this check used no sensors.

## Latest: live pre-mobile verification

- Found and fixed a real outgoing-photo failure in `photon/src/photon.ts`:
  Photon rejects the `type="application/json"` parameter on the multipart
  `Content-Type` with 400 `INVALID_ATTACHMENT_REQUEST`. Only `boundary` is now
  sent; the JSON metadata part remains. The stricter transport regression failed
  before the fix and all 52 Photon tests passed afterward. Deployed and pushed
  as `761e1ed`; [GitHub integration checks pass](https://github.com/utk7arsh/LAHacks-2026/actions/runs/39116085128).
- Real caretaker setup photo/name saved successfully. An older bridge on a
  teammate's machine caused duplicate readiness mug registrations and an obsolete
  voice-memo prompt; the user confirmed that copy is stopped. Test records remain.
- Synthetic camera/depth/hand messages entered the production real brain. It
  produced unknown touch `7de63c4a9766`; after the bridge restart, the server
  replayed it and Photon delivered the photo and typed-name question. The actual
  caretaker replied `Readiness beacon`; the bridge posted `/v1/labels`, and the
  phone socket received `label_ready` for item `86da7aaa1cb7`. The confirmation
  message was delivered too. ElevenLabs produced its exact spoken response in
  **0.792 s**; the production Swift client fetched and silently spatially rendered
  that response, including a successful Stop check.
- Photon supplied **no parent message ID** on this live answer. It matched the
  single open question. Explicit reply threading with multiple open questions
  is unit-tested but still lacks a live check; use one pending question at a time
  for the demo. Threaded confirmations/reactions get provider 409 on this line;
  the existing plain-text confirmation fallback delivered successfully.
- A controlled server restart preserved **all 12 IDs, names and labels**, cleared
  synthetic positions and allowed the bridge to reconnect automatically. Health
  is OK with no open/pending questions. All **93** compared source, dashboard
  build and service files match the tested checkout; Python/Node dependencies
  are consistent. Live dashboard HTTP/WS messages pass the actual frontend schema.
- Fresh suites: server 120 passed, one dataset skip; Photon 52 passed; frontend
  53 unit + 22 browser tests passed. Linux Photon: 51 passed, one fixture-generation
  skip; actual HEIC conversion was separately verified. Speech cancellation,
  offline cache and real Apple fallback passed 14 local integration assertions.
  The complete unsigned iOS Release build for a generic physical iPhone passes.
  Keys remain outside Git and in root-owned 0600 environment files.

Evidence: `/private/tmp/marco-readiness-20261018/`. These are real backend,
iMessage and ElevenLabs checks with **synthetic sensor input and silent Mac
rendering**. Actual camera/LiDAR, physical touch, iPhone/AirPods head tracking,
perceived spatial directions and VoiceOver remain device checks.

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
  [Frontend run](https://github.com/utk7arsh/LAHacks-2026/actions/runs/39114740624)
  passed for deployed server/bridge revision `7389d7c`.
  [Integration run](https://github.com/utk7arsh/LAHacks-2026/actions/runs/39115115948)
  passed for `d798c40` after an iOS optional-Boolean switch compatibility fix:
  120 server tests, 52 Photon tests and 8 reference tests passed; one external
  dataset test skipped. No server or bridge changes followed the deployment.
- Isolated tests on the deployed Node/Linux runtime: 51 passed, one skipped
  because its HEIC fixture generator requires macOS `sips`. Generated that
  synthetic fixture on the Mac and separately verified HEIC-to-JPEG conversion
  using the deployed bridge on Vultr. No backend item or message was created.

The audit-time findings and test scope below describe the original failure.

## What is implemented

| Flow | Path | Evidence and limit |
|---|---|---|
| Caretaker teaches an item | iMessage photo + typed name → bridge → `POST /v1/items` with `source=photon` | Local actual-server integration passes; earlier live registrations exist in bridge state. |
| Wearer asks about an unknown item | iOS query → real brain's recent fingertip + camera crop → `WS /v1/photon` → bridge → caretaker photo + prompt | Live production delivery passed with synthetic sensors; actual physical camera/touch remains unverified. |
| Caretaker answers | Typed reply → bridge → `POST /v1/labels` with `touch_id` → phone `label_ready` | Live typed reply and phone socket event passed with one open question; explicit multi-question threading remains unverified. |
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
