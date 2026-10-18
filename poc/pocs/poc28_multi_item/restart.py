"""POC 28b: after a server restart, items come back from the registry with gate=False, so the detector's query is the
WHOLE saved photo instead of the crop around the item that registration used. Does that change detection?
Same sessions and photos as check.py; each item registered on its own (no cross-item effects), both ways.

  python poc/pocs/poc28_multi_item/restart.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(Path(__file__).resolve().parent))
import check as C  # noqa: E402
from marco.perception.detector import OwlDetector  # noqa: E402
from marco.session import Session  # noqa: E402
from PIL import Image  # noqa: E402

owl = OwlDetector()
photos = {n: C.load_photo(ROOT / "server" / "data" / f) for n, f in C.PHOTOS.items()}
out = {}
for p in ("server/data/sessions/rec1-normal", "server/data/sessions/rec2-find", "server/data/sessions/rec3-moved"):
    ses = Session(ROOT / p)
    for n in [n for n in ses.truth["items"] if n in photos]:
        row = {}
        for label, gate in (("first registration (crop)", True), ("after restart (whole photo)", False)):
            owl.items.clear()
            owl.register(n, n, photos[n], gate=gate)
            hits = boxes_on = 0
            for meta in ses.frames:
                im, fr, k, scale, jsize = C.upright(ses, meta)
                d = owl.detect(im)[0]
                on = C.in_box(d, ses.truth["items"], n, fr, k, scale, jsize)
                boxes_on += bool(on)
                hits += bool(on) and d["present"]
            row[label] = dict(hits=hits, box_on_item=boxes_on, frames=len(ses.frames))
        out[f"{Path(p).name}/{n}"] = row
        print(Path(p).name, n, json.dumps(row))
(ROOT / "poc/reports/poc28_restart.json").write_text(json.dumps(out, indent=1))
