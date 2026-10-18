"""POST /v1/reset: a fresh demo. Every item, its saved files, the history and the room map are forgotten, by the
server and the dashboard, and stay forgotten after a restart. It needs {"confirm": "reset"} and is gated."""
import importlib
import importlib.util
import io
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from helpers import jpeg_bytes
from marco import brain as B, codec
from marco.perception.detector import TruthDetector
from marco.session import Session

TOOLS = Path(__file__).resolve().parents[1] / "tools"


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("MARCO_DATA", str(tmp_path))
    monkeypatch.setenv("MARCO_MODE", "stub")
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
    import marco.app
    m = importlib.reload(marco.app)
    return m, TestClient(m.app), tmp_path


def test_reset_needs_confirming_and_forgets_everything_for_good(app):
    m, c, data = app
    for name in ("keys", "mug"):
        assert c.post("/v1/items", data={"name": name}, files={"photo": ("p.jpg", jpeg_bytes(), "image/jpeg")}).status_code == 200
    m.dash.observe("dashboard", dict(type="timeline", events=[dict(kind="seen", item_id=c.get("/v1/items").json()[0]["item_id"],
                                                                    t_wall="2026-10-18T10:00:00.000Z")]))
    assert c.post("/v1/reset", json={}).status_code == 400                              # not by accident
    r = c.post("/v1/reset", json={"confirm": "reset"})
    assert r.status_code == 200 and sorted(x["name"] for x in r.json()["removed"]) == ["keys", "mug"]
    assert c.get("/v1/items").json() == []
    snap = c.get("/dashboard/snapshot").json()["data"]
    assert snap["items"] == [] and snap["recentMemory"] == [] and snap["registrations"] == []
    assert not list((data / "registry" / "photos").glob("*.jpg"))
    m2 = importlib.reload(m)                                                             # a restart
    assert TestClient(m2.app).get("/v1/items").json() == []


def test_reset_is_gated(tmp_path, monkeypatch):
    monkeypatch.setenv("MARCO_DATA", str(tmp_path))
    monkeypatch.delenv("AUTH_TEST_BYPASS", raising=False)
    monkeypatch.delenv("MARCO_AUTH", raising=False)
    import marco.app
    c = TestClient(importlib.reload(marco.app).app)
    assert c.post("/v1/reset", json={"confirm": "reset"}).status_code == 403


@pytest.fixture(scope="module")
def fake(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("fake_session", TOOLS / "fake_session.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["fake_session"] = mod
    spec.loader.exec_module(mod)
    d = tmp_path_factory.mktemp("reset") / "fake"
    mod.main(str(d))
    return d


def test_the_real_brain_forgets_items_history_and_the_room_map(fake, tmp_path, monkeypatch):
    monkeypatch.setattr(B, "LAYOUT_ASYNC", False)
    s = Session(fake)
    b = B.RealBrain(TruthDetector(s.truth["items"]), tmp_path)
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (128, 128, 128)).save(buf, "JPEG")
    for name in s.truth["items"]:
        b.register(name, buf.getvalue())
    for meta in s.frames[:10]:
        jpeg, d, c = s.frame_bytes(meta)
        b.on_frame(meta, jpeg, codec.decode_depth(d), codec.decode_conf(c))
    assert b.world.events and b.roommap.cells and b.detector.items
    removed, out = b.reset()
    assert len(removed) == len(s.truth["items"]) and out[0][1]["items"] == []
    assert not b.world.items and not b.world.events and not b.roommap.cells and not b.detector.items
    assert not b.registry.records and b.debug_detection()["recent_frames"] == []
    assert not B.RealBrain(TruthDetector(s.truth["items"]), tmp_path).world.items      # gone after a restart too
