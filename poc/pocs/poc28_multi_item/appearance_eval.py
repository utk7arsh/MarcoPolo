"""POC 28f: the appearance check (lightness, colourfulness, elongation) and trying the top 3 boxes per item, against
the old single-box check, on the venue clips with the real photos (crop registration). Hits: present with the box on
the item; false alarms: present with the box elsewhere or the item out of view. Also prints, for every box that IS on
the item, how far its appearance was from the registration crop, to show the margin left by the bounds.

  python poc/pocs/poc28_multi_item/appearance_eval.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check as C  # noqa: E402
from marco.perception import detector as D  # noqa: E402
from marco.session import Session  # noqa: E402

SESSIONS = ("server/data/sessions/rec1-normal", "server/data/sessions/rec2-find", "server/data/sessions/rec3-moved")
photos = {n: C.load_photo(ROOT / "server" / "data" / f) for n, f in C.PHOTOS.items()}
owl = D.OwlDetector()
configs = {"old: best box only, no appearance check": dict(TOP_K=1, TH_LIGHT=1e9, TH_CHROMA=1e9, TH_SHAPE=1e9),
           "top 3 boxes + appearance check (rejected: more false alarms)": dict(TOP_K=3, TH_LIGHT=35, TH_CHROMA=30, TH_SHAPE=2.5),
           "new: best box + colour check (lightness, colourfulness)": dict(TOP_K=1, TH_LIGHT=40, TH_CHROMA=30, TH_SHAPE=1e9)}
report = {}
for label, cfg in configs.items():
    for k, v in cfg.items():
        setattr(D, k, v)
    hits = fa = on = 0
    margins = []
    per = {}
    for p in SESSIONS:
        ses = Session(ROOT / p)
        owl.items.clear()
        for n in [n for n in ses.truth["items"] if n in photos]:
            owl.register(n, n, photos[n])
        for meta in ses.frames:
            im, fr, kk, scale, jsize = C.upright(ses, meta)
            for d in owl.detect(im):
                where = C.in_box(d, ses.truth["items"], d["name"], fr, kk, scale, jsize)
                key = f"{Path(p).name}/{d['name']}"
                per.setdefault(key, [0, 0])
                on += bool(where)
                if where:
                    per[key][1] += 1
                    ref = owl.items[d["item_id"]]["look"]
                    box = d["box"]
                    look = D.appearance(im.crop(tuple(int(v) for v in box)))
                    margins.append(dict(item=key, dL=round(abs(look["L"] - ref["L"]), 1), dC=round(abs(look["C"] - ref["C"]), 1),
                                        shape=round(max(look["elong"] / ref["elong"], ref["elong"] / look["elong"]), 2)))
                if d["present"] and where:
                    hits += 1
                    per[key][0] += 1
                elif d["present"]:
                    fa += 1
    report[label] = dict(hits=hits, false_alarms=fa, boxes_on_item=on, per_item={k: f"{a}/{b}" for k, (a, b) in per.items()})
    print(label, json.dumps(report[label]))
    if label.startswith("new"):
        worst = sorted(margins, key=lambda m: -max(m["dL"] / 40, m["dC"] / 30))[:6]
        print("  closest to the bounds among boxes on the item:", worst)
        report[label]["closest_to_bounds"] = worst
(ROOT / "poc/reports/poc28_appearance.json").write_text(json.dumps(report, indent=1))
