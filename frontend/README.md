# Marco Polo dashboard

React + TypeScript + Vite implementation of the approved [Paper V3 designs](https://app.paper.design/file/01M55Z1GDRDK8E0XJMJE99EECZ/p-1-0). Instrument Sans is bundled locally; the web and iOS app share the palette and typography described in [design-v3.md](docs/design-v3.md).

## Run

Node 22.13+ (Node 24 recommended):

```sh
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. The default is **Demo** mode and needs no server. The Demo button switches between guiding, within reach, found, moved keys, a saved Photon label, phone disconnection, relocalization, no map, and an empty library. These are simulated observations. The demo camera is one still frame; it does not claim to stream a device.

Objects supports search, selection, last-seen history, explicit label playback, Find, and a read-only Photon request drawer. Live supports Map / Camera, selected-object detection boxes, Recenter, direction / distance / spoken instruction, Stop, and session details. **What the wearer hears runs through every view**, driven by the phone's `dashboard.sound` reports ([contract](docs/frontend-backend-contract.md)):

- **Map:** each sound ripples from where it is in the room to the wearer. The wearer has a head (nose, ears) with a ring that turns with it and marks the sound's clock hour, so the room stays put while the head turns.
- **Camera:** a sound from the item ripples on its box, or pulses on the edge it is beyond.
- **Guidance panel:** a small listening head points at the sound and lights the ear that hears it most. It shows what is playing and the actual spoken line.
- **Objects:** the line in the AirPods shows briefly.
- **Listen in** (off until clicked) reconstructs reported cues and directions in the browser. Spoken lines request Marco's generated voice from `POST /v1/speech`; this is not a recording or clone of the wearer's voice. Browser HRTF and network timing approximate the phone output. Use headphones to hear direction.

Touch detection and guidance belong to the server and phone. Registration and caretaker messages go through Photon. Browser audio requires an explicit playback action or Listen in.

## Connect FastAPI

The `server/` implements `GET /dashboard/snapshot`, `WS /events` and `POST /dashboard/commands`, alongside the raw `/v1/dashboard` feed in [the team contract](../docs/INTERFACES.md). The adapter provides browser snapshots, sound reports and Find/Stop forwarding to the active phone. Registered items remain visible without a connected phone; live camera, pose and guidance depend on phone telemetry. Demo mode runs independently.

```sh
cp .env.example .env.local
```

Set `VITE_DATA_SOURCE=api` and restart Vite. Keep `VITE_API_BASE_URL=/api`; the dev proxy forwards HTTP, media, and WebSockets to `API_PROXY_TARGET` (default `http://127.0.0.1:8000`) and strips `/api`. A production reverse proxy should do the same. The build is static (`dist/`); do not deploy the Vite dev server as the public server.

API mode has no silent demo fallback. API URLs are public configuration, not secrets. HTTP uses `credentials: include`; WebSockets connect to the same API origin. Production HTTP, media and WebSockets use the backend's Tailscale identity allow-list. Keep that gate intact when configuring a proxy.

Read [the short FastAPI handoff](docs/fastapi-handoff.md), [the full contract](docs/frontend-backend-contract.md), [the example snapshot](docs/dashboard.snapshot.example.json), and [the JSON Schema](docs/dashboard.snapshot.schema.json).

The [original backend integration plan](docs/backend-integration-plan.md) is historical planning context. Use the [handoff](docs/fastapi-handoff.md), [team interfaces](../docs/INTERFACES.md) and [STATUS.md](../STATUS.md) for the implemented integration and verification limits.

## Workflow reference

GitHub runs [the root frontend workflow](../.github/workflows/frontend.yml) and [integration workflow](../.github/workflows/integration.yml). The nested `.github/workflows/frontend.yml` in this folder is a legacy reference; it does not run. All frontend checks remain available locally with `npm run check`.

## Verify

```sh
npm run lint
npm run build
npm test
# Local tests use installed Google Chrome.
npm run test:e2e
# All checks:
npm run check
```

For a machine without Chrome, install Playwright Chromium and use the CI browser configuration:

```sh
npx playwright install chromium
CI=1 npm run test:e2e
```

Browser tests start two servers: demo at 5173 and API mode at 5174. API tests intercept HTTP and WebSocket traffic with contract-valid messages. They cover commands, reconnects, errors, stale/out-of-order data, media failures, accessibility scans, keyboard focus and 1440 / 768 / 390 px layouts. The tests do not validate real phone, Photon, LiDAR or spatial audio integration.

The October 17 [audit](docs/audit-fixes.md) records the original map identity, command scoping, silent-connection recovery and camera empty-state fixes. Later suite results are recorded in [STATUS.md](../STATUS.md); run the commands above for your checkout.

`npm run schema:export` regenerates the backend JSON Schema from `src/lib/schema.ts`. Both the demo and shared example are validated by unit tests. Bounds must also have positive area and detection boxes must have positive width/height; these cross-field runtime checks are documented in the contract.

## Files

- `src/components/`: Objects, Live, Photon, map, camera and shared controls.
- `src/lib/schema.ts`: validated message types; source for JSON Schema.
- `src/lib/transport.ts`: snapshot fetch, WebSocket, reconnect, and command HTTP calls.
- `src/lib/store.ts`: sequence ordering, pending commands, acknowledgement, timeout/retry.
- `src/data/demo.ts`: isolated simulator; replace with API mode without changing components.
- `src/styles.css`: responsive layout, typography, colors, focus and reduced motion.

## Assets

Instrument Sans is by Rodrigo Fuenzalida, with direction from Jordan Egstad for Instrument. The official font is bundled in `public/fonts/` under the included SIL Open Font License; no font CDN is used. Source: [Instrument/instrument-sans](https://github.com/Instrument/instrument-sans).

The custom Marco Polo SVG mark follows the Paper identity. The demo keys photograph is by [Filip Szalbot on Unsplash](https://unsplash.com/photos/a-bunch-of-keys-sitting-on-top-of-a-wooden-table-PxiAc1aElFQ), used under the [Unsplash License](https://unsplash.com/license). The local sample label says “Your house keys.” and was synthesized with macOS Samantha; it is not a family recording. Demo assets are local. API mode obtains media and generated speech through the Marco server.
