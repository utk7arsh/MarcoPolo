"""Bayesian model of a human listener localizing a virtual source.

The source is RENDERED with one HRTF (Apple's generic HRTFHQ) and INTERPRETED with the
listener's own ears (a measured human HRTF from the ARI database). The mismatch between the
two is what makes generic-HRTF spatial audio imperfect (front/back reversals, polar errors).

Static model: noisy features of the rendered sound -> likelihood over candidate directions
using the listener's own templates (cf. Reijniers et al. 2014; Barumerli et al. 2023).
Dynamic model: evidence from successive sounds is combined in a world frame using the
listener's knowledge of their own head rotation (cf. McLachlan et al. 2021, active
localization), so head turns resolve front/back ambiguity.
"""
from dataclasses import dataclass

import numpy as np

from features import AZ_STEP, GRID_AZ, GRID_EL


@dataclass
class Noise:
    itd_us: float = 50.0      # internal ITD noise (one snapshot)
    ild_db: float = 3.0       # per-band ILD noise
    spec_db: float = 3.0      # per-band spectral-gradient noise
    motor_deg: float = 6.0    # response (pointing) scatter
    spec_weight: float = 1.0  # weight of monaural spectral cues


def _area_prior():
    w = np.cos(np.radians(GRID_EL))[:, None] * np.ones((1, len(GRID_AZ)))
    return np.log(w / w.sum())


LOG_PRIOR = _area_prior()


class Listener:
    def __init__(self, render_feats, own_feats, noise: Noise, rng):
        self.R, self.O, self.n, self.rng = render_feats, own_feats, noise, rng

    # -- features of what is rendered at an arbitrary head-relative direction (bilinear interp)
    def rendered(self, az, el):
        R = self.R
        el = float(np.clip(el, GRID_EL[0], GRID_EL[-1]))
        az = (az + 180.0) % 360.0 - 180.0
        ia = (az - GRID_AZ[0]) / AZ_STEP
        a0 = int(np.floor(ia)) % len(GRID_AZ); a1 = (a0 + 1) % len(GRID_AZ); fa = ia - np.floor(ia)
        e1 = int(np.searchsorted(GRID_EL, el)); e1 = min(max(e1, 1), len(GRID_EL) - 1); e0 = e1 - 1
        fe = (el - GRID_EL[e0]) / (GRID_EL[e1] - GRID_EL[e0])

        def lerp(F):
            return ((1 - fe) * ((1 - fa) * F[e0, a0] + fa * F[e0, a1]) + fe * ((1 - fa) * F[e1, a0] + fa * F[e1, a1]))
        return lerp(R["itd"]), lerp(R["ild"]), lerp(R["spec"])

    def observe(self, az, el):
        """One noisy auditory snapshot of a source rendered at head-relative (az, el)."""
        itd, ild, spec = self.rendered(az, el)
        r, n = self.rng, self.n
        return (itd + r.normal(0, n.itd_us), ild + r.normal(0, n.ild_db, ild.shape),
                spec + r.normal(0, n.spec_db, spec.shape))

    def loglik(self, obs):
        """Log-likelihood over the head-frame grid (n_el, n_az) given a snapshot."""
        itd, ild, spec = obs
        O, n = self.O, self.n
        ll = -0.5 * ((O["itd"] - itd) / n.itd_us) ** 2
        ll -= 0.5 * np.sum(((O["ild"] - ild) / n.ild_db) ** 2, axis=-1)
        ll -= 0.5 * n.spec_weight * np.sum(((O["spec"] - spec) / n.spec_db) ** 2, axis=(-1, -2))
        return ll

    def localize_static(self, az, el):
        """Single-sound localization response (MAP + motor noise), head frame."""
        lp = self.loglik(self.observe(az, el)) + LOG_PRIOR
        i = np.unravel_index(np.argmax(lp), lp.shape)
        raz, rel = GRID_AZ[i[1]], GRID_EL[i[0]]
        return add_motor_noise(raz, rel, self.n.motor_deg, self.rng)


def add_motor_noise(az, el, sd, rng):
    v = _vec(az, el) + rng.normal(0, np.radians(sd), 3)
    v /= np.linalg.norm(v)
    return np.degrees(np.arctan2(v[0], -v[2])), np.degrees(np.arcsin(np.clip(v[1], -1, 1)))


def _vec(az, el):
    a, e = np.radians(az), np.radians(el)
    return np.array([np.cos(e) * np.sin(a), np.sin(e), -np.cos(e) * np.cos(a)])


def lateral_polar(az, el):
    """Interaural-polar coordinates: lateral in [-90,90] (+ right), polar in [-90,270) (0 front, 90 up, 180 back)."""
    x, y, z = _vec(az, el)
    lat = np.degrees(np.arcsin(np.clip(x, -1, 1)))
    pol = np.degrees(np.arctan2(y, -z))
    if pol < -90:
        pol += 360
    return lat, pol


def shift_world(ll_head, yaw_deg):
    """Express a head-frame map in the world frame for head yaw `yaw_deg` (+ = right).

    World azimuth = head azimuth + yaw, so the map shifts right by yaw/AZ_STEP columns.
    """
    s = yaw_deg / AZ_STEP
    k = int(np.floor(s)); f = s - k
    return (1 - f) * np.roll(ll_head, k, axis=1) + f * np.roll(ll_head, k + 1, axis=1)


class WorldBelief:
    """Accumulates auditory evidence in a world (yaw) frame, as the listener turns.

    A "look" is one calibrated auditory snapshot (~0.3 s of broadband sound). Looks taken from
    nearly the same head-relative direction as a recent look carry no new information and are
    skipped, so long static sounds don't become unrealistically precise; new information comes
    from head movement (dynamic cues), which is what resolves front/back reversals.
    """

    def __init__(self, listener: Listener, decay_tau_s=4.0, same_dir_deg=5.0, memory_s=1.0,
                 later_look_weight=0.1, yaw_noise_deg=5.0):
        self.L = listener
        self.beta = later_look_weight   # humans integrate successive looks sub-optimally
        self.yaw_sd = yaw_noise_deg     # error in the listener's sense of own head rotation
        self.logb = LOG_PRIOR.copy()
        self.tau = decay_tau_s
        self.same = same_dir_deg
        self.mem = memory_s
        self.recent = []  # (t, rendered_az, rendered_el)
        self.t_last = None
        self.n_looks = 0

    def decay_to(self, t):
        if self.t_last is not None and self.tau:
            k = np.exp(-(t - self.t_last) / self.tau)
            self.logb = LOG_PRIOR + k * (self.logb - LOG_PRIOR)
        self.t_last = t

    def look(self, t, rendered_az, rendered_el, perceived_head_yaw):
        """Add one snapshot. rendered_*: head-relative direction actually rendered."""
        self.recent = [r for r in self.recent if t - r[0] < self.mem]
        for _, a, e in self.recent:
            if abs((a - rendered_az + 180) % 360 - 180) < self.same and abs(e - rendered_el) < self.same:
                return False
        self.decay_to(t)
        ll = self.L.loglik(self.L.observe(rendered_az, rendered_el))
        w = 1.0 if self.n_looks == 0 else self.beta
        yaw = perceived_head_yaw + (self.L.rng.normal(0, self.yaw_sd) if self.yaw_sd else 0.0)
        self.logb += w * shift_world(ll, yaw)
        self.recent.append((t, rendered_az, rendered_el))
        self.n_looks += 1
        return True

    def constrain(self, mask_world, strength=8.0):
        """Fold in a categorical cue (e.g. 'you are facing it'): mask=True where consistent."""
        self.logb = self.logb + np.where(mask_world, 0.0, -strength)

    def posterior(self):
        p = np.exp(self.logb - self.logb.max())
        return p / p.sum()

    def map_world(self):
        p = self.posterior()
        i = np.unravel_index(np.argmax(p), p.shape)
        return GRID_AZ[i[1]], GRID_EL[i[0]]

    def azimuth_marginal(self):
        return self.posterior().sum(axis=0)
