"""POC 6: Can Apple's Vision feature prints tell *your* bottle from other bottles, from across a room?

Data: 8 real iPhone videos of 8 different bottles (Google Objectron, ARKit-captured, 1440x1920).
Enrolment: native-resolution crops from the first third of each video (like "hold it up for 3 s").
Queries: crops from the last half of the video (different viewpoint), rescaled so the bottle spans
200 / 120 / 80 px -- what a 25 cm bottle spans in the 1920x1440 ARKit image at ~2 m / 3.3 m / 5 m.
Two variants: raw detector crop, and crop with Vision's foreground mask (background removed).
"""
import itertools
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]


def load(d):
    out = {}
    for f in sorted((ROOT / "data" / "tmp" / d).glob("*.bin")):
        a = np.fromfile(f, dtype="<f4")
        i, recs = 0, []
        while i < len(a):
            fid, s, n = int(a[i]), int(a[i + 1]), int(a[i + 2])
            recs.append((fid, s, a[i + 3:i + 3 + n].astype(np.float64)))
            i += 3 + n
        out[f.stem.replace("objectron_bottle_", "")] = recs
    return out


def split(recs):
    fids = sorted({r[0] for r in recs})
    enroll_f = set(fids[: max(3, len(fids) // 3)][:8])
    query_f = set(fids[len(fids) // 2:])
    gallery = np.array([r[2] for r in recs if r[0] in enroll_f and r[1] == 0])
    queries = {s: np.array([r[2] for r in recs if r[0] in query_f and r[1] == s]) for s in (0, 200, 120, 80)}
    return gallery, queries


def dmin(q, g):
    return np.min(np.linalg.norm(q[:, None, :] - g[None, :, :], axis=2), axis=1)


def evaluate(data):
    names = sorted(data)
    G, Q = {}, {}
    for n in names:
        G[n], Q[n] = split(data[n])
    res = {}
    for s in (0, 200, 120, 80):
        # closed-set: which of 3 bottles on the table is mine?
        correct = total = 0
        for trip in itertools.combinations(names, 3):
            for tgt in trip:
                q = Q[tgt][s]
                if len(q) == 0:
                    continue
                D = np.stack([dmin(q, G[o]) for o in trip], 1)
                correct += int(np.sum(np.argmin(D, 1) == trip.index(tgt)))
                total += len(q)
        # open-set: genuine vs impostor distance
        gen = np.concatenate([dmin(Q[n][s], G[n]) for n in names if len(Q[n][s])])
        imp = np.concatenate([dmin(Q[o][s], G[n]) for n in names for o in names if o != n and len(Q[o][s])])
        thr = np.percentile(imp, 1)  # accept at most 1 % of other bottles
        ths = np.linspace(min(gen.min(), imp.min()), max(gen.max(), imp.max()), 400)
        far = np.array([np.mean(imp <= t) for t in ths]); frr = np.array([np.mean(gen > t) for t in ths])
        k = int(np.argmin(np.abs(far - frr)))
        res[f"{s or 'native'} px"] = dict(three_bottle_id_accuracy_pct=round(100 * correct / total, 1),
                                          eer_pct=round(100 * (far[k] + frr[k]) / 2, 1),
                                          true_accept_at_1pct_false_accept=round(100 * float(np.mean(gen <= thr)), 1),
                                          n_genuine=int(len(gen)), n_impostor=int(len(imp)))
    return res


if __name__ == "__main__":
    out = {}
    for d, label in (("fp_raw", "raw crop"), ("fp_mask", "foreground-masked crop")):
        out[label] = evaluate(load(d))
        print(f"## {label}")
        for k, v in out[label].items():
            print(f"  bottle spans {k:>10}: 3-bottle ID {v['three_bottle_id_accuracy_pct']:5.1f}%  EER {v['eer_pct']:4.1f}%  TAR@1%FAR {v['true_accept_at_1pct_false_accept']:5.1f}%  (genuine {v['n_genuine']}, impostor {v['n_impostor']})")
    (ROOT / "reports" / "poc6_recognition.json").write_text(json.dumps(out, indent=2))
