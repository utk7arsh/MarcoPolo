"""POC 28d: the Vultr A16 runs OWLv2 in float16 (detector.py: float16 on CUDA), but every threshold was set in float32
(Mac). Same clips, photos and gates, OWLv2 in float16 vs float32 (on this Mac's GPU, MPS): do the scores move?

  python poc/pocs/poc28_multi_item/fp16.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check as C  # noqa: E402
from marco.perception.detector import OwlDetector  # noqa: E402
from marco.session import Session  # noqa: E402

SESSIONS = ("server/data/sessions/rec2-find", "server/data/sessions/rec3-moved")
photos = {n: C.load_photo(ROOT / "server" / "data" / f) for n, f in C.PHOTOS.items()}
res = {}
for label in ("float32", "float16"):
    owl = OwlDetector()
    if label == "float16":
        owl.dtype = owl.torch.float16
        owl.owl = owl.owl.half()
    rows = []
    regs = {}
    for p in SESSIONS:
        ses = Session(ROOT / p)
        owl.items.clear()
        for n in [n for n in ses.truth["items"] if n in photos]:
            r = owl.register(n, n, photos[n])
            regs[f"{Path(p).name}/{n}"] = (r["quality"], [round(v) for v in r["box"]] if r.get("box") else None)
        for meta in ses.frames:
            im, fr, k, scale, jsize = C.upright(ses, meta)
            for d in owl.detect(im):
                rows.append(dict(s=Path(p).name, f=meta["frame_id"], name=d["name"], present=d["present"],
                                 photo_name=d["photo_name"], dino=d["dino"], vs=d["vs_others"],
                                 on=C.in_box(d, ses.truth["items"], d["name"], fr, k, scale, jsize)))
    res[label] = dict(registrations=regs, rows=rows)
    hits = sum(r["present"] and bool(r["on"]) for r in rows)
    fa = sum(r["present"] and not r["on"] for r in rows)
    print(label, "registrations", regs, "| hits", hits, "false alarms", fa, "boxes on item", sum(bool(r["on"]) for r in rows))
a, b = res["float32"]["rows"], res["float16"]["rows"]
d_pn = np.array([x["photo_name"] - y["photo_name"] for x, y in zip(a, b)])
d_dn = np.array([x["dino"] - y["dino"] for x, y in zip(a, b)])
print("float16 - float32: photo_name mean %.3f max |%.3f|, dino mean %.3f max |%.3f|, present flips %d of %d" % (
    -d_pn.mean(), np.abs(d_pn).max(), -d_dn.mean(), np.abs(d_dn).max(), sum(x["present"] != y["present"] for x, y in zip(a, b)), len(a)))
(ROOT / "poc/reports/poc28_fp16.json").write_text(json.dumps(res, indent=1))
