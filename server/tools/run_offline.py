"""Run the real brain on a recorded session, without any network, and see how it does.

  python tools/run_offline.py data/sessions/fake-livingroom --detector truth
  python tools/run_offline.py data/sessions/arkitscenes-41069021 --detector owl --register-from-truth

Writes <session>/offline/: report.json (events, touches, answers, final positions vs truth), frames.jpg (contact
sheet of upright frames with boxes) and map.png (top-down room map, items, truth, trajectory).
"""
import argparse
import base64
import io
import json
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from marco import codec, geometry as G  # noqa: E402
from marco.brain import RealBrain  # noqa: E402
from marco.session import Session  # noqa: E402


def make_detector(kind, session):
    if kind == "truth":
        from marco.perception.detector import TruthDetector
        if not session.truth:
            raise SystemExit("--detector truth needs truth.json in the session")
        return TruthDetector(session.truth["items"])
    from marco.perception.detector import OwlDetector
    return OwlDetector()


def timing_summary(seconds, budget_s=1.0):
    """Per-frame processing times against the 1 frame/s budget (docs/INTERFACES.md §3.1)."""
    a = np.asarray(seconds, float)
    if a.size == 0:
        return dict(frames=0)
    return dict(frames=int(a.size), mean_s=round(float(a.mean()), 3), p50_s=round(float(np.percentile(a, 50)), 3),
                p95_s=round(float(np.percentile(a, 95)), 3), max_s=round(float(a.max()), 3),
                within_budget=bool(np.percentile(a, 95) < budget_s))


def cube_corners(t):
    """The 8 corners of a truth item without a 3D box: a cube of its size standing on its footprint."""
    p, s = np.asarray(t["position"], float), float(t.get("size", 0.1))
    return np.array([[p[0] + dx * s / 2, p[1] + dy * s, p[2] + dz * s / 2] for dx in (-1, 1) for dy in (0, 1) for dz in (-1, 1)])


def truth_crops(session, names=None, min_px=80):
    """For each truth item, a crop from the frame where it is largest in view (stands in for the user's one
    registration photo). Returns {name: upright PIL crop}."""
    from PIL import Image
    best = {}
    for meta in session.frames:
        jpeg, d, c = session.frame_bytes(meta)
        fr = G.Frame(G.mat4(meta["camera_transform"]), G.mat3(meta["intrinsics"]), tuple(meta["image_resolution"]),
                     codec.decode_depth(d), codec.decode_conf(c))
        for name, t in session.truth["items"].items():
            if names and name not in names:
                continue
            corners = np.array(t["corners"]) if "corners" in t else cube_corners(t)
            uv, z = fr.project(corners)
            if (z <= 0.2).any():
                continue
            u0, v0 = uv.min(0)
            u1, v1 = uv.max(0)
            cu0, cv0, cu1, cv1 = max(u0, 0), max(v0, 0), min(u1, fr.W), min(v1, fr.H)
            if cu1 - cu0 < min_px or cv1 - cv0 < min_px:
                continue
            inside = (cu1 - cu0) * (cv1 - cv0) / ((u1 - u0) * (v1 - v0))
            score = inside * (cu1 - cu0) * (cv1 - cv0)
            if inside > 0.8 and score > best.get(name, (0,))[0]:
                best[name] = (score, meta, [cu0, cv0, cu1, cv1])
    out = {}
    for name, (_, meta, box) in best.items():
        jpeg, _, _ = session.frame_bytes(meta)
        im = Image.open(io.BytesIO(jpeg)).convert("RGB")
        s = float(meta.get("jpeg_scale", 0.5))
        k = G.upright_turns(G.mat4(meta["camera_transform"]))
        jw, jh = im.size
        up = im.transpose([None, Image.Transpose.ROTATE_270, Image.Transpose.ROTATE_180, Image.Transpose.ROTATE_90][k]) if k else im
        b = G.rotate_box([v * s for v in box], k, jw, jh)
        out[name] = up.crop(tuple(int(v) for v in b))
    return out


def register_from_truth(brain, session, names=None):
    out = {}
    for name, crop in truth_crops(session, names).items():
        buf = io.BytesIO()
        crop.save(buf, "JPEG", quality=90)
        res, _ = brain.register(name.replace("_", " "), buf.getvalue())
        out[name] = res
    return out


def run_session(path, detector="truth", register=None, from_truth=False, out_dir=None, pictures=True):
    ses = Session(path)
    brain = RealBrain(make_detector(detector, ses))
    regs = {}
    if from_truth:
        regs = register_from_truth(brain, ses, register)
    elif register:
        for name, photo in register.items():
            regs[name] = brain.register(name, Path(photo).read_bytes())[0]
    elif ses.truth and detector == "truth":
        for name in ses.truth["items"]:
            regs[name] = brain.register(name, _dummy_jpeg())[0]
    phone_out, dash_frames, times = [], [], []
    for kind, m in ses.stream():
        if kind == "frame":
            jpeg, d, c = ses.frame_bytes(m)
            t0 = time.perf_counter()
            outs = brain.on_frame(m, jpeg, codec.decode_depth(d), codec.decode_conf(c))
            times.append(time.perf_counter() - t0)
        else:
            try:
                outs = brain.on_phone(m)
            except ValueError as e:
                outs = [("phone", dict(type="error", detail=str(e)))]
        for ch, msg in outs:
            if ch == "phone":
                phone_out.append({**msg, "at_t": m.get("t_device")})
            elif msg.get("type") == "frame":
                dash_frames.append(msg)
    report = dict(session=str(path), detector=detector, registrations=regs,
                  events=[e for e in phone_out if e.get("type") == "event"],
                  touches=[e for e in phone_out if e.get("type") == "touch"],
                  answers=[e for e in phone_out if e.get("type") == "answer"],
                  errors=[e for e in phone_out if e.get("type") == "error"][:20],
                  items=brain.items_public(), timing=timing_summary(times[2:] if len(times) > 4 else times))
    if ses.truth:
        comp = {}
        for it in brain.items_public():
            t = ses.truth["items"].get(it["name"]) or ses.truth["items"].get(it["name"].replace(" ", "_"))
            if t and it["position"]:
                d = np.array(it["position"]) - np.array(t["position"])
                comp[it["name"]] = dict(horizontal_err_cm=round(100 * float(np.hypot(d[0], d[2])), 1), height_err_cm=round(100 * float(d[1]), 1),
                                        state=it["state"])
        report["vs_truth"] = comp
        report["truth_touches"] = ses.truth.get("touches", [])
    out = Path(out_dir or Path(path) / "offline")
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=1))
    if pictures:
        _contact_sheet(dash_frames, out / "frames.jpg")
        _map_plot(brain, ses, out / "map.png")
    return report


def _dummy_jpeg():
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (128, 128), (128, 128, 128)).save(buf, "JPEG")
    return buf.getvalue()


def _contact_sheet(frames, path, n=12):
    from PIL import Image, ImageDraw
    if not frames:
        return
    pick = [frames[int(i)] for i in np.linspace(0, len(frames) - 1, min(n, len(frames)))]
    tiles = []
    for f in pick:
        im = Image.open(io.BytesIO(base64.b64decode(f["jpeg_b64"]))).convert("RGB")
        dr = ImageDraw.Draw(im)
        for b in f["boxes"]:
            col = (40, 220, 90) if b["present"] else (230, 60, 60)
            dr.rectangle(b["box"], outline=col, width=4)
            dr.text((b["box"][0] + 4, b["box"][1] + 4), f"{b['name']} {b.get('score') or ''}", fill=col)
        dr.text((8, 8), f"frame {f['frame_id']}", fill=(255, 255, 0))
        im.thumbnail((360, 360))
        tiles.append(im)
    cols = 4
    w, h = max(t.width for t in tiles), max(t.height for t in tiles)
    sheet = Image.new("RGB", (cols * w, ((len(tiles) + cols - 1) // cols) * h), "white")
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * w, (i // cols) * h))
    sheet.save(path, quality=85)


def _map_plot(brain, ses, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    pts = np.array(brain.roommap.points()) if brain.roommap.points() else np.zeros((0, 6))
    fig, ax = plt.subplots(figsize=(8, 8), facecolor="#fcfcfb")
    if len(pts):
        ax.scatter(pts[:, 0], pts[:, 2], s=2, c=pts[:, 3:6] / 255.0, alpha=0.6, linewidths=0)
    tr = np.array([[p[0], p[1]] for p in brain.world.trajectory]) if brain.world.trajectory else None
    if tr is not None and len(tr):
        ax.plot(tr[:, 0], tr[:, 1], color="#52514e", lw=1, alpha=0.7, label="you (trajectory)")
    for it in brain.items_public():
        if it["position"]:
            ax.scatter(it["position"][0], it["position"][2], s=90, color="#2a78d6", edgecolor="white", zorder=5)
            ax.annotate(it["name"], (it["position"][0], it["position"][2]), xytext=(6, 6), textcoords="offset points", fontsize=9)
    if ses.truth:
        for name, t in ses.truth["items"].items():
            ax.scatter(t["position"][0], t["position"][2], s=70, marker="x", color="#eb6834", zorder=4)
    ax.scatter([], [], s=90, color="#2a78d6", label="Marco's memory")
    if ses.truth:
        ax.scatter([], [], s=70, marker="x", color="#eb6834", label="ground truth")
    ax.set_aspect("equal")
    ax.invert_yaxis()
    ax.set_xlabel("x (m)")
    ax.set_ylabel("z (m), forward is up")
    ax.legend(loc="upper right", frameon=False)
    ax.set_title("Room map (LiDAR voxels), items and trajectory, top-down", loc="left")
    fig.savefig(path, dpi=130, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--detector", choices=["truth", "owl"], default="truth")
    ap.add_argument("--register", nargs="*", default=[], help="name=photo.jpg (one registration photo per item)")
    ap.add_argument("--register-from-truth", action="store_true", help="crop each truth item from the session itself")
    ap.add_argument("--only", nargs="*", default=None, help="limit --register-from-truth to these truth names")
    ap.add_argument("--no-pictures", action="store_true")
    a = ap.parse_args()
    reg = dict(r.split("=", 1) for r in a.register) if a.register else (a.only or None)
    rep = run_session(a.session, a.detector, reg, a.register_from_truth, pictures=not a.no_pictures)
    print(json.dumps({k: rep[k] for k in ("registrations", "vs_truth", "truth_touches") if k in rep}, indent=1))
    print("events:", [(e["kind"], e["name"]) for e in rep["events"]][:30])
    print("touches:", [(t.get("name"), t.get("at_t")) for t in rep["touches"]])
    print("answers:", rep["answers"])
    if rep["errors"]:
        print("errors:", rep["errors"][:5])
