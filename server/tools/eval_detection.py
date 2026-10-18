"""Does detection work on a real recording? Runs the real pipeline over a session with ground truth (truth.json, e.g.
from label_truth.py) and scores every registered item, frame by frame:
  visible      its truth point projects well inside the frame, within 4 m, and nothing nearer hides it
  out of view  behind the camera or outside the image
  (don't care: at the image edge, beyond 4 m, or behind something nearer: neither a hit nor a false alarm counts)
  hit          visible, and the detector says "present" with a box that contains the point
  miss         visible but not hit
  false alarm  "present" while out of view, or with the box somewhere else
and per item: passes caught (a run of frames with the item in view, caught at least once), the 3D error of each hit
(footprint placement vs truth), the final placement, time per frame, and a sweep of the presence thresholds.

  python tools/eval_detection.py data/sessions/<id> --register keys=photos/keys.jpg mug=photos/mug.jpg
  python tools/eval_detection.py data/sessions/<id> --register-from-truth --only oven table
Writes <session>/eval/report.json and sheet.jpg (green = hit, red = miss or false alarm).
"""
import argparse
import io
import itertools
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from marco import codec, geometry as G  # noqa: E402
from marco.brain import TRANSPOSE, RealBrain, crop_around  # noqa: E402
from marco.session import Session  # noqa: E402
from run_offline import timing_summary, truth_crops  # noqa: E402


class Tap:
    """Wraps a detector and keeps what it returned for the latest frame (decisions, boxes and raw scores)."""

    def __init__(self, det):
        self.det, self.last = det, []

    def detect(self, *a, **kw):
        self.last = self.det.detect(*a, **kw)
        return self.last

    def __getattr__(self, name):
        return getattr(self.det, name)


def view_state(fr, pos, size, margin=0.05, zmin=0.15, zmax=4.0, occlusion_m=0.15):
    """Should the item be seen in this frame? ("visible" | "out_of_view" | "dont_care", (u, v) of its centre, z)."""
    c = np.asarray(pos, float) + np.array([0.0, size / 2, 0.0])
    uv, z = fr.project(c[None])
    (u, v), z = uv[0], float(z[0])
    if not (z > zmin and 0 <= u < fr.W and 0 <= v < fr.H):
        return "out_of_view", (float(u), float(v)), z
    if z >= zmax or not (margin * fr.W < u < (1 - margin) * fr.W and margin * fr.H < v < (1 - margin) * fr.H):
        return "dont_care", (float(u), float(v)), z
    seen = fr.depth_at(u, v, r=1, min_conf=1)
    if seen is not None and seen < z - (occlusion_m + size / 2):   # the item's own front face is up to size/2 nearer
        return "dont_care", (float(u), float(v)), z          # something nearer is in the way, maybe only partly
    return "visible", (float(u), float(v)), z


def box_contains(sbox, uv, grow=0.25):
    u0, v0, u1, v1 = sbox
    w, h = u1 - u0, v1 - v0
    return u0 - grow * w <= uv[0] <= u1 + grow * w and v0 - grow * h <= uv[1] <= v1 + grow * h


def physical_size(sbox, fr):
    """The detection's longer side in metres, from its box and the LiDAR depth inside it (None without depth)."""
    u0, v0, u1, v1 = sbox
    z = fr.depth_at((u0 + u1) / 2, (v0 + v1) / 2, r=2, min_conf=1)
    return None if z is None else round(float(max(u1 - u0, v1 - v0) * z / fr.K[0, 0]), 3)


def runs(indices, gap=1):
    """Consecutive frame indices, allowing `gap` missing frames, as lists: the passes past an item."""
    out = []
    for i in sorted(indices):
        if out and i - out[-1][-1] <= gap + 1:
            out[-1].append(i)
        else:
            out.append([i])
    return out


def score(rows, minutes, present=lambda r: r["present"]):
    """Per-item and overall frame recall, passes caught and false alarms per minute."""
    per = {}
    for item in sorted({r["item"] for r in rows}):
        rs = [r for r in rows if r["item"] == item]
        vis = [r for r in rs if r["state"] == "visible"]
        hit = {r["frame_index"] for r in vis if present(r) and r["box_hit"]}
        fa = sum(1 for r in rs if present(r) and (r["state"] == "out_of_view" or (r["state"] == "visible" and not r["box_hit"])))
        passes = runs([r["frame_index"] for r in vis])
        per[item] = dict(visible_frames=len(vis), hits=len(hit), misses=len(vis) - len(hit), false_alarms=fa,
                         frame_recall=round(len(hit) / len(vis), 3) if vis else None,
                         passes=len(passes), passes_caught=sum(1 for p in passes if hit & set(p)),
                         false_alarms_per_min=round(fa / minutes, 2) if minutes > 0 else None)
    vis = sum(p["visible_frames"] for p in per.values())
    total = dict(visible_frames=vis, hits=sum(p["hits"] for p in per.values()),
                 false_alarms=sum(p["false_alarms"] for p in per.values()),
                 passes=sum(p["passes"] for p in per.values()), passes_caught=sum(p["passes_caught"] for p in per.values()))
    total["frame_recall"] = round(total["hits"] / vis, 3) if vis else None
    total["pass_recall"] = round(total["passes_caught"] / total["passes"], 3) if total["passes"] else None
    total["false_alarms_per_min"] = round(total["false_alarms"] / minutes, 2) if minutes > 0 else None
    return per, total


SWEEP = dict(photo_name=[-6, -5, -4, -3, -2.426, -2, -1, 0, 1, 2], dino=[0.0, 0.1, 0.15, 0.2, 0.25, 0.3, 0.38, 0.45, 0.55],
             vs_others=[-99, 0.0, 0.078, 0.5, 1.0])


def sweep(rows, minutes, grid=SWEEP):
    """The presence check at other thresholds, from the raw scores (no re-run of the model)."""
    if not rows or not any(r.get("photo_name") is not None for r in rows):
        return []
    out = []
    for a, b, c in itertools.product(grid["photo_name"], grid["dino"], grid["vs_others"]):
        def present(r, a=a, b=b, c=c):
            return (r.get("photo_name") is not None and r.get("in_range", True) and r["photo_name"] >= a and r["dino"] >= b
                    and (r.get("vs_others") is None or r["vs_others"] >= c))
        _, t = score(rows, minutes, present)
        out.append(dict(th=dict(photo_name=a, dino=b, vs_others=c), frame_recall=t["frame_recall"],
                        pass_recall=t["pass_recall"], false_alarms_per_min=t["false_alarms_per_min"]))
    return out


def operating_points(points, max_fa_per_min=(0.5, 1.0, 2.0)):
    """The best pass recall (then frame recall) within each false-alarm budget."""
    best = {}
    for lim in max_fa_per_min:
        ok = [p for p in points if p["false_alarms_per_min"] is not None and p["false_alarms_per_min"] <= lim]
        if ok:
            best[f"<= {lim} false alarms/min"] = max(ok, key=lambda p: (p["pass_recall"] or 0, p["frame_recall"] or 0))
    return best


def frame_crop(spec, half_m=0.2):
    """A registration crop from a vest-camera frame, as the phone would register an item: "SESSION:FRAME_ID:u,v"
    (u, v in sensor pixels on the item). Crops about 40 cm around it, sized by LiDAR depth."""
    from PIL import Image
    sess, fid, uv = spec.rsplit(":", 2)
    u, v = (float(x) for x in uv.split(","))
    ses = Session(sess)
    meta = next(m for m in ses.frames if m["frame_id"] == int(fid))
    jpeg, d, c = ses.frame_bytes(meta)
    fr = G.Frame(G.mat4(meta["camera_transform"]), G.mat3(meta["intrinsics"]), tuple(meta["image_resolution"]),
                 codec.decode_depth(d), codec.decode_conf(c))
    k = G.upright_turns(fr.T)
    im = Image.open(io.BytesIO(jpeg)).convert("RGB")
    up = im.transpose(TRANSPOSE[k]) if k else im
    z = fr.depth_at(u, v, r=2, min_conf=1) or 1.0
    return crop_around(up, fr, k, float(meta.get("jpeg_scale", 0.5)), (u, v), z, half_m)


def evaluate(path, register=None, from_truth=False, only=None, detector="owl", gate=True, out_dir=None, sheet=True,
             register_frames=None):
    ses = Session(path)
    if not ses.truth or not ses.truth.get("items"):
        raise SystemExit("no truth.json items: label the recording first (tools/label_truth.py)")
    truth = ses.truth["items"]
    if detector == "truth":
        from marco.perception.detector import TruthDetector
        det = Tap(TruthDetector(truth))
    else:
        from marco.perception.detector import OwlDetector
        det = Tap(OwlDetector())
    brain = RealBrain(det)
    regs = {}
    photos = {}
    if from_truth:
        photos = {n: c for n, c in truth_crops(ses, only).items()}
    for name, spec in (register_frames or {}).items():
        photos[name] = frame_crop(spec)
    for name, p in (register or {}).items():
        from PIL import Image, ImageOps
        im = ImageOps.exif_transpose(Image.open(p)).convert("RGB")         # as the server does with an upload
        im.thumbnail((2048, 2048))
        photos[name] = im
    for name, im in photos.items():
        if name not in truth:
            print(f"warning: {name} has no ground truth: it can't be scored")
        if gate:
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=90)
            regs[name] = brain.register(name, buf.getvalue())[0]
        else:
            it = brain.world.add_item(name)
            regs[name] = dict(item_id=it.item_id, **det.register(it.item_id, name, im, gate=False))
    by_id = {r["item_id"]: n for n, r in regs.items() if r.get("item_id")}
    if not by_id:
        raise SystemExit(f"nothing registered: {regs}")

    rows, times, sheet_frames = [], [], []
    for fi, meta in enumerate(ses.frames):
        jpeg, d, c = ses.frame_bytes(meta)
        depth, conf = codec.decode_depth(d), codec.decode_conf(c)
        t0 = time.perf_counter()
        brain.on_frame(meta, jpeg, depth, conf)
        times.append(time.perf_counter() - t0)
        fr = G.Frame(G.mat4(meta["camera_transform"]), G.mat3(meta["intrinsics"]), tuple(meta["image_resolution"]), depth, conf)
        up, _, _, k, scale = brain.last_frame
        jw, jh = (up.height, up.width) if k % 2 else (up.width, up.height)     # the JPEG as sent, before turning
        dets = {d_["item_id"]: d_ for d_ in det.last}
        marks = []
        for iid, name in by_id.items():
            if name not in truth:
                continue
            t = truth[name]
            state, uv, z = view_state(fr, t["position"], t.get("size", 0.1))
            d_ = dets.get(iid)
            sbox = G.detector_box_to_sensor(d_["box"], k, jw, jh, scale) if d_ else None
            pos = brain.place(sbox, fr) if sbox else None              # the server's own rule: placeable, within range
            row = dict(item=name, frame_index=fi, frame_id=meta["frame_id"], state=state, distance_m=round(z, 2),
                       present=bool(d_ and d_["present"]) and pos is not None, present_raw=bool(d_ and d_["present"]),
                       in_range=pos is not None, det_size_m=physical_size(sbox, fr) if sbox else None,
                       box_hit=bool(sbox and state == "visible" and box_contains(sbox, uv)),
                       photo_name=d_.get("photo_name") if d_ else None, dino=d_.get("dino") if d_ else None,
                       vs_others=d_.get("vs_others") if d_ else None)
            if row["present"] and row["box_hit"]:
                e = np.asarray(pos) - np.asarray(t["position"])
                row.update(err_h_m=round(float(np.hypot(e[0], e[2])), 3), err_v_m=round(float(e[1]), 3))
            rows.append(row)
            marks.append((name, state, uv, row, d_["box"] if d_ else None))
        sheet_frames.append((meta, marks))

    minutes = max((ses.frames[-1]["t_device"] - ses.frames[0]["t_device"]) / 60.0, 1e-6) if len(ses.frames) > 1 else 1e-6
    per, total = score(rows, minutes)
    for name, p in per.items():
        errs = [r["err_h_m"] for r in rows if r["item"] == name and "err_h_m" in r]
        p["hit_error_h_m_median"] = round(float(np.median(errs)), 3) if errs else None
        final = next((it for it in brain.items_public() if it["name"] == name), None)
        if final and final.get("position") is not None:
            e = np.asarray(final["position"]) - np.asarray(truth[name]["position"])
            p["final_error_h_m"] = round(float(np.hypot(e[0], e[2])), 3)
        p["state"] = final.get("state") if final else None
    points = sweep(rows, minutes)
    current = dict(photo_name=float(os.environ.get("TH_PHOTO_NAME", "-2.426")), dino=float(os.environ.get("TH_DINO", "0.38")),
                   vs_others=float(os.environ.get("TH_VS_OTHERS", "0.078")))
    report = dict(session=str(path), detector=detector, device=str(getattr(det.det, "dev", "n/a")), registrations=regs,
                  minutes=round(minutes, 2), frames=len(ses.frames), thresholds=current, total=total, items=per,
                  timing=timing_summary(times[2:] if len(times) > 4 else times),
                  operating_points=operating_points(points), rows=rows)
    out = Path(out_dir) if out_dir else ses.dir / "eval"
    out.mkdir(parents=True, exist_ok=True)
    (out / "report.json").write_text(json.dumps(report, indent=1))
    if sheet:
        draw_sheet(ses, sheet_frames, out / "sheet.jpg")
    return report


def draw_sheet(ses, frames, path, cols=6, width=300, max_frames=48):
    """Each frame upright: truth points (green = hit, red = missed) and boxes (green = hit, red = false alarm)."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.load_default(size=26)
    keep = [f for f in frames if any(m[1] == "visible" or m[3]["present"] for m in f[1])] or frames
    if len(keep) > max_frames:
        keep = [keep[i] for i in np.linspace(0, len(keep) - 1, max_frames).astype(int)]
    tiles = []
    for meta, marks in keep:
        jpeg, _, _ = ses.frame_bytes(meta)
        im = Image.open(io.BytesIO(jpeg)).convert("RGB")
        k = G.upright_turns(G.mat4(meta["camera_transform"]))
        jw, jh = im.size
        s = float(meta.get("jpeg_scale", 0.5))
        up = im.transpose(TRANSPOSE[k]) if k else im
        dr = ImageDraw.Draw(up)
        for name, state, uv, row, box in marks:
            hit = row["present"] and row["box_hit"]
            if row["present"] and box:
                col = (0, 220, 0) if hit else (160, 160, 160) if state == "dont_care" else (230, 0, 0)
                dr.rectangle(box, outline=col, width=4)
                dr.text((box[0] + 4, box[1] + 4), name, fill=col, font=font)
            if state == "visible":
                x, y = G.rotate_point(uv[0] * s, uv[1] * s, k, jw, jh)
                col = (0, 220, 0) if hit else (230, 0, 0)
                dr.ellipse([x - 10, y - 10, x + 10, y + 10], outline=col, width=4)
                if not hit:
                    dr.text((x + 12, y - 6), f"missed {name}", fill=col, font=font)
        dr.text((6, 6), f"frame {meta['frame_id']}", fill=(255, 255, 0), font=font)
        r = width / up.width
        tiles.append(up.resize((width, int(up.height * r))))
    h = max(t.height for t in tiles)
    rows_n = (len(tiles) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * width, rows_n * h), (20, 20, 20))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * width, (i // cols) * h))
    sheet.save(path, quality=85)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--register", nargs="*", default=[], help="name=photo.jpg (one registration photo per item)")
    ap.add_argument("--register-from-truth", action="store_true", help="registration crops from the recording itself")
    ap.add_argument("--register-frame", nargs="*", default=[],
                    help="name=SESSION:FRAME_ID:u,v - register from a vest-camera frame (use another recording's frame)")
    ap.add_argument("--only", nargs="*", default=None, help="limit --register-from-truth to these names")
    ap.add_argument("--detector", choices=["owl", "truth"], default="owl")
    ap.add_argument("--no-gate", action="store_true", help="register even if the retake check would reject the photo")
    ap.add_argument("--no-sheet", action="store_true")
    a = ap.parse_args()
    rep = evaluate(a.session, dict(r.split("=", 1) for r in a.register), a.register_from_truth, a.only, a.detector,
                   gate=not a.no_gate, sheet=not a.no_sheet, register_frames=dict(r.split("=", 1) for r in a.register_frame))
    print(json.dumps({k: rep[k] for k in ("total", "items", "timing", "operating_points")}, indent=1))
    print(f"wrote {Path(a.session) / 'eval'}")
