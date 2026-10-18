"""The iPhone app's wire formats against the real server. Builds the app's Swift core on this Mac (swiftc, no Xcode),
runs its unit tests, and feeds what it encodes (the frame upload, pose, hand, map, query and guidance messages) to
the server. Also checks the Swift geometry against marco/geometry.py, angle for angle."""
import importlib
import io
import json
import math
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from marco import codec, geometry as G

IOS = Path(__file__).resolve().parents[2] / "ios"
pytestmark = pytest.mark.skipif(sys.platform != "darwin" or shutil.which("swiftc") is None,
                                reason="needs swiftc on macOS (sh ios/check.sh)")


@pytest.fixture(scope="module")
def fx(tmp_path_factory):
    out = tmp_path_factory.mktemp("ios")
    r = subprocess.run(["sh", str(IOS / "check.sh"), "--emit", str(out)], capture_output=True, text=True, timeout=900)
    assert r.returncode == 0, (r.stdout[-4000:] + r.stderr[-4000:])
    assert " 0 failed" in r.stdout, r.stdout[-2000:]
    return out


@pytest.fixture()
def stub(tmp_path, monkeypatch):
    monkeypatch.setenv("MARCO_DATA", str(tmp_path))
    monkeypatch.setenv("MARCO_MODE", "stub")
    monkeypatch.setenv("STUB_SPEEDUP", "200")
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
    import marco.app
    import marco.stub
    importlib.reload(marco.stub)
    app_mod = importlib.reload(marco.app)
    return TestClient(app_mod.app), tmp_path


def truth(fx):
    d = np.frombuffer((fx / "depth_truth.f32").read_bytes(), "<f4").reshape(192, 256)
    c = np.frombuffer((fx / "conf_truth.u8").read_bytes(), np.uint8).reshape(192, 256)
    return d, c


def test_swift_geometry_matches_the_server(fx):
    g = json.loads((fx / "geometry.json").read_text())
    for case in g["heading"]:
        assert abs(G.wrap180(G.heading_deg(G.mat4(case["T"])) - case["heading"][0])) < 1e-3
    checked = 0
    for c in g["azimuth"]:
        u, t, h = np.array(c["user"]), np.array(c["target"]), c["heading"][0]
        az = G.relative_azimuth_deg(u, h, t)
        assert abs(G.wrap180(az - c["rel_az"][0])) < 1e-3
        hd = G.horizontal_distance(u, t)
        assert abs(hd - c["hdist"][0]) < 1e-4
        if abs((az / 30.0) % 1 - 0.5) > 1e-3:                       # skip float32-vs-64 rounding ties
            assert G.clock_position(az) == int(c["clock"][0])
            checked += 1
        if abs((hd / 0.7) % 1 - 0.5) > 1e-3:
            assert G.steps(hd) == int(c["steps"][0])
        # The audio placement (no server twin): listener at the ear facing heading h, x right, y up, -z ahead.
        r = math.radians(h)
        fwd, right = np.array([math.sin(r), 0, -math.cos(r)]), np.array([math.cos(r), 0, math.sin(r)])
        d = t - u
        assert np.allclose(c["listener"], [d @ right, d[1], -(d @ fwd)], atol=1e-4)
    assert checked > 150


def test_swift_frame_upload_is_accepted_and_decodes_exactly(fx, stub):
    client, data_dir = stub
    body = (fx / "frame_multipart.bin").read_bytes()
    ctype = (fx / "frame_content_type.txt").read_text()
    assert (fx / "frame_url.txt").read_text().endswith("/v1/frames")
    r = client.post("/v1/frames", content=body, headers={"content-type": ctype})
    assert r.status_code == 202, r.text
    rec = data_dir / "sessions" / "ios-contract"
    meta = json.loads((rec / "frames.jsonl").read_text().splitlines()[0])
    assert meta["image_resolution"] == [1920, 1440] and meta["jpeg_scale"] == 0.5
    assert G.mat3(meta["intrinsics"])[0, 2] == 960                    # column-major cx
    G.check_pose(G.mat4(meta["camera_transform"]))
    d, c = truth(fx)
    got_d = codec.decode_depth((rec / "frames" / "000001.depth").read_bytes())
    assert np.array_equal(got_d, d.astype("<f2").astype(np.float32))   # Apple's raw DEFLATE + float16 LE
    assert np.array_equal(codec.decode_conf((rec / "frames" / "000001.conf").read_bytes()), c)
    im = Image.open(io.BytesIO((rec / "frames" / "000001.jpg").read_bytes()))
    assert im.size == (960, 720) and im.getexif().get(0x0112, 1) == 1


def test_swift_hand_patches_match_the_server_reference(fx):
    hand = json.loads((fx / "phone.jsonl").read_text().splitlines()[1])
    assert hand["type"] == "hand" and [j["name"] for j in hand["joints"]] == __import__("marco.touch", fromlist=["JOINTS"]).JOINTS
    d, c = truth(fx)
    xy = [(j["x"], j["y"]) for j in hand["joints"]]
    ref_d, ref_c = codec.patches_from_depth(d.astype("<f2").astype(np.float32), c, xy)
    got_d = codec.decode_patches(hand["depth_patches_f16_b64"], "f16")
    got_c = codec.decode_patches(hand["conf_patches_u8_b64"], "u8")
    assert np.array_equal(np.isnan(got_d), np.isnan(ref_d)) and np.isnan(got_d[0]).sum() > 0   # the corner wrist is padded
    assert np.array_equal(np.nan_to_num(got_d, nan=-1), np.nan_to_num(ref_d, nan=-1))
    assert np.array_equal(got_c, ref_c)
    from marco.touch import TouchDetector
    det = TouchDetector()
    det.set_camera(np.array([[1450, 0, 960], [0, 1450, 720], [0, 0, 1.0]]), (1920, 1440))
    p, _ = det.fingertip(hand)                                         # the touch detector reads it as is
    assert p is not None and np.all(np.isfinite(p))


def test_swift_phone_messages_are_accepted_by_the_server(fx, stub):
    client, data_dir = stub
    body = (fx / "frame_multipart.bin").read_bytes()
    assert client.post("/v1/frames", content=body, headers={"content-type": (fx / "frame_content_type.txt").read_text()}).status_code == 202
    msgs = [json.loads(l) for l in (fx / "phone.jsonl").read_text().splitlines()]
    replies = []
    with client.websocket_connect("/v1/phone") as ws:
        for m in msgs:
            ws.send_json(m)
            if m["type"] == "query":
                while True:                                            # the stub answers each query on the socket
                    r = ws.receive_json()
                    replies.append(r)
                    if r.get("type") in ("answer", "error"):
                        break
    errors = [r for r in replies if r.get("type") == "error"]
    assert errors == []
    by_q = {r.get("query_id"): r for r in replies if r.get("type") == "answer"}
    assert by_q["q-find"]["found"] is True and by_q["q-find"]["name"] == "keys"
    assert by_q["q-what"]["status"] in ("unknown", "known", "no_touch")
    rec = data_dir / "sessions" / "ios-contract" / "phone.jsonl"           # every message carried session_id
    kinds = [json.loads(l)["type"] for l in rec.read_text().splitlines()]
    assert kinds.count("hand") == 1 and kinds.count("pose") == 1 and kinds.count("guidance") == 2


def test_a_recording_made_on_the_phone_reads_like_a_server_recording(fx):
    """ios/Marco/Core/Recorder.swift records on the phone in the server's own layout (marco/recorder.py), so a walk
    recorded with no server or network goes into server/tools as is."""
    import importlib.util
    from marco.session import Session
    path = fx / "recorded" / "ios-contract"
    ses = Session(path)
    assert [m["frame_id"] for m in ses.frames] == [1, 2, 3]
    assert all("received_wall" in m for m in ses.frames + ses.phone)
    kinds = [m["type"] for m in ses.phone]
    assert kinds[0] == "map" and kinds.count("pose") == 21 and kinds.count("hand") == 1
    _, depth, conf = ses.frame_bytes(ses.frames[0])
    d, c = truth(fx)
    assert np.array_equal(codec.decode_conf(conf), c)
    assert np.allclose(codec.decode_depth(depth), d.astype(np.float16).astype(np.float32), equal_nan=True)
    spec = importlib.util.spec_from_file_location("check_recording", Path(__file__).resolve().parents[1] / "tools" / "check_recording.py")
    check_recording = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(check_recording)
    problems, notes = check_recording.check(path)
    assert problems == [], problems
    stream = [kind for kind, _ in ses.stream()]                              # what replay.py and run_offline.py walk
    assert stream.count("frame") == 3 and stream.count("phone") == len(ses.phone)
