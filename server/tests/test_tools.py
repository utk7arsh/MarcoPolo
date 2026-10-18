"""check_recording on good and broken sessions; replay into a real (loopback-only) server end to end."""
import asyncio
import importlib
import importlib.util
import json
import shutil
import socket
import sys
import threading
import time
from pathlib import Path

import numpy as np
import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def fake(tmp_path_factory):
    d = tmp_path_factory.mktemp("rec") / "fake"
    load("fake_session").main(str(d))
    return d


def test_good_recording_passes(fake):
    probs, notes = load("check_recording").check(fake)
    assert probs == [], probs
    assert any("upright turns" in n and ": 1" in n for n in notes)       # portrait vest mount


def test_broken_recordings_are_caught(fake, tmp_path):
    bad = tmp_path / "bad"
    shutil.copytree(fake, bad)
    lines = (bad / "frames.jsonl").read_text().splitlines()
    m = json.loads(lines[0])
    m["camera_transform"] = np.asarray(m["camera_transform"]).reshape(4, 4).T.reshape(-1).tolist()   # row-major by mistake
    lines[0] = json.dumps(m)
    (bad / "frames.jsonl").write_text("\n".join(lines) + "\n")
    from PIL import Image
    p = bad / "frames" / "000002.jpg"
    Image.open(p).transpose(Image.Transpose.ROTATE_270).save(p)           # rotated to portrait before sending
    probs, _ = load("check_recording").check(bad)
    text = "\n".join(probs)
    assert "frame 1" in text and ("orthonormal" in text or "last row" in text)
    assert "frame 2: JPEG 720x960" in text


def free_port():
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_replay_into_a_running_loopback_server(fake, tmp_path, monkeypatch):
    import uvicorn
    monkeypatch.setenv("MARCO_DATA", str(tmp_path / "server-data"))
    monkeypatch.setenv("MARCO_MODE", "real")
    monkeypatch.setenv("MARCO_DETECTOR", "truth")
    monkeypatch.setenv("MARCO_TRUTH", str(fake / "truth.json"))
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
    import marco.app
    app_mod = importlib.reload(marco.app)
    for name in json.loads((fake / "truth.json").read_text())["items"]:          # register the items first
        app_mod.brain.register(name, _jpeg())
    port = free_port()
    server = uvicorn.Server(uvicorn.Config(app_mod.app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=server.run, daemon=True)
    th.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    try:
        replies = asyncio.run(load("replay").replay(str(fake), f"http://127.0.0.1:{port}", speed=200, quiet=True))
    finally:
        server.should_exit = True
        th.join(timeout=10)
    kinds = [r["type"] for r in replies]
    assert "touch" in kinds and "answer" in kinds
    rec = tmp_path / "server-data" / "sessions" / "fake"
    assert len((rec / "frames.jsonl").read_text().splitlines()) == len((fake / "frames.jsonl").read_text().splitlines())


def _jpeg():
    import io
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (128, 128)).save(buf, "JPEG")
    return buf.getvalue()
