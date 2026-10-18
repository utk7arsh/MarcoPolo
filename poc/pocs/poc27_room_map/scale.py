"""POC 27: how summarize() grows with the area mapped. The synthetic room's frames are replayed shifted into a
k x k block of rooms (6 m apart), so a long walk through many rooms is simulated; the grid caps at 40 m x 40 m.

  python poc/pocs/poc27_room_map/scale.py
"""
import io
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "server"))
from marco import codec, geometry as G  # noqa: E402
from marco.session import Session  # noqa: E402
from marco.world import layout as L  # noqa: E402
from marco.world.roommap import RoomMap  # noqa: E402

s = Session(ROOT / "server/data/sessions/fake-livingroom")
clouds = []
for meta in s.frames:
    jpeg, d, c = s.frame_bytes(meta)
    fr = G.Frame(G.mat4(meta["camera_transform"]), G.mat3(meta["intrinsics"]), tuple(meta["image_resolution"]),
                 codec.decode_depth(d), codec.decode_conf(c))
    pts, uvs = fr.point_cloud(step=4)
    rgb = np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB"))
    iu = np.minimum((uvs[:, 0] * meta["jpeg_scale"]).astype(int), rgb.shape[1] - 1)
    iv = np.minimum((uvs[:, 1] * meta["jpeg_scale"]).astype(int), rgb.shape[0] - 1)
    clouds.append((pts, rgb[iv, iu]))
floor = RoomMap().floor_y
rows = []
for k in (1, 2, 3, 5, 7):
    g = L.ColumnGrid()
    for i in range(k):
        for j in range(k):
            for pts, rgb in clouds:
                g.add(pts + [6.0 * i, 0, 6.0 * j], rgb)
    t = []
    for _ in range(3):
        t0 = time.perf_counter()
        lay = L.summarize(g, -0.049)
        t.append((time.perf_counter() - t0) * 1000)
    rows.append(dict(rooms=k * k, area_m=f"{g.hits.shape[0] / 10:.0f} x {g.hits.shape[1] / 10:.0f}", grid_mb=round(g.nbytes() / 1e6, 1),
                     walls=len(lay["walls"]), objects=len(lay["objects"]), summarize_ms=round(min(t), 1), dropped_points=g.dropped))
    print(json.dumps(rows[-1]))
(ROOT / "poc/reports/poc27_scale.json").write_text(json.dumps(rows, indent=1))
