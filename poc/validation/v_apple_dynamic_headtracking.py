"""Validate the manual head-tracking path on Apple's real engine (AVAudioEnvironmentNode).

1. Renders a world-fixed noise source while listenerAngularOrientation follows a head-yaw
   trajectory, at 10 ms updates and at 25 Hz (AirPods rate) updates.
2. Estimates the running ITD/ILD of the output and checks it against the static HRTF
   at the expected head-relative azimuth, which also pins down the yaw sign convention.
3. Checks for discontinuities (clicks) at update boundaries.
"""
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from scipy.signal import butter, sosfiltfilt

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "emulators" / "audio"))
from hrir_io import load_apple  # noqa: E402

FS = 48000
BIN = ROOT / "emulators" / "apple_audio" / "dynamic_render"
TMP = ROOT / "data" / "tmp"
TMP.mkdir(parents=True, exist_ok=True)


def trajectory(block, update_hz=None):
    dt = block / FS
    segs = [(0.5, 0, 0), (1.0, 0, 60), (0.5, 60, 60), (1.0, 60, -60), (0.5, -60, -60), (0.5, -60, 0), (0.5, 0, 0)]
    t_all, y_all = [], []
    t0 = 0.0
    for dur, a, b in segs:
        n = int(round(dur / dt))
        y_all.extend(np.linspace(a, b, n, endpoint=False) if a != b else [a] * n)
        t_all.extend(t0 + np.arange(n) * dt)
        t0 += n * dt
    t = np.array(t_all)
    y = np.array(y_all)
    true = y.copy()
    if update_hz:
        # Sample-and-hold at the AirPods update rate.
        k = np.floor(t * update_hz) / update_hz
        y = np.interp(k, t, true)
    return t, y.astype(np.float32), true


def render(yaws, block, mode="listener", src_az=0.0):
    f_in = TMP / f"yaw_{mode}_{block}.f32"
    f_out = TMP / f"out_{mode}_{block}.f32"
    yaws.astype("<f4").tofile(f_in)
    subprocess.run([str(BIN), str(f_in), str(block), str(f_out), str(src_az), "2", "noise", mode], check=True, capture_output=True)
    return np.fromfile(f_out, dtype="<f4").reshape(-1, 2).T.astype(np.float64)


def running_cues(lr, win=0.02, hop=0.01):
    sos = butter(4, 1500, "low", fs=FS, output="sos")
    L, R = sosfiltfilt(sos, lr[0]), sosfiltfilt(sos, lr[1])
    w, h = int(win * FS), int(hop * FS)
    ts, itds, ilds = [], [], []
    maxlag = 48
    for s in range(0, lr.shape[1] - w, h):
        a, b = L[s:s + w], R[s:s + w]
        xc = [np.dot(a[maxlag:-maxlag], b[maxlag + k: len(b) - maxlag + k]) for k in range(-maxlag, maxlag + 1)]
        lag = np.argmax(xc) - maxlag  # >0: right channel lags... computed below
        itds.append(-lag / FS * 1e6)  # >0 means left later => source on the right
        ilds.append(10 * np.log10(np.sum(lr[0, s:s + w] ** 2) / np.sum(lr[1, s:s + w] ** 2)))
        ts.append((s + w / 2) / FS)
    return np.array(ts), np.array(itds), np.array(ilds)


def static_table():
    h = load_apple("hrtfhq", trim=(0, 512))
    sel = h["el"] == 0
    az = h["az"][sel]
    noise = np.random.default_rng(0).standard_normal(FS)
    itd, ild = [], []
    for i in np.where(sel)[0]:
        lr = np.stack([np.convolve(noise, h["ir"][i][c])[:FS] for c in range(2)])
        _, it, il = running_cues(lr, win=0.2, hop=0.2)
        itd.append(np.median(it))
        ild.append(np.median(il))
    o = np.argsort(az)
    return az[o], np.array(itd)[o], np.array(ild)[o]


def main():
    az_tab, itd_tab, ild_tab = static_table()
    results = {}
    for label, block, upd in [("10ms_updates", 480, None), ("25Hz_updates", 480, 25)]:
        t, yaws, true = trajectory(block, upd)
        lr = render(yaws, block)
        ts, itd, ild = running_cues(lr)
        yaw_at = np.interp(ts, t + block / FS / 2, true)
        # Hypothesis A: +yaw turns head to the RIGHT => rel = src - yaw. B: +yaw turns LEFT => rel = src + yaw.
        exp_a = np.interp(-yaw_at, az_tab, itd_tab)
        exp_b = np.interp(+yaw_at, az_tab, itd_tab)
        err_a = np.sqrt(np.mean((itd - exp_a) ** 2))
        err_b = np.sqrt(np.mean((itd - exp_b) ** 2))
        # Click check: max sample-to-sample jump relative to typical signal step
        d = np.abs(np.diff(lr, axis=1))
        click_ratio = float(d.max() / np.percentile(d, 99.9))
        results[label] = dict(itd_rms_err_us_if_positive_yaw_turns_right=float(err_a),
                              itd_rms_err_us_if_positive_yaw_turns_left=float(err_b),
                              max_step_over_p99_9_step=click_ratio)
        if label == "10ms_updates":
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            fig, ax = plt.subplots(2, 1, figsize=(9, 5), sharex=True)
            ax[0].plot(t, true, label="listener yaw (deg)")
            ax[0].set_ylabel("yaw (deg)")
            ax[0].legend()
            ax[1].plot(ts, itd, ".", ms=3, label="measured ITD from Apple engine output")
            ax[1].plot(ts, exp_b if err_b < err_a else exp_a, label="expected ITD (static HRTF, world-fixed source)")
            ax[1].set_ylabel("ITD (us, +=right)")
            ax[1].set_xlabel("time (s)")
            ax[1].legend(fontsize=8)
            fig.tight_layout()
            fig.savefig(ROOT / "reports" / "figures" / "v_apple_dynamic_headtracking.png", dpi=120)
    # Equivalence: rotating the listener vs moving the source opposite
    t, yaws, true = trajectory(480)
    lr_l = render(yaws, 480, "listener")
    lr_s = render(-yaws if results["10ms_updates"]["itd_rms_err_us_if_positive_yaw_turns_left"] < results["10ms_updates"]["itd_rms_err_us_if_positive_yaw_turns_right"] else yaws, 480, "source")
    results["listener_vs_source_rotation_corr"] = float(np.corrcoef(lr_l.ravel(), lr_s.ravel())[0, 1])
    print(json.dumps(results, indent=2))
    (ROOT / "reports" / "v_apple_dynamic_headtracking.json").write_text(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()


def engine_lag_ms():
    """Estimate how far the engine's rendered direction lags the commanded listener yaw."""
    az_tab, itd_tab, _ = static_table()
    t, yaws, true = trajectory(480)
    lr = render(yaws, 480)
    ts, itd, _ = running_cues(lr, win=0.01, hop=0.0025)
    best = None
    for lag in np.arange(0, 0.2, 0.0025):
        yaw_at = np.interp(ts - lag, t + 0.005, true)
        e = np.sqrt(np.mean((itd - np.interp(-yaw_at, az_tab, itd_tab)) ** 2))
        if best is None or e < best[1]:
            best = (lag, e)
    return best[0] * 1000, best[1]


if __name__ == "__main__" and "--lag" in sys.argv:
    lag, e = engine_lag_ms()
    print(f"engine orientation smoothing lag ~ {lag:.1f} ms (ITD rms err {e:.0f} us at best lag)")
