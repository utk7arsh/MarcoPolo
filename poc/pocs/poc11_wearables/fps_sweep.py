"""POC 11 add-on: how much does the frame rate sent to the server matter?

Same day of put-downs, same chest camera (30 deg tilt) and detector model as run.py; only the frame
rate changes. Frames fall at a random phase relative to the moment the hand lets go (a fixed-rate
stream does not know when that happens), so at 0.5 fps the 1.5 s release window holds one frame
75 % of the time and none 25 % of the time.
Also: re-seen within 60 s of walking the room loop afterwards, and the largest turn speed at which a
search sweep leaves no gaps between frames (48 deg horizontal field of view, portrait chest camera).
"""
import importlib.util
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
spec = importlib.util.spec_from_file_location("poc11_run", HERE / "run.py")  # not "run": resight() imports POC 1's run.py
P = importlib.util.module_from_spec(spec)
spec.loader.exec_module(P)

CAM = "chest phone 30 deg"
WINDOW = 1.5
HFOV = 48.0


def release_capture(fps, n=600, seed=1):
    rng = np.random.default_rng(seed)
    cam = P.DEVICES[CAM]
    caught, frames = [], []
    for item, size, pt, stand, torso, hy, hp in P.day(rng, 0.3, n):
        t, p_miss, k = rng.uniform(0, 1 / fps), 1.0, 0
        while t < WINDOW:
            R, pos, f, w, h, fac = cam(stand, torso + rng.normal(0, 2), hy, hp, t, False)
            p_miss *= 1 - P.p_detect(item, P.visible_size(R, pos, f, w, h, pt, size), fac)
            t += 1 / fps
            k += 1
        caught.append(1 - p_miss)
        frames.append(k)
    return round(100 * float(np.mean(caught)), 1), round(float(np.mean(frames)), 2)


if __name__ == "__main__":
    out = {}
    for fps in (0.5, 1.0, 2.0, 3.0):
        cap, nfr = release_capture(fps)
        rs = P.resight(np.random.default_rng(2), 0.3, n_events=60, fps=fps)[CAM]
        both = 100 * (1 - (1 - cap / 100) * (1 - rs / 100))
        out[f"{fps:g} fps"] = dict(frames_in_release_window=nfr, putdown_captured_pct=cap, reseen_within_60s_walking_pct=rs,
                                   seen_by_60s_pct=round(both, 1), max_gapless_sweep_deg_per_s=HFOV * fps,
                                   uploads_MB_per_hour_at_150KB=round(150 * fps * 3600 / 1000))
        print(f"{fps:>4g} fps: {nfr:.2f} frames in the release window -> put-down caught {cap:5.1f}% | re-seen within 60 s walking {rs:5.1f}% "
              f"| seen by 60 s {both:5.1f}% | gapless sweep up to {HFOV * fps:.0f} deg/s | {150 * fps * 3.6:.0f} MB/h", flush=True)
    rep = ROOT / "reports" / "poc11_wearables.json"
    res = json.loads(rep.read_text())
    res["frame_rate_sweep_chest_30deg"] = out
    rep.write_text(json.dumps(res, indent=2))
