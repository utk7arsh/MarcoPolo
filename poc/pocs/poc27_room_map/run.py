"""POC 27: does a room layout on the dashboard map cost accuracy, latency or anything else?

  python poc/pocs/poc27_room_map/run.py [--sessions ...] [--min-hits 2] [--out poc/reports/poc27_room_map.json]

For each recorded session, frames go through the server's RoomMap exactly as on_frame does it, then
marco/world/layout.py summarises the column grid into walls and furniture. Reported per session:
  - cost: RoomMap.add per frame with the grid, the grid's own share, summarize() time, grid memory, JSON size
    (that the map points and every detection output are unchanged is harm.py's job, and test_layout.py's)
  - accuracy against ground truth where there is one:
      fake-livingroom   the emulator's room: exact walls and furniture boxes (poc/emulators/arkit/scene.py)
      arkitscenes-*     ARKitScenes' annotated furniture boxes (truth.json corners)
  - a top-down picture with truth outlines: poc/reports/figures/poc27_<session>.png
"""
import argparse
import io
import json
import re
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "server"))
sys.path.insert(0, str(ROOT / "poc" / "emulators" / "arkit"))
from marco import codec, geometry as G  # noqa: E402
from marco.session import Session  # noqa: E402
from marco.world import layout as L  # noqa: E402
from marco.world.roommap import RoomMap  # noqa: E402

KINDS_OK = {                       # truth class -> kinds that count as right
    "table": {"table"}, "chair": {"chair"}, "sofa": {"sofa"}, "shelf": {"storage"}, "storage": {"storage"},
    "cabinet": {"storage", "table"}, "oven": {"storage", "table"}, "counter": {"table", "storage"},
    "bed": {"bed"},
}


def replay(path):
    s = Session(path)
    rm = RoomMap()
    add_ms, grid_ms, cams = [], [], []
    grid_add = rm.grid.add
    spent = []

    def timed(*a, **k):
        t0 = time.perf_counter()
        grid_add(*a, **k)
        spent.append(time.perf_counter() - t0)
    rm.grid.add = timed
    for meta in s.frames:
        jpeg, d, c = s.frame_bytes(meta)
        fr = G.Frame(G.mat4(meta["camera_transform"]), G.mat3(meta["intrinsics"]), tuple(meta["image_resolution"]),
                     codec.decode_depth(d), codec.decode_conf(c))
        im = np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB"))
        scale = float(meta.get("jpeg_scale", im.shape[1] / fr.W))
        n = len(spent)
        t0 = time.perf_counter()
        rm.add(fr, im, scale)
        add_ms.append((time.perf_counter() - t0) * 1000)
        grid_ms.append(sum(spent[n:]) * 1000)
        cams.append(fr.T)
    rm.grid.add = grid_add
    return s, rm, np.array(add_ms), np.array(grid_ms), np.array(cams)


# ---------------------------------------------------------------- ground truth
def truth_synthetic():
    from scene import demo_room
    room = demo_room()
    lo, hi = room.lo, room.hi
    c = [(lo[0], lo[2]), (hi[0], lo[2]), (hi[0], hi[2]), (lo[0], hi[2])]
    walls = [(c[i], c[(i + 1) % 4]) for i in range(4)]
    objs = []
    boxes = {b.name: b for b in room.furniture}
    sofa = [boxes.pop("sofa_seat"), boxes.pop("sofa_back")]
    boxes.pop("cereal_box", None)
    kind = dict(coffee_table="table", dining_table="table", shelf="shelf", entry_table="table", kitchen_counter="counter")
    for name, b in boxes.items():
        objs.append(dict(name=name, cls=kind.get(name, "table"), poly=_rect(b.lo, b.hi), height=float(b.hi[1])))
    objs.append(dict(name="sofa", cls="sofa", poly=_rect(np.minimum(*[x.lo for x in sofa]), np.maximum(*[x.hi for x in sofa])),
                     height=float(max(x.hi[1] for x in sofa))))
    return dict(floor=0.0, walls=walls, objects=objs)


def _rect(lo, hi):
    return np.array([(lo[0], lo[2]), (hi[0], lo[2]), (hi[0], hi[2]), (lo[0], hi[2])], float)


def truth_arkitscenes(session, floor):
    objs = []
    for name, t in session.truth["items"].items():
        if "corners" not in t:
            continue
        cls = re.sub(r"[_\-\s]*\d+$", "", name)
        if cls in ("tv_monitor", "tv", "monitor"):
            continue
        cn = np.asarray(t["corners"], float)
        bot = cn[np.argsort(cn[:, 1])[:4]][:, [0, 2]]
        ctr = bot.mean(0)
        bot = bot[np.argsort(np.arctan2(bot[:, 1] - ctr[1], bot[:, 0] - ctr[0]))]
        objs.append(dict(name=name, cls=cls, poly=bot, height=float(cn[:, 1].max() - floor)))
    return dict(floor=None, walls=None, objects=objs)


# ---------------------------------------------------------------- scoring
def obj_poly(o):
    yaw = np.radians(o["yaw"])
    f = np.array([np.sin(yaw), -np.cos(yaw)])               # facing (x, z)
    r = np.array([-f[1], f[0]])                             # width axis
    c = np.array([o["x"], o["z"]])
    w, d = o["width"] / 2, o["depth"] / 2
    return np.array([c - r * w - f * d, c + r * w - f * d, c + r * w + f * d, c - r * w + f * d])


def raster(poly, x0, z0, nx, nz, res=0.05):
    from matplotlib.path import Path as MPath
    xs = x0 + (np.arange(nx) + 0.5) * res
    zs = z0 + (np.arange(nz) + 0.5) * res
    X, Z = np.meshgrid(xs, zs, indexing="ij")
    return MPath(poly).contains_points(np.stack([X.ravel(), Z.ravel()], 1)).reshape(nx, nz)


def iou(p, q, res=0.05):
    both = np.vstack([p, q])
    x0, z0 = both.min(0) - res
    nx, nz = (np.ceil((both.max(0) + res - [x0, z0]) / res)).astype(int)
    a, b = raster(p, x0, z0, nx, nz, res), raster(q, x0, z0, nx, nz, res)
    return float((a & b).sum() / max((a | b).sum(), 1))


def score_objects(objects, truth):
    """Greedy one-to-one matching by footprint overlap (or a near centre for small things)."""
    preds = [dict(o, poly=obj_poly(o)) for o in objects]
    pairs = []
    for i, t in enumerate(truth):
        for j, p in enumerate(preds):
            ov = iou(t["poly"], p["poly"])
            dist = float(np.hypot(*(t["poly"].mean(0) - p["poly"].mean(0))))
            size = float(np.ptp(t["poly"], 0).max())
            if ov >= 0.1 or dist <= max(0.3, 0.35 * size):
                pairs.append((ov - 0.1 * dist, i, j, ov, dist))
    pairs.sort(reverse=True)
    ti, pj, rows = set(), set(), []
    for _, i, j, ov, dist in pairs:
        if i in ti or j in pj:
            continue
        ti.add(i)
        pj.add(j)
        t, p = truth[i], preds[j]
        rows.append(dict(truth=t["name"], cls=t["cls"], kind=p["kind"], kind_ok=p["kind"] in KINDS_OK.get(t["cls"], {t["cls"]}),
                         iou=round(ov, 2), centre_err_m=round(dist, 2)))
    for i, t in enumerate(truth):
        if i not in ti:
            rows.append(dict(truth=t["name"], cls=t["cls"], kind=None, kind_ok=False, iou=0.0, centre_err_m=None))
    extras = [dict(kind=p["kind"], x=p["x"], z=p["z"], width=p["width"], depth=p["depth"]) for j, p in enumerate(preds) if j not in pj]
    found = [r for r in rows if r["kind"] is not None]
    return dict(truth_objects=len(truth), found=len(found), kind_right=sum(r["kind_ok"] for r in rows),
                median_iou=round(float(np.median([r["iou"] for r in found])), 2) if found else None,
                median_centre_err_m=round(float(np.median([r["centre_err_m"] for r in found])), 2) if found else None,
                extra=len(extras), rows=rows, extras=extras)


def score_walls(walls, truth_walls, observed_pts, tol=0.15, step=0.05):
    """Precision: share of drawn wall length within tol of a true wall. Recall: share of the true wall length that
    the walk saw (map points within 0.3 m) and that has a drawn wall within tol."""
    def samples(segs):
        out = []
        for a, b in segs:
            a, b = np.asarray(a, float), np.asarray(b, float)
            n = max(int(np.hypot(*(b - a)) / step), 1)
            out.append(a + np.outer(np.linspace(0, 1, n + 1), b - a))
        return np.vstack(out) if out else np.zeros((0, 2))

    def dist_to(p, segs):
        best = np.full(len(p), np.inf)
        for a, b in segs:
            a, b = np.asarray(a, float), np.asarray(b, float)
            v = b - a
            t = np.clip((p - a) @ v / (v @ v), 0, 1)
            best = np.minimum(best, np.hypot(*(p - (a + t[:, None] * v)).T))
        return best
    P = samples(walls)
    T = samples(truth_walls)
    from scipy.spatial import cKDTree
    seen = cKDTree(observed_pts).query(T, distance_upper_bound=0.3)[0] < np.inf if len(observed_pts) else np.zeros(len(T), bool)
    prec = float((dist_to(P, truth_walls) <= tol).mean()) if len(P) else None
    rec = float((dist_to(T[seen], walls) <= tol).mean()) if seen.any() and walls else 0.0
    return dict(drawn_m=round(len(P) * step, 1), precision=None if prec is None else round(prec, 2),
                truth_seen_m=round(float(seen.sum()) * step, 1), recall_seen=round(rec, 2))


# ---------------------------------------------------------------- picture
def draw(path, rm, floor, lay, cams, truth=None, title=""):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Polygon
    c = np.array(rm.points(), float)
    fig, ax = plt.subplots(figsize=(7, 7))
    if len(c):
        h = c[:, 1] - floor
        k = (h > 0.15) & (h < 2.5)
        ax.scatter(c[~k, 0], c[~k, 2], s=0.3, c="#e6e6e6")
        ax.scatter(c[k, 0], c[k, 2], s=0.6, c=c[k, 3:6] / 255, alpha=0.5)
    for a, b in lay["walls"]:
        ax.plot([a[0], b[0]], [a[1], b[1]], "-", c="#555", lw=3, solid_capstyle="round")
    colors = dict(table="#c8a46e", chair="#5b8bd6", sofa="#8a5bd6", bench="#999", bed="#d65b8a", storage="#6e8c5b",
                  tree="#2e9d3f", plant="#6cc070")
    for o in lay["objects"]:
        ax.add_patch(Polygon(obj_poly(o), closed=True, fc=colors.get(o["kind"], "#aaa"), ec="k", lw=0.8, alpha=0.75))
        f = np.array([np.sin(np.radians(o["yaw"])), -np.cos(np.radians(o["yaw"]))])
        if o["kind"] in ("chair", "sofa", "bed", "storage"):
            ax.arrow(o["x"], o["z"], *(f * 0.25), head_width=0.06, color="k", lw=0.6)
        ax.text(o["x"], o["z"], o["kind"], fontsize=6, ha="center", va="center")
    if truth:
        for t in truth["objects"]:
            ax.add_patch(Polygon(t["poly"], closed=True, fill=False, ec="#d33", lw=1, ls="--"))
        for a, b in truth.get("walls") or []:
            ax.plot([a[0], b[0]], [a[1], b[1]], "--", c="#d33", lw=1)
    ax.plot(cams[:, 0, 3], cams[:, 2, 3], "-", c="#1559d6", lw=1)
    ax.set_aspect("equal")
    ax.set_title(title, fontsize=9)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", nargs="*", default=[
        "server/data/sessions/fake-livingroom", "server/data/sessions/arkitscenes-41069021",
        "server/data/sessions/rec1-normal", "server/data/sessions/rec2-find", "server/data/sessions/rec3-moved"])
    ap.add_argument("--min-hits", type=int, default=L.MIN_HITS)
    ap.add_argument("--out", default="poc/reports/poc27_room_map.json")
    ap.add_argument("--figs", default="poc/reports/figures")
    a = ap.parse_args()
    L.MIN_HITS = a.min_hits
    report = {}
    for p in a.sessions:
        name = Path(p).name
        s, rm, add_ms, grid_ms, cams = replay(ROOT / p if not Path(p).is_absolute() else p)
        floor = rm.floor_y()
        times = []
        for _ in range(5):
            t0 = time.perf_counter()
            lay = L.summarize(rm.grid, floor, min_hits=a.min_hits)
            times.append((time.perf_counter() - t0) * 1000)
        r = dict(frames=len(s.frames), voxels=len(rm.cells), floor_y=floor,
                 roommap_add_ms_p50=round(float(np.median(add_ms)), 2), grid_add_ms_p50=round(float(np.median(grid_ms)), 2),
                 grid_add_ms_max=round(float(grid_ms.max()), 2), summarize_ms_p50=round(float(np.median(times)), 1),
                 summarize_ms_max=round(float(max(times)), 1), grid_mb=round(rm.grid.nbytes() / 1e6, 2),
                 grid_cols=list(rm.grid.hits.shape[:2]) if rm.grid.hits is not None else None,
                 layout_json_bytes=len(json.dumps(lay)), walls=len(lay["walls"]),
                 objects={k: sum(o["kind"] == k for o in lay["objects"]) for k in sorted({o["kind"] for o in lay["objects"]})})
        truth = None
        if name == "fake-livingroom":
            truth = truth_synthetic()
        elif s.truth and any("corners" in t for t in s.truth["items"].values()):
            truth = truth_arkitscenes(s, floor)
        if truth:
            r["objects_vs_truth"] = score_objects(lay["objects"], truth["objects"])
            if truth.get("walls"):
                r["walls_vs_truth"] = score_walls(lay["walls"], truth["walls"], np.array(rm.points())[:, [0, 2]])
        Path(a.figs).mkdir(parents=True, exist_ok=True)
        draw(Path(a.figs) / f"poc27_{name}.png", rm, floor, lay, cams, truth, f"{name}: {r['walls']} walls, {r['objects']}")
        Path("/tmp/poc27").mkdir(exist_ok=True)
        (Path("/tmp/poc27") / f"{name}.layout.json").write_text(json.dumps(dict(lay, floor_y=floor, cams=cams[:, [0, 2], 3].round(3).tolist())))
        report[name] = r
        brief = {k: v for k, v in r.items() if k not in ("objects_vs_truth",)}
        print(name, json.dumps(brief))
        if "objects_vs_truth" in r:
            o = r["objects_vs_truth"]
            print("   objects: found %d/%d, kind right %d, median IoU %s, centre err %s, extra %d" % (
                o["found"], o["truth_objects"], o["kind_right"], o["median_iou"], o["median_centre_err_m"], o["extra"]))
            for row in o["rows"]:
                print("     ", row)
            for e in o["extras"]:
                print("      extra", e)
    Path(a.out).write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
