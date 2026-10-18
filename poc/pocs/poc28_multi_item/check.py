"""POC 28: with several registered items, does every frame check every item, and what stops items 2, 3, ... being
found? The real OwlDetector runs on recorded sessions three ways:
  alone     each item registered on its own (what it would score with no other items)
  together  all items registered, in registration order
  reversed  all items registered, in reverse order
Per item and frame it records the gates (photo+name logit, DINOv2 similarity, margin over the other items) and
where the box is. If an item passes alone but fails together, the other registrations are what stop it.

  python poc/pocs/poc28_multi_item/check.py [--sessions ...]
"""
import argparse
import io
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "server"))
from marco import codec, geometry as G  # noqa: E402
from marco.brain import TRANSPOSE  # noqa: E402
from marco.perception.detector import TH, OwlDetector  # noqa: E402
from marco.session import Session  # noqa: E402

PHOTOS = {"bottle": "bottle.jpeg", "power bank": "powerbank.jpeg", "wallet": "wallet.jpg"}


def load_photo(path):
    """A registration photo as the server sees it (brain.register: EXIF-upright, at most 2048 px)."""
    from PIL import ImageOps
    from marco.brain import MAX_PHOTO_PX
    im = ImageOps.exif_transpose(Image.open(path)).convert("RGB")
    im.thumbnail((MAX_PHOTO_PX, MAX_PHOTO_PX))
    return im


def upright(ses, meta):
    jpeg, d, c = ses.frame_bytes(meta)
    T = G.mat4(meta["camera_transform"])
    k = G.upright_turns(T)
    im = Image.open(io.BytesIO(jpeg)).convert("RGB")
    fr = G.Frame(T, G.mat3(meta["intrinsics"]), tuple(meta["image_resolution"]), codec.decode_depth(d), codec.decode_conf(c))
    return (im.transpose(TRANSPOSE[k]) if k else im), fr, k, float(meta.get("jpeg_scale", im.width / fr.W)), im.size


def in_box(det, ses_truth, name, fr, k, scale, jsize):
    """Does the detection box contain the item's true position (projected)?"""
    t = ses_truth.get(name)
    if t is None:
        return None
    uv, z = fr.project(np.asarray(t["position"], float)[None])
    if not (0.15 < float(z[0]) < 6):
        return None
    sb = G.detector_box_to_sensor(det["box"], k, jsize[0], jsize[1], scale)
    u, v = uv[0]
    return bool(sb[0] - 20 <= u <= sb[2] + 20 and sb[1] - 20 <= v <= sb[3] + 20)


def run(owl, ses, names, photos):
    owl.items.clear()
    for n in names:
        res = owl.register(n, n, photos[n])
        if res["quality"] != "ok":
            print(f"   registration of {n!r} refused: {res['reason']}")
    rows = []
    for meta in ses.frames:
        im, fr, k, scale, jsize = upright(ses, meta)
        for d in owl.detect(im):
            rows.append(dict(frame=meta["frame_id"], name=d["name"], present=d["present"], photo_name=round(d["photo_name"], 3),
                             dino=round(d["dino"], 3), vs_others=None if d["vs_others"] is None else round(d["vs_others"], 3),
                             on_item=in_box(d, ses.truth["items"], d["name"], fr, k, scale, jsize), box=d["box"]))
    return rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sessions", nargs="*", default=["server/data/sessions/rec1-normal", "server/data/sessions/rec2-find",
                                                       "server/data/sessions/rec3-moved"])
    ap.add_argument("--out", default="poc/reports/poc28_multi_item.json")
    a = ap.parse_args()
    owl = OwlDetector()
    photos = {n: load_photo(ROOT / "server" / "data" / f) for n, f in PHOTOS.items()}
    report = {}
    for p in a.sessions:
        ses = Session(ROOT / p)
        names = [n for n in ses.truth["items"] if n in photos]
        res = dict(alone=[r for n in names for r in run(owl, ses, [n], photos)], together=run(owl, ses, names, photos),
                   reversed=run(owl, ses, names[::-1], photos))
        print(Path(p).name, "items:", names)
        summary = {}
        for n in names:
            s = {}
            for mode, rows in res.items():
                mine = [r for r in rows if r["name"] == n]
                s[mode] = dict(present=sum(r["present"] for r in mine), present_on_item=sum(r["present"] and bool(r["on_item"]) for r in mine),
                               box_on_item=sum(bool(r["on_item"]) for r in mine), frames=len(mine),
                               failed_only_vs_others=sum((not r["present"]) and r["photo_name"] >= TH["photo_name"] and r["dino"] >= TH["dino"]
                                                         for r in mine))
            same = all(a_["photo_name"] == b_["photo_name"] and a_["box"] == b_["box"]
                       for a_, b_ in zip([r for r in res["alone"] if r["name"] == n], [r for r in res["together"] if r["name"] == n]))
            s["scores_same_alone_vs_together"] = same
            summary[n] = s
            print(f"  {n:11s}", json.dumps(s))
        report[Path(p).name] = dict(summary=summary, rows=res)
    Path(a.out).write_text(json.dumps(report, indent=1))


if __name__ == "__main__":
    main()
