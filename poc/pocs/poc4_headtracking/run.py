"""POC 4: Which way of computing head direction keeps the "Polo" fixed in the room with a chest phone?

Truth: head yaw (world) = torso yaw + head-on-torso yaw. The chest phone's ARKit heading tracks
the torso (accurate: ~0.5-1.7 deg rotation error); the AirPods report head yaw relative to an
arbitrary start, drifting (no magnetometer). Pipelines compared (what the renderer is told):

  phone_only        listener yaw = ARKit torso yaw (no AirPods)
  airpods_only      listener yaw = AirPods yaw + start alignment (drifts)
  fused (ours)      listener yaw = AirPods yaw + offset, offset slowly pulled toward the torso
                    heading while the head is roughly forward (complementary filter, tau 20 s);
                    needs no entitlement (CMHeadphoneMotionManager + ARKit)
  apple_auto_rel    Apple automatic head tracking IF it reports head relative to the iPhone,
                    with listener yaw = ARKit torso yaw (correct composition)
  apple_auto_abs    Apple automatic head tracking IF it reports head relative to a start heading,
                    with listener yaw = ARKit torso yaw (body turns counted twice)
Metric: error of the rendered head yaw (deg); requirement from POC 5: < 5 deg most of the time.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "emulators" / "motion"))
from airpods import AirPodsModel, AirPodsStream, human_session  # noqa: E402


def wrap(a):
    return (np.asarray(a) + 180.0) % 360.0 - 180.0


def run(seed, model: AirPodsModel, tau=5.0, gate_rate=30.0, gate_hot=15.0):  # tuned: see sweep in report
    rng = np.random.default_rng(seed)
    t, torso, hot, walking = human_session(rng)
    head = torso + hot
    arkit_torso = torso + np.cumsum(rng.normal(0, 0.02, len(t)))  # ~1 deg wander over minutes
    st = AirPodsStream(model, rng)
    samples = st.samples(t, head)
    # Sample-and-hold of the latest delivered AirPods yaw at each render tick.
    deliv = np.array([s[0] for s in samples])
    reps = np.array([s[2] for s in samples])
    idx = np.searchsorted(deliv, t, side="right") - 1
    have = idx >= 0
    ap = np.where(have, reps[np.clip(idx, 0, None)], np.nan)
    # Fused estimator.
    off = arkit_torso[0] - (ap[have][0] if have.any() else 0)
    fused = np.full(len(t), np.nan)
    prev = None
    for i in range(len(t)):
        if np.isnan(ap[i]):
            fused[i] = arkit_torso[i]
            continue
        est = ap[i] + off
        rate = 0 if prev is None else abs(wrap(ap[i] - prev)) / (t[1] - t[0])
        prev = ap[i]
        hot_est = wrap(est - arkit_torso[i])
        if rate < gate_rate and abs(hot_est) < gate_hot:
            off += (t[1] - t[0]) / tau * wrap(arkit_torso[i] - (ap[i] + off))
        fused[i] = ap[i] + off
    airpods_only = ap + (torso[0] - (ap[have][0] if have.any() else 0))
    # Apple automatic (unknown semantics): system tracks head relative to phone with ~2 deg error and
    # the same delivery latency; or relative to the start heading (drifting like raw AirPods).
    lag = int(round(model.latency_ms / 1000 / (t[1] - t[0])))
    hot_lagged = np.r_[np.full(lag, hot[0]), hot[:-lag]] if lag else hot
    apple_rel = arkit_torso + hot_lagged + rng.normal(0, 1.0, len(t))
    apple_abs = arkit_torso + (airpods_only - torso[0])
    # Ray-Ban Meta glasses' fused orientation (DAT Motion, with magnetometer): no drift, but indoor
    # magnetic disturbance biases heading (17.4 deg RMSE with state-of-the-art mitigation, NAVI 2024).
    # Modelled as a bias that wanders as you move through the home (OU, sd 17.4 deg, tau 5 s while walking).
    mag_bias = np.zeros(len(t)); dtt = t[1] - t[0]
    for i in range(1, len(t)):
        a = dtt / 5.0 if walking[i] else 0.0
        mag_bias[i] = mag_bias[i - 1] - a * mag_bias[i - 1] + (17.4 * np.sqrt(2 * a) * rng.normal() if a else 0.0)
    glasses_mag = head + mag_bias + rng.normal(0, 1.0, len(t))
    pipelines = dict(phone_only=arkit_torso, airpods_only=airpods_only, fused=fused,
                     apple_auto_rel=apple_rel, apple_auto_abs=apple_abs, glasses_compass_only=glasses_mag)
    out = {}
    for k, v in pipelines.items():
        e = np.abs(wrap(v - head))
        e = e[~np.isnan(e)]
        out[k] = dict(median=float(np.median(e)), p90=float(np.percentile(e, 90)), pct_under_5=float(100 * np.mean(e < 5)),
                      last_minute_median=float(np.median(e[-int(60 / (t[1] - t[0])):])))
    return out


def aggregate(runs):
    keys = runs[0].keys()
    return {k: {m: float(np.median([r[k][m] for r in runs])) for m in runs[0][k]} for k in keys}


if __name__ == "__main__":
    res = {}
    cases = {
        "nominal (drift 3 deg/min, latency 50 ms)": AirPodsModel(),
        "low drift 1 deg/min": AirPodsModel(yaw_drift_deg_per_min=1.0),
        "high drift 10 deg/min": AirPodsModel(yaw_drift_deg_per_min=10.0),
        "latency 150 ms": AirPodsModel(latency_ms=150.0),
    }
    for name, m in cases.items():
        res[name] = aggregate([run(s, m) for s in range(12)])
        print(f"\n## {name}   (head-yaw error over a 5-min session, median of 12 sessions)")
        for k, v in res[name].items():
            print(f"  {k:16} median {v['median']:5.1f} deg  p90 {v['p90']:6.1f} deg  <5deg {v['pct_under_5']:5.1f}%  last-minute median {v['last_minute_median']:5.1f}")
    (ROOT / "reports" / "poc4_headtracking.json").write_text(json.dumps(res, indent=2))
