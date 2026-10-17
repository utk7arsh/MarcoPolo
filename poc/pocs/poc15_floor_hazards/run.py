"""POC 15: Can the chest phone warn about trip hazards on the floor ahead, early enough, without crying wolf?

Wearer walks straight down a 6 m hallway/room at 0.6 or 1.0 m/s with the phone in the chest vest
tilted 30 deg down. One object lies on the floor in the walking path. App logic (what we'd ship):
LiDAR points (confidence >= medium) in the walking corridor (+-0.45 m), 0.5-4 m ahead, more than
h_thr above the floor plane -> 5 cm grid clusters -> alert if a cluster has >= 12 points in 2 of the
last 3 frames (10 Hz). Measured: distance/time of first alert, and false alerts on an empty floor.
Uses the validated LiDAR noise model (iPhone = 1.5x measured iPad error), flying pixels at edges.
"""
import json
import sys
from pathlib import Path

import numpy as np
from scipy.ndimage import median_filter

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "emulators" / "arkit"))
from device import CX, CY, FX, FY, SX, SY, Phone, chest_camera_pose  # noqa: E402
from scene import Box, Room  # noqa: E402

OBJECTS = {  # name: (width x, height y, depth z) in metres
    "bag (35x20x25 cm)": (0.35, 0.20, 0.25),
    "shoe (10x10x28 cm)": (0.10, 0.10, 0.28),
    "box (40x25x30 cm)": (0.40, 0.25, 0.30),
    "bottle lying (7x7x25 cm)": (0.07, 0.07, 0.25),
    "book (17x3x24 cm)": (0.17, 0.03, 0.24),
    "cable / rug edge (1.5 cm)": (0.60, 0.015, 0.05),
}


def floor_noise_sd(dist, cam_h=1.30):
    """Expected vertical scatter of floor points at a horizontal distance (from the LiDAR noise model)."""
    rng_ = np.hypot(dist, cam_h)
    sd_range = 1.5 * (0.012 + 0.011 * rng_)          # high-confidence depth noise (iPhone = 1.5x iPad)
    return sd_range * cam_h / rng_                    # vertical component along a downward ray


def hazard_points(fr, h_min, corridor=0.45, rng_lim=(0.5, 3.0)):
    """High-confidence points standing above the LOCAL floor by more than max(h_min, 3 sigma(d))."""
    T = fr["T_arkit"]
    # 5x5 median filter: removes isolated noisy pixels; real objects (>= ~5 px) survive.
    d = median_filter(fr["depth"].astype(float), size=5)
    ok = median_filter((fr["conf"] == 2).astype(np.uint8), size=5) == 1
    v, u = np.nonzero(ok)
    z = d[v, u]
    uf, vf = (u + 0.5) / SX, (v + 0.5) / SY
    pc = np.stack([(uf - CX) / FX * z, -(vf - CY) / FY * z, -z], 1)
    pw = pc @ T[:3, :3].T + T[:3, 3]
    cam = T[:3, 3]
    fwd = -T[:3, 2]; fwd[1] = 0; fwd /= np.linalg.norm(fwd)
    right = np.array([-fwd[2], 0, fwd[0]])
    rel = pw - cam
    ahead, side = rel @ fwd, rel @ right
    m = (ahead > rng_lim[0]) & (ahead < rng_lim[1]) & (np.abs(side) < corridor) & (pw[:, 1] < 0.8)
    pw, ahead = pw[m], ahead[m]
    if len(pw) == 0:
        return pw
    # local floor height per 0.25 m band (the floor dominates each band) -> removes depth bias
    band = np.floor(ahead / 0.25).astype(int)
    floor = np.zeros(len(pw))
    for b in np.unique(band):
        sel = band == b
        floor[sel] = np.percentile(pw[sel, 1], 40)
    thr = np.maximum(h_min, 3.0 * floor_noise_sd(ahead))
    return pw[(pw[:, 1] - floor) > thr]


def persistent_cells(history, cell=0.05, need=3, min_pts=8):
    """World-fixed 5 cm cells hit in each of the last `need` frames (noise doesn't repeat; objects do)."""
    if len(history) < need:
        return 0
    sets = []
    for pts in history[-need:]:
        keys = np.floor(pts[:, [0, 2]] / cell).astype(int) if len(pts) else np.zeros((0, 2), int)
        # dilate by one cell so small walking jitter still overlaps
        sets.append({(a + dx, b + dz) for a, b in map(tuple, keys) for dx in (-1, 0, 1) for dz in (-1, 0, 1)})  # 1-cell dilation for walking jitter
    common = set.intersection(*sets)
    last = np.floor(history[-1][:, [0, 2]] / cell).astype(int) if len(history[-1]) else np.zeros((0, 2), int)
    return int(sum(1 for k in map(tuple, last) if k in common)) >= min_pts


def walk(obj, speed, h_thr, seed, tilt=30.0):
    rng = np.random.default_rng(seed)
    furn = []
    obj_z = -4.2
    if obj:
        w, h, dz = OBJECTS[obj]
        furn.append(Box("hazard", [-w / 2 + rng.uniform(-0.15, 0.15), 0.0, obj_z - dz / 2], [w / 2, h, obj_z + dz / 2]))
        furn[-1].hi[0] = furn[-1].lo[0] + w
    room = Room(lo=np.array([-1.2, 0.0, -10.5]), hi=np.array([1.2, 2.6, 1.0]), furniture=furn, items={})  # far wall stays out of range
    ph = Phone(room, rng)
    hist, first = [], None
    t, z0 = 0.0, 0.5
    while True:
        z = z0 - speed * t
        if obj and z - 0.12 < obj_z + 0.4:  # reached the object
            break
        if not obj and z < -3.5:
            break
        T = chest_camera_pose((0.0, z), 0.0, t, tilt_deg=tilt, walking=True)
        fr = ph.frame(T, t)
        hist.append(hazard_points(fr, h_thr))
        if first is None and persistent_cells(hist):
            first = (z - 0.12) - obj_z if obj else t
        t += 0.1
    return first, t


if __name__ == "__main__":
    res = {}
    for h_thr in (0.05,):
        # false alerts on a bare floor
        fa = [walk(None, 0.8, h_thr, s)[0] is not None for s in range(10)]
        res[f"bare floor, height threshold {int(h_thr * 100)} cm: walks with a false alert"] = f"{sum(fa)}/10"
        print(f"\n## threshold {int(h_thr * 100)} cm above floor: false alerts on a bare floor in {sum(fa)}/10 walks")
        for obj in OBJECTS:
            for speed in (0.6, 1.0):
                firsts = [walk(obj, speed, h_thr, s)[0] for s in range(5)]
                det = [f for f in firsts if f is not None]
                key = f"{obj}, {speed} m/s, thr {int(h_thr * 100)} cm"
                res[key] = dict(detected=f"{len(det)}/5", median_alert_distance_m=round(float(np.median(det)), 2) if det else None,
                                median_warning_s=round(float(np.median(det)) / speed, 1) if det else None)
                print(f"  {obj:28} at {speed} m/s: detected {len(det)}/5, alert at {res[key]['median_alert_distance_m']} m ahead "
                      f"({res[key]['median_warning_s']} s warning)")
    (ROOT / "reports" / "poc15_floor_hazards.json").write_text(json.dumps(res, indent=2))
