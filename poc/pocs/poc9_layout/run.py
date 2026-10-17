"""POC 9: "What's on the table?" -- can a listener hear the layout from one ping per item?

Three items on a table 2 m ahead, spaced s cm apart (left, middle, right), each pinged once in a
random order through Apple's HRTF. The calibrated listener reports where each ping came from; we
score whether the perceived left-to-right order is right. Compared with pings rendered at
exaggerated ("spread") angles, where the app widens the layout by a factor k for this overview.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "emulators" / "listener"))
from cache import load_all  # noqa: E402
from model import Listener, Noise  # noqa: E402

F = load_all()
NOISE = Noise(itd_us=60, ild_db=5.0, spec_db=12.0, motor_deg=11.0)
SUBJ = [k for k in F if k != "apple"]

if __name__ == "__main__":
    res = {}
    for spread in (1.0, 3.0):
        for s_cm in (10, 20, 30, 45):
            ang = np.degrees(np.arctan2(s_cm / 100, 2.0)) * spread
            ok = n = 0
            for si, sub in enumerate(SUBJ):
                rng = np.random.default_rng(si)
                L = Listener(F["apple"], F[sub], NOISE, rng)
                for _ in range(60):
                    true = np.array([-ang, 0.0, ang])
                    perc = [L.localize_static(a, -20)[0] for a in true]
                    perc = [(np.sign(p) * 180 - p) if abs(p) > 90 else p for p in perc]  # mirror back->front (lateral angle)
                    ok += int(np.all(np.argsort(perc) == np.arange(3)))
                    n += 1
            key = f"spacing {s_cm} cm ({ang:.1f} deg rendered{', 3x spread' if spread > 1 else ''})"
            res[key] = round(100 * ok / n, 1)
            print(f"{key:45} correct left-to-right order: {res[key]:5.1f}%   (chance 16.7%)")
    (ROOT / "reports" / "poc9_layout.json").write_text(json.dumps(res, indent=2))
