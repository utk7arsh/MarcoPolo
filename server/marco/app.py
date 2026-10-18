"""Marco server: the INTERFACES.md protocol. MARCO_MODE=stub (default) answers with fake perception; the real
pipeline plugs in behind the same methods later.

Run (loopback only):  AUTH_TEST_BYPASS=1 python -m marco.app        # local development on this laptop
                      MARCO_AUTH=tailscale TAILSCALE_ALLOWED_LOGINS=a@x,b@y python -m marco.app   # + tailscale serve
"""
import asyncio
import json
import logging
import os
import re
import time
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

from . import codec, geometry as G
from .auth import require_caller, ws_caller
from .dashboard import MIN_PUSH_S, SAFE_ID, Dashboard
from .dashboard_commands import CommandError
from .hub import Hub
from .recorder import Recorder
from .stub import StubBrain
from .speech import SpeechOutput, SpeechSettings, SpeechUnavailable
from .photon_requests import PendingLabelRequests

DATA = Path(os.environ.get("MARCO_DATA", Path(__file__).resolve().parents[1] / "data"))
REQUIRED_META = ("session_id", "map_id", "frame_id", "t_device", "camera_transform", "intrinsics", "image_resolution")

# No built-in /docs, /redoc or /openapi.json: they would answer without the auth gate. The API is docs/INTERFACES.md.
app = FastAPI(title="Marco server", version="0.2", docs_url=None, redoc_url=None, openapi_url=None)
hub = Hub()
recorder = Recorder(DATA / "sessions")


def make_brain():
    mode = os.environ.get("MARCO_MODE", "stub")
    if mode == "stub":
        return StubBrain(DATA)
    if mode == "real":
        from .brain import RealBrain
        from .perception.detector import OwlDetector, TruthDetector
        det = os.environ.get("MARCO_DETECTOR", "owl")
        if det == "truth":
            truth = json.loads(Path(os.environ["MARCO_TRUTH"]).read_text())["items"]
            return RealBrain(TruthDetector(truth), DATA)
        return RealBrain(OwlDetector(), DATA)
    raise SystemExit(f"MARCO_MODE must be stub or real, got {mode!r}")


brain = make_brain()
dash = Dashboard(brain)                 # the browser's API (frontend/), built from what the core publishes
DASHBOARD_ONLY = {"command_ack"}        # phone messages for the dashboard adapter only, not the brain
latest_frame: dict[str, int] = {}
work_lock = asyncio.Lock()
frame_tasks: set[asyncio.Task] = set()  # frames still on their way through the brain (held so they aren't collected)
FRAMES_ASYNC = os.environ.get("MARCO_FRAMES_ASYNC", "1") != "0"   # 0: answer after the brain is done (tests)
speech = SpeechOutput(SpeechSettings.from_env())
pending_labels = PendingLabelRequests()


class SpeechRequest(BaseModel):
    text: str = Field(min_length=1, max_length=360)


@app.post("/v1/speech")
async def spoken_reply(body: SpeechRequest, caller=Depends(require_caller)):
    """A short, already-decided Marco line; never a prompt or speech-recognition request."""
    try:
        audio, cached = await speech.render(body.text)
    except ValueError:
        raise HTTPException(status_code=422, detail="speech text must contain 1 to 360 characters") from None
    except SpeechUnavailable:
        raise HTTPException(status_code=503, detail="speech output unavailable; use on-device speech") from None
    return Response(audio, media_type="audio/wav", headers={
        "Cache-Control": "private, no-store", "X-Marco-Speech-Provider": "elevenlabs",
        "X-Marco-Speech-Cache": "hit" if cached else "miss",
    })


async def dispatch(out):
    for channel, msg in out:
        if channel == "photon" and msg.get("type") == "label_request":
            pending_labels.add(msg)
        dash.observe(channel, msg)
        await hub.send(channel, msg)
        if channel == "phone":
            recorder.message(msg.get("session_id", "server"), "out", msg)


def validate_meta(meta: dict, jpeg_size):
    missing = [k for k in REQUIRED_META if k not in meta]
    if missing:
        raise ValueError(f"meta is missing {missing}")
    T = G.mat4(meta["camera_transform"])
    G.check_pose(T)
    K = G.mat3(meta["intrinsics"])
    if not (100 < K[0, 0] < 10000 and abs(K[1, 0]) < 1e-6 and abs(K[0, 1]) < 1e-6 and abs(K[2, 2] - 1) < 1e-6):
        raise ValueError("intrinsics look wrong (expect fx, fy around 1400-1700 for 1920x1440, column-major)")
    W, H = meta["image_resolution"]
    s = float(meta.get("jpeg_scale", 0.5))
    if abs(jpeg_size[0] - W * s) > 2 or abs(jpeg_size[1] - H * s) > 2:
        raise ValueError(f"JPEG is {jpeg_size[0]}x{jpeg_size[1]} but image_resolution x jpeg_scale is {W * s:.0f}x{H * s:.0f}. "
                         "Send the sensor image unrotated (landscape), scaled by jpeg_scale.")


@app.post("/v1/frames", status_code=202)
async def post_frame(meta: str = Form(...), image: UploadFile = File(...), depth: UploadFile = File(...),
                     confidence: UploadFile = File(...), caller=Depends(require_caller)):
    from io import BytesIO

    from PIL import Image
    try:
        m = json.loads(meta)
        jpeg, d_raw, c_raw = await image.read(), await depth.read(), await confidence.read()
        im = Image.open(BytesIO(jpeg))
        if im.getexif().get(0x0112, 1) != 1:
            raise ValueError("the JPEG has an EXIF orientation tag; send sensor pixels with no orientation tag")
        validate_meta(m, im.size)
        d, c = codec.decode_depth(d_raw), codec.decode_conf(c_raw)
    except (ValueError, KeyError, json.JSONDecodeError, OSError) as e:
        raise HTTPException(status_code=422, detail=str(e))
    recorder.frame(m, jpeg, d_raw, c_raw)
    dash.observe_frame_meta(m)
    sid, fid = m["session_id"], int(m["frame_id"])
    latest_frame[sid] = max(fid, latest_frame.get(sid, -1))
    if not FRAMES_ASYNC:
        return dict(frame_id=fid, status=await process_frame(m, jpeg, d, c))
    # 202 now, as INTERFACES.md 3.1 says: the phone's upload no longer waits out detection (175-380 ms on the A16).
    task = asyncio.create_task(process_frame(m, jpeg, d, c))
    frame_tasks.add(task)
    task.add_done_callback(frame_tasks.discard)
    return dict(frame_id=fid, status="accepted")


async def process_frame(m, jpeg, d, c):
    sid, fid = m["session_id"], int(m["frame_id"])
    try:
        async with work_lock:                           # one frame through the brain at a time
            if fid < latest_frame[sid]:
                return "superseded"                     # a newer frame arrived while this one waited
            out = await run_in_threadpool(brain.on_frame, m, jpeg, d, c)
        await dispatch(out)
        return "accepted"
    except Exception:
        if not FRAMES_ASYNC:
            raise
        logging.getLogger("marco").exception("frame %s of session %s failed in the brain", fid, sid)
        return "failed"


async def play_guidance(item_id):
    try:
        for delay, channel, msg in brain.guidance_sequence(item_id):
            await asyncio.sleep(delay)
            await dispatch([(channel, msg)])
    finally:
        brain.guidance_done(item_id)


@app.websocket("/v1/phone")
async def ws_phone(ws: WebSocket):
    await ws.accept()
    if await ws_caller(ws) is None:
        return
    hub.join("phone", ws)
    try:
        while True:
            msg = await ws.receive_json()
            recorder.message(msg.get("session_id", "phone"), "phone", msg)
            dash.observe_phone(ws, msg)
            if msg.get("type") in DASHBOARD_ONLY:
                continue
            try:
                out = await run_in_threadpool(brain.on_phone, msg)
            except (ValueError, KeyError) as e:
                await ws.send_json(dict(type="error", detail=str(e), for_type=msg.get("type")))
                continue
            await dispatch(out)
            if msg.get("type") == "guidance" and msg.get("phase") not in (None, "off", "touched") and msg.get("item_id"):
                asyncio.create_task(play_guidance(msg["item_id"]))
    except WebSocketDisconnect:
        pass
    finally:
        hub.leave("phone", ws)
        dash.phone_closed(ws)


async def _listen_only(ws: WebSocket, channel: str):
    await ws.accept()
    if await ws_caller(ws) is None:
        return
    hub.join(channel, ws)
    try:
        if channel == "photon":
            for request in pending_labels.pending():
                hub.send_to(ws, request)
        if channel == "dashboard":
            await ws.send_json(brain.snapshot())
            await ws.send_json(dict(type="timeline", events=brain.events[-200:]))
        while True:
            await ws.receive_text()                     # keeps the socket open; inbound messages are ignored
    except WebSocketDisconnect:
        pass
    finally:
        hub.leave(channel, ws)


@app.websocket("/v1/photon")
async def ws_photon(ws: WebSocket):
    await _listen_only(ws, "photon")


@app.websocket("/v1/dashboard")
async def ws_dashboard(ws: WebSocket):
    await _listen_only(ws, "dashboard")


def checked_source(source: str) -> str:
    s = (source or "").strip()
    if not re.fullmatch(r"[a-z0-9_-]{1,32}", s):
        raise HTTPException(status_code=422, detail="source must be a short lowercase token, e.g. app or photon")
    return s


@app.post("/v1/items")
async def post_item(name: str = Form(...), photo: UploadFile = File(...), source: str = Form("app"),
                    caller=Depends(require_caller)):
    src = checked_source(source)
    try:
        res, out = brain.register(name.strip(), await photo.read(), source=src)
        dash.observe_registration(name.strip(), res, src)
    except OSError as e:
        raise HTTPException(status_code=422, detail=f"unreadable photo: {e}")
    await dispatch(out)
    return res


@app.post("/v1/labels")
async def post_label(name: str = Form(...), touch_id: str | None = Form(None), item_id: str | None = Form(None),
                     text: str | None = Form(None), audio: UploadFile | None = File(None), source: str = Form("photon"),
                     caller=Depends(require_caller)):
    src = checked_source(source)
    if not touch_id and not item_id:
        raise HTTPException(status_code=422, detail="give touch_id (label what was touched) or item_id (relabel an item)")
    data = await audio.read() if audio is not None else None
    ext = (Path(audio.filename).suffix.lstrip(".") if audio is not None and audio.filename else "m4a")
    try:
        out = brain.label(touch_id, item_id, name.strip(), text, data, ext, source=src)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    pending_labels.resolve(touch_id)
    await dispatch(out)
    item = next((m["item_id"] for _, m in out if m.get("type") == "label_ready"), None)
    return dict(status="ok", item_id=item)          # Photon adds a later voice note to this item_id


@app.delete("/v1/items")
async def delete_items(source: str, caller=Depends(require_caller)):
    """Forget every item (and its label, voice note and saved files) registered by one source, e.g. source=photon
    when a caretaker texts /restart to start testing afresh. The phone's own setup items (source=app) are untouched."""
    removed, out = brain.remove(checked_source(source))
    await dispatch(out)
    return dict(status="ok", removed=removed)


@app.get("/")
def status(caller=Depends(require_caller)):
    """What a browser shows at the server's URL: it's up, who you are, where the API is (behind the same gate)."""
    return dict(service="marco", ok=True, signed_in_as=caller, mode=os.environ.get("MARCO_MODE", "stub"),
                items=len(brain.items_public()), api="/v1/... (docs/INTERFACES.md); try /v1/items")


@app.get("/v1/items")
def get_items(caller=Depends(require_caller)):
    return brain.items_public()


@app.get("/v1/timeline")
def get_timeline(item_id: str | None = None, caller=Depends(require_caller)):
    return [e for e in brain.events if item_id is None or e.get("item_id") == item_id]


@app.get("/v1/touch/{touch_id}/crop.jpg")
def get_crop(touch_id: str, caller=Depends(require_caller)):
    tc = brain.touches.get(touch_id)
    if tc is None:
        raise HTTPException(status_code=404, detail="unknown touch_id")
    return Response(tc["crop_jpeg"], media_type="image/jpeg")


@app.get("/v1/audio/{audio_id}")
def get_audio(audio_id: str, caller=Depends(require_caller)):
    a = brain.audio.get(audio_id)
    if a is None:
        raise HTTPException(status_code=404, detail="unknown audio_id")
    data, ext = a
    return Response(data, media_type={"m4a": "audio/mp4", "caf": "audio/x-caf", "mp3": "audio/mpeg", "wav": "audio/wav"}.get(ext, "application/octet-stream"))


# ---------------------------------------------------------------- the dashboard's API (frontend/docs/fastapi-handoff.md)
# Each route also answers under /api, the browser's default base path, so it works with or without a proxy that
# strips the prefix. All of them sit behind the same auth gate as /v1.

@app.get("/dashboard/snapshot")
@app.get("/api/dashboard/snapshot")
def dashboard_snapshot(caller=Depends(require_caller)):
    return dash.snapshot()


@app.websocket("/events")
@app.websocket("/api/events")
async def dashboard_events(ws: WebSocket):
    """A complete snapshot at once, then after each change (at most 5/s) and at least once a second."""
    await ws.accept()
    if await ws_caller(ws) is None:
        return
    while True:
        snap = dash.snapshot()               # outside the try: a bug here must not look like a disconnect
        try:
            await ws.send_json(snap)
        except Exception:                    # the browser went away
            return
        t0 = time.monotonic()
        await dash.wait_change(1.0)
        rest = MIN_PUSH_S - (time.monotonic() - t0)
        if rest > 0:
            await asyncio.sleep(rest)


@app.post("/dashboard/commands")
@app.post("/api/dashboard/commands")
async def dashboard_command(request: Request, caller=Depends(require_caller)):
    """Find or Stop for the bound phone. 202 means sent; the snapshot's lastCommand follows the phone's answer."""
    try:
        body = await request.json()
    except (ValueError, UnicodeDecodeError):
        body = None
    try:
        rec, msg = dash.relay.submit(body, session_id=dash.session_id, device_id=dash.device_id(),
                                     connected=dash.phone_connected(), item=dash.item)
    except CommandError as e:
        return JSONResponse(e.body(), status_code=e.status)
    cid = rec["cmd"]["commandId"]
    if msg is not None:                                  # new: to the bound phone's outbox only (a retry sends nothing)
        if dash.phone_ws is None or not hub.send_to(dash.phone_ws, msg):
            dash.relay.failed(cid, "phone_disconnected: the command couldn't be sent.")
            return JSONResponse(CommandError(409, "phone_disconnected", "iPhone is disconnected.").body(), status_code=409)
        recorder.message(dash.session_id or "server", "out", msg)
        dash.observe("dashboard", dict(type="command_sent"))
    return JSONResponse(dict(commandId=cid, status="pending"), status_code=202)


def _media(data, media_type):
    return Response(data, media_type=media_type, headers={"Cache-Control": "private, max-age=60"})


@app.get("/media/frames/{token}.jpg")
@app.get("/api/media/frames/{token}.jpg")
def media_frame(token: str, caller=Depends(require_caller)):
    f = dash.frame(token)
    if f is None:
        raise HTTPException(status_code=404, detail="that frame has expired")
    return _media(f["jpeg"], "image/jpeg")


@app.get("/media/items/{item_id}.jpg")
@app.get("/api/media/items/{item_id}.jpg")
def media_item_photo(item_id: str, caller=Depends(require_caller)):
    photo = brain.registry.photo(item_id) if SAFE_ID.match(item_id) else None
    if photo is None:
        raise HTTPException(status_code=404, detail="no photo for that item")
    return _media(photo, "image/jpeg")


@app.get("/media/audio/{audio_id}")
@app.get("/api/media/audio/{audio_id}")
def media_audio(audio_id: str, caller=Depends(require_caller)):
    return get_audio(audio_id, caller)


@app.get("/media/touch/{touch_id}.jpg")
@app.get("/api/media/touch/{touch_id}.jpg")
def media_touch(touch_id: str, caller=Depends(require_caller)):
    return get_crop(touch_id, caller)


@app.get("/app")
def dashboard_app_root(caller=Depends(require_caller)):
    return RedirectResponse("/app/")


@app.get("/app/{path:path}")
def dashboard_app(path: str, caller=Depends(require_caller)):
    """The built dashboard (frontend/dist), when MARCO_DASHBOARD_DIR points at it: one origin with the API, so the
    browser's calls carry the same tailnet login. Unknown paths get index.html (client-side routes)."""
    root_dir = os.environ.get("MARCO_DASHBOARD_DIR")
    if not root_dir:
        raise HTTPException(status_code=404, detail="the dashboard isn't installed on this server (MARCO_DASHBOARD_DIR)")
    root = Path(root_dir).resolve()
    target = (root / path).resolve() if path else root / "index.html"
    if target != root and root not in target.parents:
        raise HTTPException(status_code=404, detail="not found")
    if not target.is_file():
        target = root / "index.html"
    if not target.is_file():
        raise HTTPException(status_code=404, detail="the dashboard build has no index.html")
    return FileResponse(target)


def main():
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit(f"refusing to bind {host}: the server binds loopback only. Reach it from other devices "
                         "through `tailscale serve` (see server/README.md), never a public or LAN bind.")
    uvicorn.run(app, host=host, port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()
