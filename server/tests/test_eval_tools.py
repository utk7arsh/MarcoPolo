"""The real-video test tools on synthetic sessions with known truth: label_truth (one click + LiDAR -> position),
eval_detection (visibility, scoring, threshold sweep, end to end) and inspect_session (blur, depth, pose consistency)."""
import importlib.util
import json
import shutil
import sys
from pathlib import Path

import numpy as np
import pytest

from marco import codec, geometry as G

TOOLS = Path(__file__).resolve().parents[1] / "tools"
sys.path.insert(0, str(TOOLS))


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def fake(tmp_path_factory):
    d = tmp_path_factory.mktemp("evaltools") / "fake"
    load("fake_session").main(str(d))
    return d


def frames_of(session_dir):
    from marco.session import Session
    ses = Session(session_dir)
    lt = load("label_truth")
    return ses, [(m, lt.frame_of(ses, m)) for m in ses.frames]


def test_one_click_gives_the_items_position(fake, tmp_path):
    ses, frames = frames_of(fake)
    ev = load("eval_detection")
    truth = ses.truth["items"]
    name, t = "jar", truth["jar"]
    seen = [(m, f) for m, f in frames if ev.view_state(f, t["position"], t["size"])[0] == "visible"]
    centre = np.array(t["position"]) + [0, t["size"] / 2, 0]
    meta, fr = min(seen, key=lambda mf: abs(mf[1].project(centre[None])[1][0] - 1.5))   # about 1.5 m away, no hand
    uu, vv = fr.project(centre[None])[0][0]                        # click the middle of the jar
    work = tmp_path / "s"
    shutil.copytree(fake, work)
    (work / "truth.json").unlink()                                  # label from scratch
    from marco.session import Session
    out = load("label_truth").label_click(Session(work), name, meta["frame_id"], float(uu), float(vv), 0.1)
    got = np.array(out["items"][name]["position"])
    err = got - np.array(t["position"])
    assert np.hypot(err[0], err[2]) < 0.07 and abs(err[1]) < 0.03, err      # its front surface: a radius toward the camera
    saved = json.loads((work / "truth.json").read_text())["items"][name]
    assert saved["labelled_from"]["frame_id"] == meta["frame_id"] and saved["size"] == 0.1


def test_view_states():
    ev = load("eval_detection")
    T = np.eye(4)
    T[:3, 3] = [0, 1.2, 0]
    K = np.array([[1450.0, 0, 960], [0, 1450, 720], [0, 0, 1]])
    depth = np.full((192, 256), 3.0, np.float32)
    fr = G.Frame(T, K, (1920, 1440), depth, np.full((192, 256), 2, np.uint8))
    assert ev.view_state(fr, [0, 1.15, -2.0], 0.1)[0] == "visible"
    assert ev.view_state(fr, [0, 1.15, 2.0], 0.1)[0] == "out_of_view"            # behind the camera
    assert ev.view_state(fr, [9.0, 1.15, -2.0], 0.1)[0] == "out_of_view"         # far outside the image
    assert ev.view_state(fr, [0, 1.15, -5.0], 0.1)[0] == "dont_care"             # beyond 4 m
    assert ev.view_state(fr, [0, 1.15, -3.5], 0.1)[0] == "dont_care"             # LiDAR sees a wall at 3 m: hidden
    assert ev.view_state(fr, [0, 0.9, -3.3], 0.8)[0] == "visible"                # a big box: its front face is nearer
    assert ev.box_contains([100, 100, 200, 200], (210, 150)) and not ev.box_contains([100, 100, 200, 200], (240, 150))
    assert ev.runs([1, 2, 4, 8, 9]) == [[1, 2, 4], [8, 9]]


def test_scoring_counts_hits_misses_passes_and_false_alarms():
    ev = load("eval_detection")
    row = lambda i, state, present, box_hit: dict(item="keys", frame_index=i, state=state, present=present, box_hit=box_hit)
    rows = [row(0, "visible", True, True), row(1, "visible", False, False), row(2, "visible", True, False),   # pass 1
            row(5, "out_of_view", True, False), row(6, "dont_care", True, False),                             # 1 false alarm
            row(9, "visible", False, False), row(10, "visible", False, False)]                                # pass 2, missed
    per, total = ev.score(rows, minutes=2.0)
    k = per["keys"]
    assert (k["visible_frames"], k["hits"], k["misses"]) == (5, 1, 4)
    assert k["false_alarms"] == 2 and k["false_alarms_per_min"] == 1.0          # out of view + wrong box; don't-care ignored
    assert (k["passes"], k["passes_caught"]) == (2, 1) and total["pass_recall"] == 0.5


def test_threshold_sweep_finds_a_better_operating_point():
    ev = load("eval_detection")
    rng = np.random.default_rng(0)
    rows = []
    for i in range(200):
        vis = i % 2 == 0
        pn = rng.normal(1.0 if vis else -4.0, 0.8)                                 # present frames score higher
        rows.append(dict(item="mug", frame_index=i, state="visible" if vis else "out_of_view", present=pn >= 2.0,
                         box_hit=vis, photo_name=pn, dino=0.6 if vis else 0.5, vs_others=None))
    points = ev.sweep(rows, minutes=3.3)
    best = ev.operating_points(points)["<= 0.5 false alarms/min"]
    assert best["frame_recall"] > 0.9 and best["th"]["photo_name"] <= -1
    _, now = ev.score(rows, 3.3)
    assert now["frame_recall"] < 0.3                                                # the strict threshold misses most


def test_evaluation_end_to_end_with_the_truth_detector(fake, tmp_path):
    rep = load("eval_detection").evaluate(str(fake), from_truth=True, detector="truth", out_dir=str(tmp_path / "ev"))
    t = rep["total"]
    assert t["visible_frames"] > 10 and 0.6 <= t["frame_recall"] <= 1.0             # the truth detector misses 15%
    assert t["false_alarms"] == 0 and t["pass_recall"] >= 0.8
    errs = [p["hit_error_h_m_median"] for p in rep["items"].values() if p["hit_error_h_m_median"] is not None]
    assert errs and max(errs) < 0.12
    assert (tmp_path / "ev" / "sheet.jpg").stat().st_size > 10_000 and rep["timing"]["frames"] > 0
    assert json.loads((tmp_path / "ev" / "report.json").read_text())["total"] == t


def test_inspect_passes_a_good_recording_and_catches_bad_poses_and_blur(fake, tmp_path):
    ins = load("inspect_session")
    good = ins.inspect(str(fake), out_dir=str(tmp_path / "good"))
    s = good["summary"]
    # The emulator's LiDAR is noisier than the real thing (4.4 cm here; real ARKitScenes frames agree to 1.5 cm).
    assert s["consistency_cm_median"] < 6 and s["depth_coverage_median"] > 0.9 and s["upright_turns"] == 1
    assert good["problems"] == [] and (tmp_path / "good" / "inspect.jpg").exists()
    bad = tmp_path / "bad"
    shutil.copytree(fake, bad)
    lines = (bad / "frames.jsonl").read_text().splitlines()
    out = []
    for i, line in enumerate(lines):                                              # every other pose turned 6 degrees
        m = json.loads(line)
        if i % 2:
            a = np.radians(6)
            R = np.array([[np.cos(a), 0, np.sin(a), 0], [0, 1, 0, 0], [-np.sin(a), 0, np.cos(a), 0], [0, 0, 0, 1]])
            m["camera_transform"] = G.flat_colmajor(G.mat4(m["camera_transform"]) @ R)
        out.append(json.dumps(m))
    (bad / "frames.jsonl").write_text("\n".join(out) + "\n")
    rep = ins.inspect(str(bad), out_dir=str(tmp_path / "badout"), picture=False)
    assert rep["summary"]["consistency_cm_median"] > ins.CONSISTENCY_BAD_CM
    assert any("disagree" in p for p in rep["problems"])
    from PIL import Image, ImageFilter
    im = Image.open(fake / "frames" / "000005.jpg")
    assert ins.blur_score(im.filter(ImageFilter.GaussianBlur(6))) < 0.3 * ins.blur_score(im)
