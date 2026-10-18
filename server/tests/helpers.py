"""Shared builders for valid (and deliberately broken) phone messages."""
import io
import json

import numpy as np
from PIL import Image

from marco import codec, geometry as G


def emulated(tilt=30.0, xz=(0.0, -1.2), yaw=0.0, seed=0):
    from device import K, Phone, chest_camera_pose
    from scene import demo_room
    room = demo_room()
    T = chest_camera_pose(xz, yaw, 0.0, tilt_deg=tilt)
    fr = Phone(room, np.random.default_rng(seed)).frame(T, 0.0)
    return room, T, K, fr


def jpeg_bytes(w=960, h=720, exif_orientation=None):
    im = Image.fromarray(np.random.default_rng(1).integers(0, 255, (h, w, 3), dtype=np.uint8))
    buf = io.BytesIO()
    if exif_orientation:
        ex = Image.Exif()
        ex[0x0112] = exif_orientation
        im.save(buf, "JPEG", exif=ex.tobytes())
    else:
        im.save(buf, "JPEG")
    return buf.getvalue()


def frame_parts(frame_id=1, session="s1", T=None, K=None, depth=None, conf=None, jpeg=None, t=1000.0, row_major=False):
    if T is None:
        _, T, K, fr = emulated()
        depth, conf = fr["depth"], fr["conf"]
    flat_T = np.asarray(T).reshape(-1).tolist() if row_major else G.flat_colmajor(T)
    meta = dict(session_id=session, map_id="m1", frame_id=frame_id, t_device=t, t_wall="2026-10-17T15:00:00.000Z",
                tracking="normal", camera_transform=flat_T, intrinsics=G.flat_colmajor(K), image_resolution=[1920, 1440],
                jpeg_scale=0.5)
    files = {"image": ("f.jpg", jpeg if jpeg is not None else jpeg_bytes(), "image/jpeg"),
             "depth": ("f.depth", codec.encode_depth(depth), "application/octet-stream"),
             "confidence": ("f.conf", codec.encode_conf(conf), "application/octet-stream")}
    return {"meta": json.dumps(meta)}, files, meta


def pose_msg(T, t=1000.0, session="s1"):
    return dict(type="pose", session_id=session, map_id="m1", t_device=t, camera_transform=G.flat_colmajor(T),
                head_yaw_deg=G.heading_deg(T), head_source="phone")
