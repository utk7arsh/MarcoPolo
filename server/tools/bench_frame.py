"""Does the real pipeline keep up with 1 frame per second? Times everything the server does with one frame (decode,
OWLv2 detection, the presence check, 3D placement, the world model, the room map and the dashboard feeds) on a
recorded session, for growing numbers of registered items. Registration photos are crops of the session's own
truth items (more items than that reuse them under new names).

  python tools/bench_frame.py data/sessions/arkitscenes-41069021 --items 1 5 10 20
"""
import argparse
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from marco import codec  # noqa: E402
from marco.brain import RealBrain  # noqa: E402
from marco.session import Session  # noqa: E402
from run_offline import timing_summary, truth_crops  # noqa: E402


def bench(path, counts=(1, 5, 10), detector=None, warmup=2, rounds=2, min_px=80):
    ses = Session(path)
    if detector is None:
        from marco.perception.detector import OwlDetector
        detector = OwlDetector()
    crops = list(truth_crops(ses, min_px=min_px).items())
    if not crops:
        raise SystemExit("the session has no truth items in view to register")
    rows = []
    for n in counts:
        brain = RealBrain(detector)
        detector.items.clear()
        for i in range(n):
            name, crop = crops[i % len(crops)]
            label = name if i < len(crops) else f"{name} {i // len(crops) + 1}"
            it = brain.world.add_item(label)
            detector.register(it.item_id, label if label in getattr(detector, "truth", {label: 0}) else name, crop, gate=False)
        times = []
        for r in range(rounds):
            for j, meta in enumerate(ses.frames):
                jpeg, d, c = ses.frame_bytes(meta)
                t0 = time.perf_counter()
                brain.on_frame(meta, jpeg, codec.decode_depth(d), codec.decode_conf(c))
                if r > 0 or j >= warmup:                         # the first frames warm the GPU up
                    times.append(time.perf_counter() - t0)
        rows.append(dict(items=n, device=str(getattr(detector, "dev", "n/a")), **timing_summary(times)))
    return rows


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("session")
    ap.add_argument("--items", nargs="+", type=int, default=[1, 5, 10])
    ap.add_argument("--rounds", type=int, default=2)
    a = ap.parse_args()
    for row in bench(a.session, a.items, rounds=a.rounds):
        print(json.dumps(row))
