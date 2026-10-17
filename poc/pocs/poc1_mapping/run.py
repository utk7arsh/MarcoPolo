"""POC 1: How accurately does the chest iPhone place items in 3D while the wearer walks around?

A wearer walks two loops through a furnished room (scene.demo_room) at 0.8 m/s with the torso
sweeping +-35 deg, ARKit pose drifting (~0.3 % of distance), detector at 2 Hz. For every detection
we compare three position methods to ground truth, then the fused (median) memory position.
Variants: iPhone depth noise 1.5x vs 2x the iPad measurement, a clear (transparent) bottle, and
a 20 deg downward mount tilt.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for p in ("emulators/arkit", "core"):
    sys.path.insert(0, str(ROOT / p))
from device import DetectorModel, LidarModel, Phone, chest_camera_pose, detect  # noqa: E402
from mapping import METHODS  # noqa: E402
from scene import demo_room  # noqa: E402

PATH = np.array([(0, 0.5), (0, -1.2), (-1.2, -1.5), (-1.3, -2.9), (1.0, -2.9), (1.4, -2.0), (0.8, -0.3), (-1.2, 0.3), (0, 0.5)])
SPEED = 0.8


def walk(loops=2, dt=1 / 60):
    seg = np.diff(PATH, axis=0)
    lens = np.linalg.norm(seg, axis=1)
    total = lens.sum() * loops
    t = 0.0
    while t * SPEED < total:
        s = (t * SPEED) % lens.sum()
        i = int(np.searchsorted(np.cumsum(lens), s, side="right"))
        i = min(i, len(seg) - 1)
        f = (s - np.r_[0, np.cumsum(lens)][i]) / lens[i]
        xz = PATH[i] + f * seg[i]
        heading = np.degrees(np.arctan2(seg[i][0], -seg[i][1]))
        yaw = heading + 35 * np.sin(2 * np.pi * t / 5.0)
        yield t, xz, yaw
        t += dt


def run(seed=0, lidar=None, tilt=0.0, transparent_bottle=False, det_hz=2.0):
    rng = np.random.default_rng(seed)
    room = demo_room()
    if transparent_bottle:
        room.items["bottle"].material = "transparent"
    ph = Phone(room, rng, lidar=lidar)
    det = DetectorModel()
    rows = []
    next_det = 0.0
    prev_yaw = None
    for t, xz, yaw in walk():
        T = chest_camera_pose(xz, yaw, t, tilt_deg=tilt, walking=True)
        if t < next_det:
            ph.drift.update(T[:3, 3], 1 / 60)
            prev_yaw = yaw
            continue
        next_det = t + 1 / det_hz
        ang = abs(yaw - prev_yaw) * 60 if prev_yaw is not None else 0
        prev_yaw = yaw
        fr = ph.frame(T, t)
        for d in detect(fr, room, det, rng, ang_speed_deg_s=ang):
            if d["true_index"] < 0:
                continue
            item = fr["prims"][d["true_index"]]
            gt = item.base
            dist = np.linalg.norm(gt - T[:3, 3])
            r = dict(t=t, item=item.name, dist=dist)
            for m, fn in METHODS.items():
                p = fn(d, fr)
                if p is None:
                    continue
                r[m + "_h"] = float(np.linalg.norm((p - gt)[[0, 2]]))
                r[m + "_y"] = float(p[1] - gt[1])
                r[m + "_p"] = p.tolist()
            r["gt"] = gt.tolist()
            rows.append(r)
    return rows


def summarize(rows):
    out = {}
    bins = [(0, 1.5), (1.5, 2.5), (2.5, 3.5), (3.5, 5.0)]
    for m in METHODS:
        out[m] = {}
        for lo, hi in bins:
            e = [r[m + "_h"] for r in rows if lo <= r["dist"] < hi and m + "_h" in r]
            if e:
                out[m][f"{lo}-{hi} m"] = dict(n=len(e), median_cm=100 * float(np.median(e)), p90_cm=100 * float(np.percentile(e, 90)))
        # fused per item: median of all estimates (what the memory stores)
        fused = {}
        for it in {r["item"] for r in rows}:
            ps = np.array([r[m + "_p"] for r in rows if r["item"] == it and m + "_p" in r])
            gt = np.array(next(r["gt"] for r in rows if r["item"] == it))
            if len(ps):
                f = np.median(ps, axis=0)
                fused[it] = dict(n=len(ps), horiz_err_cm=round(100 * float(np.linalg.norm((f - gt)[[0, 2]])), 1),
                                 height_err_cm=round(100 * float(f[1] - gt[1]), 1))
        out[m]["fused_per_item"] = fused
    per_item = {}
    for it in sorted({r["item"] for r in rows}):
        ds = [r["dist"] for r in rows if r["item"] == it]
        per_item[it] = dict(detections=len(ds), min_dist=round(min(ds), 2), max_dist=round(max(ds), 2))
    out["detections"] = per_item
    return out


if __name__ == "__main__":
    res = {}
    variants = {
        "nominal (iPhone noise 1.5x iPad)": dict(),
        "pessimistic depth (2x iPad)": dict(lidar=LidarModel(iphone_factor=2.0)),
        "transparent bottle": dict(transparent_bottle=True),
        "mount tilted 20 deg down": dict(tilt=20.0),
    }
    for name, kw in variants.items():
        rows = []
        for s in range(3):
            rows += run(seed=s, **kw)
        res[name] = summarize(rows)
        print(f"\n## {name}")
        for m in METHODS:
            bins = {k: v for k, v in res[name][m].items() if k != "fused_per_item"}
            print(f"  {m:13} " + "  ".join(f"{k}: med {v['median_cm']:.1f} / p90 {v['p90_cm']:.1f} cm (n={v['n']})" for k, v in bins.items()))
            print(f"  {'':13} fused: " + ", ".join(f"{it} {v['horiz_err_cm']}cm h{v['height_err_cm']:+}" for it, v in res[name][m]["fused_per_item"].items()))
        print("  detections:", res[name]["detections"])
    (ROOT / "reports" / "poc1_mapping.json").write_text(json.dumps(res, indent=2))
