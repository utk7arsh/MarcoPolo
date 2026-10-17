# Marco Polo dashboard

React + TypeScript + Vite implementation of the [Paper v2 designs](https://app.paper.design/file/01M55Z1GDRDK8E0XJMJE99EECZ/p-1-0).

## Run

Node 22.13+ (Node 24 recommended):

```sh
cd frontend
npm ci
npm run dev
```

Open http://127.0.0.1:5173. The default is **Demo** mode and needs no server. The Demo button switches between guiding, within reach, found, moved keys, a saved Photon label, phone disconnection, relocalization, no map, and an empty library. These are simulated observations. The demo camera is one still frame; it does not claim to stream a device.

Objects supports search, selection, last-seen history, explicit voice-label playback, Find, and a read-only Photon request drawer. Live supports Map / Camera, selected-object detection boxes, Recenter, direction / distance / spoken instruction, Stop, and session details. The frontend never detects touch, produces spatial navigation audio, registers an object, or sends a Photon message. The iPhone and future backend own those actions.

## Connect FastAPI

```sh
cp .env.example .env.local
```

Set `VITE_DATA_SOURCE=api` and restart Vite. Keep `VITE_API_BASE_URL=/api`; the dev proxy forwards HTTP, media, and WebSockets to `API_PROXY_TARGET` (default `http://127.0.0.1:8000`) and strips `/api`. A production reverse proxy should do the same. The build is static (`dist/`); do not deploy the Vite dev server as the public server.

API mode has no silent demo fallback. API URLs are public configuration, not secrets. HTTP uses browser cookies (`credentials: include`); WebSockets use the same browser session. No auth provider or login screen is invented here. The backend must implement its chosen access policy for HTTP, media and WebSockets together.

Read [the short FastAPI handoff](docs/fastapi-handoff.md), [the full contract](docs/frontend-backend-contract.md), [the example snapshot](docs/dashboard.snapshot.example.json), and [the JSON Schema](docs/dashboard.snapshot.schema.json).

## Workflow reference

The workflow template is kept in `.github/workflows/frontend.yml` inside this frontend folder. GitHub only runs workflows from the repository root `.github/workflows/`; copy the template there to enable automatic checks. All checks remain available locally with `npm run check`.

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

`npm run schema:export` regenerates the backend JSON Schema from `src/lib/schema.ts`. Both the demo and shared example are validated by unit tests. Bounds must also have positive area and detection boxes must have positive width/height; these cross-field runtime checks are documented in the contract.

## Files

- `src/components/`: Objects, Live, Photon, map, camera and shared controls.
- `src/lib/schema.ts`: validated message types; source for JSON Schema.
- `src/lib/transport.ts`: snapshot fetch, WebSocket, reconnect, and command HTTP calls.
- `src/lib/store.ts`: sequence ordering, pending commands, acknowledgement, timeout/retry.
- `src/data/demo.ts`: isolated simulator; replace with API mode without changing components.
- `src/styles.css`: responsive layout, typography, colors, focus and reduced motion.

## Assets

The custom Marco Polo SVG mark follows the Paper identity. The demo keys photograph is by [Filip Szalbot on Unsplash](https://unsplash.com/photos/a-bunch-of-keys-sitting-on-top-of-a-wooden-table-PxiAc1aElFQ), used under the [Unsplash License](https://unsplash.com/license). Replace it with the team's actual object photo for the live demo. The local sample voice label says “Your house keys.” and was synthesized with macOS Samantha; it is not a family recording. No external image or audio service is contacted at runtime.
