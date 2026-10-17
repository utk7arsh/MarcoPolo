"""Emulated CMHeadphoneMotionManager stream (AirPods Pro/Max/3+), from research/airpods_facts.md.

What a real app receives:
  * CMDeviceMotion at ~25 Hz (40 ms), not configurable; small timestamp jitter
  * attitude: gravity-referenced pitch/roll; yaw relative to an arbitrary reference (orientation
    when updates started) -- AirPods have no magnetometer, so yaw drifts with gyro bias
  * delivered to the app after a transport/processing delay (not published; parameter)
  * rare dropouts (Bluetooth), and a re-zero of yaw when another app grabs spatial audio
Unpublished quantities (drift rate, latency, noise) are parameters; POCs sweep them.
"""
from dataclasses import dataclass

import numpy as np


@dataclass
class AirPodsModel:
    rate_hz: float = 25.0
    jitter_ms: float = 3.0
    latency_ms: float = 50.0          # sensor -> app callback (unknown; swept)
    yaw_drift_deg_per_min: float = 3.0  # typical magnitude of gyro-bias yaw drift (unknown; swept)
    noise_deg: float = 0.3
    dropout_per_min: float = 0.5
    dropout_s: float = 0.6


class AirPodsStream:
    def __init__(self, model: AirPodsModel, rng):
        self.m, self.rng = model, rng
        self.bias = rng.choice([-1, 1]) * model.yaw_drift_deg_per_min / 60.0  # deg/s
        self.ref_yaw = None
        self.drift = 0.0
        self.next_t = 0.0
        self.drop_until = -1.0

    def samples(self, t_grid, head_yaw_true, head_pitch_true=None):
        """Yield (t_delivered, t_sample, yaw_reported) for a true head-yaw trajectory (deg, world)."""
        m, r = self.m, self.rng
        out = []
        dt_grid = np.diff(t_grid, prepend=t_grid[0])
        t = t_grid[0]
        k = 0
        while True:
            t = self.next_t
            if t > t_grid[-1]:
                break
            yaw = float(np.interp(t, t_grid, head_yaw_true))
            if self.ref_yaw is None:
                self.ref_yaw = yaw
            # bias random-walks slowly around its typical magnitude
            self.bias += r.normal(0, 0.002) - 0.001 * (self.bias - np.sign(self.bias) * m.yaw_drift_deg_per_min / 60)
            self.drift += self.bias / m.rate_hz
            if r.uniform() < m.dropout_per_min / 60 / m.rate_hz:
                self.drop_until = t + m.dropout_s
            if t >= self.drop_until:
                rep = yaw - self.ref_yaw + self.drift + r.normal(0, m.noise_deg)
                out.append((t + m.latency_ms / 1000, t, rep))
            self.next_t = t + 1 / m.rate_hz + r.normal(0, m.jitter_ms / 1000)
            k += 1
        return out


def human_session(rng, dur=300.0, dt=0.02):
    """5 minutes of a blind user at home: walking, turning the body, looking around.

    Returns time grid, torso yaw (world, deg), head-on-torso yaw (deg), walking flag.
    Head-on-torso: mostly near 0 (OU process, ~8 deg sd) with occasional look-arounds up to
    +-70 deg lasting 1-4 s; torso: turns of 30-180 deg every 5-20 s.
    """
    n = int(dur / dt)
    t = np.arange(n) * dt
    torso = np.zeros(n)
    hot = np.zeros(n)
    walking = np.zeros(n, bool)
    next_turn = rng.uniform(3, 10)
    next_look = rng.uniform(2, 6)
    look_end, look_amp = -1, 0.0
    turn = None
    walk_until = 0.0
    for i in range(1, n):
        ti = t[i]
        torso[i] = torso[i - 1]
        if turn is None and ti > next_turn:
            amp = rng.choice([-1, 1]) * rng.uniform(30, 180)
            turn = (ti, torso[i - 1], amp, abs(amp) / rng.uniform(60, 120))
            next_turn = ti + rng.uniform(5, 20)
            walk_until = ti + turn[3] + rng.uniform(2, 8)
        if turn is not None:
            t0, y0, amp, T = turn
            s = min((ti - t0) / T, 1)
            torso[i] = y0 + amp * (10 * s ** 3 - 15 * s ** 4 + 6 * s ** 5)
            if s >= 1:
                turn = None
        walking[i] = (turn is None) and ti < walk_until
        if walking[i]:
            torso[i] += rng.normal(0, 1.5 * np.sqrt(dt))
        if ti > next_look and look_end < ti:
            look_amp = rng.choice([-1, 1]) * rng.uniform(20, 70)
            look_end = ti + rng.uniform(1, 4)
            next_look = look_end + rng.uniform(3, 12)
        target = look_amp if ti < look_end else 0.0
        hot[i] = hot[i - 1] + (target - hot[i - 1]) * min(dt / 0.25, 1) + rng.normal(0, 8 * np.sqrt(2 * dt / 2.0))
        hot[i] = np.clip(hot[i], -80, 80)
    return t, torso, hot, walking
