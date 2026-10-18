"""tools/fetch_arkitscenes.py without the network: URLs, safe unzipping, the layout, and converting from that layout."""
import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"
PROBE = Path(__file__).resolve().parents[2] / "poc" / "research" / "datasets_probe"


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def zip_bytes(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    return buf.getvalue()


def test_urls_follow_apples_layout():
    f = load("fetch_arkitscenes")
    u = [x[0] for x in f.urls("41069021")]
    base = "https://docs-assets.developer.apple.com/ml-research/datasets/arkitscenes/v1"
    assert u == [f"{base}/upsampling/Validation/41069021.zip", f"{base}/raw/Validation/41069021/lowres_wide.traj",
                 f"{base}/raw/Validation/41069021/wide_intrinsics.zip",
                 f"{base}/raw/Validation/41069021/41069021_3dod_annotation.json"]


def test_unsafe_zip_members_are_refused(tmp_path):
    f = load("fetch_arkitscenes")
    bad = tmp_path / "bad.zip"
    bad.write_bytes(zip_bytes({"../escaped.txt": b"x"}))
    with pytest.raises(ValueError):
        f.safe_extract(bad, tmp_path / "out")
    assert not (tmp_path / "escaped.txt").exists()
    good = tmp_path / "good.zip"
    good.write_bytes(zip_bytes({"a/b.txt": b"y"}))
    f.safe_extract(good, tmp_path / "out")
    assert (tmp_path / "out" / "a" / "b.txt").read_bytes() == b"y"


def test_fetch_lays_out_what_the_converter_reads_and_skips_what_it_has(tmp_path, monkeypatch):
    f = load("fetch_arkitscenes")
    files = {"41069021.zip": zip_bytes({"41069021/wide/41069021_1.000.png": b"png"}), "lowres_wide.traj": b"traj",
             "wide_intrinsics.zip": zip_bytes({"wide_intrinsics/41069021_1.000.pincam": b"pin"}),
             "41069021_3dod_annotation.json": b"{}"}
    calls = []

    def fake_open(url, timeout):
        calls.append(url)
        return io.BytesIO(files[url.rsplit("/", 1)[1]])

    monkeypatch.setattr(f.urllib.request, "urlopen", fake_open)
    root = f.fetch("41069021", tmp_path / "scene")
    assert len(calls) == 4
    scene, traj, pincams, boxes = load("arkitscenes_session").root_paths(root)
    assert (scene / "wide" / "41069021_1.000.png").exists() and traj.read_bytes() == b"traj"
    assert (pincams / "41069021_1.000.pincam").exists() and boxes.exists()
    f.fetch("41069021", tmp_path / "scene")
    assert len(calls) == 4                                          # nothing downloaded twice


@pytest.mark.skipif(not (PROBE / "arkitscenes_41069021_small").exists(), reason="ARKitScenes sample not on this machine")
def test_a_fetched_layout_converts(tmp_path):
    root = tmp_path / "41069021-root"
    root.mkdir()
    (root / "41069021").symlink_to(PROBE / "arkitscenes_upsampling_val_41069021" / "x" / "41069021")
    (root / "wide_intrinsics").symlink_to(PROBE / "arkitscenes_41069021_small" / "x_wide_intrinsics" / "wide_intrinsics")
    for name in ("lowres_wide.traj", "41069021_3dod_annotation.json"):
        (root / name).symlink_to(PROBE / "arkitscenes_41069021_small" / name)
    conv = load("arkitscenes_session")
    out = tmp_path / "session"
    conv.main(*map(str, conv.root_paths(root)), str(out))
    frames = (out / "frames.jsonl").read_text().splitlines()
    assert len(frames) > 5 and json.loads((out / "truth.json").read_text())["items"]
    probs, _ = load("check_recording").check(out)
    assert [p for p in probs if not p.startswith("frame rate")] == [], probs   # this subset has a frame every ~10 s
