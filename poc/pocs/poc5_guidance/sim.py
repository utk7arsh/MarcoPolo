"""POC 5: which way of "calling" an item gets a blindfolded person to it fastest and most reliably?

A simulated listener (Bayesian localization model calibrated to human data, validated against
head-movement studies; see validation/v_listener_model.py) hears sounds rendered with Apple's
generic HRTF through a head tracker with realistic motion-to-sound latency, turns their head and
body with human kinematics (Brimijoin et al. 2010), and walks at a blind pedestrian's indoor pace.

Each strategy is a sound schedule plus optional categorical cues ("facing it", "behind you") or
speech. All strategies get the same "within reach" announcement, computed from the map distance.
"""
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "emulators" / "listener"))
from cache import load_all  # noqa: E402
from features import GRID_AZ  # noqa: E402
from model import Listener, Noise, WorldBelief  # noqa: E402

NOISE = Noise(itd_us=60, ild_db=5.0, spec_db=12.0, motor_deg=11.0)
FEATS = load_all()
SUBJECTS = [k for k in FEATS if k != "apple"]
DT = 0.02
EAR_HEIGHT = 1.60
REACH = 0.6           # "within reach" announcement radius (m, torso to item, horizontal)
WALK_SPEED = 0.6      # m/s, cautious indoor pace without vision (sensitivity-tested)
HEAD_ON_TORSO_MAX = 60.0


def wrap(a):
    return (a + 180.0) % 360.0 - 180.0


@dataclass
class Strategy:
    name: str
    period: object = 1.0          # seconds between calls, or callable(distance) -> seconds
    dur: float = 0.15             # duration of each call (s); >= period means continuous
    lock_deg: float = 0.0         # on-axis cue half-width (0 = none)
    behind_deg: float = 0.0       # behind cue when |rel| > this (0 = none)
    single: bool = False          # call only once
    clock_speech: bool = False    # speak clock-face direction first
    speech_only: bool = False     # no spatial audio, spoken clock directions only
    magnify: float = 1.0          # azimuth magnification near the front ("supernormal")
    note: str = ""


def tempo_by_distance(d):
    return float(np.clip(0.35 + 0.2 * d, 0.4, 1.0))


STRATEGIES = [
    Strategy("single_call", single=True, note="one 'Polo', then walk on memory"),
    Strategy("call_1hz", period=1.0, note="doc design: 150 ms chime once a second"),
    Strategy("call_1hz_tempo", period=tempo_by_distance, note="1 Hz far, speeding up to 2.5 Hz near"),
    Strategy("pulse_4hz", period=0.25, dur=0.06, note="short broadband clicks 4x/s"),
    Strategy("continuous", period=0.3, dur=0.3, note="continuous broadband texture"),
    Strategy("call_1hz_lock_behind", period=1.0, lock_deg=10, behind_deg=110, note="1 Hz + 'facing it' + 'behind' variants"),
    Strategy("beacon_2_5hz_lock_behind", period=0.4, lock_deg=10, behind_deg=110, note="Soundscape-style beacon"),
    Strategy("clock_then_beacon", period=0.4, lock_deg=10, behind_deg=110, clock_speech=True, note="'2 o'clock, 3 m' then beacon"),
    Strategy("beacon_supernormal", period=0.4, lock_deg=10, behind_deg=110, magnify=1.5, note="beacon + 1.5x azimuth magnification"),
    Strategy("speech_only", speech_only=True, note="spoken clock directions every 2 s, no spatial audio"),
]


def magnify(rel, k):
    if k == 1.0:
        return rel
    a = abs(rel)
    knee = 40.0
    out = k * a if a <= knee else k * knee + (a - knee) * (180 - k * knee) / (180 - knee)
    return np.sign(rel) * min(out, 180.0)


class Head:
    """Minimum-jerk head-yaw movements with human peak velocities."""

    AMP = np.array([0, 30, 60, 105, 180.0])
    VPK = np.array([20, 50, 120, 150, 170.0])  # deg/s (Brimijoin et al. 2010)

    def __init__(self, yaw=0.0):
        self.yaw = yaw
        self.plan = None

    def go(self, t, target, replan_tol=12.0):
        if self.plan is not None and abs(wrap(target - self.plan[2])) < replan_tol:
            return  # already heading there; humans refine smoothly rather than restart
        a = abs(wrap(target - self.yaw))
        if a < 2:
            return
        v = np.interp(a, self.AMP, self.VPK)
        self.plan = (t, self.yaw, self.yaw + wrap(target - self.yaw), 1.875 * a / v)

    def step(self, t):
        if self.plan:
            t0, y0, y1, T = self.plan
            s = min((t - t0) / T, 1.0)
            self.yaw = y0 + (y1 - y0) * (10 * s ** 3 - 15 * s ** 4 + 6 * s ** 5)
            if s >= 1.0:
                self.plan = None

    @property
    def moving(self):
        return self.plan is not None


@dataclass
class Result:
    strategy: str
    subject: str
    target_az: float
    dist: float
    arrived: bool = False
    t_arrive: float = np.nan
    t_face: float = np.nan
    facing_err_at_arrival: float = np.nan
    path_len: float = 0.0
    wrong_way_first_turn: bool = False
    n_reorients: int = 0
    log: list = field(default_factory=list)


def run_trial(strat: Strategy, subject, target_az, dist, rng, latency=0.2, yaw_bias=0.0,
              walk_speed=WALK_SPEED, t_max=30.0, keep_log=False):
    L = Listener(FEATS["apple"], FEATS[subject], NOISE, rng)
    B = WorldBelief(L, decay_tau_s=4.0)
    head = Head(0.0)
    torso = 0.0
    pos = np.zeros(2)  # (right, forward) metres
    tgt = dist * np.array([np.sin(np.radians(target_az)), np.cos(np.radians(target_az))])
    res = Result(strat.name, subject, target_az, dist)
    hist_t, hist_yaw = [0.0], [0.0]
    next_call, pending, walking = 0.0, [], False
    first_turn_checked = False
    last_cue = None
    called_once = False
    t = 0.0

    def bearing(p):
        d = tgt - p
        return np.degrees(np.arctan2(d[0], d[1])), np.hypot(*d)

    if strat.clock_speech or strat.speech_only:
        next_call = 2.0  # utterance takes ~2 s ("Keys. Two o'clock, three meters.")
        b, _ = bearing(pos)
        hour = int(np.round(wrap(b - torso) / 30.0)) % 12
        pending.append((2.0 + 0.3, "clock", hour * 30.0))

    while t < t_max:
        b, d = bearing(pos)
        rel_true = wrap(b - head.yaw)
        if np.isnan(res.t_face) and abs(rel_true) < 10:
            res.t_face = t
        if d < REACH:
            res.arrived, res.t_arrive = True, t
            res.facing_err_at_arrival = abs(wrap(b - torso))
            break

        # Rendered head yaw: what the tracker reported `latency` seconds ago, plus any bias.
        rendered_yaw = np.interp(t - latency, hist_t, hist_yaw) + yaw_bias
        rel_rendered = wrap(b - rendered_yaw)

        # Sound events.
        if not strat.speech_only and t >= next_call and not (strat.single and called_once):
            called_once = True
            period = strat.period(d) if callable(strat.period) else strat.period
            mid = t + strat.dur / 2
            el = np.degrees(np.arctan2(0.75 - EAR_HEIGHT, max(d, 0.3)))
            cue = None
            if strat.lock_deg and abs(rel_rendered) < strat.lock_deg:
                cue = "lock"
            elif strat.behind_deg and abs(rel_rendered) > strat.behind_deg:
                cue = "behind"
            elif strat.lock_deg:
                cue = "off"
            noise_scale = np.sqrt(max(1.0, 0.12 / strat.dur))
            pending.append((mid + 0.25, "look", (magnify(rel_rendered, strat.magnify), el, noise_scale, cue, head.yaw)))
            next_call = t + max(period, strat.dur)
        if strat.speech_only and t >= next_call:
            hour = int(np.round(wrap(b - torso) / 30.0)) % 12
            pending.append((t + 1.2, "clock", hour * 30.0))
            next_call = t + 2.0

        # Perception + decisions (after reaction time).
        due = [p for p in pending if p[0] <= t]
        pending = [p for p in pending if p[0] > t]
        for _, kind, payload in due:
            if kind == "clock":
                aim = torso + (payload if payload <= 180 else payload - 360) + rng.normal(0, 8)
                if strat.speech_only:
                    if payload == 0:
                        walking = True
                    else:
                        walking = False
                        head.plan = None
                        head.yaw = torso = aim  # turn in place by the stated clock angle
                        res.n_reorients += 1
                else:
                    mask = np.abs(wrap(GRID_AZ[None, :] - aim)) < 25
                    B.constrain(np.broadcast_to(mask, B.logb.shape), strength=3.0)
                    head.go(t, aim)
                continue
            rel_r, el, ns, cue, yaw_at_sound = payload
            saved = L.n.itd_us, L.n.ild_db, L.n.spec_db
            L.n.itd_us, L.n.ild_db, L.n.spec_db = (x * ns for x in saved)
            B.recent = []  # each discrete call is a new look
            B.look(t, rel_r, el, yaw_at_sound)
            L.n.itd_us, L.n.ild_db, L.n.spec_db = saved
            if cue:
                diff = np.abs(wrap(GRID_AZ[None, :] - yaw_at_sound))
                m = {"lock": diff < strat.lock_deg, "behind": diff > strat.behind_deg,
                     "off": (diff >= strat.lock_deg) & (diff <= (strat.behind_deg or 180))}[cue]
                B.constrain(np.broadcast_to(m, B.logb.shape), strength=4.0)
            last_cue = cue
            aim, _ = B.map_world()
            marg = B.azimuth_marginal()
            conf = marg[np.abs(wrap(GRID_AZ - aim)) < 20].sum()
            if not first_turn_checked:
                first_turn_checked = True
                lat = np.degrees(np.arcsin(np.sin(np.radians(target_az))))
                if abs(lat) < 60:
                    res.wrong_way_first_turn = (np.cos(np.radians(aim)) > 0) != (np.cos(np.radians(target_az)) > 0)
            err = wrap(aim - head.yaw)
            aligned = (cue == "lock") if strat.lock_deg else (abs(err) < 10 and conf > 0.5)
            if walking:
                if abs(wrap(aim - torso)) > 45 and cue != "lock":
                    walking = False
                    res.n_reorients += 1
                    head.go(t, aim)
                else:
                    torso += np.clip(wrap(aim - torso), -15, 15) if cue != "lock" else 0.0
                    head.go(t, torso)
            else:
                if aligned:
                    walking = True
                    torso = head.yaw
                elif abs(err) >= 4:
                    head.go(t, aim)
                else:
                    # Unsure but nothing obvious to do: a small exploratory head turn.
                    head.go(t, head.yaw + rng.choice([-15, 15]))

        # Motion.
        was_moving = head.moving
        head.step(t)
        if was_moving and not head.moving and not walking and not strat.speech_only and B.n_looks:
            # Finished a turn: decide whether to set off, using what has been heard so far.
            aim, _ = B.map_world()
            conf = B.azimuth_marginal()[np.abs(wrap(GRID_AZ - aim)) < 20].sum()
            ok = (last_cue == "lock") if strat.lock_deg else (abs(wrap(aim - head.yaw)) < 10 and conf > 0.5)
            if ok or (strat.single and abs(wrap(aim - head.yaw)) < 10):
                walking, torso = True, head.yaw
        if not walking:
            off = wrap(head.yaw - torso)
            if abs(off) > HEAD_ON_TORSO_MAX:
                torso = head.yaw - np.sign(off) * HEAD_ON_TORSO_MAX
        else:
            torso += rng.normal(0, 2.0 * np.sqrt(DT))  # veering
            if not head.moving:
                head.yaw = torso + 4 * np.sin(2 * np.pi * 0.5 * t)
            step = walk_speed * DT * np.array([np.sin(np.radians(torso)), np.cos(np.radians(torso))])
            pos = pos + step
            res.path_len += walk_speed * DT
        t += DT
        hist_t.append(t)
        hist_yaw.append(head.yaw)
        if keep_log:
            res.log.append((t, head.yaw, torso, pos[0], pos[1]))
    return res


def run_all(strategies=STRATEGIES, n_targets=24, seed=7, **kw):
    out = []
    for si, s in enumerate(SUBJECTS):
        rng = np.random.default_rng(seed + 1000 * si)
        targets = [(rng.uniform(-180, 180), rng.uniform(1.5, 5.0)) for _ in range(n_targets)]
        for st in strategies:
            for k, (az, d) in enumerate(targets):
                out.append(run_trial(st, s, az, d, np.random.default_rng(seed + 1000 * si + k), **kw))
    return out


def summarize(results, deadline=15.0):
    rows = {}
    for st in {r.strategy for r in results}:
        rs = [r for r in results if r.strategy == st]
        ok = [r for r in rs if r.arrived and r.t_arrive <= deadline and r.facing_err_at_arrival < 30]
        arr = [r.t_arrive for r in rs if r.arrived]
        face = [r.t_face for r in rs if not np.isnan(r.t_face)]
        ww = [r for r in rs if abs(np.degrees(np.arcsin(np.sin(np.radians(r.target_az))))) < 60]
        eff = [np.hypot(np.sin(np.radians(r.target_az)) * r.dist, np.cos(np.radians(r.target_az)) * r.dist) - REACH for r in rs if r.arrived and r.path_len > 0]
        pl = [r.path_len for r in rs if r.arrived and r.path_len > 0]
        rows[st] = dict(
            n=len(rs),
            success_within_15s_pct=100 * len(ok) / len(rs),
            reached_within_15s_any_side_pct=100 * np.mean([r.arrived and r.t_arrive <= deadline for r in rs]),
            median_item_bearing_at_arrival_deg=float(np.nanmedian([r.facing_err_at_arrival for r in rs])) if arr else np.nan,
            arrived_within_30s_pct=100 * len(arr) / len(rs),
            median_time_to_reach_s=float(np.median(arr)) if arr else np.nan,
            p90_time_to_reach_s=float(np.percentile(arr, 90)) if arr else np.nan,
            median_time_to_face_s=float(np.median(face)) if face else np.nan,
            first_percept_front_back_reversal_pct=100 * np.mean([r.wrong_way_first_turn for r in ww]) if ww else np.nan,
            path_efficiency_pct=100 * float(np.sum(eff) / np.sum(pl)) if pl else np.nan,
            median_reorients=float(np.median([r.n_reorients for r in rs])),
        )
    return rows


if __name__ == "__main__":
    res = run_all()
    rows = summarize(res)
    order = [s.name for s in STRATEGIES]
    print(f"{'strategy':28} {'ok<=15s':>8} {'arr<=30':>8} {'t_reach':>8} {'p90':>6} {'t_face':>7} {'FBrev1st':>8} {'pathEff':>7}")
    for k in order:
        r = rows[k]
        print(f"{k:28} {r['success_within_15s_pct']:7.1f}% {r['arrived_within_30s_pct']:7.1f}% {r['median_time_to_reach_s']:8.1f} {r['p90_time_to_reach_s']:6.1f} {r['median_time_to_face_s']:7.1f} {r['first_percept_front_back_reversal_pct']:7.1f}% {r['path_efficiency_pct']:6.1f}%")
    out = ROOT / "reports" / "poc5_guidance_nominal.json"
    out.write_text(json.dumps(rows, indent=2))
