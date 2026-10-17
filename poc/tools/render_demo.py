"""Render listenable binaural demos with Apple's own HRTF (HRIRs extracted from AVAudioEnvironmentNode).

Outputs to reports/audio/ (48 kHz stereo WAV). Listen on headphones with macOS "Spatialize Stereo"
turned OFF (Control Centre > Sound/AirPods), otherwise macOS re-spatialises the file.
  01_direction_tour.wav     the call from 8 directions around you (front, front-right, right, ...)
  02_doc_design_1hz.wav     doc design: call once a second, as heard by a simulated user turning to it
  03_recommended_beacon.wav 2.5 Hz beacon with "facing it" / "behind you" variants, faster when near,
                            and a "within reach" chime, along the same kind of simulated walk
The first one is the most useful: it lets the team hear Apple's generic HRTF (and front/back
confusion) before writing any iOS code.
"""
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "emulators" / "audio"), str(ROOT / "pocs" / "poc5_guidance"), str(ROOT / "emulators" / "listener")]
from hrir_io import load_apple  # noqa: E402

FS = 48000
H = load_apple("hrtfhq", trim=(0, 256))
OUT = ROOT / "reports" / "audio"
OUT.mkdir(parents=True, exist_ok=True)
RNG = np.random.default_rng(3)


def hrir(az, el):
    az = (az + 180) % 360 - 180
    i = np.argmin(np.abs((H["az"] - az + 180) % 360 - 180) + 2.0 * np.abs(H["el"] - el))
    return H["ir"][i]


def env(n, a=0.002, tau=0.05):
    t = np.arange(n) / FS
    return np.minimum(t / a, 1) * np.exp(-t / tau)


def call(kind="base", dur=0.15):
    """Broadband 'Polo' call: a soft two-partial pluck plus a short airy noise burst for localisation."""
    n = int(dur * FS)
    t = np.arange(n) / FS
    f0 = {"base": 1175.0, "lock": 1568.0, "behind": 587.0}[kind]
    tone = 0.5 * np.sin(2 * np.pi * f0 * t) + 0.25 * np.sin(2 * np.pi * 2 * f0 * t) + 0.12 * np.sin(2 * np.pi * 3.01 * f0 * t)
    noise = RNG.standard_normal(n)
    spec = np.fft.rfft(noise)
    f = np.fft.rfftfreq(n, 1 / FS)
    lo, hi = (2000, 14000) if kind != "behind" else (300, 1800)
    spec[(f < lo) | (f > hi)] = 0
    noise = np.fft.irfft(spec, n)
    noise /= np.abs(noise).max() + 1e-9
    x = 0.6 * tone * env(n, tau=0.06) + 0.8 * noise * env(n, a=0.001, tau=0.03)  # mostly broadband: localises best
    if kind == "lock":  # "you're facing it": a quick double ding
        x = x + np.r_[np.zeros(int(0.07 * FS)), x[: n - int(0.07 * FS)]] * 0.8
    return 0.3 * x / np.abs(x).max()


def reach_chime():
    out = np.zeros(int(0.5 * FS))
    for k, f in enumerate((1047, 1319, 1568)):
        n = int(0.18 * FS)
        t = np.arange(n) / FS
        s = int(k * 0.11 * FS)
        out[s:s + n] += 0.25 * np.sin(2 * np.pi * f * t) * env(n, tau=0.08)
    return out


def place(buf, x, start, az, el, gain=1.0):
    h = hrir(az, el)
    for c in range(2):
        y = np.convolve(x, h[c]) * gain
        e = min(len(buf[c]), start + len(y))
        buf[c, start:e] += y[: e - start]


def tour():
    names = ["front", "front-right", "right", "back-right", "back", "back-left", "left", "front-left"]
    buf = np.zeros((2, int(1.2 * FS * len(names) * 2)))
    pos = 0
    for k, nm in enumerate(names):
        az = 45 * k
        for r in range(3):
            place(buf, call(), pos + int(r * 0.35 * FS), az, 0)
        pos += int(2.0 * FS)
    return buf[:, :pos]


def walk_demo(strategy_name):
    import sim
    st = [s for s in sim.STRATEGIES if s.name == strategy_name][0]
    for seed in range(50):
        r = sim.run_trial(st, "nh5", 135.0, 3.0, np.random.default_rng(seed), keep_log=True)
        if r.arrived:
            break
    log = np.array(r.log)
    T = log[-1, 0] + 1.0
    buf = np.zeros((2, int(T * FS) + FS))
    tgt = 3.0 * np.array([np.sin(np.radians(135.0)), np.cos(np.radians(135.0))])
    t, next_call = 0.0, 0.0
    while t < log[-1, 0]:
        i = min(int(t / sim.DT), len(log) - 1)
        _, hy, _, x, y = log[i]
        d = tgt - np.array([x, y])
        dist = float(np.hypot(*d))
        rel = (np.degrees(np.arctan2(d[0], d[1])) - hy + 180) % 360 - 180
        el = np.degrees(np.arctan2(0.75 - 1.6, max(dist, 0.3)))
        kind = "base"
        if st.lock_deg:
            kind = "lock" if abs(rel) < st.lock_deg else ("behind" if abs(rel) > st.behind_deg else "base")
        gain = min(1.0, 1.0 / max(dist, 0.5))
        place(buf, call(kind), int(t * FS), rel, el, gain)
        period = st.period(dist) if callable(st.period) else st.period
        t += period
    place(buf, reach_chime(), int(log[-1, 0] * FS), 0, -30)
    return buf


if __name__ == "__main__":
    for name, b in [("01_direction_tour", tour()), ("02_doc_design_1hz", walk_demo("call_1hz")),
                    ("03_recommended_beacon", walk_demo("beacon_2_5hz_lock_behind"))]:
        b = b / (np.abs(b).max() + 1e-9) * 0.8
        sf.write(OUT / f"{name}.wav", b.T, FS)
        print(name, f"{b.shape[1] / FS:.1f} s")
