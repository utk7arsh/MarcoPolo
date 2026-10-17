"""POC 11: Which everyday wearable actually sees you put things down?

A wearer goes through a day of put-downs (keys, wallet, bottle, glasses case, mug on six home
surfaces). For each put-down we check whether the camera would detect the item during the
1.5 s release window, and how often it is re-seen while walking around afterwards.

Devices (real camera geometry):
  chest phone 0 deg / 30 deg  iPhone wide camera, portrait, fx=1600 @1920x1440 (48 x 62 deg), 1.30 m
  glasses                     Ray-Ban Meta (DAT stream 720x1280, ~100 deg diagonal -> 61 x 92 deg),
                              eye height 1.62 m, follows the head; Bluetooth compression modelled
                              as needing 1.3x more pixels; continuous 2 fps
  glasses (look-down bursts)  same, but frames only while the head is pitched down > 20 deg
  cap                         ESP32-S3 Sense OV2640 (~66 deg diag), under the brim, 30 deg below
                              the head direction, frames only while looking down
Head behaviour while placing (the crux for head-worn cameras):
  looks at hands  pitches toward the item 90 % of the time (typical sighted behaviour)
  blind-typical   looks toward the item only 30 % of the time, otherwise head roughly level
                  (there is no good published number for this; we sweep it)
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "emulators" / "arkit"))
from device import DetectorModel, chest_camera_pose  # noqa: E402

DET = DetectorModel()
SURFACES = {  # placement point (x, y, z) and where the wearer stands (x, z)
    "entry table": ((-2.30, 0.80, 0.55), (-1.75, 0.55)),
    "coffee table": ((0.20, 0.45, -2.00), (0.20, -1.45)),
    "dining table": ((1.55, 0.75, -0.70), (1.00, -0.70)),
    "kitchen counter": ((2.20, 0.92, -3.50), (1.65, -3.50)),
    "sofa seat": ((0.50, 0.45, -3.45), (0.50, -2.95)),
    "shelf": ((-2.30, 1.20, -1.10), (-1.80, -1.10)),
}
ITEMS = {"keys": 0.08, "wallet": 0.11, "bottle": 0.25, "glasses_case": 0.16, "mug": 0.10}


def rot_cam(yaw_deg, pitch_deg):
    """Camera-to-world rotation (ARKit axes: x right, y up, camera looks down -z) for a forward camera."""
    a, p = np.radians(yaw_deg), np.radians(pitch_deg)
    fwd = np.array([np.sin(a) * np.cos(p), np.sin(p), -np.cos(a) * np.cos(p)])
    right = np.array([np.cos(a), 0.0, np.sin(a)])
    up = np.cross(right, fwd)
    return np.stack([right, up, -fwd], 1)


def visible_size(R, cam_pos, f, w, h, item_pos, size):
    """Projected longest side (px) of an item if fully inside the image, else 0."""
    pc = (item_pos - cam_pos) @ R
    z = -pc[2]
    if z < 0.1:
        return 0.0
    u, v = w / 2 + f * pc[0] / z, h / 2 - f * pc[1] / z
    s = f * size / z
    if not (s / 2 <= u <= w - s / 2 and s / 2 <= v <= h - s / 2):
        return 0.0
    return s


def chest_cam(tilt):
    def cam(torso_xz, torso_yaw, head_yaw, head_pitch, t, walking):
        T = chest_camera_pose(torso_xz, torso_yaw, t, tilt_deg=tilt, walking=walking)
        # Portrait sensor: 1920 px along the vertical axis. Equivalent upright pinhole: w=1440, h=1920.
        R = rot_cam(torso_yaw, -tilt)
        return R, T[:3, 3], 1600.0, 1440, 1920, 1.0
    return cam


def glasses_cam(mode):
    f = 616.0  # 720x1280, ~100 deg diagonal

    def cam(torso_xz, torso_yaw, head_yaw, head_pitch, t, walking):
        if mode == "lookdown" and head_pitch > -20:
            return None
        fwd = np.array([np.sin(np.radians(head_yaw)), 0, -np.cos(np.radians(head_yaw))])
        right = np.array([np.cos(np.radians(head_yaw)), 0, np.sin(np.radians(head_yaw))])
        pos = np.array([torso_xz[0], 1.62, torso_xz[1]]) + 0.08 * fwd - 0.07 * right
        return rot_cam(head_yaw, head_pitch - 5), pos, f, 720, 1280, 1.3
    return cam


def cap_cam(torso_xz, torso_yaw, head_yaw, head_pitch, t, walking):
    if head_pitch > -20:
        return None
    fwd = np.array([np.sin(np.radians(head_yaw)), 0, -np.cos(np.radians(head_yaw))])
    pos = np.array([torso_xz[0], 1.72, torso_xz[1]]) + 0.10 * fwd
    f = 800 / np.tan(np.radians(33)) / np.sqrt(1 + (600 / 800) ** 2)  # 1600x1200, 66 deg diagonal
    return rot_cam(head_yaw, head_pitch - 30), pos, f, 1200, 1600, 1.6  # portrait-ish under the brim


DEVICES = {"chest phone 0 deg": chest_cam(0), "chest phone 30 deg": chest_cam(30),
           "glasses (2 fps stream)": glasses_cam("stream"), "glasses (look-down bursts)": glasses_cam("lookdown"),
           "cap (look-down bursts)": cap_cam}


def p_detect(name, px, factor):
    return float(DET.p_detect(name, px / factor, 1.0, 0.0)) if px > 0 else 0.0


def day(rng, p_look, n_events=120):
    """Yield put-down events: (item, size, surface point, stand position, torso yaw, head trajectory)."""
    names = list(SURFACES)
    for _ in range(n_events):
        s = names[rng.integers(len(names))]
        item = list(ITEMS)[rng.integers(len(ITEMS))]
        pt, stand = SURFACES[s]
        pt = np.array(pt) + np.r_[rng.uniform(-0.15, 0.15), 0, rng.uniform(-0.1, 0.1)]
        stand = np.array(stand) + rng.normal(0, 0.08, 2)
        dx, dz = pt[0] - stand[0], pt[2] - stand[1]
        yaw_to = np.degrees(np.arctan2(dx, -dz))
        torso = yaw_to + rng.normal(0, 15)
        horiz = np.hypot(dx, dz)
        looks = rng.uniform() < p_look
        pitch_to = np.degrees(np.arctan2(pt[1] - 1.62, horiz))
        if looks:
            head_yaw, head_pitch = yaw_to + rng.normal(0, 5), pitch_to + rng.normal(0, 6)
        else:
            head_yaw, head_pitch = torso + rng.normal(0, 12), rng.normal(-8, 8)
        yield item, ITEMS[item], pt, stand, torso, head_yaw, head_pitch


if __name__ == "__main__":
    res = {}
    for label, p_look in (("looks at hands (p=0.9)", 0.9), ("blind-typical (p=0.3)", 0.3), ("never looks down (p=0)", 0.0)):
        rng = np.random.default_rng(1)
        events = list(day(rng, p_look))
        res[label] = {}
        for dname, cam in DEVICES.items():
            caught = []
            for item, size, pt, stand, torso, hy, hp in events:
                # 1.5 s release window at 2 fps = 3 frames with a little head/body motion
                p_miss = 1.0
                for k in range(3):
                    c = cam(stand, torso + rng.normal(0, 2), hy + rng.normal(0, 3), hp + rng.normal(0, 3), k * 0.5, False)
                    if c is None:
                        continue
                    R, pos, f, w, h, fac = c
                    p_miss *= 1 - p_detect(item, visible_size(R, pos, f, w, h, pt, size), fac)
                caught.append(1 - p_miss)
            res[label][dname] = round(100 * float(np.mean(caught)), 1)
        print(f"\n## wearer {label}: put-downs captured during release")
        for k, v in res[label].items():
            print(f"  {k:28} {v:5.1f}%")
    (ROOT / "reports" / "poc11_wearables.json").write_text(json.dumps(res, indent=2))


def resight(rng, p_look, n_events=60, walk_s=60.0, fps=2.0):
    """P(item re-seen within walk_s while the wearer walks the room loop afterwards)."""
    sys.path.insert(0, str(ROOT / "pocs" / "poc1_mapping"))
    from run import walk as loop_walk  # POC 1's room loop
    traj = [(t, xz, yaw) for t, xz, yaw in loop_walk(loops=6) if t < walk_s]
    frames = traj[:: int(60 / fps)]
    out = {d: [] for d in DEVICES}
    for item, size, pt, *_ in list(day(rng, p_look, n_events)):
        start = rng.integers(len(frames))
        seq = frames[start:] + frames[:start]
        for dname, cam in DEVICES.items():
            p_miss = 1.0
            for k, (t, xz, yaw) in enumerate(seq):
                glance = rng.uniform() < (0.15 if p_look > 0.5 else 0.05)  # occasional look down at surfaces
                hy = yaw + rng.normal(0, 20)
                hp = rng.normal(-35, 8) if glance else rng.normal(-10, 7)
                c = cam(xz, yaw, hy, hp, t, True)
                if c is None:
                    continue
                R, pos, f, w, h, fac = c
                p_miss *= 1 - p_detect(item, visible_size(R, pos, f, w, h, pt, size), fac)
            out[dname].append(1 - p_miss)
    return {d: round(100 * float(np.mean(v)), 1) for d, v in out.items()}


if __name__ == "__main__" and "--resight" in sys.argv:
    res = json.loads((ROOT / "reports" / "poc11_wearables.json").read_text())
    for label, p_look in (("looks at hands (p=0.9)", 0.9), ("blind-typical (p=0.3)", 0.3)):
        r = resight(np.random.default_rng(2), p_look)
        res[f"re-seen within 60 s of walking, {label}"] = r
        print(f"\n## re-seen within 60 s while walking around, wearer {label}")
        for k, v in r.items():
            print(f"  {k:28} {v:5.1f}%")
    (ROOT / "reports" / "poc11_wearables.json").write_text(json.dumps(res, indent=2))
