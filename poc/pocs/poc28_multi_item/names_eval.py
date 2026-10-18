"""POC 28g: does a descriptive name help? The detector scores each box on the photo plus "a photo of {name}", so the
name is part of every check. Same photos, same venue clips, all items registered together; only the names change.
The colour check is off here, to measure the name alone. Hits: present with the box on the item; false alarms:
present with the box elsewhere or the item out of view.

  python poc/pocs/poc28_multi_item/names_eval.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check as C  # noqa: E402
from marco.perception import detector as D  # noqa: E402
from marco.session import Session  # noqa: E402

D.TH_LIGHT = D.TH_CHROMA = float("inf")
SESSIONS = ("server/data/sessions/rec1-normal", "server/data/sessions/rec2-find", "server/data/sessions/rec3-moved")
NAMES = {
    "plain": {"bottle": "bottle", "power bank": "power bank", "wallet": "wallet"},
    "descriptive": {"bottle": "black metal water bottle", "power bank": "black and blue power bank",
                    "wallet": "black leather wallet"},
}
photos = {n: C.load_photo(ROOT / "server" / "data" / f) for n, f in C.PHOTOS.items()}
owl = D.OwlDetector()
report = {}
for label, names in NAMES.items():
    hits = fa = 0
    per, regs = {}, {}
    for p in SESSIONS:
        ses = Session(ROOT / p)
        owl.items.clear()
        for truth_name in [n for n in ses.truth["items"] if n in photos]:
            res = owl.register(truth_name, names[truth_name], photos[truth_name])
            regs[names[truth_name]] = res["quality"]
        for meta in ses.frames:
            im, fr, kk, scale, jsize = C.upright(ses, meta)
            for d in owl.detect(im):
                where = C.in_box(d, ses.truth["items"], d["item_id"], fr, kk, scale, jsize)
                key = f"{Path(p).name}/{d['item_id']}"
                per.setdefault(key, [0, 0])
                per[key][1] += bool(where)
                if d["present"] and where:
                    hits += 1
                    per[key][0] += 1
                elif d["present"]:
                    fa += 1
    report[label] = dict(names=names, registrations=regs, hits=hits, false_alarms=fa,
                         per_item={k: f"{a}/{b}" for k, (a, b) in per.items()})
    print(label, json.dumps(report[label]))
(ROOT / "poc/reports/poc28_names.json").write_text(json.dumps(report, indent=1))
