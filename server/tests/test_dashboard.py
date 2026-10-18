"""The dashboard adapter (marco/dashboard.py, dashboard_commands.py) against the stub brain, in-process: snapshots
validate against the browser's exported JSON Schema (frontend/docs/dashboard.snapshot.schema.json) plus the
refinements JSON Schema can't express, the event socket, media, Find/Stop with phone acknowledgement, and access."""
import importlib
import io
import json
import time
from pathlib import Path

import jsonschema
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from helpers import emulated, frame_parts, jpeg_bytes, pose_msg

SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "frontend" / "docs" / "dashboard.snapshot.schema.json").read_text())
VALIDATOR = jsonschema.validators.validator_for(SCHEMA)(SCHEMA)


def valid(snap):
    """Schema-valid, plus schema.ts's refinements (positive map area, boxes with x2 > x1 and y2 > y1)."""
    VALIDATOR.validate(snap)
    m = snap["data"]["map"]
    if m is not None:
        b = m["bounds"]
        assert b["maxX"] > b["minX"] and b["maxZ"] > b["minZ"]
    cam = snap["data"]["camera"]
    if cam is not None:
        for box in cam["boxes"]:
            x1, y1, x2, y2 = box["boxPx"]
            assert x2 > x1 and y2 > y1
    return snap["data"]


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("MARCO_DATA", str(tmp_path))
    monkeypatch.setenv("MARCO_MODE", "stub")
    monkeypatch.setenv("STUB_SPEEDUP", "200")
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
    monkeypatch.setenv("DASHBOARD_COMMAND_TIMEOUT_S", "0.4")
    monkeypatch.delenv("MARCO_DASHBOARD_DIR", raising=False)
    import marco.app
    import marco.stub
    importlib.reload(marco.stub)
    app_mod = importlib.reload(marco.app)
    return app_mod, TestClient(app_mod.app)


def live_phone(c, ws):
    """A connected phone: a pose on the socket, and one frame (the stub places its fake items around the user)."""
    _, T, _, _ = emulated()
    ws.send_json(pose_msg(T))
    data, files, _ = frame_parts()
    assert c.post("/v1/frames", data=data, files=files).status_code == 202
    return T


def synced(ws, n=[0]):
    """Wait until the server has handled everything sent on this phone socket (messages are handled in order)."""
    n[0] += 1
    qid = f"sync-{n[0]}"
    ws.send_json(dict(type="query", session_id="s1", query_id=qid, kind="find", name="mug"))
    while ws.receive_json().get("query_id") != qid:
        pass


def test_every_dashboard_route_is_closed_without_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("MARCO_DATA", str(tmp_path))
    monkeypatch.delenv("AUTH_TEST_BYPASS", raising=False)
    monkeypatch.delenv("MARCO_AUTH", raising=False)
    import marco.app
    c = TestClient(importlib.reload(marco.app).app)
    for path in ("/dashboard/snapshot", "/api/dashboard/snapshot", "/media/frames/1-1.jpg", "/api/media/items/x.jpg",
                 "/media/audio/a", "/media/touch/t.jpg", "/app", "/app/index.html"):
        assert c.get(path).status_code == 403, path
    for path in ("/dashboard/commands", "/api/dashboard/commands"):
        assert c.post(path, json={"commandId": "c1", "deviceId": "d", "type": "stop"}).status_code == 403
    from starlette.websockets import WebSocketDisconnect
    for path in ("/events", "/api/events"):
        with pytest.raises(WebSocketDisconnect) as e:
            with c.websocket_connect(path) as ws:
                ws.receive_json()
        assert e.value.code == 1008


def test_before_any_phone_the_snapshot_is_valid_and_says_so(server):
    _, c = server
    for path in ("/dashboard/snapshot", "/api/dashboard/snapshot"):
        snap = c.get(path).json()
        assert snap["type"] == "dashboard.snapshot" and snap["schemaVersion"] == 1
        d = valid(snap)
        assert d["devices"]["phone"]["state"] == "disconnected" and d["devices"]["phone"]["tracking"] == "unavailable"
        assert d["map"] is None and d["camera"] is None and d["wearer"] is None and d["lastCommand"] is None
        assert d["navigation"]["state"] == "unavailable" and d["navigation"]["audioPattern"] == "off"


def test_live_phone_state_maps_into_the_snapshot_and_media_loads(server):
    _, c = server
    with c.websocket_connect("/v1/phone") as ws:
        live_phone(c, ws)
        assert c.post("/v1/items", data={"name": "remote"}, files={"photo": ("p.jpg", jpeg_bytes(), "image/jpeg")}).json()["quality"] == "ok"
        d = valid(c.get("/dashboard/snapshot").json())
    assert d["session"]["id"] == "s1" and d["session"]["deviceId"] == "s1" and d["session"]["worldMapId"] == "m1"
    assert d["devices"]["phone"] == dict(state="connected", lastMessageAt=d["devices"]["phone"]["lastMessageAt"], tracking="normal")
    w = d["wearer"]
    assert w["worldMapId"] == "m1" and isinstance(w["position"]["x"], float) and w["headYawDeg"] is not None
    items = {it["name"]: it for it in d["items"]}
    assert {"keys", "mug", "bottle", "remote"} <= set(items)
    keys = items["keys"]["lastSeen"]
    assert keys["worldMapId"] == "m1" and keys["position"] is not None and keys["surface"]
    assert items["remote"]["lastSeen"] is None and items["remote"]["photoUrl"] == f"/media/items/{items['remote']['id']}.jpg"
    photo = c.get("/api" + items["remote"]["photoUrl"])
    assert photo.status_code == 200 and photo.headers["content-type"] == "image/jpeg"
    cam = d["camera"]
    img = c.get("/api" + cam["imageUrl"])
    assert img.status_code == 200 and Image.open(io.BytesIO(img.content)).size == (cam["widthPx"], cam["heightPx"])
    assert cam["frameId"] == 1 and cam["capturedAt"] == "2026-10-17T15:00:00.000Z"
    for box in cam["boxes"]:                                       # upright pixels, inside the upright image
        assert 0 <= box["boxPx"][0] < box["boxPx"][2] <= cam["widthPx"] and 0 <= box["boxPx"][1] < box["boxPx"][3] <= cam["heightPx"]
    assert c.get("/media/frames/999-999.jpg").status_code == 404
    assert c.get("/media/items/..%2F..%2Fsecret.jpg").status_code == 404


def test_guidance_labels_and_memory(server):
    _, c = server
    with c.websocket_connect("/v1/photon") as photon, c.websocket_connect("/v1/phone") as ws:
        live_phone(c, ws)
        ws.send_json(dict(type="guidance", session_id="s1", item_id="fake-keys", phase="approach", rel_azimuth_deg=-30.5,
                          distance_m=1.2))
        synced(ws)
        nav = valid(c.get("/dashboard/snapshot").json())["navigation"]
        assert nav["state"] == "guiding" and nav["audioPattern"] == "beacon" and nav["targetItemId"] == "fake-keys"
        assert nav["bearingDeg"] == -30.5 and nav["bearingReference"] == "head" and nav["distanceM"] == 1.2
        ws.send_json(dict(type="guidance", session_id="s1", item_id="fake-keys", phase="reach", rel_azimuth_deg=0, distance_m=0.3))
        synced(ws)
        assert valid(c.get("/dashboard/snapshot").json())["navigation"]["audioPattern"] == "steady"
        while ws.receive_json()["type"] != "touch_end":            # the stub's fake hand reaches and touches
            pass
        ws.send_json(dict(type="query", session_id="s1", query_id="w1", kind="what_is_this"))
        assert ws.receive_json()["status"] == "unknown"
        req = photon.receive_json()
        regs = valid(c.get("/dashboard/snapshot").json())["registrations"]
        assert regs[0]["id"] == req["touch_id"] and regs[0]["status"] == "waiting_for_label"
        assert c.get("/api" + regs[0]["photoUrl"]).headers["content-type"] == "image/jpeg"
        c.post("/v1/labels", data={"touch_id": req["touch_id"], "name": "cumin", "text": "That's the cumin, love"},
               files={"audio": ("memo.m4a", b"fake-audio", "audio/mp4")})
        d = valid(c.get("/dashboard/snapshot").json())
    reg = next(r for r in d["registrations"] if r["id"] == req["touch_id"])
    assert reg["status"] == "saved" and reg["label"]["transcript"] == "That's the cumin, love"
    cumin = next(it for it in d["items"] if it["name"] == "cumin")
    assert reg["itemId"] == cumin["id"] and cumin["voiceLabel"]["audioUrl"].startswith("/media/audio/")
    assert c.get(cumin["voiceLabel"]["audioUrl"]).content == b"fake-audio"
    assert d["recentMemory"][0]["kind"] == "label_saved" and d["recentMemory"][0]["itemId"] == cumin["id"]


def test_events_socket_sends_at_once_then_heartbeats_and_never_rolls_back(server):
    _, c = server
    first = c.get("/dashboard/snapshot").json()
    with c.websocket_connect("/api/events") as ev:
        t0 = time.monotonic()
        a = ev.receive_json()
        b = ev.receive_json()                                     # nothing changed: a heartbeat
        dt = time.monotonic() - t0
    assert a["streamId"] == b["streamId"] == first["streamId"]
    assert first["sequence"] < a["sequence"] < b["sequence"] and dt < 1.6
    valid(a)


def test_find_and_stop_go_to_the_phone_and_follow_its_answer(server):
    _, c = server
    cmd = dict(commandId="c-1", deviceId="s1", type="find", itemId="fake-keys")
    r = c.post("/api/dashboard/commands", json=cmd)
    assert r.status_code == 409 and r.json()["error"]["code"] == "phone_disconnected"
    with c.websocket_connect("/v1/phone") as ws:
        live_phone(c, ws)
        r = c.post("/api/dashboard/commands", json=cmd)
        assert r.status_code == 202 and r.json() == dict(commandId="c-1", status="pending")
        msg = ws.receive_json()
        while msg["type"] != "command":
            msg = ws.receive_json()
        assert msg["action"] == "find" and msg["item_id"] == "fake-keys" and msg["session_id"] == "s1"
        assert len(msg["position"]) == 3 and msg["name"] == "keys" and msg["expires_wall"].endswith("Z")
        assert valid(c.get("/dashboard/snapshot").json())["lastCommand"] == dict(commandId="c-1", status="pending", reason=None)
        ws.send_json(dict(type="command_ack", session_id="s1", command_id="c-1", status="accepted"))
        ws.send_json(dict(type="command_ack", session_id="s1", command_id="c-1", status="applied"))
        ws.send_json(dict(type="query", session_id="s1", query_id="q1", kind="find", name="mug"))
        nxt = ws.receive_json()
        while nxt.get("type") == "hand_proximity":
            nxt = ws.receive_json()
        assert nxt["type"] == "answer" and nxt["query_id"] == "q1"   # acks are for the adapter: no error reply
        assert valid(c.get("/dashboard/snapshot").json())["lastCommand"]["status"] == "completed"
        assert c.post("/dashboard/commands", json=cmd).json() == dict(commandId="c-1", status="pending")   # a retry
        bad = c.post("/dashboard/commands", json=dict(cmd, type="stop", itemId=None))
        assert bad.status_code == 409 and bad.json()["error"]["code"] == "command_conflict"
        assert c.post("/dashboard/commands", json=dict(cmd, commandId="c-2", itemId="nope")).json()["error"]["code"] == "unknown_item"
        assert c.post("/dashboard/commands", json=dict(cmd, commandId="c-3", deviceId="old")).json()["error"]["code"] == "session_mismatch"
        assert c.post("/dashboard/commands", json={"type": "find"}).status_code == 400
        assert c.post("/dashboard/commands", content=b"not json", headers={"content-type": "application/json"}).status_code == 400
        rid = c.post("/v1/items", data={"name": "remote"}, files={"photo": ("p.jpg", jpeg_bytes(), "image/jpeg")}).json()["item_id"]
        r = c.post("/dashboard/commands", json=dict(cmd, commandId="c-4", itemId=rid))   # registered, never seen
        assert r.status_code == 409 and r.json()["error"]["code"] == "location_unavailable"
        assert c.post("/dashboard/commands", json=dict(commandId="c-5", deviceId="s1", type="stop")).status_code == 202
        msg = ws.receive_json()
        while msg["type"] != "command":
            msg = ws.receive_json()
        assert msg["action"] == "stop" and "item_id" not in msg
        time.sleep(0.6)                                            # no answer within the (test) timeout
        last = valid(c.get("/dashboard/snapshot").json())["lastCommand"]
        assert last["commandId"] == "c-5" and last["status"] == "rejected" and last["reason"].startswith("no_answer")


def test_a_new_phone_session_rejects_open_commands(server):
    _, c = server
    with c.websocket_connect("/v1/phone") as ws:
        live_phone(c, ws)
        assert c.post("/dashboard/commands", json=dict(commandId="c-9", deviceId="s1", type="stop")).status_code == 202
        _, T, _, _ = emulated()
        ws.send_json(pose_msg(T, t=2000.0, session="s2"))         # the app restarted
        ws.send_json(dict(type="query", session_id="s2", query_id="z", kind="find", name="mug"))
        while ws.receive_json().get("query_id") != "z":
            pass
        d = valid(c.get("/dashboard/snapshot").json())
    assert d["session"]["id"] == "s2" and d["lastCommand"]["status"] == "rejected"
    assert d["lastCommand"]["reason"].startswith("session_replaced")


def test_the_built_dashboard_is_served_behind_the_gate(server, tmp_path, monkeypatch):
    _, c = server
    assert c.get("/app/").status_code == 404                       # not installed
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>marco</html>")
    (dist / "assets" / "app.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("no")
    monkeypatch.setenv("MARCO_DASHBOARD_DIR", str(dist))
    assert c.get("/app", follow_redirects=False).status_code in (302, 307)
    assert c.get("/app/").text == "<html>marco</html>"
    assert "javascript" in c.get("/app/assets/app.js").headers["content-type"]
    assert c.get("/app/objects/keys").text == "<html>marco</html>"                 # client-side route
    assert c.get("/app/..%2Fsecret.txt").text != "no"
