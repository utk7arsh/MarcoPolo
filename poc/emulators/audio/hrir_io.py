"""Load HRIR sets extracted from Apple's AVAudioEnvironmentNode (see apple_audio/extract_hrir.swift)."""
import json
from pathlib import Path

import numpy as np

DATA = Path(__file__).resolve().parents[2] / "data"


def load_apple(algorithm="hrtfhq", subdir="apple_hrir", trim=(0, None)):
    d = DATA / subdir
    meta = json.loads((d / f"hrir_{algorithm}.json").read_text())
    n = meta["count"]
    frames = meta["entries"][0]["frames"]
    raw = np.fromfile(d / f"hrir_{algorithm}.f32", dtype="<f4").reshape(n, 2, frames)
    az = np.array([e["az"] for e in meta["entries"]], float)
    el = np.array([e["el"] for e in meta["entries"]], float)
    dist = np.array([e["dist"] for e in meta["entries"]], float)
    pre = meta["preDelay"]
    ir = raw[:, :, pre + trim[0]: (pre + trim[1]) if trim[1] else None]
    return dict(ir=ir.astype(np.float64), az=az, el=el, dist=dist, fs=meta["sampleRate"], meta=meta)
