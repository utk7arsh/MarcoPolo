"""Fidelity tests for the audio side: Apple's renderer as extracted, and the simulated listener.

Run: .venv/bin/python -m pytest -q validation/test_audio_emulators.py
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT / "emulators" / "audio"), str(ROOT / "emulators" / "listener")]
from features import itd_us  # noqa: E402
from hrir_io import load_apple  # noqa: E402

A = load_apple("hrtfhq", trim=(0, 512))


def pick(h, az, el=0, dist=None):
    m = (h["az"] == az) & (h["el"] == el)
    if dist is not None:
        m &= h["dist"] == dist
    return np.where(m)[0][0]


def test_apple_itd_is_human_like():
    """Low-frequency ITD at 90 deg within the range of 12 measured human heads (656-776 us)."""
    itd90 = itd_us(A["ir"][pick(A, 90)], A["fs"])
    assert 620 < itd90 < 800, itd90
    # monotonic over the frontal quadrant and correct sign
    vals = [itd_us(A["ir"][pick(A, a)], A["fs"]) for a in (0, 15, 30, 45, 60, 90)]
    assert all(b > a for a, b in zip(vals, vals[1:])), vals
    assert itd_us(A["ir"][pick(A, -90)], A["fs"]) < -620


def test_apple_has_front_back_spectral_cue():
    """Front sources are brighter (8-16 kHz) than their back mirror images (pinna shadow)."""
    f = np.fft.rfftfreq(1024, 1 / A["fs"])
    band = (f > 8000) & (f < 16000)
    for fa, ba in ((30, 150), (0, -180)):
        F = np.abs(np.fft.rfft(A["ir"][pick(A, fa)][1], 1024))[band]
        B = np.abs(np.fft.rfft(A["ir"][pick(A, ba)][1], 1024))[band]
        assert 20 * np.log10(F.mean() / B.mean()) > 2.0


def test_apple_default_distance_model_clamps_inside_1m():
    """Default inverse-distance attenuation: -6 dB per doubling beyond 1 m, NO gain increase inside 1 m."""
    D = load_apple("hrtfhq", subdir="apple_hrir/dist", trim=(0, 512))
    lev = {d: 10 * np.log10((D["ir"][pick(D, 0, 0, d)] ** 2).sum()) for d in (0.25, 0.5, 1.0, 2.0, 4.0)}
    assert abs(lev[0.25] - lev[1.0]) < 0.1 and abs(lev[0.5] - lev[1.0]) < 0.1
    assert abs((lev[1.0] - lev[2.0]) - 6.0) < 0.3 and abs((lev[2.0] - lev[4.0]) - 6.0) < 0.3


def test_apple_engine_dynamic_rotation_recorded():
    """Recorded result of validation/v_apple_dynamic_headtracking.py: +yaw = head turns right; no clicks."""
    r = json.loads((ROOT / "reports" / "v_apple_dynamic_headtracking.json").read_text())
    for k in ("10ms_updates", "25Hz_updates"):
        assert r[k]["itd_rms_err_us_if_positive_yaw_turns_right"] < 80
        assert r[k]["itd_rms_err_us_if_positive_yaw_turns_left"] > 500
        assert r[k]["max_step_over_p99_9_step"] < 3
    assert r["listener_vs_source_rotation_corr"] > 0.999


def test_listener_matches_published_localization():
    """Calibrated + out-of-sample targets (Oberem 2020, Wenzel 1993, Begault 2001, Middlebrooks 1999)."""
    r = json.loads((ROOT / "reports" / "v_listener_model.json").read_text())
    st = r["static_all_subjects"]
    assert 5 <= st["individual"]["front_back_pct"] <= 15
    assert 20 <= st["apple_generic"]["front_back_pct"] <= 45
    assert 8 <= st["individual"]["lateral_rms_deg"] <= 16
    assert st["apple_generic"]["local_polar_rms_deg"] > st["individual"]["local_polar_rms_deg"]
    # out of sample: head movement must cut generic-HRTF reversals by at least half, to ~5-10 %
    assert r["front_back_pct_generic_headmove_2s"] < 0.5 * r["front_back_pct_generic_static_2s"]
    assert 2 <= r["front_back_pct_generic_headmove_2s"] <= 12
