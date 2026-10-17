"""Calibrate listener-model noise so static localization matches published human data.

Targets (static, broadband, headphones):
  individual HRTF      front/back confusions ~8-13 %   (Oberem et al. 2020: 7.6 % avg incl. dynamic; static higher)
  non-individual HRTF  front/back confusions ~20-35 %  (Oberem 2020 static ~20 %; Wenzel 1993 ~31 %; Begault 2001 59 % untrained speech)
  lateral error        ~10-15 deg RMS; local polar error ~25-35 deg (Middlebrooks 1999; Majdak 2010)
One noise parameter set must reproduce BOTH conditions (mismatch is the only difference).
"""
import itertools
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from cache import load_all  # noqa: E402
from model import Listener, Noise, lateral_polar  # noqa: E402

FEATS = load_all()
SUBJECTS = [k for k in FEATS if k != "apple"]


def sample_dirs(rng, n):
    az = rng.uniform(-180, 180, n)
    el = np.degrees(np.arcsin(rng.uniform(np.sin(np.radians(-30)), np.sin(np.radians(45)), n)))
    return az, el


def evaluate(noise, n=150, seed=1, subjects=SUBJECTS):
    out = {}
    for cond in ("individual", "apple_generic"):
        fb = lat_e = pol_e = qe = 0.0
        cnt_fb = cnt = cnt_pol = 0
        for si, s in enumerate(subjects):
            rng = np.random.default_rng(seed + si)
            render = FEATS[s] if cond == "individual" else FEATS["apple"]
            L = Listener(render, FEATS[s], noise, rng)
            az, el = sample_dirs(rng, n)
            for a, e in zip(az, el):
                ra, re_ = L.localize_static(a, e)
                lt, pt = lateral_polar(a, e)
                lr, pr = lateral_polar(ra, re_)
                lat_e += (lr - lt) ** 2
                dp = (pr - pt + 180) % 360 - 180
                if abs(lt) <= 60:
                    cnt_fb += 1
                    fb += (np.cos(np.radians(a)) > 0) != (np.cos(np.radians(ra)) > 0)
                if abs(dp) > 90:
                    qe += 1
                else:
                    pol_e += dp ** 2
                    cnt_pol += 1
                cnt += 1
        out[cond] = dict(front_back_pct=100 * fb / cnt_fb, quadrant_err_pct=100 * qe / cnt,
                         lateral_rms_deg=float(np.sqrt(lat_e / cnt)), local_polar_rms_deg=float(np.sqrt(pol_e / max(cnt_pol, 1))))
    return out


def score(r):
    t = 0.0
    t += ((r["individual"]["front_back_pct"] - 10) / 4) ** 2
    t += ((r["apple_generic"]["front_back_pct"] - 27) / 6) ** 2
    t += ((r["individual"]["lateral_rms_deg"] - 12) / 4) ** 2
    t += ((r["individual"]["local_polar_rms_deg"] - 28) / 6) ** 2
    return t


if __name__ == "__main__":
    best = []
    grid = itertools.product([30, 60, 100], [2.0, 4.0, 7.0], [2.0, 3.5, 6.0], [1.0])
    for itd, ild, spec, w in grid:
        nz = Noise(itd_us=itd, ild_db=ild, spec_db=spec, motor_deg=6.0, spec_weight=w)
        r = evaluate(nz, n=60, subjects=SUBJECTS[:6])
        best.append((score(r), (itd, ild, spec, w), r))
        print(f"itd {itd:4} ild {ild:4} spec {spec:4} -> indiv FB {r['individual']['front_back_pct']:5.1f}% lat {r['individual']['lateral_rms_deg']:5.1f} pol {r['individual']['local_polar_rms_deg']:5.1f} | apple FB {r['apple_generic']['front_back_pct']:5.1f}% lat {r['apple_generic']['lateral_rms_deg']:5.1f} pol {r['apple_generic']['local_polar_rms_deg']:5.1f}  score {score(r):6.2f}", flush=True)
    best.sort(key=lambda x: x[0])
    print("BEST", best[0][1])
