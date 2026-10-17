"""Fidelity tests: does the emulated iPhone output look like a real LiDAR iPhone's ARFrame?

Reference numbers: research/arkit_lidar_facts.md (ARKitScenes LiDAR vs Faro laser-scan GT, our
own measurement over 1.85 M pixels; Apple docs; MobileEgo/Kim VIO benchmarks).
Run: .venv/bin/python -m pytest -q validation/test_arkit_emulator.py
"""
import sys
from pathlib import Path

import numpy as np
import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "emulators" / "arkit"))
from device import (DEP_H, DEP_W, IMG_H, IMG_W, LidarModel, Phone, VIODrift, chest_camera_pose,  # noqa: E402
                    detect, DetectorModel, project, unproject)
from scene import Box, Room, demo_room  # noqa: E402

# Measured high-confidence RMSE (cm) per GT-depth band on iPad Pro LiDAR (our ARKitScenes run).
MEASURED_HC_RMSE = {(0.5, 1.0): 2.8, (1.0, 1.5): 3.4, (1.5, 2.0): 3.7, (2.0, 2.5): 4.8, (2.5, 3.0): 5.0, (3.0, 4.0): 5.6}


def wall_room():
    return Room(lo=np.array([-3, 0, -6.0]), hi=np.array([3, 3, 1.0]), furniture=[], items={})


def test_arframe_formats():
    ph = Phone(demo_room(), np.random.default_rng(0))
    f = ph.frame(chest_camera_pose((0, 0), 0, 0), 0)
    assert f["depth"].shape == (DEP_H, DEP_W) == (192, 256)
    assert f["depth"].dtype == np.float32
    assert f["conf"].dtype == np.uint8 and set(np.unique(f["conf"])) <= {0, 1, 2}
    assert np.all(f["depth"] > 0), "ARKit returns dense depth with no holes"
    assert f["T_arkit"].shape == (4, 4)


def test_portrait_fov_matches_measured():
    """Portrait chest phone: horizontal FOV ~48.4 deg, vertical ~61.9 deg (fx=1600 @1920x1440)."""
    T = chest_camera_pose((0, 0), 0, 0)
    hfov = vfov = None
    for name, pts in [("h", np.array([[np.tan(np.radians(a)), 1.3, -1.0] for a in np.arange(0, 40, 0.1)])),
                      ("v", np.array([[0, 1.3 + 1.0 * np.tan(np.radians(a)), -1.0] for a in np.arange(0, 40, 0.1)]))]:
        uv, z = project(T, pts + np.array([0, 0, -0.12]))
        inside = (uv[:, 0] >= 0) & (uv[:, 0] <= IMG_W) & (uv[:, 1] >= 0) & (uv[:, 1] <= IMG_H)
        half = np.arange(0, 40, 0.1)[inside].max()
        if name == "h":
            hfov = 2 * half
        else:
            vfov = 2 * half
    assert abs(hfov - 48.4) < 1.5, hfov
    assert abs(vfov - 61.9) < 2.5, vfov


def test_project_unproject_roundtrip():
    T = chest_camera_pose((0.3, -0.5), 37, 1.0, tilt_deg=20)
    p = np.array([0.8, 0.75, -2.0])
    (u, v), z = project(T, p[None])[0][0], project(T, p[None])[1][0]
    assert np.allclose(unproject(T, u, v, z), p, atol=1e-9)


@pytest.mark.parametrize("band", list(MEASURED_HC_RMSE))
def test_depth_noise_matches_measured_iphone(band):
    """High-confidence RMSE should be the measured iPad value x iPhone factor (1.5) within 25 %."""
    rng = np.random.default_rng(1)
    errs = []
    for k in range(30):
        zw = rng.uniform(*band)
        room = Room(lo=np.array([-3, 0, -0.12 - zw]), hi=np.array([3, 3, 1.0]))
        ph = Phone(room, rng)
        f = ph.frame(chest_camera_pose((0, 0), 0, 0), 0)
        m = (f["conf"] == 2) & (f["gt_depth"] >= band[0]) & (f["gt_depth"] < band[1])
        errs.append((f["depth"] - f["gt_depth"])[m])
    e = np.concatenate(errs)
    rmse_cm = 100 * np.sqrt(np.mean(e ** 2))
    target = MEASURED_HC_RMSE[band] * LidarModel().iphone_factor
    assert abs(rmse_cm - target) / target < 0.25, (rmse_cm, target)


def test_confidence_mix_typical_room():
    rng = np.random.default_rng(2)
    ph = Phone(demo_room(), rng)
    c = np.concatenate([ph.frame(chest_camera_pose((0, 0), y, 0), 0)["conf"].ravel() for y in (0, 45, 90, -60)])
    hi = np.mean(c == 2)
    assert 0.80 < hi < 0.97, hi  # measured 94 % high in ARKitScenes homes


def test_small_objects_pulled_to_background():
    """Measured: protrusions <~6 depth px read +11..+15 cm toward the background."""
    rng = np.random.default_rng(3)
    biases = []
    for k in range(20):
        room = Room(lo=np.array([-3, 0, -6.0]), hi=np.array([3, 3, 1.0]),
                    items={"thin": Box("thin", [-0.012, 1.25, -2.512], [0.012, 1.35, -2.488], is_item=True)})
        ph = Phone(room, rng)
        f = ph.frame(chest_camera_pose((0, 0), 0, 0), 0)
        m = f["gt_idx"] == 0
        if m.any():
            biases.append(np.mean((f["depth"] - f["gt_depth"])[m]))
    assert np.mean(biases) > 0.4, np.mean(biases)  # wall is ~3.5 m behind: pulled far toward it


def test_vio_drift_rate():
    """~0.3 % of distance travelled (MobileEgo 2026: 0.2-0.5 %)."""
    rates = []
    for s in range(20):
        dr = VIODrift(rng=np.random.default_rng(s))
        p = np.zeros(3)
        for i in range(3000):  # 50 m walk at 1 m/s, 60 Hz
            p = p + np.array([1 / 60, 0, 0])
            dr.update(p, 1 / 60)
        rates.append(np.linalg.norm(dr.offset) / 50)
    assert 0.0015 < np.median(rates) < 0.005, np.median(rates)


def test_detector_size_dependence():
    det = DetectorModel()
    assert det.p_detect("bottle", 200, 1.0, 0) > 0.95
    assert det.p_detect("keys", 20, 1.0, 0) < 0.15
    assert det.p_detect("bottle", 200, 0.2, 0) == 0.0  # mostly occluded -> no detection


def test_detector_sees_bottle_on_coffee_table():
    rng = np.random.default_rng(4)
    room = demo_room()
    ph = Phone(room, rng)
    hits = 0
    for k in range(10):
        f = ph.frame(chest_camera_pose((0, 0), 0, 0, tilt_deg=10), 0)
        hits += any(d["label"] == "bottle" for d in detect(f, room, DetectorModel(), rng))
    assert hits >= 8
