"""Convert an ARKitScenes sample (real iPad Pro LiDAR + RGB + ARKit poses + 3D object boxes) into a recorded session,
so the real pipeline (OWLv2, 3D placement, world model) runs on real images and real LiDAR.

Conversions (each checked):
  - poses: ARKitScenes .traj stores world->camera as axis-angle + translation (OpenCV camera: x right, y down,
    z forward). We invert it, flip to ARKit's camera axes (y up, z back), and rotate the world from z-up to y-up.
  - depth: lowres_depth PNG (uint16 mm, 256x192) -> metres; confidence PNG (0/1/2) as is
  - images: wide 1920x1440 PNG -> 960x720 JPEG (sensor orientation, no EXIF), intrinsics from the matching .pincam
  - truth: 3D object boxes -> footprint position (centre of the bottom face), size and the 8 corners (y-up)

  python tools/fetch_arkitscenes.py && python tools/arkitscenes_session.py --root data/arkitscenes/41069021
  python tools/arkitscenes_session.py                                   # scene 41069021 from poc/research
  python tools/arkitscenes_session.py --scene <x/ID dir> --traj <lowres_wide.traj> --pincams <dir> --boxes <json> --out <dir>
"""
import argparse
import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).resolve()
REPO = HERE.parents[2]
sys.path.insert(0, str(HERE.parents[1]))
from marco import codec, geometry as G  # noqa: E402

PROBE = REPO / "poc" / "research" / "datasets_probe"
CV_TO_ARKIT = np.diag([1.0, -1.0, -1.0, 1.0])
Z_UP_TO_Y_UP = np.array([[1.0, 0, 0, 0], [0, 0, 1.0, 0], [0, -1.0, 0, 0], [0, 0, 0, 1.0]])


def rodrigues(aa):
    aa = np.asarray(aa, float)
    th = np.linalg.norm(aa)
    if th < 1e-12:
        return np.eye(3)
    k = aa / th
    Kx = np.array([[0, -k[2], k[1]], [k[2], 0, -k[0]], [-k[1], k[0], 0]])
    return np.eye(3) + np.sin(th) * Kx + (1 - np.cos(th)) * Kx @ Kx


def load_traj(path):
    """{timestamp: camera-to-world (OpenCV camera axes, ARKitScenes world)}"""
    out = {}
    for line in Path(path).read_text().splitlines():
        tok = line.split()
        if len(tok) != 7:
            continue
        E = np.eye(4)
        E[:3, :3] = rodrigues([float(x) for x in tok[1:4]])
        E[:3, 3] = [float(x) for x in tok[4:7]]
        out[float(tok[0])] = np.linalg.inv(E)
    return out


def world_is_z_up(poses):
    """Average 'image up' direction of the camera in the world: +z means a z-up world."""
    ups = np.array([T[:3, :3] @ np.array([0, -1.0, 0]) for T in poses.values()])
    m = ups.mean(0)
    return abs(m[2]) > abs(m[1]), m


def to_arkit(T_cv, z_up):
    T = T_cv @ CV_TO_ARKIT
    return Z_UP_TO_Y_UP @ T if z_up else T


def read_pincam(path):
    w, h, fx, fy, cx, cy = [float(x) for x in Path(path).read_text().split()]
    return (int(w), int(h)), np.array([[fx, 0, cx], [0, fy, cy], [0, 0, 1.0]])


def boxes_to_truth(path, z_up):
    data = json.loads(Path(path).read_text())["data"]
    W = Z_UP_TO_Y_UP[:3, :3] if z_up else np.eye(3)
    items, count = {}, {}
    for o in data:
        obb = o["segments"]["obbAligned"]
        c = np.asarray(obb["centroid"], float)
        L = np.asarray(obb["axesLengths"], float)
        R = np.asarray(obb["normalizedAxes"], float).reshape(3, 3)       # rows are the box axes (ARKitScenes box_utils)
        signs = np.array([[sx, sy, sz] for sx in (-1, 1) for sy in (-1, 1) for sz in (-1, 1)], float)
        corners = (c + (signs * L / 2) @ R) @ W.T
        base = corners.mean(0)
        base[1] = corners[:, 1].min()
        horiz = max(np.ptp(corners[:, 0]), np.ptp(corners[:, 2]))
        label = o["label"]
        count[label] = count.get(label, 0) + 1
        name = label if count[label] == 1 else f"{label} {count[label]}"
        items[name] = dict(position=[round(float(v), 4) for v in base], size=round(float(horiz), 3),
                           corners=[[round(float(v), 4) for v in p] for p in corners])
    return items


def main(scene, traj, pincams, boxes, out):
    out = Path(out)
    (out / "frames").mkdir(parents=True, exist_ok=True)
    poses_cv = load_traj(traj)
    z_up, up = world_is_z_up(poses_cv)
    print(f"world up axis (camera 'up' averaged): {np.round(up, 3)} -> {'z-up, rotating to y-up' if z_up else 'already y-up'}")
    tps = np.array(sorted(poses_cv))
    pins = {float(p.stem.split("_")[1]): p for p in Path(pincams).glob("*.pincam")}
    pts = np.array(sorted(pins))
    sid = f"arkitscenes-{Path(scene).name}"
    frames_f, phone_f = open(out / "frames.jsonl", "w"), open(out / "phone.jsonl", "w")
    n = 0
    t_first = t_last = None
    for img in sorted(Path(scene, "wide").glob("*.png"), key=lambda p: float(p.stem.split("_")[1])):
        ts = float(img.stem.split("_")[1])
        i = int(np.argmin(np.abs(tps - ts)))
        if abs(tps[i] - ts) > 0.1:
            continue                                          # no pose close enough
        j = int(np.argmin(np.abs(pts - ts)))
        res, K = read_pincam(pins[pts[j]])
        T = to_arkit(poses_cv[tps[i]], z_up)
        G.check_pose(T)
        rgb = Image.open(img).convert("RGB")
        assert rgb.size == res, (rgb.size, res)
        buf = io.BytesIO()
        rgb.resize((res[0] // 2, res[1] // 2)).save(buf, "JPEG", quality=85)
        depth = np.asarray(Image.open(Path(scene, "lowres_depth", img.name)), np.float32) / 1000.0
        conf = np.asarray(Image.open(Path(scene, "confidence", img.name)), np.uint8)
        n += 1
        base = out / "frames" / f"{n:06d}"
        base.with_suffix(".jpg").write_bytes(buf.getvalue())
        base.with_suffix(".depth").write_bytes(codec.encode_depth(depth))
        base.with_suffix(".conf").write_bytes(codec.encode_conf(conf))
        frames_f.write(json.dumps(dict(session_id=sid, map_id=sid, frame_id=n, t_device=ts, t_wall=f"2026-10-17T15:{int(ts) // 60 % 60:02d}:{int(ts) % 60:02d}.000Z",
                                       tracking="normal", camera_transform=G.flat_colmajor(T), intrinsics=G.flat_colmajor(K),
                                       image_resolution=list(res), jpeg_scale=0.5)) + "\n")
        t_first = ts if t_first is None else t_first
        t_last = ts
    for t in tps:
        if t_first is not None and t_first - 1 <= t <= t_last + 1:
            T = to_arkit(poses_cv[t], z_up)
            phone_f.write(json.dumps(dict(type="pose", session_id=sid, map_id=sid, t_device=float(t), camera_transform=G.flat_colmajor(T),
                                          head_yaw_deg=round(G.heading_deg(T), 2), head_source="phone")) + "\n")
    frames_f.close()
    phone_f.close()
    truth = dict(items=boxes_to_truth(boxes, z_up), touches=[], note="footprint = centre of the box's bottom face (y-up world)")
    (out / "truth.json").write_text(json.dumps(truth, indent=1))
    print(f"wrote {out}: {n} frames, {len(truth['items'])} annotated objects: {sorted(truth['items'])}")


def root_paths(root):
    """The layout tools/fetch_arkitscenes.py writes: <id>/, wide_intrinsics/, lowres_wide.traj, <id>_3dod_annotation.json."""
    root = Path(root)
    vid = next(p.name for p in root.iterdir() if p.is_dir() and p.name.isdigit())
    return root / vid, root / "lowres_wide.traj", root / "wide_intrinsics", root / f"{vid}_3dod_annotation.json"


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=None, help="a folder from tools/fetch_arkitscenes.py (sets the four paths below)")
    ap.add_argument("--scene", default=str(PROBE / "arkitscenes_upsampling_val_41069021" / "x" / "41069021"))
    ap.add_argument("--traj", default=str(PROBE / "arkitscenes_41069021_small" / "lowres_wide.traj"))
    ap.add_argument("--pincams", default=str(PROBE / "arkitscenes_41069021_small" / "x_wide_intrinsics" / "wide_intrinsics"))
    ap.add_argument("--boxes", default=str(PROBE / "arkitscenes_41069021_small" / "41069021_3dod_annotation.json"))
    ap.add_argument("--out", default=str(HERE.parents[1] / "data" / "sessions" / "arkitscenes-41069021"))
    a = ap.parse_args()
    if a.root:
        a.scene, a.traj, a.pincams, a.boxes = map(str, root_paths(a.root))
    main(a.scene, a.traj, a.pincams, a.boxes, a.out)
