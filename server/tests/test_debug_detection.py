"""GET /v1/debug/detection: for a live session, why each registered item was or wasn't found in each recent frame."""
import importlib
import importlib.util
import io
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from marco import brain as B, codec, geometry as G
from marco.brain import RealBrain, _failed_gates
from marco.perception.detector import TH, TruthDetector
from marco.session import Session

TOOLS = Path(__file__).resolve().parents[1] / "tools"


@pytest.fixture(scope="module")
def fake(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("fake_session", TOOLS / "fake_session.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["fake_session"] = m
    spec.loader.exec_module(m)
    d = tmp_path_factory.mktemp("debug") / "fake"
    m.main(str(d))
    return d


def dummy_jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (128, 128, 128)).save(buf, "JPEG")
    return buf.getvalue()


def test_every_frame_says_what_each_item_scored_and_where_it_went(fake, monkeypatch):
    monkeypatch.setattr(B, "LAYOUT_ASYNC", False)
    s = Session(fake)
    b = RealBrain(TruthDetector(s.truth["items"]))
    for name in s.truth["items"]:
        b.register(name, dummy_jpeg())
    for meta in s.frames[:12]:
        jpeg, d, c = s.frame_bytes(meta)
        b.on_frame(meta, jpeg, codec.decode_depth(d), codec.decode_conf(c))
    dbg = b.debug_detection()
    assert dbg["detector"] == "TruthDetector" and dbg["frames_seen"] == 12 and dbg["missing_from_detector"] == []
    assert {x["name"] for x in dbg["detector_items"]} == set(s.truth["items"])
    assert [r["outcome"] for r in dbg["registrations"]] == ["ok"] * len(s.truth["items"])
    frames = dbg["recent_frames"]
    assert frames[0]["frame_id"] == s.frames[11]["frame_id"]                      # newest first
    results = [r["result"] for f in frames for r in f["items"]]
    assert any(x.startswith("placed at") for x in results)
    assert all(x.startswith(("placed at", "not present", "present, not placed")) for x in results)


def test_an_item_the_detector_lost_is_named():
    b = RealBrain(TruthDetector({}))
    b.world.add_item("keys")                                                       # e.g. its photo failed to reload
    assert b.debug_detection()["missing_from_detector"] == ["keys"]


def test_reasons_for_not_placing_and_for_not_present():
    b = RealBrain(TruthDetector({}))
    K = np.array([[1500.0, 0, 960], [0, 1500, 720], [0, 0, 1]])
    far = G.Frame(np.eye(4), K, (1920, 1440), np.full((192, 256), 5.5, np.float32), np.full((192, 256), 2, np.uint8))
    pos, why = b.place_why([900, 650, 1000, 750], far)
    assert pos is None and "MAX_RANGE_M" in why
    blind = G.Frame(np.eye(4), K, (1920, 1440), np.full((192, 256), np.nan, np.float32), np.zeros((192, 256), np.uint8))
    assert "no usable LiDAR depth" in b.place_why([900, 650, 1000, 750], blind)[1]
    d = dict(photo_name=TH["photo_name"] + 1, dino=TH["dino"] - 0.1, vs_others=TH["vs_others"] + 1)
    assert _failed_gates(d) == f"DINOv2 crop similarity {d['dino']:.2f} < {TH['dino']:.2f}"


def test_the_route_is_gated_and_works_in_stub_mode(tmp_path, monkeypatch):
    monkeypatch.setenv("MARCO_DATA", str(tmp_path))
    monkeypatch.setenv("MARCO_MODE", "stub")
    monkeypatch.delenv("AUTH_TEST_BYPASS", raising=False)
    monkeypatch.delenv("MARCO_AUTH", raising=False)
    import marco.app
    c = TestClient(importlib.reload(marco.app).app)
    assert c.get("/v1/debug/detection").status_code == 403
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
    r = c.get("/v1/debug/detection")
    assert r.status_code == 200 and r.json()["detector"] == "stub"


class Recorder:
    """A detector that records how each item was registered."""

    def __init__(self, refuse=()):
        self.items, self.calls, self.refuse = {}, [], set(refuse)

    def register(self, item_id, name, im=None, gate=True):
        self.calls.append((name, gate))
        if gate and name in self.refuse:
            return dict(quality="retake", reason="can't see it", box=None)
        self.items[item_id] = name
        return dict(quality="ok", reason="", box=[0, 0, 10, 10])

    def detect(self, *a, **k):
        return []


def test_a_restart_crops_phone_photos_like_registering_did(tmp_path):
    first = RealBrain(Recorder(), tmp_path)
    first.register("keys", dummy_jpeg())
    first.register("wallet", dummy_jpeg())
    from marco.registry import Registry
    Registry(tmp_path / "registry").save("t1", name="jar", source="photon", photo=dummy_jpeg())   # a touch crop
    det = Recorder(refuse={"wallet"})
    after = RealBrain(det, tmp_path)                                               # restart
    assert ("keys", True) in det.calls and ("keys", False) not in det.calls       # cropped, as when registered
    assert ("wallet", True) in det.calls and ("wallet", False) in det.calls       # name check fails now: whole photo
    assert ("jar", False) in det.calls and ("jar", True) not in det.calls         # Photon's crop stays whole
    assert set(det.items.values()) == {"keys", "wallet", "jar"}
    outcomes = {r["name"]: r["outcome"] for r in after.debug_detection()["registrations"]}
    assert outcomes == {"keys": "reloaded after a restart (cropped to the item)",
                        "wallet": "reloaded after a restart (whole photo)", "jar": "reloaded after a restart (whole photo)"}
