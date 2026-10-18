"""The Stray Scanner converter on a synthetic export built from the emulator session, in both pose conventions."""
import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from marco import codec, geometry as G

TOOLS = Path(__file__).resolve().parents[1] / "tools"
cv2 = pytest.importorskip("cv2")


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def R_to_quat(R):
    w = np.sqrt(max(1e-12, 1 + R[0, 0] + R[1, 1] + R[2, 2])) / 2
    return [(R[2, 1] - R[1, 2]) / (4 * w), (R[0, 2] - R[2, 0]) / (4 * w), (R[1, 0] - R[0, 1]) / (4 * w), w]


@pytest.fixture(scope="module")
def fake(tmp_path_factory):
    d = tmp_path_factory.mktemp("st") / "fake"
    load("fake_session").main(str(d))
    return d


def make_stray(fake, dst, convention, k_scale):
    """Write the fake session's frames as a Stray Scanner export (one video frame per depth frame, video at 960x720,
    intrinsics for the video size when k_scale is 0.5 or for the 1920x1440 sensor when it is 1)."""
    (dst / "depth").mkdir(parents=True)
    (dst / "confidence").mkdir()
    metas = [json.loads(l) for l in (fake / "frames.jsonl").read_text().splitlines()]
    vw = cv2.VideoWriter(str(dst / "rgb.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 1, (960, 720))
    rows = ["timestamp, frame, x, y, z, qx, qy, qz, qw, fx, fy, cx, cy, distortion_center_x, distortion_center_y"]
    for i, m in enumerate(metas):
        base = fake / "frames" / f"{m['frame_id']:06d}"
        rgb = np.asarray(Image.open(base.with_suffix(".jpg")).convert("RGB"))
        vw.write(cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR))
        d = codec.decode_depth(base.with_suffix(".depth").read_bytes())
        Image.fromarray((d * 1000).astype(np.uint16)).save(dst / "depth" / f"{i:06d}.png")
        Image.fromarray(codec.decode_conf(base.with_suffix(".conf").read_bytes())).save(dst / "confidence" / f"{i:06d}.png")
        T = G.mat4(m["camera_transform"])
        if convention == "opencv":
            T = T @ np.diag([1.0, -1, -1, 1])
        K = G.mat3(m["intrinsics"]) * np.array([[k_scale], [k_scale], [1]])
        q = R_to_quat(T[:3, :3])
        rows.append(", ".join(str(v) for v in [m["t_device"], i, *T[:3, 3], *q, K[0, 0], K[1, 1], K[0, 2], K[1, 2], "", ""]))
    vw.release()
    (dst / "odometry.csv").write_text("\n".join(rows) + "\n")
    return metas


@pytest.mark.parametrize("convention,k_scale", [("arkit", 1.0), ("opencv", 0.5)])
def test_stray_export_converts_back_to_the_same_poses(fake, tmp_path, convention, k_scale):
    src = tmp_path / "export"
    metas = make_stray(fake, src, convention, k_scale)
    out = tmp_path / "session"
    picked = load("stray_session").main(str(src), str(out), fps=2)
    assert picked == convention                                   # the LiDAR overlap test finds the right one
    got = [json.loads(l) for l in (out / "frames.jsonl").read_text().splitlines()]
    assert len(got) == len(metas)
    for g, ref in zip(got, metas):
        assert g["t_device"] == ref["t_device"] and g["image_resolution"] == [960, 720]
        assert np.allclose(G.mat4(g["camera_transform"]), G.mat4(ref["camera_transform"]), atol=1e-5)
        assert np.allclose(G.mat3(g["intrinsics"]), G.mat3(ref["intrinsics"]) * np.array([[0.5], [0.5], [1]]), atol=1e-3)
    d0 = codec.decode_depth((out / "frames" / "000001.depth").read_bytes())
    d_ref = codec.decode_depth((fake / "frames" / f"{metas[0]['frame_id']:06d}.depth").read_bytes())
    assert np.nanmax(np.abs(d0 - d_ref)) < 0.002                  # mm PNG round trip
    probs, _ = load("check_recording").check(out)
    assert [p for p in probs if not p.startswith("pose rate")] == [], probs   # this export has 1 pose/s, a real one 60/s


def test_one_second_spacing_from_a_60fps_export(tmp_path):
    """Frame picking on a real-rate export: 60 video frames/s, poses kept at 10/s."""
    src = tmp_path / "export"
    (src / "depth").mkdir(parents=True)
    vw = cv2.VideoWriter(str(src / "rgb.mp4"), cv2.VideoWriter_fourcc(*"mp4v"), 60, (320, 240))
    rows = ["timestamp, frame, x, y, z, qx, qy, qz, qw, fx, fy, cx, cy"]
    for i in range(150):                                         # 2.5 s, looking at a wall 2 m ahead
        vw.write(np.full((240, 320, 3), i % 255, np.uint8))
        Image.fromarray(np.full((192, 256), 2000, np.uint16)).save(src / "depth" / f"{i:06d}.png")
        rows.append(f"{10 + i / 60:.6f}, {i}, {0.001 * i}, 0, 0, 0, 0, 0, 1, 240, 240, 160, 120")
    vw.release()
    (src / "odometry.csv").write_text("\n".join(rows) + "\n")
    out = tmp_path / "session"
    load("stray_session").main(str(src), str(out))
    ts = [json.loads(l)["t_device"] for l in (out / "frames.jsonl").read_text().splitlines()]
    assert len(ts) == 3 and np.allclose(np.diff(ts), 1.0, atol=1 / 60 + 1e-6)
    poses = [json.loads(l) for l in (out / "phone.jsonl").read_text().splitlines()]
    assert 24 <= len(poses) <= 26
