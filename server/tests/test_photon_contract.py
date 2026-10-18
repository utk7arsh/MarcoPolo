"""The Photon scaffold's HTTP client (photon-scaffold/src/server.js, run by Node) against a real loopback server: fetch the touch
crop, post a text label, add a voice note to it, register an item. The phone must get label_ready with playable audio."""
import importlib
import json
import shutil
import subprocess
import threading
import time
from pathlib import Path

import httpx
import pytest
from websockets.sync.client import connect

from helpers import emulated, frame_parts, jpeg_bytes, pose_msg
from test_tools import free_port

PHOTON = Path(__file__).resolve().parents[2] / "photon-scaffold"
pytestmark = pytest.mark.skipif(shutil.which("node") is None, reason="needs node")


def test_photon_client_labels_a_touch_and_registers_an_item(tmp_path, monkeypatch):
    import uvicorn
    monkeypatch.setenv("MARCO_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("MARCO_MODE", "stub")
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
    import marco.app
    import marco.stub
    importlib.reload(marco.stub)
    app_mod = importlib.reload(marco.app)
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(app_mod.app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    try:
        data, files, _ = frame_parts()
        assert httpx.post(f"{base}/v1/frames", data=data, files=files).status_code == 202
        _, T, _, _ = emulated()
        with connect(f"ws://127.0.0.1:{port}/v1/phone") as ws:
            ws.send(json.dumps(pose_msg(T)))
            ws.send(json.dumps(dict(type="query", query_id="w1", kind="what_is_this")))
            ans = json.loads(ws.recv(timeout=10))
            assert ans["status"] == "unknown"
            voice, photo = tmp_path / "Audio Message.caf", tmp_path / "keys.jpg"
            voice.write_bytes(b"caf-bytes")
            photo.write_bytes(jpeg_bytes())
            r = subprocess.run(["node", str(PHOTON / "tools" / "smoke.js"), base, ans["touch_id"],
                                f"/v1/touch/{ans['touch_id']}/crop.jpg", str(voice), str(photo)],
                               capture_output=True, text=True, timeout=60)
            assert r.returncode == 0, r.stderr[-2000:]
            out = json.loads(r.stdout.strip().splitlines()[-1])
            assert out["cropIsJpeg"] and out["cropBytes"] > 1000
            assert out["label"]["item_id"] and out["voice"]["item_id"] == out["label"]["item_id"]
            assert out["item"]["quality"] == "ok"
            first, second = json.loads(ws.recv(timeout=10)), json.loads(ws.recv(timeout=10))
            assert first["type"] == second["type"] == "label_ready"
            assert first["label_text"] == "That's the cumin, love" and first["label_audio_url"] is None
            assert second["item_id"] == first["item_id"] and second["label_audio_url"]
            a = httpx.get(base + second["label_audio_url"])
            assert a.content == b"caf-bytes" and a.headers["content-type"] == "audio/x-caf"
        assert any(i["name"] == "keys" for i in httpx.get(f"{base}/v1/items").json())
    finally:
        server.should_exit = True
        th.join(timeout=10)
