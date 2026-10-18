"""POC 28c: what would find more of the items without more false alarms? All items registered together, two ways:
  crop   the box around the item that registration crops to (today's first registration)
  whole  the whole saved photo (what the server uses after a restart: gate=False)
and the presence check swept over the DINOv2 threshold (OWLv2 photo+name and the margin over other items as today).
A hit is "present" with the box on the item; a false alarm is "present" with the box elsewhere or the item out of view.

  python poc/pocs/poc28_multi_item/sweep.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check as C  # noqa: E402
from marco.perception.detector import TH, OwlDetector  # noqa: E402
from marco.session import Session  # noqa: E402

SESSIONS = ("server/data/sessions/rec1-normal", "server/data/sessions/rec2-find", "server/data/sessions/rec3-moved")
owl = OwlDetector()
photos = {n: C.load_photo(ROOT / "server" / "data" / f) for n, f in C.PHOTOS.items()}
rows = {}
for gate, label in ((True, "crop"), (False, "whole")):
    rows[label] = []
    for p in SESSIONS:
        ses = Session(ROOT / p)
        owl.items.clear()
        for n in [n for n in ses.truth["items"] if n in photos]:
            owl.register(n, n, photos[n], gate=gate)
        for meta in ses.frames:
            im, fr, k, scale, jsize = C.upright(ses, meta)
            for d in owl.detect(im):
                rows[label].append(dict(session=Path(p).name, frame=meta["frame_id"], name=d["name"], photo_name=d["photo_name"],
                                        dino=d["dino"], vs_others=d["vs_others"],
                                        on_item=C.in_box(d, ses.truth["items"], d["name"], fr, k, scale, jsize)))
out = {}
for label, rs in rows.items():
    for th in (0.38, 0.33, 0.30, 0.25, 0.20):
        def present(r):
            return r["photo_name"] >= TH["photo_name"] and r["dino"] >= th and (r["vs_others"] is None or r["vs_others"] >= TH["vs_others"])
        hits = sum(present(r) and bool(r["on_item"]) for r in rs)
        false = sum(present(r) and not r["on_item"] for r in rs)
        per_item = {}
        for r in rs:
            k = f"{r['session']}/{r['name']}"
            per_item.setdefault(k, [0, 0])
            per_item[k][0] += present(r) and bool(r["on_item"])
            per_item[k][1] += bool(r["on_item"])
        out[f"{label} dino>={th}"] = dict(hits=hits, boxes_on_item=sum(bool(r["on_item"]) for r in rs), false_alarms=false,
                                          per_item={k: f"{h}/{n}" for k, (h, n) in per_item.items()})
        print(f"{label:5s} dino>={th:.2f}", json.dumps(out[f"{label} dino>={th}"]))
(ROOT / "poc/reports/poc28_sweep.json").write_text(json.dumps(dict(summary=out, rows=rows), indent=1))
