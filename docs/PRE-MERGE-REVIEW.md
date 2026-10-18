# Local pre-merge review — October 18, 2026

> **Historical review at `cc38be3`.** Later releases added the root CI workflows and deployed the speech/dashboard integration. The deployment and CI gaps below describe this review's original snapshot. See [STATUS.md](../STATUS.md) for later release evidence; local log paths are private evidence placeholders, not files shipped in this repository.

## Authorized push recheck

The user subsequently authorized pulling and pushing. `git pull --ff-only origin
main` reported already up to date at `cc38be3`; all suites and the unsigned iOS
Release build in the table below passed again. The real speech integration's
14 assertions and HTTP boundaries passed again, with a fresh provider response
of **0.810 s**. Logs for this run are `<local-evidence>/marco-push-*.log`.
Initial sandbox attempts could not use loopback sockets and compiler caches;
the complete checks passed with local system access and no tests disabled.

Read-only live `/dashboard/snapshot` returned 200 and matched the frontend's
actual Zod schema. Three live `/events` snapshots passed the same schema with
increasing sequences. `/v1/items` returned 200; `GET /v1/speech` returned 404.
The shared server still needs deployment/configuration; pushing source does not
activate the new speech provider. No shared deployment or command was sent.

The following sections record the earlier local review, before push authorization.

Reviewed the current uncommitted speech migration and the other local integration
changes against `origin/main` (`cc38be3`). A fresh fetch reports zero committed
divergence. No commit, push, deployment or real caretaker message was performed.

## Fixed findings

1. **Malformed audio could remain in the phone's phrase cache.** The original
   validator accepted any response with RIFF/WAVE signatures, even an invalid
   header. The decoder fell back to Apple, but the bad cached bytes prevented
   that phrase from retrying the provider. The client now validates the endpoint's
   actual PCM format, header/data lengths and 20-second limit before caching.
   Tests use a real PCM fixture and cover malformed headers and same-phrase
   recovery. All 12 new assertions failed before the fix and pass afterward.
2. **The browser reconnect test could count a canceled startup request as
   recovery.** In React StrictMode, Chromium made two startup requests, so the
   hard-coded expectation of two fetches completed before the watchdog refetch.
   The test now records the startup count, waits for a new fetch and verifies
   visible recovery. Added a unit regression for recovery from the HTTP snapshot
   before the replacement WebSocket delivers data. No production transport
   timing or stale-data suppression was weakened.

## Verification after the fixes

| Check | Result |
| --- | --- |
| Server suite, including cross-component contracts | 110 passed; 1 external ARKitScenes dataset skipped |
| Swift typecheck and checks | 387 passed |
| iOS Release, generic device, signing disabled | Build succeeded |
| Photon typecheck and tests | 47 passed, zero skips |
| Photon reference contract tests | 8 passed |
| Dashboard format, lint, schema and production build | Passed |
| Dashboard unit / CI-mode Chromium browser tests | 53 / 22 passed, zero final failures |
| Actual local HTTP → Swift → spatial renderer | 14 integration assertions plus HTTP 403/503/422 boundary checks passed |
| Real ElevenLabs generation after validation fix | 0.826 s; cache hit synchronous |
| Python dependency consistency | 66 packages compatible |
| Git whitespace and deploy script shell syntax | Passed |
| Configured API keys in tracked/unignored files | No matches; both ignored env files remain private |
| Tracked/unignored files larger than 10 MB | None |

The first CI-browser attempt could not launch because Chromium was not installed.
Installed the test browser outside the repo, then reproduced and fixed finding 2.
The final full dashboard check passed. No test was disabled or expectation of
successful recovery removed to get a passing run.

## Remaining boundaries

- **Existing CI placement issue:** the workflow currently lives at
  `frontend/.github/workflows/frontend.yml`, following the earlier folder-layout
  request. GitHub requires an entry under the repository-root `.github/workflows`
  directory to discover and run it. The file was not relocated in this review;
  a green local run does not mean GitHub merge protection is configured.
  [GitHub workflow location requirement](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax#about-yaml-syntax-for-workflows).
- Physical iPhone/AirPods playback, actual head motion, perceived front/back,
  walking, route changes and device latency still need hardware verification.
  Local rendering is not proof of any of these.
- Vultr has not been updated by this work. Activating the new voice needs the
  endpoint deployed with its private environment and the updated app installed.

Logs: `<local-evidence>/marco-review-{swift,server,photon,frontend-final,integration}.log`
and `<local-evidence>/marco-review-xcode-release.log`. Audio/results from the corrected
client are under `<local-evidence>/marco-pre-merge-evidence-20261018/`.
