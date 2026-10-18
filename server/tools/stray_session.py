"""Convert an iPhone recording from the free Stray Scanner app (iPhone Pro LiDAR + video + ARKit poses) into a
recorded session, so the pipeline can run on real iPhone 16 Pro data before our own app is ready.

Stray Scanner export (github.com/strayrobots/scanner docs/format.md): rgb.mp4, depth/000000.png (uint16 mm,
256x192), confidence/000000.png (0/1/2), odometry.csv: timestamp, frame, x, y, z, qx, qy, qz, qw[, fx, fy, cx, cy, ...]
(older exports: intrinsics in camera_matrix.csv).
Its docs don't state the camera-axis convention of the pose, so both are tried (ARKit's y-up/z-back, or OpenCV's
y-down/z-forward) and the one whose LiDAR frames line up across the recording is kept.

  python tools/stray_session.py <stray export folder> --out data/sessions/<name> [--fps 1]
"""
import argparse
import io
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from marco import codec, geometry as G  # noqa: E402

CV_TO_ARKIT = np.diag([1.0, -1.0, -1.0, 1.0])
RATIOS = (0.25, 1 / 3, 0.375, 0.5, 2 / 3, 0.75, 1.5, 2.0, 3.0, 4.0)


def quat_to_R(qx, qy, qz, qw):
    n = np.sqrt(qx * qx + qy * qy + qz * qz + qw * qw)
    x, y, z, w = qx / n, qy / n, qz / n, qw / n
    return np.array([[1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
                     [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
                     [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)]])


def read_odometry(path):
    lines = [l for l in Path(path).read_text().splitlines() if l.strip()]
    head = [h.strip() for h in lines[0].split(",")]
    rows = []
    for l in lines[1:]:
        vals = [v.strip() for v in l.split(",")]
        rows.append({h: (float(v) if v not in ("", None) else None) for h, v in zip(head, vals)})
    return rows


def overlap_score(frames, convention, vox=0.10):
    """Share of each frame's LiDAR voxels seen by other frames, with poses read in `convention`."""
    keys = []
    for T, K, res, d, c in frames:                           # T as read from the file, before any axis flip
        fr = G.Frame(T if convention == "arkit" else T @ CV_TO_ARKIT, K, res, d, c)
        keys.append(set(map(tuple, np.floor(fr.point_cloud(step=4)[0] / vox).astype(int))))
    s = []
    for i, k in enumerate(keys):
        others = set().union(*[o for j, o in enumerate(keys) if j != i])
        s.append(len(k & others) / max(len(k), 1))
    return float(np.mean(s)) if s else 0.0


def pose(row, convention):
    T = np.eye(4)
    T[:3, :3] = quat_to_R(row["qx"], row["qy"], row["qz"], row["qw"])
    T[:3, 3] = [row["x"], row["y"], row["z"]]
    return T if convention == "arkit" else T @ CV_TO_ARKIT


def intrinsics(row, K_file, w):
    if row.get("fx"):
        K = np.array([[row["fx"], 0, row["cx"]], [0, row["fy"], row["cy"]], [0, 0, 1.0]])
    elif K_file is not None:
        K = np.array(K_file, float)
    else:
        raise SystemExit("no intrinsics: odometry.csv has no fx/fy/cx/cy and camera_matrix.csv is missing")
    r = w / (2 * K[0, 2])                                     # intrinsics for another resolution than the video
    if abs(r - 1) > 0.1:
        K[:2] *= min(RATIOS, key=lambda c: abs(c - r))
    return K


def main(src, out, fps=1.0):
    import cv2
    src, out = Path(src), Path(out)
    (out / "frames").mkdir(parents=True, exist_ok=True)
    odo = read_odometry(src / "odometry.csv")
    by_frame = {int(r["frame"]): r for r in odo}
    K_file = np.loadtxt(src / "camera_matrix.csv", delimiter=",") if (src / "camera_matrix.csv").exists() else None
    cap = cv2.VideoCapture(str(src / "rgb.mp4"))
    if not cap.isOpened():
        raise SystemExit("cannot open rgb.mp4 (OpenCV needs an FFmpeg build with HEVC decoding)")
    frames, last_t, i = [], -1e9, -1
    while True:
        ok, bgr = cap.read()
        if not ok:
            break
        i += 1
        row = by_frame.get(i)
        name = f"{i:06d}.png"
        if row is None or row["timestamp"] - last_t < 1.0 / fps - 1e-6 or not (src / "depth" / name).exists():
            continue
        last_t = row["timestamp"]
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
        h, w = rgb.shape[:2]
        depth = np.asarray(Image.open(src / "depth" / name), np.float32) / 1000.0
        cpath = src / "confidence" / name
        conf = np.asarray(Image.open(cpath), np.uint8) if cpath.exists() else np.full(depth.shape, 2, np.uint8)
        frames.append((row, intrinsics(row, K_file, w), (w, h), depth, conf, rgb))
    if not frames:
        raise SystemExit("no video frames with matching odometry and depth found")
    scores = {cv: overlap_score([(pose(f[0], "arkit"), *f[1:5]) for f in frames], cv) for cv in ("arkit", "opencv")}
    conv = max(scores, key=scores.get)
    print(f"pose convention: {conv} (LiDAR overlap arkit {scores['arkit']:.3f}, opencv {scores['opencv']:.3f})")
    sid = f"stray-{src.name}"
    wall = lambda t: time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(1792000000 + t)) + ".000Z"
    with open(out / "frames.jsonl", "w") as ff, open(out / "phone.jsonl", "w") as pf:
        for n, (row, K, (w, h), depth, conf, rgb) in enumerate(frames, 1):
            buf = io.BytesIO()
            Image.fromarray(rgb).resize((w // 2, h // 2)).save(buf, "JPEG", quality=85)
            base = out / "frames" / f"{n:06d}"
            base.with_suffix(".jpg").write_bytes(buf.getvalue())
            base.with_suffix(".depth").write_bytes(codec.encode_depth(depth))
            base.with_suffix(".conf").write_bytes(codec.encode_conf(conf))
            ff.write(json.dumps(dict(session_id=sid, map_id=sid, frame_id=n, t_device=row["timestamp"], t_wall=wall(row["timestamp"]),
                                     tracking="normal", camera_transform=G.flat_colmajor(pose(row, conv)), intrinsics=G.flat_colmajor(K),
                                     image_resolution=[w, h], jpeg_scale=0.5)) + "\n")
        last_t = -1e9
        for row in odo:                                       # poses at about 10/s
            if row["timestamp"] - last_t < 0.1 - 1e-6:
                continue
            last_t = row["timestamp"]
            T = pose(row, conv)
            pf.write(json.dumps(dict(type="pose", session_id=sid, map_id=sid, t_device=row["timestamp"], camera_transform=G.flat_colmajor(T),
                                     head_yaw_deg=round(G.heading_deg(T), 2), head_source="phone")) + "\n")
    print(f"wrote {out}: {len(frames)} frames")
    return conv


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fps", type=float, default=1.0)
    a = ap.parse_args()
    main(a.src, a.out, a.fps)
