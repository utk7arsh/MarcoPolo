"""Download one ARKitScenes validation scene (real iPad Pro LiDAR, RGB, ARKit poses and 3D object boxes; about 50 MB)
from Apple's public dataset server, laid out for arkitscenes_session.py --root. The data is Apple's (ARKitScenes
licence), so it stays out of git (server/data/ is ignored).

  python tools/fetch_arkitscenes.py                 # scene 41069021 -> data/arkitscenes/41069021/
  python tools/arkitscenes_session.py --root data/arkitscenes/41069021 --out data/sessions/arkitscenes-41069021
"""
import argparse
import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

BASE = "https://docs-assets.developer.apple.com/ml-research/datasets/arkitscenes/v1"


def urls(video_id, split="Validation"):
    """(url, local name, unzip?) for what the converter needs: RGB + depth + confidence, poses, intrinsics, boxes."""
    raw = f"{BASE}/raw/{split}/{video_id}"
    return [(f"{BASE}/upsampling/{split}/{video_id}.zip", f"{video_id}.zip", True),
            (f"{raw}/lowres_wide.traj", "lowres_wide.traj", False),
            (f"{raw}/wide_intrinsics.zip", "wide_intrinsics.zip", True),
            (f"{raw}/{video_id}_3dod_annotation.json", f"{video_id}_3dod_annotation.json", False)]


def safe_extract(zip_path, dest):
    """Extract, refusing members that would land outside dest (absolute paths, '..', links)."""
    dest = Path(dest).resolve()
    with zipfile.ZipFile(zip_path) as z:
        for m in z.infolist():
            target = (dest / m.filename).resolve()
            if target != dest and dest not in target.parents:
                raise ValueError(f"unsafe path in {zip_path}: {m.filename}")
            if (m.external_attr >> 16) & 0o170000 == 0o120000:
                raise ValueError(f"symlink in {zip_path}: {m.filename}")
        z.extractall(dest)


def fetch(video_id, root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    for url, name, unzip in urls(video_id):
        path = root / name
        done = (root / name.removesuffix(".zip")) if unzip else path
        if done.exists():
            print(f"have {done}")
            continue
        tmp = path.with_suffix(path.suffix + ".tmp")
        print(f"get {url}")
        with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
            shutil.copyfileobj(r, f)
        tmp.rename(path)
        if unzip:
            safe_extract(path, root)
    return root


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", default="41069021")
    ap.add_argument("--root", default=None, help="default: data/arkitscenes/<video>")
    a = ap.parse_args()
    root = fetch(a.video, a.root or Path(__file__).resolve().parents[1] / "data" / "arkitscenes" / a.video)
    print(f"ready: python tools/arkitscenes_session.py --root {root} --out data/sessions/arkitscenes-{a.video}")
    sys.exit(0)
