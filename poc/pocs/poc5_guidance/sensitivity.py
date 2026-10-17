"""POC 5b: are the strategy rankings robust to latency, tracking error, pace and listener ability?"""
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import sim  # noqa: E402

KEY = ["call_1hz", "call_1hz_tempo", "continuous", "call_1hz_lock_behind", "beacon_2_5hz_lock_behind", "clock_then_beacon"]
STRATS = [s for s in sim.STRATEGIES if s.name in KEY]
CASES = [
    ("latency 50 ms", dict(latency=0.05)),
    ("latency 350 ms", dict(latency=0.35)),
    ("latency 500 ms", dict(latency=0.5)),
    ("yaw error 10 deg", dict(yaw_bias=10.0)),
    ("yaw error 20 deg", dict(yaw_bias=20.0)),
    ("slow walker 0.4 m/s", dict(walk_speed=0.4)),
    ("fast walker 0.9 m/s", dict(walk_speed=0.9)),
]

if __name__ == "__main__":
    out = {}
    base_noise = sim.NOISE
    for label, kw in CASES + [("poorer listener (1.5x noise)", "noise")]:
        if kw == "noise":
            sim.NOISE.itd_us, sim.NOISE.ild_db, sim.NOISE.spec_db = 90, 7.5, 18.0
            kw = {}
        rows = sim.summarize(sim.run_all(STRATS, n_targets=16, **kw))
        out[label] = rows
        print(f"\n## {label}")
        for k in KEY:
            r = rows[k]
            print(f"  {k:28} ok<=15s {r['success_within_15s_pct']:5.1f}%  median {r['median_time_to_reach_s']:4.1f}s  p90 {r['p90_time_to_reach_s']:4.1f}s  pathEff {r['path_efficiency_pct']:5.1f}%", flush=True)
    (sim.ROOT / "reports" / "poc5_guidance_sensitivity.json").write_text(json.dumps(out, indent=2))
