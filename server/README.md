# Marco server (Vedant)

Perception and world model, speaking [docs/INTERFACES.md](../docs/INTERFACES.md):
- frames, poses and hands come in from the phone;
- answers, touches and events go back to it;
- `label_request` goes to Photon;
- live feeds go to the dashboard.

It has two brains behind the same routes:
- `MARCO_MODE=stub` (the default): fake items with real geometry, for building the app and dashboard without models.
- `MARCO_MODE=real`: OWLv2 + DINOv2 detection, 3D placement, the world model and touch.

## Setup
```
cd server
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # or reuse ../poc/.venv
```
The team's tested versions:
- Python 3.12;
- fastapi 0.143, uvicorn 0.54, numpy 2.3, pillow 12.3;
- torch 2.14, transformers 5.20, opencv-python 5.0.

## Run
**On this laptop only, for development** (loopback, no auth):
```
AUTH_TEST_BYPASS=1 python -m marco.app            # http://127.0.0.1:8000
```
`AUTH_TEST_BYPASS` lets every caller in. Never set it while `tailscale serve` is forwarding to this port.

**For the team (venue Mac or the Vultr GPU box):**
1. Everyone joins the team tailnet. In the admin console, turn on MagicDNS and HTTPS certificates.
2. On the server machine:
   ```
   MARCO_AUTH=tailscale TAILSCALE_ALLOWED_LOGINS=vedant@…,utkarsh@… python -m marco.app
   tailscale serve --bg 8000                       # https://<machine>.<tailnet>.ts.net, tailnet only
   ```
   - The app binds 127.0.0.1 only; `main()` refuses anything else.
   - `tailscale serve` is the only way in, and it adds `Tailscale-User-Login`, which the gate checks against the allow-list.
   - Never use `tailscale funnel` (that is the public internet), and don't open a LAN or cloud port. On Vultr, keep the firewall closed: Tailscale needs no inbound ports.
   - **Vultr GPU box:** `deploy/vultr/marco-vultr.sh` does all of this (provision, install, systemd, `tailscale serve`). See [deploy/vultr/README.md](../deploy/vultr/README.md).
3. Real models: add `MARCO_MODE=real`. Weights download on first use.
   - **1 frame/s holds.** Measured on this Apple Silicon Mac (MPS) with real iPad frames, the full per-frame pipeline takes:
     - 0.33 s with 1 item;
     - 0.37 s with 10 items;
     - 0.42 s with 20 items (p95 0.43 s).

     The pipeline covers decode, OWLv2, the presence check, 3D placement, the world model, the room map and the feeds.
   - If a frame ever takes longer, the server keeps only the newest frame rather than queueing.
   - Check any new machine with `python tools/bench_frame.py data/sessions/<session> --items 1 10 20`.

| Variable | Default | What |
|---|---|---|
| `MARCO_MODE` | `stub` | `stub` or `real` |
| `MARCO_DETECTOR` | `owl` | `owl`, or `truth` with `MARCO_TRUTH=<session>/truth.json` (synthetic sessions) |
| `MARCO_DATA` | `server/data` | recordings (`sessions/<session_id>/`), and registrations and labels (`registry/`), which survive a restart |
| `MARCO_AUTH` | `closed` | `closed` rejects everything; `tailscale` admits `TAILSCALE_ALLOWED_LOGINS` |
| `AUTH_TEST_BYPASS` | unset | `1` = tests and loopback development only |
| `HOST`, `PORT` | `127.0.0.1`, `8000` | loopback only |
| `TH_PHOTO_NAME`, `TH_DINO`, `TH_VS_OTHERS`, `GATE_NAME_SCORE` | POC 25/26 values | presence and retake thresholds: refit on the real props |
| `STUB_SPEEDUP` | `1` | speeds up the stub's fake touch sequence (tests) |

Every message and frame that arrives is recorded under `data/sessions/<session_id>/`:
- `frames.jsonl` and `frames/` (JPEG, depth, confidence);
- `phone.jsonl` (everything the phone sent);
- `out.jsonl` (everything sent back).

## Sample data, offline runs and replay
Synthetic, with ground truth (a room, 6 items, and a hand touching a jar lid):
```
python tools/fake_session.py data/sessions/fake
python tools/run_offline.py data/sessions/fake --detector truth          # -> data/sessions/fake/offline/
```

Real iPad LiDAR (ARKitScenes, about 50 MB from Apple's public dataset server; Apple's licence, so it stays out of git):
```
python tools/fetch_arkitscenes.py
python tools/arkitscenes_session.py --root data/arkitscenes/41069021 --out data/sessions/arkitscenes-41069021
python tools/run_offline.py data/sessions/arkitscenes-41069021 --detector owl --register-from-truth --only oven table
```

Real **iPhone 16 Pro** data before our app exists (the free Stray Scanner app records LiDAR, video and ARKit poses):
```
python tools/stray_session.py <stray export folder> --out data/sessions/stray-kitchen
python tools/run_offline.py data/sessions/stray-kitchen --detector owl --register keys=keys.jpg mug=mug.jpg
```

`run_offline.py` writes three files:
- `report.json`: events, touches and answers, final positions against the truth, and per-frame timing against the 1 s budget;
- `frames.jpg`: every frame upright, with its boxes;
- `map.png`: the room from above, with items and the walk.

Stream any session into a running server, as if the phone were live (for the dashboard and Photon):
```
python tools/replay.py data/sessions/fake --server http://127.0.0.1:8000 --speed 4
```

**Test detection on real video:** [docs/TESTING.md](../docs/TESTING.md).
- `inspect_session.py` checks that video, depth and poses agree.
- `label_truth.py` takes one click per item.
- `eval_detection.py` scores hits, misses and false alarms against the 1 frame/s budget, and sweeps the thresholds.

Check a phone recording against the contract (run it on the first recording from the vest):
```
python tools/check_recording.py data/sessions/<session_id>
```

## The dashboard's API
`marco/dashboard.py` serves the dashboard in `frontend/` from what the core already publishes (`docs/INTERFACES.md` §6):
- `GET /dashboard/snapshot`, `WS /events`, `POST /dashboard/commands` (Find and Stop, confirmed by the phone) and `GET /media/...`;
- each also under `/api/...`, behind the same auth gate.

To serve the dashboard from the server itself, so the browser and the API share one tailnet URL:
1. Build it on a laptop with npm:
   ```
   cd frontend
   VITE_DATA_SOURCE=api npm run build -- --base=/app/
   ```
2. Copy `frontend/dist` to the server, e.g. `/opt/marco/frontend/dist`.
3. Set `MARCO_DASHBOARD_DIR=/opt/marco/frontend/dist` in `/etc/marco/local.env`, and restart.
4. Open `https://<server>.<tailnet>.ts.net/app/`.

During development, `npm run dev` proxies `/api` to this server instead (`API_PROXY_TARGET`).

| Variable | Default | What |
|---|---|---|
| `MARCO_DASHBOARD_DIR` | unset | the built dashboard, served at `/app/` |
| `MARCO_ROOM_ID`, `MARCO_ROOM_NAME` | `room`, `Room` | the room the dashboard shows |
| `DASHBOARD_COMMAND_TIMEOUT_S` | `10` | how long a command waits for the phone's answer before `rejected` / `no_answer` |

## Code
| Module | What |
|---|---|
| `marco/app.py` | FastAPI routes and WebSockets, validation (422 with a reason), latest-frame-wins, recording |
| `marco/auth.py` | the fail-closed gate |
| `marco/geometry.py` | column-major matrices, upright rotation from gravity, box to 3D, headings, clock positions, surfaces |
| `marco/codec.py` | depth/confidence (zlib or raw DEFLATE), hand patches |
| `marco/stub.py` | the stub brain |
| `marco/dashboard.py`, `marco/dashboard_commands.py` | the dashboard's API: snapshots, the event socket, media, Find/Stop relayed to the phone |
| `marco/brain.py` | the real brain: detection, placement, world, touch, answers, labels |
| `marco/perception/detector.py` | OWLv2 image-guided detection + presence check + retake gate; `TruthDetector` for synthetic sessions |
| `marco/world/memory.py` | items, sightings, moved/put down/picked up/missing/left behind, answers |
| `marco/registry.py` | registrations and labels saved under `MARCO_DATA/registry/` (photos, voice notes, `items.json`) and reloaded at start; `DELETE /v1/items?source=photon` removes Photon's |
| `marco/world/roommap.py` | the voxel room map |
| `marco/touch.py` | touch from the hand stream (fingertip depth continuity, vote, identity within 15 cm) |
| `marco/recorder.py`, `marco/session.py` | writing and reading recorded sessions |

## Tests
```
../poc/.venv/bin/python -m pytest -q tests
```
Besides the server's own unit and API tests, two contract tests run each client against the server:
- `test_ios_contract.py` builds the iPhone app's Swift core with `swiftc` and sends its exact bytes to the server.
- `test_photon_contract.py` runs the Photon scaffold's JS client (`photon-scaffold/`) against a live loopback server.

They skip themselves where `swiftc` or `node` is missing.
