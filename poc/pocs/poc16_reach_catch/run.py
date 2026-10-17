"""POC 16: "That's cinnamon" -- can Marco warn before the wrong jar is picked up?

Reaches are simulated with the minimum-jerk model of human arm movement (Flash & Hogan 1985), with
durations from Fitts' law (0.6-1.4 s, slower for blind reaching), slight path curvature, and endpoint
scatter. The fingertip is tracked by the chest camera (Vision hand pose + LiDAR) at 30 fps with 1 cm
3-D noise and a total pipeline latency of 100-250 ms (camera -> Vision -> logic -> AirPods audio).
Eight jars 5.5 cm apart (identities known from POC 13's row matching). In half the trials the person
reaches for the wrong jar (the neighbour of the one they asked for).

Two catches:
  A. before contact: predict the jar from the hand's motion (intersection of the velocity ray with the
     jar row) and warn once the prediction is stable for 3 frames and the hand is within 15 cm.
     Useful only if heard >= the time needed to stop a reach (stop-signal RT ~200-300 ms).
  B. at touch, before lifting: the fingertip stops on a jar; Marco names it within the latency. The
     touch-to-lift interval for grasping is ~300-600 ms; blind users typically confirm by touch first.
Metrics: warning lead time before contact (A), time from touch to the name being heard (B), and false
warnings on correct reaches.
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SP, N = 0.055, 8
JARS = np.stack([np.arange(N) * SP - (N - 1) * SP / 2, np.zeros(N), np.zeros(N)], 1)  # x along row, y up, z toward body


def min_jerk(p0, p1, T, t):
    s = np.clip(t / T, 0, 1)
    return p0 + (p1 - p0) * (10 * s ** 3 - 15 * s ** 4 + 6 * s ** 5)


def reach(rng, target, T, fps=30.0):
    start = np.array([rng.uniform(-0.15, 0.15), -0.25 + rng.uniform(-0.05, 0.05), 0.30 + rng.uniform(-0.05, 0.05)])
    end = JARS[target] + np.array([rng.normal(0, 0.008), 0.03, 0.03])  # fingertip arrives in front of the jar
    via = (start + end) / 2 + np.array([rng.normal(0, 0.04), 0.06, 0])  # curved path
    ts = np.arange(0, T + 0.2, 1 / fps)
    a = np.array([min_jerk(start, via, T / 2, t) if t < T / 2 else min_jerk(via, end, T / 2, t - T / 2) for t in ts])
    # smooth the via-point join a little
    return ts, a


def predict(pos, vel):
    """Jar under the hand's motion: where the velocity ray crosses the jar plane (z = 0.03)."""
    if vel[2] > -0.02:
        return int(np.argmin(np.abs(JARS[:, 0] - pos[0])))
    t = (0.03 - pos[2]) / vel[2]
    x = pos[0] + vel[0] * max(t, 0)
    return int(np.argmin(np.abs(JARS[:, 0] - x)))


def trial(rng, latency, wrong):
    asked = rng.integers(1, N - 1)
    target = asked + (rng.choice([-1, 1]) if wrong else 0)
    T = rng.uniform(0.6, 1.4)
    ts, path = reach(rng, target, T)
    meas = path + rng.normal(0, 0.01, path.shape)
    contact_t = T
    warned_at, stable, last = None, 0, None
    for k in range(3, len(ts)):
        p = meas[k]
        v = (meas[k] - meas[k - 3]) / (ts[k] - ts[k - 3])
        if np.linalg.norm(p - JARS[target]) > 0.15:
            continue
        g = predict(p, v)
        stable = stable + 1 if g == last else 1
        last = g
        if stable >= 3 and g != asked and warned_at is None:
            warned_at = ts[k] + latency
    lead = (contact_t - warned_at) if warned_at is not None else None
    touch_named = latency + rng.uniform(0, 1 / 30)  # B: hand stops on the jar -> name heard after the pipeline
    return lead, touch_named


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    res = {}
    for lat in (0.10, 0.15, 0.25):
        leads, false_warn = [], 0
        for _ in range(3000):
            lead, _ = trial(rng, lat, True)
            leads.append(lead)
        for _ in range(3000):
            lead, _ = trial(rng, lat, False)
            false_warn += lead is not None
        L = np.array([l if l is not None else -np.inf for l in leads])
        key = f"pipeline latency {int(lat * 1000)} ms"
        res[key] = {
            "A_warned_before_contact_pct": round(100 * float(np.mean(L > 0)), 1),
            "A_warned_>=200ms_before_contact_pct": round(100 * float(np.mean(L >= 0.2)), 1),
            "A_warned_>=300ms_before_contact_pct": round(100 * float(np.mean(L >= 0.3)), 1),
            "A_median_lead_ms": round(1000 * float(np.median(L[np.isfinite(L)])), 0) if np.isfinite(L).any() else None,
            "A_false_warnings_on_correct_reaches_pct": round(100 * false_warn / 3000, 1),
            "B_name_heard_after_touch_ms": round(1000 * (lat + 1 / 60), 0),
            "B_before_lift_if_touch_to_lift_300ms": lat + 1 / 60 < 0.30,
        }
        print(f"## {key}")
        for k, v in res[key].items():
            print(f"   {k}: {v}")
    (ROOT / "reports" / "poc16_reach_catch.json").write_text(json.dumps(res, indent=2))
