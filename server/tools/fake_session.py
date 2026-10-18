"""Make a synthetic recorded session (recorder.py layout) from the validated ARKit/LiDAR emulator, with ground truth.

The wearer walks two loops of the emulator's living room with the phone in the vest (portrait, 30 deg tilt),
then stands at the kitchen counter and touches the lid of a spice jar with the index finger pointing down (the
hand is rendered into the LiDAR depth, so the hand stream's depth patches are realistic; POC 24's geometry).
Why a counter-height lid: from the chest, the back of the hand hides the fingertip when you touch a low table or
poke the side of something straight ahead, and a hidden fingertip never counts as a touch. Frames: 1/s; poses: 10/s; hand: 15/s during the
reach. truth.json has every item's true footprint position, size and the touch time.

Images are flat-shaded renders of the scene (not photos): good for wiring, geometry and the dashboard, not for
testing OWLv2 (use tools/arkitscenes_session.py for real images).

  python tools/fake_session.py data/sessions/fake-livingroom
"""
import io
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
sys.path.insert(0, str(REPO / "poc" / "emulators" / "arkit"))
sys.path.insert(0, str(HERE.parents[1]))
from device import CX, CY, FX, FY, IMG_H, IMG_W, K, Phone, chest_camera_pose, pixel_rays, project  # noqa: E402
from scene import Box, Cylinder, demo_room  # noqa: E402

from marco import codec, geometry as G  # noqa: E402
from marco.touch import JOINTS  # noqa: E402

PATH = np.array([(0, 0.5), (0, -1.2), (-1.2, -1.5), (-1.3, -2.9), (1.0, -2.9), (1.4, -2.0), (0.8, -0.3), (-1.2, 0.3), (0, 0.5)])
SPEED, T0 = 0.8, 1000.0
PALETTE = {-1: (205, 200, 190), "coffee_table": (150, 100, 60), "dining_table": (120, 80, 50), "sofa_seat": (80, 90, 140),
           "sofa_back": (70, 80, 130), "shelf": (160, 150, 120), "entry_table": (140, 110, 80), "kitchen_counter": (180, 180, 185),
           "bottle": (40, 160, 70), "keys": (240, 200, 30), "wallet": (90, 50, 30), "glasses_case": (30, 30, 30),
           "mug": (220, 60, 60), "finger": (230, 180, 150), "palm": (225, 175, 145), "cereal_box": (200, 50, 50)}


def walk(loops=2, dt=0.1):
    seg = np.diff(PATH, axis=0)
    lens = np.linalg.norm(seg, axis=1)
    total = lens.sum() * loops
    t = 0.0
    while t * SPEED < total:
        s = (t * SPEED) % lens.sum()
        i = min(int(np.searchsorted(np.cumsum(lens), s, side="right")), len(seg) - 1)
        f = (s - np.r_[0, np.cumsum(lens)][i]) / lens[i]
        heading = np.degrees(np.arctan2(seg[i][0], -seg[i][1]))
        yield t, PATH[i] + f * seg[i], heading + 35 * np.sin(2 * np.pi * t / 5.0)
        t += dt


def render_rgb(room, T, w=480, h=360):
    s = w / IMG_W
    o, d = pixel_rays(T, w, h, FX * s, FY * s, CX * s, CY * s)
    z, idx = room.cast(o, d)
    prims = room.prims()
    img = np.zeros((h * w, 3), np.float32)
    for i in np.unique(idx):
        name = "shell" if i < 0 else prims[i].name
        img[idx == i] = PALETTE.get(name if i >= 0 else -1, (128, 128, 128))
    shade = np.clip(1.15 - 0.12 * z, 0.45, 1.0)[:, None]
    rgb = Image.fromarray((img * shade).clip(0, 255).astype(np.uint8).reshape(h, w, 3)).resize((960, 720), Image.Resampling.NEAREST)
    buf = io.BytesIO()
    rgb.save(buf, "JPEG", quality=85)
    return buf.getvalue()


def hand_boxes(tip):
    """POC 24's hand: index finger pointing down, palm above it reaching back toward the wearer (-x here, the
    wearer faces +x). Boxes, so the hand occludes things and shows up in the LiDAR depth."""
    t = np.asarray(tip)
    f = Box("finger", [t[0] - 0.009, t[1], t[2] - 0.009], [t[0] + 0.009, t[1] + 0.08, t[2] + 0.009])
    p = Box("palm", [t[0] - 0.081, t[1] + 0.08, t[2] - 0.02], [t[0] + 0.009, t[1] + 0.105, t[2] + 0.06])
    return [f, p]


def hand_joints(tip):
    t = np.asarray(tip)
    up = np.array([0, 1.0, 0])                         # from the fingertip back up the finger
    pts = {"indexTip": t, "indexDIP": t + 0.022 * up, "indexPIP": t + 0.047 * up, "indexMCP": t + 0.082 * up,
           "wrist": t + np.array([-0.07, 0.092, 0.02])}
    for i, n in enumerate(JOINTS):
        if n not in pts:                      # other fingers curled near the palm
            pts[n] = t + np.array([-0.01 - 0.004 * (i % 4), 0.085, 0.01 + 0.008 * (i // 4)])
    return pts


def main(out_dir):
    out = Path(out_dir)
    (out / "frames").mkdir(parents=True, exist_ok=True)
    for f in ("frames.jsonl", "phone.jsonl"):
        (out / f).write_text("")
    rng = np.random.default_rng(0)
    room = demo_room()
    room.items["jar"] = Cylinder("jar", 2.05, -3.0, 0.92, 1.02, 0.035, surface="kitchen_counter")   # a spice jar
    phone = Phone(room, rng)
    sid = out.name
    fid = 0
    frames_f, phone_f = open(out / "frames.jsonl", "w"), open(out / "phone.jsonl", "w")

    def write_frame(t, T_true, extra=None):
        nonlocal fid
        fid += 1
        fr = phone.frame(T_true, t, dt=0.0)
        T = fr["T_arkit"]
        meta = dict(session_id=sid, map_id=f"{sid}-map", frame_id=fid, t_device=round(T0 + t, 4),
                    t_wall=time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(1792000000 + t)) + ".000Z", tracking="normal",
                    camera_transform=G.flat_colmajor(T), intrinsics=G.flat_colmajor(K), image_resolution=[IMG_W, IMG_H],
                    jpeg_scale=0.5)
        base = out / "frames" / f"{fid:06d}"
        base.with_suffix(".jpg").write_bytes(render_rgb(room, T_true))
        base.with_suffix(".depth").write_bytes(codec.encode_depth(fr["depth"]))
        base.with_suffix(".conf").write_bytes(codec.encode_conf(fr["conf"]))
        frames_f.write(json.dumps(meta) + "\n")
        return fr

    def write_pose(t, T_arkit):
        phone_f.write(json.dumps(dict(type="pose", session_id=sid, map_id=f"{sid}-map", t_device=round(T0 + t, 4),
                                      camera_transform=G.flat_colmajor(T_arkit), head_yaw_deg=round(G.heading_deg(T_arkit), 2),
                                      head_source="phone")) + "\n")

    t_last_frame = -1.0
    t_end = 0.0
    for t, xz, yaw in walk(loops=2, dt=0.1):
        T = chest_camera_pose(xz, yaw, t, tilt_deg=30, walking=True)
        phone.drift.update(T[:3, 3], 0.1)
        write_pose(t, phone.drift.apply(T))
        if t - t_last_frame >= 1.0:
            write_frame(t, T)
            t_last_frame = t
        t_end = t
    # walk to the kitchen counter, stand facing the jar (facing +x), reach and touch its lid from above
    jar = room.items["jar"]
    stand = np.array([jar.cx - 0.60, jar.cz])          # the camera sits 0.12 m in front of the chest: ~0.48 m to the jar
    t = t_end + 0.1
    T_stand = chest_camera_pose(stand, 90.0, t, tilt_deg=30)
    tip_touch = np.array([jar.cx, jar.y1, jar.cz])
    tip_start = tip_touch + np.array([-0.25, 0.15, 0.05])
    reach_t0, touch_t = t + 2.0, None
    for i in range(int(7.0 * 15)):
        tt = t + i / 15
        if tt < reach_t0:
            tip = None
        else:
            a = min(1.0, (tt - reach_t0) / 0.8)                       # 0.8 s reach, then hold
            if tt > reach_t0 + 2.3:
                a = max(0.0, 1.0 - (tt - reach_t0 - 2.3) / 0.6)       # then withdraw
            tip = tip_start + (tip_touch - tip_start) * a
            if a >= 1.0 and touch_t is None:
                touch_t = tt
        room.furniture = [p for p in room.furniture if p.name not in ("finger", "palm")] + (hand_boxes(tip) if tip is not None else [])
        if i % 15 == 0:
            write_frame(tt, T_stand)
        if i % 2 == 0:
            phone.drift.update(T_stand[:3, 3], 2 / 15)
            write_pose(tt, phone.drift.apply(T_stand))
        if tip is None:
            continue
        fr = phone.frame(T_stand, tt, dt=0.0)
        T_ark = fr["T_arkit"]
        pts = hand_joints(tip)
        joints, xy = [], []
        for n in JOINTS:
            (u, v), z = project(T_stand, pts[n][None])[0][0], project(T_stand, pts[n][None])[1][0]
            iu, iv = int(u * 256 / IMG_W), int(v * 192 / IMG_H)
            # visible = nothing nearer than the joint at its pixel (the palm can hide the fingertip)
            visible = 0 <= iu < 256 and 0 <= iv < 192 and float(fr["gt_depth"][iv, iu]) >= float(z) - 0.015
            x, y = (u + rng.normal(0, 4)) / IMG_W, 1 - (v + rng.normal(0, 4)) / IMG_H
            joints.append(dict(name=n, x=round(float(x), 5), y=round(float(y), 5), conf=round(float(rng.uniform(0.6, 0.95) if visible else rng.uniform(0.15, 0.45)), 3)))
            xy.append((x, y))
        dp, cp = codec.patches_from_depth(fr["depth"], fr["conf"], xy)
        phone_f.write(json.dumps(dict(type="hand", session_id=sid, t_device=round(T0 + tt, 4), camera_transform=G.flat_colmajor(T_ark),
                                      vision_orientation="up", chirality="right", joints=joints, patch=9,
                                      depth_patches_f16_b64=codec.encode_patches(dp, "f16"),
                                      conf_patches_u8_b64=codec.encode_patches(cp, "u8"))) + "\n")
    t_fin = t + 7.0
    phone_f.write(json.dumps(dict(type="query", session_id=sid, query_id="find-keys", kind="find", name="keys", t_device=round(T0 + t_fin, 4))) + "\n")
    frames_f.close()
    phone_f.close()
    truth = dict(items={n: dict(position=[round(float(v), 4) for v in p.base], size=round(float(max(p.hi - p.lo) if isinstance(p, Box) else 2 * p.r), 3))
                        for n, p in room.items.items()},
                 touches=[dict(item="jar", t_device=round(T0 + touch_t, 4))] if touch_t else [],
                 note="positions are item footprints (base) in the emulator's true world frame; ARKit drift is in the poses")
    (out / "truth.json").write_text(json.dumps(truth, indent=1))
    print(f"wrote {out}: {fid} frames, truth for {len(truth['items'])} items, touch at {truth['touches']}")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else str(HERE.parents[1] / "data" / "sessions" / "fake-livingroom"))
