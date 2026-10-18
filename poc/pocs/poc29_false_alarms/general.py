"""POC 29: general false alarms on held-out footage, nothing tuned to the live frames.

The CURRENT server detector (OwlDetector: OWLv2-base + DINOv2-small, deployed thresholds) on two sets it was never
tuned on:
  ORBIT  18 items of 5 blind users, 224 px handheld frames (POC 22/25). Each user registers only their own items, as
         at home, so "looks more like this item than my other items" compares within a user. Every frame is scored
         against every user's items: the item's own frames are positives (the box must be on the human-drawn box,
         IoU >= 0.3); frames of OTHER users are negatives (the item can't be there): look-alikes (same category, e.g.
         someone else's keys) and other objects. Frames of the same user's other items are left out (may hold it).
  venue  our 3 chest-camera clips (rec1-3) with the real photos: positives are boxes on the item.
Two input changes from the audit are scored side by side, with no threshold fitted on either set:
  dino   the stock DINOv2 preprocessing (shortest edge 256, then the middle 224: a tall bottle loses its ends) against
         the crop padded to a square first (the whole object is compared)
  box    the best image-query patch (now) against the best image + name patch
vs_all is POC 26's margin: against every registered item, every user's (it registered all 18 in one server).
Plus the colour check (on in main, not deployed) and "two frames agree" (both of two frames of one video pass), the
memory's second-sighting rule.

  poc/.venv/bin/python -I poc/pocs/poc29_false_alarms/general.py        # writes poc/reports/poc29_rows.json
"""
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "server"))
from marco.perception import detector as D  # noqa: E402
from marco.session import Session  # noqa: E402


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


B = load("poc22_bench", ROOT / "poc/pocs/poc22_registered_find/bench.py")
C = load("poc28_check", ROOT / "poc/pocs/poc28_multi_item/check.py")
MEAN = (124, 116, 104)            # ImageNet mean: zero after DINOv2's normalisation


def square(im):
    w, h = im.size
    s = max(w, h)
    out = Image.new("RGB", (s, s), MEAN)
    out.paste(im, ((s - w) // 2, (s - h) // 2))
    return out


def iou(a, b):
    return B.iou(a, b)


class Probe:
    """The deployed detect() maths, opened up so both variants come out of one OWLv2 pass."""

    def __init__(self):
        self.d = D.OwlDetector()
        self.torch = self.d.torch
        self.regs = []                                 # dict(key, name, group, q_img, q_txt, dc, ds, look)

    def register(self, key, name, group, photos):
        for i, im in enumerate(photos):
            res = self.d.register(key, name, im)
            if res["quality"] == "ok":
                it = self.d.items[key]
                crop = D.registration_crop(im, res["box"])
                self.regs.append(dict(key=key, name=name, group=group, q_img=it["q_img"], q_txt=it["q_txt"],
                                      dc=it["dino"].reshape(-1, it["dino"].shape[-1]), ds=self._dino_ref(square(crop)),
                                      look=it["look"], tries=i + 1))
                return True
        return False

    def _dino_ref(self, im):
        with self.torch.no_grad():
            return self.d._dino([im])

    def frame(self, im):
        d, T = self.d, self.torch
        with T.no_grad():
            Q = T.cat([r["q_img"] for r in self.regs], dim=1)
            Qt = T.cat([r["q_txt"] for r in self.regs], dim=1)
            fmap, feats = d._pass(im)
            L = d.owl.class_predictor(image_feats=feats, query_embeds=Q)[0][0].float().cpu().numpy()
            Lt = d.owl.class_predictor(image_feats=feats, query_embeds=Qt)[0][0].float().cpu().numpy()
            boxes = d.owl.box_predictor(feats, fmap)[0].float().cpu().numpy()
            picks, crops = [], []
            for q in range(len(self.regs)):
                for how, b in (("img", int(L[:, q].argmax())), ("txt", int((L[:, q] + Lt[:, q]).argmax()))):
                    box = d._to_px(boxes[b].tolist(), im)
                    crop = im.crop(tuple(int(v) for v in box))
                    picks.append((q, how, b, box, crop))
                    crops += [crop, square(crop)]
            E = d._dino(crops)
        out = {}
        for k, (q, how, b, box, crop) in enumerate(picks):
            r = self.regs[q]
            others = [j for j, o in enumerate(self.regs) if o["group"] == r["group"] and j != q]
            look = D.appearance(crop)
            out[(r["key"], how)] = dict(
                box=[round(v, 1) for v in box], photo_name=float(L[b, q] + Lt[b, q]),
                vs_others=float(L[b, q] - L[b, others].max()) if others else None,
                vs_all=float(L[b, q] - np.delete(L[b], q).max()) if len(self.regs) > 1 else None,    # POC 26's setup
                dino_c=float((r["dc"].to(E.device) @ E[2 * k]).max()), dino_s=float((r["ds"].to(E.device) @ E[2 * k + 1]).max()),
                dL=abs(look["L"] - r["look"]["L"]), dC=abs(look["C"] - r["look"]["C"]))
        return out


def orbit(p):
    its = B.items()
    rows = []
    for it in its:
        name = B.NAMES.get(it["obj"], it["obj"].replace("-", " "))
        photos = [C.load_photo(it["regdir"] / f) for f in it["reg_order"]]
        if not p.register(it["name"], name, it["name"].split("--")[0], photos):
            print("not registered (every photo asked for a retake):", it["name"], flush=True)
    cat = {it["name"]: B.CATEGORY.get(it["obj"], it["obj"]) for it in its}
    for it in its:
        for fi, (path, gt) in enumerate(it["tests"]):
            res = p.frame(Image.open(path).convert("RGB"))
            for (key, how), v in res.items():
                kind = ("own" if key == it["name"] else
                        "same_user" if key.split("--")[0] == it["name"].split("--")[0] else
                        "lookalike" if cat[key] == cat[it["name"]] else "other")
                rows.append(dict(ds="orbit", video=it["name"], frame=fi, item=key, how=how, kind=kind,
                                 on_item=bool(kind == "own" and iou(v["box"], gt) >= 0.3), **v))
    return rows, {r["key"]: r["tries"] for r in p.regs}


def venue(p):
    rows = []
    photos = {n: C.load_photo(ROOT / "server" / "data" / f) for n, f in C.PHOTOS.items()}
    for sp in ("rec1-normal", "rec2-find", "rec3-moved"):
        ses = Session(ROOT / "server/data/sessions" / sp)
        p.regs.clear()
        p.d.items.clear()
        for n in [n for n in ses.truth["items"] if n in photos]:
            p.register(n, n, "venue", [photos[n]])
        for meta in ses.frames:
            im, fr, kk, scale, jsize = C.upright(ses, meta)
            for (key, how), v in p.frame(im).items():
                where = C.in_box(dict(box=v["box"]), ses.truth["items"], key, fr, kk, scale, jsize)
                rows.append(dict(ds="venue", video=sp, frame=int(meta["frame_id"]), item=key, how=how,
                                 kind="own" if where is not None else "out_of_view", on_item=bool(where), **v))
    return rows


if __name__ == "__main__":
    t0 = time.time()
    p = Probe()
    rows, tries = orbit(p)
    print(f"ORBIT: {len(rows)} rows in {time.time() - t0:.0f} s; registration tries {tries}", flush=True)
    rows += venue(p)
    out = ROOT / "poc/reports/poc29_rows.json"
    out.write_text(json.dumps(dict(thresholds=D.TH, colour=[D.TH_LIGHT, D.TH_CHROMA], tries=tries, rows=rows)))
    print(f"wrote {out} ({len(rows)} rows) in {time.time() - t0:.0f} s", flush=True)
