"""End-to-end check of a running Marco server, the way the phone uses it: register items from photos, stream a
recorded session in at real-time pace (frames over HTTP, poses and hands over the phone WebSocket), then ask
"where is my ...?" for each item. Run it from any machine that can reach the server (on the tailnet for Vultr).

  python tools/live_check.py --server https://marco-gpu.<tailnet>.ts.net --session data/sessions/rec2-find \\
      --register bottle=data/bottle.jpeg "power bank=data/powerbank.jpeg" wallet=data/wallet.jpg
  python tools/live_check.py --server http://127.0.0.1:8000 --header "Tailscale-User-Login: you@github" ...  # on the box

Prints what happened (registrations, frames accepted, events, answers, timing) and exits non-zero if the server
refused something. Registered items stay on the server until it restarts.
"""
import argparse
import asyncio
import json
import sys
import time
import uuid
from pathlib import Path

import httpx
import websockets

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import replay  # noqa: E402


def register(server, photos, headers):
    out = {}
    with httpx.Client(base_url=server, headers=headers, timeout=120) as c:
        for name, path in photos.items():
            t = time.time()
            r = c.post("/v1/items", data={"name": name}, files={"photo": (Path(path).name, Path(path).read_bytes(), "image/jpeg")})
            out[name] = dict(status=r.status_code, seconds=round(time.time() - t, 2),
                             **(r.json() if r.headers.get("content-type", "").startswith("application/json") else {}))
    return out


async def ask(server, names, headers, session_id):
    url = server.replace("https://", "wss://").replace("http://", "ws://") + "/v1/phone"
    answers = {}
    async with websockets.connect(url, additional_headers=headers) as ws:
        for name in names:
            qid = uuid.uuid4().hex[:8]
            await ws.send(json.dumps(dict(type="query", session_id=session_id, query_id=qid, kind="find", name=name)))
            while True:
                m = json.loads(await asyncio.wait_for(ws.recv(), timeout=30))
                if m.get("query_id") == qid or m.get("type") == "error":
                    answers[name] = m
                    break
    return answers


def check(server, session, photos, headers=None, speed=1.0, extra=()):
    headers = headers or {}
    report = dict(server=server, registrations=register(server, photos, headers) if photos else {})
    t = time.time()
    replies = asyncio.run(replay.replay(session, server, speed=speed, headers=headers, quiet=True))
    frames = sum(1 for _ in Path(session, "frames.jsonl").read_text().splitlines() if _.strip())
    report["stream"] = dict(frames=frames, seconds=round(time.time() - t, 1), speed=speed)
    report["events"] = [dict(kind=m["kind"], name=m["name"], surface=m.get("surface"), position=m.get("position"))
                        for m in replies if m.get("type") == "event"]
    report["errors"] = [m for m in replies if m.get("type") == "error"][:10]
    names = list(photos) + [n for n in extra if n not in photos]
    report["answers"] = asyncio.run(ask(server, names, headers, "live-check")) if names else {}
    return report


def summary(report):
    lines = [f"server {report['server']}"]
    for n, r in report["registrations"].items():
        lines.append(f"  register {n}: HTTP {r['status']} {r.get('quality', '')} {r.get('reason') or ''} ({r['seconds']} s)")
    s = report["stream"]
    lines.append(f"  streamed {s['frames']} frames in {s['seconds']} s (x{s['speed']})")
    for e in report["events"]:
        lines.append(f"  event: {e['kind']} {e['name']} on the {e['surface']} at {e['position']}")
    for n, a in report["answers"].items():
        if a.get("type") == "error":
            lines.append(f"  where is my {n}? error: {a.get('detail')}")
        elif a.get("found"):
            lines.append(f"  where is my {n}? found: on the {a.get('surface')} at {a.get('position')}, seen {a.get('seen_ago_s')} s ago")
        else:
            lines.append(f"  where is my {n}? not found ({a.get('reason')})")
    for e in report["errors"]:
        lines.append(f"  server error: {e.get('detail')}")
    return "\n".join(lines)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--server", required=True)
    ap.add_argument("--session", required=True, help="a recorded session (e.g. from stray_session.py)")
    ap.add_argument("--register", nargs="*", default=[], help="name=photo.jpg")
    ap.add_argument("--header", action="append", default=[], help="'Name: value' (only for calls on the box itself)")
    ap.add_argument("--ask", nargs="*", default=[], help="also ask for these (items registered earlier)")
    ap.add_argument("--speed", type=float, default=1.0)
    a = ap.parse_args()
    hdrs = {k.strip(): v.strip() for k, v in (h.split(":", 1) for h in a.header)}
    try:
        rep = check(a.server.rstrip("/"), a.session, dict(r.split("=", 1) for r in a.register), hdrs, a.speed, a.ask)
    except SystemExit as e:
        print(f"the server refused the stream: {e}")
        sys.exit(1)
    except (httpx.HTTPError, OSError, websockets.WebSocketException) as e:
        print(f"can't reach {a.server}: {e} (on the tailnet? allowed login?)")
        sys.exit(1)
    print(summary(rep))
    bad = [r for r in rep["registrations"].values() if r["status"] != 200] or rep["errors"]
    sys.exit(1 if bad else 0)
