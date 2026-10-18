"""Marco server: the INTERFACES.md protocol. MARCO_MODE=stub (default) answers with fake perception; the real
pipeline plugs in behind the same methods later.

Run (loopback only):  AUTH_TEST_BYPASS=1 python -m marco.app        # local development on this laptop
                      MARCO_AUTH=tailscale TAILSCALE_ALLOWED_LOGINS=a@x,b@y python -m marco.app   # + tailscale serve
"""
import asyncio
import json
import os
from pathlib import Path

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import Response

from . import codec, geometry as G
from .auth import require_caller, ws_caller
from .hub import Hub
from .recorder import Recorder
from .stub import StubBrain

DATA = Path(os.environ.get("MARCO_DATA", Path(__file__).resolve().parents[1] / "data"))
REQUIRED_META = ("session_id", "map_id", "frame_id", "t_device", "camera_transform", "intrinsics", "image_resolution")

app = FastAPI(title="Marco server", version="0.1")
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
latest_frame: dict[str, int] = {}
work_lock = asyncio.Lock()


async def dispatch(out):
    for channel, msg in out:
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
    sid, fid = m["session_id"], int(m["frame_id"])
    latest_frame[sid] = max(fid, latest_frame.get(sid, -1))
    async with work_lock:                               # one frame through the brain at a time
        if fid < latest_frame[sid]:
            return dict(frame_id=fid, status="superseded")   # a newer frame arrived while this one waited
        out = await run_in_threadpool(brain.on_frame, m, jpeg, d, c)
    await dispatch(out)
    return dict(frame_id=fid, status="accepted")


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


async def _listen_only(ws: WebSocket, channel: str):
    await ws.accept()
    if await ws_caller(ws) is None:
        return
    hub.join(channel, ws)
    try:
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


@app.post("/v1/items")
async def post_item(name: str = Form(...), photo: UploadFile = File(...), caller=Depends(require_caller)):
    try:
        res, out = brain.register(name.strip(), await photo.read())
    except OSError as e:
        raise HTTPException(status_code=422, detail=f"unreadable photo: {e}")
    await dispatch(out)
    return res


@app.post("/v1/labels")
async def post_label(name: str = Form(...), touch_id: str | None = Form(None), item_id: str | None = Form(None),
                     text: str | None = Form(None), audio: UploadFile | None = File(None), caller=Depends(require_caller)):
    if not touch_id and not item_id:
        raise HTTPException(status_code=422, detail="give touch_id (label what was touched) or item_id (relabel an item)")
    data = await audio.read() if audio is not None else None
    ext = (Path(audio.filename).suffix.lstrip(".") if audio is not None and audio.filename else "m4a")
    try:
        out = brain.label(touch_id, item_id, name.strip(), text, data, ext)
    except KeyError as e:
        raise HTTPException(status_code=404, detail=str(e))
    await dispatch(out)
    item = next((m["item_id"] for _, m in out if m.get("type") == "label_ready"), None)
    return dict(status="ok", item_id=item)          # Photon adds a later voice note to this item_id


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


def main():
    import uvicorn

    host = os.environ.get("HOST", "127.0.0.1")
    if host not in ("127.0.0.1", "localhost", "::1"):
        raise SystemExit(f"refusing to bind {host}: the server binds loopback only. Reach it from other devices "
                         "through `tailscale serve` (see server/README.md), never a public or LAN bind.")
    uvicorn.run(app, host=host, port=int(os.environ.get("PORT", "8000")))


if __name__ == "__main__":
    main()
