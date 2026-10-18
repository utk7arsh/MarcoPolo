"""Stream a recorded session into a running Marco server, as if the phone were live (for the dashboard and for
end-to-end checks).

  python tools/replay.py data/sessions/fake-livingroom --server http://127.0.0.1:8000 [--speed 4]

Frames go to POST /v1/frames; poses, hands and queries go over the /v1/phone WebSocket, in recorded order and timing
(divided by --speed). Server replies are printed. Add --header 'Name: value' if the server needs one.
"""
import argparse
import asyncio
import json
import sys
import time
from pathlib import Path

import httpx
import websockets

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from marco.session import Session  # noqa: E402


async def replay(path, server, speed=1.0, headers=None, quiet=False, max_items=None):
    ses = Session(path)
    headers = headers or {}
    ws_url = server.replace("http://", "ws://").replace("https://", "wss://") + "/v1/phone"
    replies = []
    async with httpx.AsyncClient(base_url=server, headers=headers, timeout=60) as http, \
            websockets.connect(ws_url, additional_headers=headers) as ws:

        async def listen():
            try:
                async for raw in ws:
                    msg = json.loads(raw)
                    replies.append(msg)
                    if not quiet and msg.get("type") != "hand_proximity":
                        print("<-", json.dumps(msg)[:160])
            except websockets.ConnectionClosed:
                pass

        task = asyncio.create_task(listen())
        t0_rec, t0_wall = None, time.monotonic()
        for n, (kind, m) in enumerate(ses.stream()):
            if max_items and n >= max_items:
                break
            t = float(m.get("t_device") or 0.0)
            t0_rec = t if t0_rec is None else t0_rec
            wait = (t - t0_rec) / speed - (time.monotonic() - t0_wall)
            if wait > 0:
                await asyncio.sleep(wait)
            if kind == "frame":
                jpeg, d, c = ses.frame_bytes(m)
                r = await http.post("/v1/frames", data={"meta": json.dumps(m)},
                                    files={"image": ("f.jpg", jpeg, "image/jpeg"), "depth": ("f.depth", d, "application/octet-stream"),
                                           "confidence": ("f.conf", c, "application/octet-stream")})
                if r.status_code != 202:
                    raise SystemExit(f"frame {m['frame_id']}: HTTP {r.status_code} {r.text[:200]}")
            else:
                await ws.send(json.dumps({k: v for k, v in m.items() if k != "received_wall"}))
        await asyncio.sleep(0.5)
        task.cancel()
    return replies


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--server", default="http://127.0.0.1:8000")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--header", action="append", default=[])
    a = ap.parse_args()
    hdrs = dict(h.split(":", 1) for h in a.header)
    asyncio.run(replay(a.session, a.server, a.speed, {k.strip(): v.strip() for k, v in hdrs.items()}))
