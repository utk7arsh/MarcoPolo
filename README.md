# Marco

A wearable for blind and low-vision people: an **iPhone 16 Pro** in a chest vest (LiDAR + camera), **AirPods Pro 3** (spatial audio), and a server that remembers where things are.

- **"Marco, where are my keys?"** *"Polo! Behind you, two steps, on the table,"* then a beacon that comes from the keys, until your hand touches them.
- **Touch a jar** and hear which one it is, in the voice of the person who labelled it.
- **Family labels things over iMessage:** Marco texts them a photo of anything it doesn't know.

```
 iPhone app (ios/)  -- frames 1/s, pose 10/s, hands 15/s, voice queries -->  server (server/)  -- label_request -->  Photon bridge (photon/)
                    <-- answers, touch, proximity, events, labels --------                     <-- labels, photos ---   <-> caretaker, iMessage
                                                                              server -- live feeds --> dashboard
```
The contract between the parts is [docs/INTERFACES.md](docs/INTERFACES.md): every message, coordinate convention and byte format. Status, decisions and next steps are in [STATUS.md](STATUS.md).

## Who works where
| Part | Folder | Start here |
|---|---|---|
| Perception, world model, touch, API (Vedant) | `server/` | [server/README.md](server/README.md) |
| iPhone app: ARKit, LiDAR, uploads, spatial audio, voice (Utkarsh) | `ios/` | [ios/README.md](ios/README.md) |
| Mac spatial-audio tools, listening experiments and regression tests | `spatial/` | [spatial/README.md](spatial/README.md) |
| Caretaker labelling over iMessage (Utkarsh) | `photon/` | [photon/README.md](photon/README.md) |
| Photon reference wiring: speaks the contract's §5 exactly, tested against the server | `photon-scaffold/` | [photon-scaffold/README.md](photon-scaffold/README.md) |
| Dashboard (Sandeep) | `frontend/` | [frontend/README.md](frontend/README.md), [frontend/docs/fastapi-handoff.md](frontend/docs/fastapi-handoff.md) |
| The research and 26 POCs behind every decision | `poc/` | [poc/README.md](poc/README.md), [poc/REQUIREMENTS.md](poc/REQUIREMENTS.md) |

## Quick start
The server runs in stub mode with no models (fake items, real geometry), so each part can be built against it straight away.
```
cd server && python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
AUTH_TEST_BYPASS=1 .venv/bin/python -m marco.app          # http://127.0.0.1:8000, this laptop only
```

**Run the pipeline on sample data** (no phone needed):
```
cd server
python tools/fake_session.py data/sessions/fake                        # synthetic room, 6 items, a hand touching a jar
python tools/run_offline.py data/sessions/fake --detector truth        # -> report.json, frames.jpg, map.png
python tools/fetch_arkitscenes.py                                      # real iPad LiDAR + video + ARKit poses (~50 MB)
python tools/arkitscenes_session.py --root data/arkitscenes/41069021 --out data/sessions/arkitscenes-41069021
python tools/run_offline.py data/sessions/arkitscenes-41069021 --detector owl --register-from-truth --only oven table
python tools/stray_session.py <Stray Scanner export> --out data/sessions/my-kitchen   # your own iPhone recording
python tools/bench_frame.py data/sessions/arkitscenes-41069021 --items 1 10 20       # does 1 frame/s hold here?
```

**Test on real video** (our own props, recorded on the iPhone 16 Pro): [docs/TESTING.md](docs/TESTING.md). Record with Stray Scanner, then:
- check the recording (`inspect_session.py`);
- click each item once to label it (`label_truth.py`);
- score detection (`eval_detection.py`): passes caught, false alarms per minute, placement error and time per frame, plus a picture of every hit and miss.

**Dashboard data:**
1. Start the stub (above).
2. Connect a WebSocket to `ws://127.0.0.1:8000/v1/dashboard`.
3. Stream a recorded session into the server: `python tools/replay.py data/sessions/fake --server http://127.0.0.1:8000`.

You'll receive `frame` (upright JPEG plus boxes), `world` (items and the user), `map_points` (coloured voxels), `guidance` (for the radar) and `timeline` messages (§6 of the contract). There are also `GET /v1/items` and `GET /v1/timeline`.

The dashboard in `frontend/` expects routes the server doesn't serve yet: `GET /dashboard/snapshot`, `WS /events` and `POST /dashboard/commands` (see `frontend/docs/fastapi-handoff.md`). Adding them is the next server step (STATUS.md).

## Tests
```
cd server && ../poc/.venv/bin/python -m pytest -q tests     # server, tools, and both client contract tests
sh ios/check.sh                                             # Swift core: type-check + unit tests (no Xcode needed)
cd photon-scaffold && npm test                              # Photon reference wiring (no install needed)
```
The contract tests:
- build the iPhone app's Swift core and feed the exact bytes it sends to the server;
- run the Photon scaffold's client against a live loopback server.

`photon/` and `frontend/` have their own tests (`npm install` first, see their READMEs).

## Security
- **Private only:** the server binds 127.0.0.1 and is reached through `tailscale serve` (tailnet only, never `funnel`).
- **Fail-closed gate:** every route goes through `server/marco/auth.py`, which admits only the logins in `TAILSCALE_ALLOWED_LOGINS`.
- **Nothing sensitive in git:** no secrets, recordings or downloaded datasets (see `.gitignore`).
