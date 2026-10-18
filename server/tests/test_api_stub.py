"""The whole INTERFACES.md protocol against the stub brain, in-process (FastAPI TestClient opens no socket)."""
import importlib
import json

import pytest
from fastapi.testclient import TestClient

from helpers import emulated, frame_parts, jpeg_bytes, pose_msg


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("MARCO_DATA", str(tmp_path))
    monkeypatch.setenv("MARCO_MODE", "stub")
    monkeypatch.setenv("STUB_SPEEDUP", "200")
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
    import marco.app
    import marco.stub
    importlib.reload(marco.stub)
    app_mod = importlib.reload(marco.app)
    return app_mod, TestClient(app_mod.app), tmp_path


def test_everything_is_closed_without_auth(tmp_path, monkeypatch):
    monkeypatch.setenv("MARCO_DATA", str(tmp_path))
    monkeypatch.delenv("AUTH_TEST_BYPASS", raising=False)
    monkeypatch.delenv("MARCO_AUTH", raising=False)
    import marco.app
    c = TestClient(importlib.reload(marco.app).app)
    data, files, _ = frame_parts()
    assert c.post("/v1/frames", data=data, files=files).status_code == 403
    assert c.get("/v1/items").status_code == 403
    for builtin in ("/docs", "/redoc", "/openapi.json"):                 # FastAPI's own pages skip the gate: off
        assert c.get(builtin).status_code == 404
    assert c.post("/v1/items", data={"name": "keys"}, files={"photo": ("p.jpg", jpeg_bytes(), "image/jpeg")}).status_code == 403
    from starlette.websockets import WebSocketDisconnect
    with pytest.raises(WebSocketDisconnect) as e:
        with c.websocket_connect("/v1/phone") as ws:
            ws.receive_json()
    assert e.value.code == 1008


def test_tailscale_mode_only_admits_allowed_logins(tmp_path, monkeypatch):
    monkeypatch.setenv("MARCO_DATA", str(tmp_path))
    monkeypatch.delenv("AUTH_TEST_BYPASS", raising=False)
    monkeypatch.setenv("MARCO_AUTH", "tailscale")
    monkeypatch.setenv("TAILSCALE_ALLOWED_LOGINS", "vedant@example.com, utkarsh@example.com")
    import marco.app
    c = TestClient(importlib.reload(marco.app).app)
    assert c.get("/v1/items").status_code == 403
    assert c.get("/v1/items", headers={"Tailscale-User-Login": "stranger@example.com"}).status_code == 403
    assert c.get("/v1/items", headers={"Tailscale-User-Login": "Utkarsh@example.com"}).status_code == 200


def test_frame_upload_is_accepted_recorded_and_streamed_to_the_dashboard(server):
    app_mod, c, tmp = server
    with c.websocket_connect("/v1/dashboard") as dash:
        first = dash.receive_json()
        assert first["type"] == "world"
        dash.receive_json()                              # timeline
        data, files, meta = frame_parts(frame_id=7)
        r = c.post("/v1/frames", data=data, files=files)
        assert r.status_code == 202 and r.json()["status"] == "accepted"
        kinds = set()
        for _ in range(3):
            kinds.add(dash.receive_json()["type"])
        assert {"frame", "map_points", "world"} <= kinds
    sess = tmp / "sessions" / "s1"
    assert (sess / "frames" / "000007.jpg").exists() and (sess / "frames" / "000007.depth").exists()
    assert json.loads((sess / "frames.jsonl").read_text().splitlines()[0])["frame_id"] == 7


@pytest.mark.parametrize("problem, match", [
    ("row_major", "column-major"),
    ("exif", "EXIF orientation"),
    ("rotated_jpeg", "unrotated"),
    ("bad_depth", "zlib"),
])
def test_bad_frames_are_rejected_with_a_reason(server, problem, match):
    _, c, _ = server
    kw = {}
    if problem == "row_major":
        kw["row_major"] = True
    data, files, _ = frame_parts(**kw)
    if problem == "exif":
        files["image"] = ("f.jpg", jpeg_bytes(exif_orientation=6), "image/jpeg")
    if problem == "rotated_jpeg":
        files["image"] = ("f.jpg", jpeg_bytes(720, 960), "image/jpeg")     # portrait pixels instead of the sensor image
    if problem == "bad_depth":
        files["depth"] = ("f.depth", b"not compressed", "application/octet-stream")
    r = c.post("/v1/frames", data=data, files=files)
    assert r.status_code == 422 and match in r.json()["detail"]


def test_find_then_guidance_produces_proximity_and_touch(server):
    _, c, _ = server
    _, T, _, _ = emulated()
    with c.websocket_connect("/v1/phone") as ws:
        ws.send_json(pose_msg(T))
        ws.send_json(dict(type="query", query_id="q1", kind="find", name="keys"))
        ans = ws.receive_json()
        assert ans["type"] == "answer" and ans["found"] and ans["name"] == "keys" and len(ans["position"]) == 3
        ws.send_json(dict(type="guidance", item_id=ans["item_id"], phase="behind", rel_azimuth_deg=180, distance_m=2.0))
        seen = []
        while True:
            m = ws.receive_json()
            seen.append(m["type"])
            if m["type"] == "touch_end":
                break
        assert seen.count("hand_proximity") > 10 and "touch" in seen


def test_what_is_this_goes_to_photon_and_comes_back_as_a_label(server):
    _, c, _ = server
    _, T, _, _ = emulated()
    data, files, _ = frame_parts()
    assert c.post("/v1/frames", data=data, files=files).status_code == 202
    with c.websocket_connect("/v1/photon") as photon, c.websocket_connect("/v1/phone") as ws:
        ws.send_json(pose_msg(T))
        ws.send_json(dict(type="query", query_id="q2", kind="what_is_this"))
        ans = ws.receive_json()
        assert ans["status"] == "unknown"
        req = photon.receive_json()
        assert req["type"] == "label_request" and req["touch_id"] == ans["touch_id"]
        crop = c.get(req["crop_url"])
        assert crop.status_code == 200 and crop.headers["content-type"] == "image/jpeg"
        r = c.post("/v1/labels", data={"touch_id": req["touch_id"], "name": "cumin", "text": "That's the cumin, love"},
                   files={"audio": ("memo.m4a", b"fake-audio", "audio/mp4")})
        assert r.status_code == 200
        ready = ws.receive_json()
        assert ready["type"] == "label_ready" and ready["name"] == "cumin" and ready["label_audio_url"]
        assert r.json() == dict(status="ok", item_id=ready["item_id"])
        assert c.get(ready["label_audio_url"]).content == b"fake-audio"
        ws.send_json(dict(type="query", query_id="q3", kind="what_is_this"))
        again = ws.receive_json()
        assert again["status"] == "known" and again["label_text"] == "That's the cumin, love"


def test_registration_retake_and_ok(server):
    _, c, _ = server
    assert c.post("/v1/items", data={"name": "keys"}, files={"photo": ("p.jpg", jpeg_bytes(32, 32), "image/jpeg")}).json()["quality"] == "retake"
    ok = c.post("/v1/items", data={"name": "remote"}, files={"photo": ("p.jpg", jpeg_bytes(), "image/jpeg")}).json()
    assert ok["quality"] == "ok" and any(i["name"] == "remote" for i in c.get("/v1/items").json())


def test_root_url_says_the_server_is_up_but_only_behind_the_gate(server, monkeypatch):
    _, c, _ = server
    r = c.get("/")
    assert r.status_code == 200 and r.json()["ok"] is True and r.json()["signed_in_as"] == "test-bypass"
    monkeypatch.delenv("AUTH_TEST_BYPASS")
    assert c.get("/").status_code == 403                          # closed without a login, like every route


def test_set_place_door_needs_a_pose_then_answers_ok(server):
    _, c, _ = server
    _, T, _, _ = emulated()
    with c.websocket_connect("/v1/phone") as ws:
        ws.send_json(dict(type="query", query_id="d0", kind="set_place", name="door"))
        assert ws.receive_json()["type"] == "error"                 # no pose yet
        ws.send_json(pose_msg(T))
        ws.send_json(dict(type="query", query_id="d1", kind="set_place", name="door"))
        ans = ws.receive_json()
        assert ans == dict(type="answer", query_id="d1", kind="set_place", name="door", ok=True)


def test_bad_websocket_messages_get_an_error_not_a_disconnect(server):
    _, c, _ = server
    with c.websocket_connect("/v1/phone") as ws:
        ws.send_json(dict(type="hand", joints=[], depth_patches_f16_b64="", conf_patches_u8_b64=""))
        err = ws.receive_json()
        assert err["type"] == "error"
        ws.send_json(dict(type="query", query_id="q", kind="find", name="nothing"))
        assert ws.receive_json()["type"] == "answer"
