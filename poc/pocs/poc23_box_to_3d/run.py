"""POC 23: the bugs that will bite when server boxes come back to the phone and become 3D positions.

A. Stale pose. The server answers 0.3-1.5 s after the frame was taken; the wearer has moved and turned
   (torso sweeping +-35 deg while walking, as in POC 1). Placing the box with the pose and depth of the
   CURRENT frame instead of the frame it came from is the easiest bug to write. Measured: horizontal error
   of the placed item for the correct path (pose + depth saved with the frame) vs the stale paths.
B. Orientation and scale. ARKit's capturedImage is landscape (sensor orientation); the app uploads an
   upright portrait 960 px JPEG. Boxes must be rotated and scaled back. We check the round trip and what
   the three classic mistakes do to the 3D position: wrong rotation direction, no rotation, no rescale.
C. EXIF orientation. If the app sends a landscape JPEG with an orientation tag instead of rotating pixels,
   do the server's two image loaders (PIL, used by OWLv2's processor; OpenCV, used by Ultralytics/YOLOE)
   agree on which way is up?
"""
import io
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for p in ("emulators/arkit", "core", "pocs/poc1_mapping"):
    sys.path.insert(0, str(ROOT / p))
from device import IMG_H, IMG_W, DetectorModel, Phone, chest_camera_pose, detect  # noqa: E402
from mapping import locate_footprint, locate_median  # noqa: E402
from run import walk  # noqa: E402  (POC 1's room loop)
from scene import demo_room  # noqa: E402

UP_LONG = 960  # long side of the uploaded JPEG
S = UP_LONG / IMG_W


def sensor_to_upload(b):
    """Sensor-landscape box (u0,v0,u1,v1) -> upright portrait upload box (x0,y0,x1,y1).
    Portrait = the sensor image rotated 90 deg clockwise (CIImage.oriented(.right)): x' = H-1-v, y' = u."""
    u0, v0, u1, v1 = b
    return np.array([(IMG_H - 1 - v1) * S, u0 * S, (IMG_H - 1 - v0) * S, u1 * S])


def upload_to_sensor(b, mode="correct"):
    x0, y0, x1, y1 = b
    if mode == "no rescale":
        x0, y0, x1, y1 = x0 * S, y0 * S, x1 * S, y1 * S      # forgot to divide by the scale
    elif mode != "no rotation":
        x0, y0, x1, y1 = x0 / S, y0 / S, x1 / S, y1 / S
    if mode in ("correct", "no rescale"):
        return np.array([y0, IMG_H - 1 - x1, y1, IMG_H - 1 - x0])
    if mode == "wrong direction":                             # undid a clockwise turn as if it were counter-clockwise
        return np.array([IMG_W - 1 - y1, x0, IMG_W - 1 - y0, x1])
    return np.array([x0 / S, y0 / S, x1 / S, y1 / S])         # "no rotation": treat portrait px as sensor px


def part_a():
    out = {}
    for lat in (0.3, 0.6, 1.0, 1.5):
        rng = np.random.default_rng(3)
        room = demo_room()
        phone = Phone(room, rng)
        det = DetectorModel()
        traj = list(walk(loops=2))
        dt = traj[1][0] - traj[0][0]
        step = int(round(1.0 / dt))                           # 1 frame per second to the server
        lag = int(round(lat / dt))
        errs = {"correct (saved pose + depth)": [], "stale pose + stale depth": [], "stale pose, saved depth": []}
        for i in range(0, len(traj) - lag, step):
            t, xz, yaw = traj[i]
            T = chest_camera_pose(xz, yaw, t, tilt_deg=30, walking=True)
            fr = phone.frame(T, t)
            t2, xz2, yaw2 = traj[i + lag]
            T2 = chest_camera_pose(xz2, yaw2, t2, tilt_deg=30, walking=True)
            fr2 = phone.frame(T2, t2)
            for d in detect(fr, room, det, rng):
                if d["true_index"] < 0:
                    continue
                gt = fr["prims"][d["true_index"]].base
                for name, frame in (("correct (saved pose + depth)", fr),
                                    ("stale pose + stale depth", fr2),
                                    ("stale pose, saved depth", dict(fr, T_arkit=fr2["T_arkit"]))):
                    p = locate_footprint(d, frame)
                    if p is not None:
                        errs[name].append(100 * float(np.linalg.norm((p - gt)[[0, 2]])))
        out[f"server latency {lat} s"] = {k: dict(n=len(v), median_cm=round(float(np.median(v)), 1), p90_cm=round(float(np.percentile(v, 90)), 1))
                                          for k, v in errs.items() if v}
        print(f"latency {lat} s:", {k: (v['median_cm'], v['p90_cm']) for k, v in out[f'server latency {lat} s'].items()}, flush=True)
    return out


def part_b():
    rng = np.random.default_rng(5)
    room = demo_room()
    phone = Phone(room, rng)
    det = DetectorModel()
    rows = {m: [] for m in ("correct", "wrong direction", "no rotation", "no rescale")}
    roundtrip = []
    for t, xz, yaw in list(walk(loops=1))[::60]:
        T = chest_camera_pose(xz, yaw, t, tilt_deg=30, walking=True)
        fr = phone.frame(T, t)
        for d in detect(fr, room, det, rng):
            if d["true_index"] < 0:
                continue
            gt = fr["prims"][d["true_index"]].base
            up = sensor_to_upload(d["bbox"])
            roundtrip.append(float(np.abs(upload_to_sensor(up) - d["bbox"]).max()))
            for m in rows:
                bb = upload_to_sensor(up, m)
                p = locate_median(dict(d, bbox=bb), fr)
                rows[m].append(np.inf if p is None else 100 * float(np.linalg.norm((p - gt)[[0, 2]])))
    res = {"round_trip_max_px_error": round(max(roundtrip), 3)}
    for m, v in rows.items():
        v = np.array(v)
        res[m] = dict(n=len(v), median_cm=round(float(np.median(v)), 1), placed_within_30cm_pct=round(100 * float((v < 30).mean()), 1))
    print("orientation:", res, flush=True)
    return res


def part_c():
    from PIL import Image
    import cv2
    w, h = 400, 300
    im = Image.new("RGB", (w, h), (40, 40, 40))
    im.paste((255, 0, 0), (0, 0, 60, 60))                     # a red mark in the top-left of the sensor image
    ex = Image.Exif()
    ex[0x0112] = 6                                             # "rotate 90 CW to display" (what iOS writes for portrait)
    buf = io.BytesIO()
    im.save(buf, "JPEG", exif=ex.tobytes())
    raw = buf.getvalue()
    pil = Image.open(io.BytesIO(raw))
    arr = cv2.imdecode(np.frombuffer(raw, np.uint8), cv2.IMREAD_COLOR)
    tmp = ROOT / "data" / "tmp" / "exif_test.jpg"
    tmp.write_bytes(raw)
    arr_file = cv2.imread(str(tmp))
    res = {"jpeg_pixels_wxh": [w, h], "exif_orientation": 6,
           "PIL Image.open size": list(pil.size),
           "OpenCV imdecode (bytes) size": [int(arr.shape[1]), int(arr.shape[0])],
           "OpenCV imread (file path, what Ultralytics uses for paths) size": [int(arr_file.shape[1]), int(arr_file.shape[0])]}
    res["loaders_agree"] = res["PIL Image.open size"] == res["OpenCV imread (file path, what Ultralytics uses for paths) size"]
    print("exif:", res, flush=True)
    return res


if __name__ == "__main__":
    out = {"A_stale_pose": part_a(), "B_orientation": part_b(), "C_exif": part_c()}
    (ROOT / "reports" / "poc23_box_to_3d.json").write_text(json.dumps(out, indent=2))
