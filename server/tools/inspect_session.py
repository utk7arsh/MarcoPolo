"""Is the recording itself good? Check that video, depth and poses agree before judging detection:
  blur         variance of the Laplacian of each frame (low = blurred: walking too fast, or too dark)
  depth        share of LiDAR pixels with confidence, and the median depth
  consistency  the previous frame's LiDAR points, moved by the two poses into this frame, against this frame's own
               LiDAR: a few cm when poses, depth and intrinsics agree; tens of cm when one of them is wrong
  orientation  upright turns from gravity (the portrait vest mount is 1)
Writes <session>/inspect/inspect.json and inspect.jpg: frames upright with the LiDAR depth over them (the colours
must sit on the objects; if they're shifted or mirrored, the image and depth don't line up).

  python tools/inspect_session.py data/sessions/<id>
"""
import io
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from marco import codec, geometry as G  # noqa: E402
from marco.brain import TRANSPOSE  # noqa: E402
from marco.session import Session  # noqa: E402

CONSISTENCY_BAD_CM = 8.0
COVERAGE_BAD = 0.5
BLUR_RELATIVE = 0.3            # a frame below this share of the session's median sharpness counts as blurred


def blur_score(im):
    g = np.asarray(im.convert("L").resize((480, max(1, int(480 * im.height / im.width)))), float)
    lap = -4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
    return float(lap.var())


def consistency_cm(prev, fr, step=4):
    """Median |depth| disagreement (cm) of the previous frame's LiDAR points seen from this frame; None if too few."""
    pts, _ = prev.point_cloud(step=step)
    if len(pts) < 50:
        return None
    uv, z = fr.project(pts)
    ok = (z > 0.2) & (uv[:, 0] >= 0) & (uv[:, 0] < fr.W) & (uv[:, 1] >= 0) & (uv[:, 1] < fr.H)
    iu = np.clip((uv[ok, 0] * fr.sx).astype(int), 0, fr.dw - 1)
    iv = np.clip((uv[ok, 1] * fr.sy).astype(int), 0, fr.dh - 1)
    d, c = fr.depth[iv, iu], fr.conf[iv, iu]
    good = (c >= 2) & np.isfinite(d)
    if good.sum() < 50:
        return None
    return float(np.median(np.abs(d[good] - z[ok][good]))) * 100


def inspect(path, out_dir=None, picture=True):
    from PIL import Image
    ses = Session(path)
    rows, prev = [], None
    for meta in ses.frames:
        jpeg, d, c = ses.frame_bytes(meta)
        depth, conf = codec.decode_depth(d), codec.decode_conf(c)
        fr = G.Frame(G.mat4(meta["camera_transform"]), G.mat3(meta["intrinsics"]), tuple(meta["image_resolution"]), depth, conf)
        im = Image.open(io.BytesIO(jpeg)).convert("RGB")
        valid = np.isfinite(depth) & (conf >= 1)
        rows.append(dict(frame_id=meta["frame_id"], t=meta["t_device"], blur=round(blur_score(im), 1),
                         depth_coverage=round(float(valid.mean()), 3),
                         depth_median_m=round(float(np.median(depth[valid])), 2) if valid.any() else None,
                         consistency_cm=None if prev is None else _round(consistency_cm(prev, fr)),
                         upright_turns=G.upright_turns(fr.T)))
        prev = fr
    blur_med = float(np.median([r["blur"] for r in rows]))
    for r in rows:
        r["blurred"] = r["blur"] < BLUR_RELATIVE * blur_med
    cons = [r["consistency_cm"] for r in rows if r["consistency_cm"] is not None]
    span = rows[-1]["t"] - rows[0]["t"] if len(rows) > 1 else 0
    turns = [r["upright_turns"] for r in rows]
    summary = dict(frames=len(rows), seconds=round(span, 1), fps=round((len(rows) - 1) / span, 2) if span > 0 else None,
                   blurred_frames=sum(r["blurred"] for r in rows),
                   depth_coverage_median=round(float(np.median([r["depth_coverage"] for r in rows])), 3),
                   consistency_cm_median=round(float(np.median(cons)), 2) if cons else None,
                   upright_turns=max(set(turns), key=turns.count))
    problems = []
    if summary["consistency_cm_median"] is not None and summary["consistency_cm_median"] > CONSISTENCY_BAD_CM:
        problems.append(f"poses, depth and intrinsics disagree by {summary['consistency_cm_median']} cm between frames "
                        "(a wrong pose convention, row-major matrices, or intrinsics for another resolution?)")
    if summary["depth_coverage_median"] < COVERAGE_BAD:
        problems.append(f"only {summary['depth_coverage_median']:.0%} of LiDAR pixels are usable (too far, too dark, or glass?)")
    if summary["blurred_frames"] > 0.2 * len(rows):
        problems.append(f"{summary['blurred_frames']} of {len(rows)} frames are blurred: walk slower or add light")
    if len(set(turns)) > 1:
        problems.append(f"the image orientation changes during the recording ({sorted(set(turns))}): is the phone fixed in the vest?")
    report = dict(session=str(path), summary=summary, problems=problems, frames=rows)
    out = Path(out_dir) if out_dir else ses.dir / "inspect"
    out.mkdir(parents=True, exist_ok=True)
    (out / "inspect.json").write_text(json.dumps(report, indent=1))
    if picture:
        overlay_sheet(ses, rows, out / "inspect.jpg")
    return report


def _round(x):
    return None if x is None else round(x, 2)


def overlay_sheet(ses, rows, path, cols=6, width=300, max_frames=24):
    """Frames upright with the LiDAR depth (near = red, far = blue) blended over them."""
    from PIL import Image, ImageDraw, ImageFont
    font = ImageFont.load_default(size=26)
    pick = np.linspace(0, len(ses.frames) - 1, min(max_frames, len(ses.frames))).astype(int)
    tiles = []
    for i in pick:
        meta, r = ses.frames[i], rows[i]
        jpeg, d, c = ses.frame_bytes(meta)
        im = Image.open(io.BytesIO(jpeg)).convert("RGB")
        depth, conf = codec.decode_depth(d), codec.decode_conf(c)
        t = np.clip((np.nan_to_num(depth, nan=9.0) - 0.3) / 3.7, 0, 1)
        rgb = np.stack([1 - t, 1 - np.abs(2 * t - 1), t], -1) * 255
        alpha = np.where((conf >= 1) & np.isfinite(depth), 110, 0)[..., None]
        dm = Image.fromarray(np.concatenate([rgb, alpha], -1).astype(np.uint8), "RGBA").resize(im.size, Image.NEAREST)
        im = Image.alpha_composite(im.convert("RGBA"), dm).convert("RGB")
        k = r["upright_turns"]
        up = im.transpose(TRANSPOSE[k]) if k else im
        dr = ImageDraw.Draw(up)
        dr.text((6, 6), f"frame {meta['frame_id']}  blur {r['blur']:.0f}{' BLURRED' if r['blurred'] else ''}  "
                        f"consistency {r['consistency_cm'] if r['consistency_cm'] is not None else '-'} cm", fill=(255, 255, 0), font=font)
        tiles.append(up.resize((width, int(up.height * width / up.width))))
    h = max(t.height for t in tiles)
    sheet = Image.new("RGB", (cols * width, ((len(tiles) + cols - 1) // cols) * h), (20, 20, 20))
    for i, t in enumerate(tiles):
        sheet.paste(t, ((i % cols) * width, (i // cols) * h))
    sheet.save(path, quality=85)


if __name__ == "__main__":
    rep = inspect(sys.argv[1])
    print(json.dumps(rep["summary"], indent=1))
    for p in rep["problems"]:
        print("PROBLEM:", p)
    print("OK" if not rep["problems"] else f"{len(rep['problems'])} problem(s)")
