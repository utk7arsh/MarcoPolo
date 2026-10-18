"""tools/investigate_live.py on a session recorded the way the live server records it: frames.jsonl, phone.jsonl and
the server's out.jsonl with received_wall, the brain's per-frame log lines, and the registry. It must join the log to
the frames, show where each item was placed, and report the guidance run and its touch."""
import importlib.util
import io
import json
import logging
import sys
import time
from pathlib import Path

import pytest
from PIL import Image

from marco import brain as B, codec
from marco.perception.detector import TruthDetector
from marco.session import Session

TOOLS = Path(__file__).resolve().parents[1] / "tools"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def fake(tmp_path_factory):
    d = tmp_path_factory.mktemp("investigate") / "fake"
    _load("fake_session").main(str(d))
    return d


def _record_live(fake, data, log_path, monkeypatch):
    """Run the real brain over the fake walk as the live server would, writing what the recorder writes."""
    monkeypatch.setattr(B, "LAYOUT_ASYNC", False)
    s = Session(fake)
    b = B.RealBrain(TruthDetector(s.truth["items"]), data)
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), (90, 90, 90)).save(buf, "JPEG")
    for name in s.truth["items"]:
        b.register(name, buf.getvalue())
    jar = next(i for i, it in b.world.items.items() if it.name == "jar")
    sdir = data / "sessions" / "live1"
    (sdir / "frames").mkdir(parents=True)
    h = logging.FileHandler(log_path)
    h.setFormatter(logging.Formatter("%(asctime)s marco %(levelname)s %(message)s"))
    lg = logging.getLogger("marco")
    lg.addHandler(h)
    old = lg.level
    lg.setLevel(logging.INFO)
    frames, phone, out = [], [], []
    guiding = False
    try:
        for kind, m in s.stream():
            if kind == "frame":
                jpeg, d, c = s.frame_bytes(m)
                base = sdir / "frames" / f"{int(m['frame_id']):06d}"
                base.with_suffix(".jpg").write_bytes(jpeg)
                base.with_suffix(".depth").write_bytes(d)
                base.with_suffix(".conf").write_bytes(c)
                frames.append({**m, "received_wall": time.time()})
                res = b.on_frame(m, jpeg, codec.decode_depth(d), codec.decode_conf(c))
            else:
                if m["type"] == "hand" and not guiding:          # the phone guides to the jar as the hand reaches
                    guiding = True
                    g = dict(type="guidance", session_id=m.get("session_id"), item_id=jar, phase="reach", distance_m=0.4)
                    phone.append({**g, "received_wall": time.time()})
                    out += [{**x, "received_wall": time.time()} for ch, x in b.on_phone(g) if ch == "phone"]
                phone.append({**m, "received_wall": time.time()})
                res = b.on_phone(m)
            out += [{**x, "received_wall": time.time()} for ch, x in res if ch == "phone"]
        g = dict(type="guidance", item_id=jar, phase="off")
        phone.append({**g, "received_wall": time.time()})
    finally:
        lg.removeHandler(h)
        lg.setLevel(old)
        h.close()
    for path, rows in ((sdir / "frames.jsonl", frames), (sdir / "phone.jsonl", phone),
                       (data / "sessions" / "server" / "out.jsonl", out)):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("".join(json.dumps(r) + "\n" for r in rows))
    return s, jar, out


def test_it_joins_the_log_to_the_frames_and_reports_items_light_and_the_touch(fake, tmp_path, monkeypatch):
    I = _load("investigate_live")
    data, log = tmp_path / "data", tmp_path / "marco.log"
    t0 = time.time() - 1
    s, jar, out = _record_live(fake, data, log, monkeypatch)
    assert any(m["type"] == "touch" for m in out)                              # the walk does end in a touch
    rep = I.investigate(data, t0, time.time() + 1, log, tmp_path / "out")
    (ses,) = rep["sessions"]
    assert ses["frames"] == len(s.frames) and ses["luma_median"] is not None and ses["tracking"]
    logged = sum(" marco INFO frame " in line for line in log.read_text().splitlines())   # frames with a detection
    assert logged and rep["log"]["clock_offset_hours"] == 0 and rep["log"]["lines_matched_to_frames"] == logged
    placed = {n: d for n, d in rep["detection"].items() if d["placed"]}
    assert placed and all((tmp_path / "out" / d["sheet"]).exists() for d in placed.values())
    assert all(d["spots"] >= 1 and d["top_spots"][0]["placements"] >= 1 for d in placed.values())
    (g,) = [g for g in rep["guidance"] if g["item"] == "jar"]
    assert g["touch"] and g["touch"]["on_target"] and g["hand_messages"] > 0
    assert len(rep["registry"]) == len(s.truth["items"]) and list((tmp_path / "out" / "registry").glob("jar_*_photo.jpg"))
    md = (tmp_path / "out" / "report.md").read_text()
    assert "jar" in md and "luma" in md


def test_log_lines_parse_into_placed_unplaced_and_refused(tmp_path):
    I = _load("investigate_live")
    p = tmp_path / "x.log"
    p.write_text("Oct 18 13:17:47 marco-gpu python[1]: 2026-10-18 13:17:47,102 marco INFO frame 1020: Pringles: not present: "
                 "photo+name score -22.35 < -2.43, DINOv2 crop similarity 0.01 < 0.30; Bottle: present, not placed: 8.2 m away, "
                 "beyond MAX_RANGE_M 4.0 m; Coffee: placed at [-0.38, -0.48, -0.93], 0.85 m away\nunrelated line\n")
    (r,) = I.parse_log(p)
    assert r["frame_id"] == "1020" and [x["kind"] for x in r["res"]] == ["absent", "unplaced", "placed"]
    assert r["res"][2]["pos"] == [-0.38, -0.48, -0.93] and r["res"][2]["dist"] == 0.85
    assert "DINOv2 crop similarity" in r["res"][0]["why"]


def test_spots_cluster_per_map_and_dot_moves_need_two_sightings():
    I = _load("investigate_live")
    mk = lambda pos, t, m="a": dict(name="cup", pos=pos, t=t, map_id=m)
    ps = [mk([0, 0, 0], 0), mk([0.1, 0, 0], 1), mk([2, 0, 0], 2), mk([0, 0, 0], 3, "b")]
    sp = I.spots(ps)
    assert [len(s["members"]) for s in sp] == [2, 1, 1] and sp[0]["map_id"] == "a"
    moves = I.dot_moves([mk([0, 0, 0], 0), mk([2, 0, 0], 1), mk([2, 0, 0], 2)])
    assert len(moves) == 1 and moves[0]["metres"] == 2.0
