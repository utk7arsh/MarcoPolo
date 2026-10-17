"""POC 14 analysis: can a drop trigger built on Apple's built-in classes separate drops from everyday sounds?"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
meta = {m["path"]: m for m in json.loads((ROOT / "data" / "downloads" / "freesound" / "index.json").read_text())}
res = json.loads((ROOT / "data" / "tmp" / "drop_cls.json").read_text())
DROP_CLASSES = ["keys_jangling", "coin_dropping", "thump_thud"]
rows = []
for r in res:
    if "error" in r:
        print("ERROR", r["path"], r["error"][:80]); continue
    m = meta[r["path"]]
    score = max(r["watch"][k] for k in DROP_CLASSES)
    rows.append((m["label"], score, m["title"][:42], r["top"][:3]))
rows.sort(key=lambda x: -x[1])
for lab, sc, title, top in rows:
    print(f"{lab:5} drop-score {sc:4.2f}  {title:44} top: {', '.join(top)}")
pos = np.array([s for l, s, *_ in rows if l == "drop"]); neg = np.array([s for l, s, *_ in rows if l == "other"])
out = {}
for thr in (0.2, 0.3, 0.5, 0.7):
    out[f"threshold {thr}"] = dict(drops_detected_pct=round(100 * float(np.mean(pos >= thr)), 1), false_triggers_pct=round(100 * float(np.mean(neg >= thr)), 1))
    print(f"threshold {thr}: drops detected {100 * np.mean(pos >= thr):5.1f}% ({len(pos)} clips), false triggers on everyday sounds {100 * np.mean(neg >= thr):5.1f}% ({len(neg)} clips)")
(ROOT / "reports" / "poc14_drop_audio.json").write_text(json.dumps(out, indent=2))
