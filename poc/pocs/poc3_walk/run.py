"""POC 3: As the wearer walks to an item, do distance and direction update correctly?

Full chain on the emulators: ARKit (drifting) chest-phone pose at 60 Hz, LiDAR + detector at 2 Hz
feeding the item memory (POC 1/2 logic), AirPods head yaw at 25 Hz fused with the ARKit heading
(POC 4), and a chest-to-ears offset. At every audio tick we compare what the app would render
(head-relative azimuth, distance, height, tempo, "within reach") to ground truth.
Variants: listener placed at the phone (no ear offset) vs at the ears; 3 starting positions.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for p in ("emulators/arkit", "emulators/motion", "core"):
    sys.path.insert(0, str(ROOT / p))
from airpods import AirPodsModel, AirPodsStream  # noqa: E402
from device import DetectorModel, Phone, chest_camera_pose, detect, yaw_vectors  # noqa: E402
from mapping import Memory  # noqa: E402
from scene import demo_room  # noqa: E402

SIZES = {"bottle": 0.25, "keys": 0.08, "wallet": 0.11, "glasses_case": 0.16, "mug": 0.10}
EAR_UP, EAR_BACK = 0.30, 0.10   # ears relative to the phone on the sternum (m)
REACH = 0.6


def wrap(a):
    return (np.asarray(a) + 180) % 360 - 180


def heading_of(T):
    """Torso heading from the chest camera: horizontal component of the optical axis (-z_cam)."""
    f = -T[:3, 2]
    return float(np.degrees(np.arctan2(f[0], -f[2])))


def tempo(d):
    return float(np.clip(0.35 + 0.2 * d, 0.4, 1.0))


def run(seed, start, target="bottle", ear_offset=True, speed=0.6, dt=1 / 60):
    rng = np.random.default_rng(seed)
    room = demo_room()
    ph = Phone(room, rng)
    det = DetectorModel()
    mem = Memory(list(SIZES), det, SIZES)
    item = room.items[target]
    goal = item.base
    # 1) Earlier in the day: the item was seen once from ~3 m (memory starts there).
    T0 = chest_camera_pose(start, float(np.degrees(np.arctan2(goal[0] - start[0], -(goal[2] - start[1])))), 0, tilt_deg=15)
    for k in range(4):
        fr = ph.frame(T0, k * 0.5)
        mem.update(k * 0.5, fr, detect(fr, room, det, rng))
    if mem.items[target].pos is None:
        return None
    # 2) Now walk toward it (veering, head looking around a little), as POC 5's listener would.
    t, pos = 0.0, np.array(start, float)
    torso = heading_of(T0) + rng.normal(0, 8)
    hot = 0.0
    ts, hy, logs = [], [], []
    ap = AirPodsStream(AirPodsModel(), rng)
    off = None
    next_det, ap_buf = 0.0, []
    ap_t, ap_y = [], []
    while t < 20:
        hot += (-hot) * dt / 0.5 + rng.normal(0, 25 * np.sqrt(dt))
        head_true = torso + hot
        ts.append(t); hy.append(head_true)
        T = chest_camera_pose(pos, torso, t, tilt_deg=15, walking=True)
        if t >= next_det:
            fr = ph.frame(T, t)
            mem.update(t, fr, detect(fr, room, det, rng, ang_speed_deg_s=10))
            next_det = t + 0.5
            Ta = fr["T_arkit"]
        else:
            ph.drift.update(T[:3, 3], dt)
            Ta = ph.drift.apply(T)
        # AirPods yaw: arbitrary reference (start heading), gyro-bias drift, small noise; fused
        # with the ARKit heading exactly as in POC 4 (tau 5 s, 15 deg gate).
        ap_now = (head_true - hy[0]) + ap.bias * t + rng.normal(0, 0.3)
        arkit_heading = heading_of(Ta)
        if off is None:
            off = arkit_heading - ap_now
        est = ap_now + off
        if abs(wrap(est - arkit_heading)) < 15:
            off += dt / 5.0 * wrap(arkit_heading - (ap_now + off))
        head_est = ap_now + off
        # App's listener position: phone position + ear offset along its heading.
        fwd, _ = yaw_vectors(arkit_heading)
        phone_p = Ta[:3, 3]
        lis = phone_p + (np.array([0, EAR_UP, 0]) - EAR_BACK * fwd if ear_offset else 0)
        it = mem.items[target]
        rel = it.pos - lis
        az_app = wrap(np.degrees(np.arctan2(rel[0], -rel[2])) - head_est)
        d_app = float(np.linalg.norm(rel[[0, 2]]))
        torso_app = float(np.linalg.norm((it.pos - phone_p)[[0, 2]]))
        el_app = float(np.degrees(np.arctan2(rel[1], d_app)))
        # Truth.
        fwd_t, _ = yaw_vectors(torso)
        ears = np.array([pos[0], 1.30 + EAR_UP, pos[1]]) + (0.12 - EAR_BACK) * np.r_[fwd_t[0], 0, fwd_t[2]]
        relt = goal - ears
        az_true = wrap(np.degrees(np.arctan2(relt[0], -relt[2])) - head_true)
        d_true = float(np.linalg.norm(relt[[0, 2]]))
        torso_true = float(np.linalg.norm((goal - np.array([pos[0], 0, pos[1]]))[[0, 2]]))
        el_true = float(np.degrees(np.arctan2(relt[1], d_true)))
        logs.append((t, az_app, az_true, d_app, d_true, el_app, el_true, torso_app, torso_true, float(np.linalg.norm((it.pos - goal)[[0, 2]]))))
        if torso_app < REACH:
            break
        # Walk: steer toward the item (as a guided listener would, with ~4 deg aiming noise).
        bearing = np.degrees(np.arctan2(goal[0] - pos[0], -(goal[2] - pos[1])))
        torso += np.clip(wrap(bearing - torso), -60 * dt, 60 * dt) + rng.normal(0, 1.5 * np.sqrt(dt))
        fwd_t, _ = yaw_vectors(torso)
        pos = pos + speed * dt * np.array([fwd_t[0], fwd_t[2]])
        t += dt
    L = np.array(logs)
    return dict(az_err=np.abs(wrap(L[:, 1] - L[:, 2])), d_err=L[:, 3] - L[:, 4], el_err=L[:, 5] - L[:, 6],
                d_true=L[:, 4], reach_true=L[-1, 8], item_err_start=L[0, 9], item_err_end=L[-1, 9],
                monotonic_violations=int(np.sum(np.diff(L[:, 3]) > 0.05)))


if __name__ == "__main__":
    starts = [(1.0, 0.6), (-1.5, 0.3), (1.4, -0.4)]
    res = {}
    for ear in (True, False):
        rs = [r for s in range(10) for st in starts if (r := run(s, st, ear_offset=ear)) is not None]
        az = np.concatenate([r["az_err"] for r in rs]); de = np.concatenate([r["d_err"] for r in rs])
        el = np.concatenate([r["el_err"] for r in rs]); dt_ = np.concatenate([r["d_true"] for r in rs])
        near = dt_ < 1.2
        key = "listener at ears (offset model)" if ear else "listener at phone (no offset)"
        res[key] = dict(
            walks=len(rs),
            azimuth_err_median_deg=float(np.median(az)), azimuth_err_p90_deg=float(np.percentile(az, 90)),
            azimuth_err_p90_within_1_2m_deg=float(np.percentile(az[near], 90)),
            distance_err_median_cm=float(100 * np.median(np.abs(de))), distance_err_p90_cm=float(100 * np.percentile(np.abs(de), 90)),
            elevation_err_median_deg=float(np.median(np.abs(el))), elevation_err_p90_within_1_2m_deg=float(np.percentile(np.abs(el[near]), 90)),
            within_reach_announced_at_true_torso_dist_cm=[round(100 * float(np.percentile([r["reach_true"] for r in rs], q)), 1) for q in (10, 50, 90)],
            item_pos_err_cm_start_vs_end=[round(100 * float(np.median([r["item_err_start"] for r in rs])), 1), round(100 * float(np.median([r["item_err_end"] for r in rs])), 1)],
            distance_monotonic_violations_total=int(sum(r["monotonic_violations"] for r in rs)))
        print(f"## {key}"); [print(f"  {k}: {v}") for k, v in res[key].items()]
    (ROOT / "reports" / "poc3_walk.json").write_text(json.dumps(res, indent=2))
