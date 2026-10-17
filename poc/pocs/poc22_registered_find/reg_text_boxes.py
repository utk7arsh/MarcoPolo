"""Registration the way the app would do it: the user says what it is ("these are my keys"), so box
that named thing in the registration frames with a text-prompted detector (not the most salient
thing, which is often the user's hand)."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import bench  # noqa: E402

from ultralytics import YOLOE  # noqa: E402

m = YOLOE("yoloe-26l-seg.pt")
for d in sorted(bench.DATA.glob("P*--*")):
    name = bench.NAMES.get(d.name.split("--")[1], d.name.split("--")[1].replace("-", " "))
    try:
        m.set_classes([name], m.get_text_pe([name]))
    except Exception:
        m.set_classes([name])
    fg = json.loads((d / "register" / "boxes.json").read_text())
    out = {}
    for f in sorted(fg):
        r = m.predict(str(d / "register" / f), conf=0.01, verbose=False)[0]
        if len(r.boxes) and float(r.boxes.conf.max()) >= 0.05:
            out[f] = r.boxes.xyxy[int(r.boxes.conf.argmax())].tolist()
    (d / "register" / "boxes_text.json").write_text(json.dumps(out, indent=1))
    print(f"{d.name:30} '{name}': boxed in {len(out)}/{len(fg)} registration frames")
