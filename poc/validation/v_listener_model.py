"""Validate the simulated listener against published human data.

Calibrated (in-sample): static front/back confusion and error levels, individual vs generic HRTF.
Out-of-sample check: head movement must cut front/back confusions by roughly half or more
(Oberem et al. 2020: 16.5 % static -> 6.3-7.1 % dynamic; Begault et al. 2001: 59 % -> 28 %;
Wightman & Kistler 1999: confusions largely disappear when listeners move their heads).
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "emulators" / "listener"))
from cache import load_all  # noqa: E402
from calibrate import evaluate  # noqa: E402
from model import Listener, Noise, WorldBelief, add_motor_noise  # noqa: E402

NOISE = Noise(itd_us=60, ild_db=5.0, spec_db=12.0, motor_deg=11.0)
FEATS = load_all()
SUBJ = [k for k in FEATS if k != "apple"]


def dynamic_trial(L, az, el, rng, scan_deg=20.0, dur=2.0, hop=0.3):
    """Listener hears a ~2 s sound while making a natural head movement, then points."""
    B = WorldBelief(L, decay_tau_s=None)
    phase = rng.uniform(0, 2 * np.pi)
    for t in np.arange(0, dur, hop):
        yaw = scan_deg * np.sin(2 * np.pi * t / dur + phase) if scan_deg else 0.0
        B.look(t, ((az - yaw) + 180) % 360 - 180, el, yaw)
    ra, re_ = B.map_world()
    return add_motor_noise(ra, re_, NOISE.motor_deg, rng)


def fb_rate(render_key, scan_deg, n=80):
    fb = cnt = 0
    for si, s in enumerate(SUBJ):
        rng = np.random.default_rng(100 + si)
        L = Listener(FEATS[render_key] if render_key else FEATS[s], FEATS[s], NOISE, rng)
        for _ in range(n):
            az = rng.uniform(-180, 180)
            el = np.degrees(np.arcsin(rng.uniform(np.sin(np.radians(-30)), np.sin(np.radians(45)))))
            lat = np.degrees(np.arcsin(np.cos(np.radians(el)) * np.sin(np.radians(az))))
            if abs(lat) > 60:
                continue
            ra, _ = dynamic_trial(L, az, el, rng, scan_deg)
            cnt += 1
            fb += (np.cos(np.radians(az)) > 0) != (np.cos(np.radians(ra)) > 0)
    return 100 * fb / cnt


if __name__ == "__main__":
    static = evaluate(NOISE, n=150)
    res = {"noise": NOISE.__dict__, "static_all_subjects": static,
           "front_back_pct_generic_static_2s": fb_rate("apple", 0.0),
           "front_back_pct_generic_headmove_2s": fb_rate("apple", 20.0),
           "front_back_pct_individual_static_2s": fb_rate(None, 0.0),
           "front_back_pct_individual_headmove_2s": fb_rate(None, 20.0)}
    print(json.dumps(res, indent=2))
    (ROOT / "reports" / "v_listener_model.json").write_text(json.dumps(res, indent=2))
