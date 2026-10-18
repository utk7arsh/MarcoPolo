"""POC 27: does the room layout change what Marco detects, or slow a frame down? The real brain runs each session
with the layout off (the column grid and room_layout disabled, RoomMap.add as it was) and on, alternating
off/on/off/on, and compares every output except the new room_layout messages.

  python poc/pocs/poc27_room_map/harm.py [--rounds 2] [--out poc/reports/poc27_harm.json]

Sessions and detectors:
  fake-livingroom        ground-truth detector (CPU only: shows the layout's own cost most clearly)
  rec2-find              OWLv2 + DINOv2 with the real registration photos (server/data/*.jpeg|jpg)
  arkitscenes-41069021   OWLv2 + DINOv2 registered from truth crops
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "server" / "tools"))
import run_offline as RO  # noqa: E402
from marco import brain as B, codec  # noqa: E402
from marco.session import Session  # noqa: E402
from marco.world import layout as L  # noqa: E402
from marco.world import roommap as RM  # noqa: E402

PHOTOS = {"bottle": "bottle.jpeg", "power bank": "powerbank.jpeg", "wallet": "wallet.jpg"}
SKIP_KEYS = {"t_wall", "last_seen_wall", "event_id", "at", "touch_id"}   # wall clock and random ids


def old_add(self, fr, rgb, jpeg_scale):
    """RoomMap.add before the column grid."""
    pts, uvs = fr.point_cloud(step=self.step)
    if not len(pts):
        return []
    keys = np.floor(pts / self.voxel).astype(np.int64)
    h, w = rgb.shape[:2]
    new = []
    for key, p, (u, v) in zip(map(tuple, keys), pts, uvs):
        if key in self.cells:
            continue
        iu, iv = min(int(u * jpeg_scale), w - 1), min(int(v * jpeg_scale), h - 1)
        r, g, b = (int(c) for c in rgb[iv, iu][:3])
        cell = [round(float(p[0]), 3), round(float(p[1]), 3), round(float(p[2]), 3), r, g, b]
        self.cells[key] = cell
        new.append(cell)
    return new


def norm(x, names):
    """Outputs made comparable across two brains: item ids -> names, wall-clock fields dropped, images hashed."""
    if isinstance(x, dict):
        out = {}
        for k, v in x.items():
            if k in SKIP_KEYS:
                continue
            if k == "item_id":
                v = names.get(v, v)
            elif k == "jpeg_b64":
                v = hashlib.sha1(v.encode()).hexdigest()
            out[k] = norm(v, names)
        return out
    if isinstance(x, (list, tuple)):
        return [norm(v, names) for v in x]
    if isinstance(x, float):
        return round(x, 6)
    return x


def run(path, detector, layout, owl=None):
    ses = Session(path)
    saved = (B.LAYOUT_EVERY, RM.RoomMap.add, L.ColumnGrid.add)
    if not layout:
        B.LAYOUT_EVERY = 0
        RM.RoomMap.add = old_add
    try:
        det = owl if detector == "owl" else RO.make_detector("truth", ses)
        if detector == "owl":
            det.items.clear()
        brain = B.RealBrain(det)
        if detector == "truth":
            for name in ses.truth["items"]:
                brain.register(name, RO._dummy_jpeg())
        elif Path(path).name.startswith("rec"):
            for name in ses.truth["items"]:
                brain.register(name, (ROOT / "server" / "data" / PHOTOS[name]).read_bytes())
        else:
            RO.register_from_truth(brain, ses, None)
        names = {it.item_id: it.name for it in brain.world.items.values()}
        outs, times, layouts = [], [], []
        for kind, m in ses.stream():
            if kind != "frame":                 # pose-driven world snapshots are throttled by the wall clock: skipped
                outs.append(norm([(ch, msg) for ch, msg in brain.on_phone(m) if msg.get("type") != "world"], names))
                continue
            jpeg, d, c = ses.frame_bytes(m)
            t0 = time.perf_counter()
            o = brain.on_frame(m, jpeg, codec.decode_depth(d), codec.decode_conf(c))
            times.append((time.perf_counter() - t0) * 1000)
            layouts += [msg for ch, msg in o if msg.get("type") == "room_layout"]
            outs.append(norm([(ch, msg) for ch, msg in o if msg.get("type") != "room_layout"], names))
        return outs, np.array(times), layouts
    finally:
        B.LAYOUT_EVERY, RM.RoomMap.add, L.ColumnGrid.add = saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--rounds", type=int, default=2)
    ap.add_argument("--out", default="poc/reports/poc27_harm.json")
    a = ap.parse_args()
    from marco.perception.detector import OwlDetector
    owl = OwlDetector()
    report = {}
    for path, det in (("server/data/sessions/fake-livingroom", "truth"), ("server/data/sessions/rec2-find", "owl"),
                      ("server/data/sessions/arkitscenes-41069021", "owl")):
        res = {False: [], True: []}
        for _ in range(a.rounds):
            for layout in (False, True):
                res[layout].append(run(ROOT / path, det, layout, owl))
        base = res[False][0][0]
        same = all(r[0] == base for runs in res.values() for r in runs)
        t_off = np.concatenate([r[1][2:] for r in res[False]])          # first two frames are warm-up
        t_on = np.concatenate([r[1][2:] for r in res[True]])
        n_layouts = len(res[True][0][2])
        r = dict(detector=det, frames=len(res[True][0][1]), outputs_identical=same, layouts_sent=n_layouts,
                 frame_ms_off=dict(p50=round(float(np.median(t_off)), 1), p95=round(float(np.percentile(t_off, 95)), 1),
                                   mean=round(float(t_off.mean()), 1)),
                 frame_ms_on=dict(p50=round(float(np.median(t_on)), 1), p95=round(float(np.percentile(t_on, 95)), 1),
                                  mean=round(float(t_on.mean()), 1)),
                 mean_added_ms=round(float(t_on.mean() - t_off.mean()), 1))
        report[Path(path).name] = r
        print(Path(path).name, json.dumps(r))
    Path(a.out).write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
