# Marco spoken replies: output-only ElevenLabs

User decision: October 17–18, 2026. ElevenLabs supplies Marco's speaking voice.
Caretaker labels use photos and typed names. Scribe and the voice-label path have
been removed from the active Photon bridge; this supersedes that portion of the
original diagram. Existing saved data is preserved.

## Implemented flow

1. The caretaker sends a photo and typed name through Photon, or types an answer
   to an unknown-item question. Recordings are not downloaded or transcribed.
2. Apple's existing iOS speech recognizer hears wearer commands. The existing
   `Lines` and guidance rules select the exact response; no LLM is involved.
3. `SpeechOutputClient` posts that short line to authenticated `POST /v1/speech`.
4. The private server calls ElevenLabs with its server-only key, stock George
   voice (`JBFqnCBsd6RMkjVDRZzb`), `eleven_flash_v2_5`, and `pcm_24000`.
5. The server wraps 24 kHz mono 16-bit PCM in WAV. `SpatialAudio` converts it to
   the existing 48 kHz mono voice node, through Apple's HRTF and stereo output.
   Item-relative speech retains its world anchor; general status stays ahead.

Beeps, dings, haptics, head fusion and the 60 Hz guidance loop remain local.
VoiceOver continues to operate/read the control panel. It is not replaced by TTS.
No UI redesign, voice agent, cloning, recognition service or second audio graph.

## Limits and fallback

- Server: 360 characters, 20 seconds of PCM, 2.5 s deadline, two concurrent calls
  and at most eight pending unique lines. Duplicate requests share generation.
- Memory-only caches: server 128 entries / 8 MiB keyed by voice/model/text;
  phone 64 entries / 8 MiB, cleared when its configured server changes.
  Fixed phrases cache on first use; there is no startup prewarming or disk cache.
- Phone: 3 s deadline. Failure, unavailable provider or decode failure selects
  existing `AVSpeechSynthesizer`, through the same spatial node. A transport or
  response failure skips cloud requests for uncached lines for 15 seconds;
  cached replies remain usable offline.
- A newer line, wake cue, Stop or session stop invalidates pending playback;
  late cloud/Apple callbacks are ignored. No speech request per sensor tick.
- Existing optional audio fields and stored media remain readable for old clients;
  current Photon and iOS no longer use caregiver recordings as labels.

## Configuration and activation

The provided key is in ignored `server/.env` (0600), removed from `photon/.env`.
`server/.env.example` documents the three output-only variables. Launch with an
explicit env-file loader; the server does not auto-read `.env`. For the existing
Vultr service, put the variables privately in `/etc/marco/local.env`, deploy this
code and restart. See [server setup](../server/README.md). The deploy sync excludes
`.env*`; no key belongs in a browser, phone bundle, Git or Photon configuration.

The implementation is deployed on Vultr and its process loads the private
environment file. Live private `/v1/speech` calls and the production Swift HTTP
client pass, including silent spatial rendering. The physical updated-app test
remains. See [the deployment and integration audit](PHOTON-INTEGRATION-AUDIT.md).

## Verification (October 18, 2026)

Latest deployed check: real caretaker reply → `label_ready` → exact Marco line
→ private Vultr `/v1/speech` → ElevenLabs WAV passed (0.792 s generation/request).
The actual Swift client fetched and silently spatially rendered that same line.
Fourteen local HTTP/rendering assertions also rechecked Stop, delayed responses,
offline cache and actual Apple fallback. See the current
[integration audit](PHOTON-INTEGRATION-AUDIT.md) for evidence and limits.
The earlier measurements below describe previous runs.

- 12 server speech tests: authentication, exact provider request, valid WAV,
  failures/timeouts, cache bounds, coalescing, cancellation and safe errors.
- 387 Swift checks, including request shape, cancellation, stale callbacks,
  fallback cooldown and cache isolation; generic-device Xcode Debug build passes.
  The deeper review added malformed-WAV rejection/recovery tests and an iOS
  Release build. See [the review](PRE-MERGE-REVIEW.md).
- 47 Photon tests, including recording rejection and actual isolated local-server
  typed labeling, persistence and reset. No shared item was deleted.
- Live provided-key generation through the actual endpoint: HTTP 200, mono
  24 kHz/16-bit WAV, 1.95 seconds of audio; first request **1.005 s**, cached
  repeat **0.001 s**. These are endpoint timings, not device playback latency.
  The real WAV also decodes and converts to non-silent 48 kHz mono through the
  production Swift audio converter, without sending sound to the headphones.
- Still required on physical iPhone/AirPods: world-fixed positioning, simultaneous
  beacon playback, Stop cancellation, offline fallback and perceived voice quality.

### Additional local end-to-end run

The production Swift URLSession client was tested against temporary loopback
servers, followed by the actual `SpatialAudio` graph in offline rendering mode.
Fourteen integration assertions passed: real provider audio, client caching,
left/right stereo rendering, player Stop, delayed-reply cancellation, HTTP 503
fallback/cooldown, actual Apple fallback synthesis and cache reuse after local
server shutdown. Separate HTTP checks returned expected 403, 503 and 422.
Fresh reply time was **1.071 s**; cached reply was synchronous (~0.009 ms).
All temporary servers were stopped; nothing was deployed or played audibly.
Evidence: `<local-evidence>/marco-local-speech-evidence-20261018/report.json` and WAV
samples alongside it. Regression suites again passed: server 110 (one dataset
skip), Swift 375 and Photon 47. These checks do not prove physical head tracking
or perceived spatial directions on AirPods.

Official API references: [convert text to speech](https://elevenlabs.io/docs/api-reference/text-to-speech/convert)
and [streaming guide](https://elevenlabs.io/docs/eleven-api/guides/how-to/text-to-speech/streaming).
The implementation buffers a bounded short reply before playback; it does not
claim streaming playback. Actual TTS access was verified with the provided key.
