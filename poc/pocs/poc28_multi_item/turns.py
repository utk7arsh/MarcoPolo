"""POC 28e: the DINOv2 crop check against the registration crop at 1 vs 4 rotations (MARCO_DINO_TURNS), all items
registered together (crop registration, as on a first registration), swept over the DINOv2 threshold.

  python poc/pocs/poc28_multi_item/turns.py
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
out = {}
for turns in (1, 4):
    D.DINO_TURNS = turns
    rows = []
    for p in SESSIONS:
        ses = Session(ROOT / p)
        owl.items.clear()
        for n in [n for n in ses.truth["items"] if n in photos]:
            owl.register(n, n, photos[n])
        for meta in ses.frames:
            im, fr, k, scale, jsize = C.upright(ses, meta)
            for d in owl.detect(im):
                rows.append(dict(photo_name=d["photo_name"], dino=d["dino"], vs=d["vs_others"],
                                 on=C.in_box(d, ses.truth["items"], d["name"], fr, k, scale, jsize), name=d["name"], s=Path(p).name))
    for th in (0.38, 0.33, 0.30, 0.25):
        ok = [r for r in rows if r["photo_name"] >= D.TH["photo_name"] and r["dino"] >= th and (r["vs"] is None or r["vs"] >= D.TH["vs_others"])]
        hits, fa = sum(bool(r["on"]) for r in ok), sum(not r["on"] for r in ok)
        per = {}
        for r in rows:
            k_ = f"{r['s']}/{r['name']}"
            per.setdefault(k_, [0, 0])
            per[k_][1] += bool(r["on"])
        for r in ok:
            if r["on"]:
                per[f"{r['s']}/{r['name']}"][0] += 1
        out[f"turns={turns} dino>={th}"] = dict(hits=hits, false_alarms=fa, per_item={k: f"{a}/{b}" for k, (a, b) in per.items()})
        print(f"turns={turns} dino>={th:.2f}", json.dumps(out[f"turns={turns} dino>={th}"]))
(ROOT / "poc/reports/poc28_turns.json").write_text(json.dumps(out, indent=1))
