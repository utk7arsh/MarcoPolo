"""POC 29 analysis of poc/reports/poc29_rows.json (general.py). Nothing here is fitted on the venue clips or on live
frames: the only threshold chosen is the square-crop DINOv2 one, and it is chosen on ORBIT to give exactly the
deployed check's ORBIT false-alarm rate (an equal-false-alarm comparison), then carried unchanged to the venue clips.

  poc/.venv/bin/python -I poc/pocs/poc29_false_alarms/analyze.py     # writes poc/reports/poc29_false_alarms.json
"""
import itertools
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[3]
data = json.loads((ROOT / "poc/reports/poc29_rows.json").read_text())
TH = data["thresholds"]
rows = data["rows"]
NEG = ("lookalike", "other")


def auc(pos, neg):
    pos, neg = np.asarray(pos, float), np.asarray(neg, float)
    if not len(pos) or not len(neg):
        return None
    return round(float((pos[:, None] > neg[None, :]).mean() + 0.5 * (pos[:, None] == neg[None, :]).mean()), 3)


def present(r, dino="c", th_dino=None, colour=False, margin="vs_others"):
    th_dino = TH["dino"] if th_dino is None else th_dino
    ok = r["photo_name"] >= TH["photo_name"] and r[f"dino_{dino}"] >= th_dino and \
        (r[margin] is None or r[margin] >= TH["vs_others"])
    return ok and (not colour or (r["dL"] <= 40 and r["dC"] <= 30))


def orbit_scores(rs, **kw):
    own = [r for r in rs if r["kind"] == "own"]
    neg = [r for r in rs if r["kind"] in NEG]
    caught = [present(r, **kw) and r["on_item"] for r in own]
    fa = {k: [present(r, **kw) for r in neg if r["kind"] == k] for k in NEG}
    pairs_pos, pairs_neg = [], []
    by = {}
    for r in rs:
        by.setdefault((r["video"], r["item"], r["kind"]), []).append(r)
    for (_, _, kind), g in by.items():
        for a, b in itertools.combinations(g, 2):
            if kind == "own":
                pairs_pos.append(present(a, **kw) and a["on_item"] and present(b, **kw) and b["on_item"])
            elif kind in NEG:
                pairs_neg.append(present(a, **kw) and present(b, **kw))
    allfa = fa["lookalike"] + fa["other"]
    return dict(caught_on_item_pct=round(100 * np.mean(caught), 1),
                false_alarm_pct=round(100 * np.mean(allfa), 2),
                false_alarm_pct_lookalike=round(100 * np.mean(fa["lookalike"]), 2),
                false_alarm_pct_other=round(100 * np.mean(fa["other"]), 2),
                two_frames_caught_pct=round(100 * np.mean(pairs_pos), 1),
                two_frames_false_alarm_pct=round(100 * np.mean(pairs_neg), 3),
                n_own=len(own), n_neg=len(allfa))


def venue_scores(rs, **kw):
    hits = sum(present(r, **kw) and r["on_item"] for r in rs)
    fas = sum(present(r, **kw) and not r["on_item"] for r in rs)
    on = sum(r["on_item"] for r in rs)
    return dict(hits=hits, false_alarms=fas, boxes_on_item=on)


report = {}
for how in ("img", "txt"):
    o = [r for r in rows if r["ds"] == "orbit" and r["how"] == how]
    v = [r for r in rows if r["ds"] == "venue" and r["how"] == how]
    pos = [r for r in o if r["kind"] == "own" and r["on_item"]]
    neg = [r for r in o if r["kind"] in NEG]
    vpos = [r for r in v if r["on_item"]]
    vneg = [r for r in v if not r["on_item"]]
    rep = dict(box_on_item_pct_orbit=round(100 * np.mean([r["on_item"] for r in o if r["kind"] == "own"]), 1),
               box_on_item_venue=f"{len(vpos)}/{sum(r['kind'] == 'own' for r in v)}",
               auc_orbit={k: dict(all=auc([r[k] for r in pos], [r[k] for r in neg]),
                                  lookalike=auc([r[k] for r in pos], [r[k] for r in neg if r["kind"] == "lookalike"]))
                          for k in ("dino_c", "dino_s", "photo_name")},
               auc_venue={k: auc([r[k] for r in vpos], [r[k] for r in vneg]) for k in ("dino_c", "dino_s", "photo_name")},
               median_dino_venue={k: dict(on_item=round(float(np.median([r[k] for r in vpos])), 3) if vpos else None,
                                          elsewhere=round(float(np.median([r[k] for r in vneg])), 3) if vneg else None)
                                  for k in ("dino_c", "dino_s")})
    cfg = {"POC 26's setup: all 18 registered in one server, TH_DINO 0.38": dict(dino="c", th_dino=0.38, margin="vs_all"),
           "POC 26's setup, TH_DINO 0.30": dict(dino="c", margin="vs_all"),
           "deployed (centre crop, TH_DINO 0.30)": dict(dino="c"),
           "main now (+ colour check)": dict(dino="c", colour=True),
           "POC 26 (centre crop, TH_DINO 0.38)": dict(dino="c", th_dino=0.38)}
    target = orbit_scores(o, dino="c")["false_alarm_pct"]
    cands = sorted({round(r["dino_s"], 4) for r in o})
    t_s = min((t for t in cands if orbit_scores(o, dino="s", th_dino=t)["false_alarm_pct"] <= target), default=1.0)
    cfg[f"square crop, TH_DINO {t_s:.3f} (same ORBIT false alarms as deployed)"] = dict(dino="s", th_dino=t_s)
    rep["configs"] = {k: dict(orbit=orbit_scores(o, **c), venue=venue_scores(v, **c)) for k, c in cfg.items()}
    def sweep(dino):
        """Every DINOv2 threshold, the other gates as deployed: (caught %, false-alarm %) on ORBIT."""
        ts = sorted({round(r[f"dino_{dino}"], 3) for r in o})[::4]
        return [(t, orbit_scores(o, dino=dino, th_dino=t)) for t in ts]
    curves = {d: sweep(d) for d in ("c", "s")}
    rep["equal_recall"] = {}
    for want in (64.0, 80.0):
        row = {}
        for d, cv in curves.items():
            best = min((sc["false_alarm_pct"], t) for t, sc in cv if sc["caught_on_item_pct"] >= want)
            row["centre crop" if d == "c" else "square crop"] = dict(th_dino=best[1], false_alarm_pct=best[0])
        rep["equal_recall"][f"caught >= {want:.0f}%"] = row
    report[f"box chosen by {'image query' if how == 'img' else 'image + name'}"] = rep
out = ROOT / "poc/reports/poc29_false_alarms.json"
out.write_text(json.dumps(dict(thresholds=TH, registration_tries=data["tries"], results=report), indent=1))
print(json.dumps(report, indent=1))
