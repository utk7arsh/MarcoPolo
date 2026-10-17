"""POC 2: Does the memory notice moves correctly, and never send someone to an empty spot?

Scenarios (each repeated with 40 random seeds; detector at 2 Hz; ARKit drift on):
  A in-view move       teammate moves the bottle 25 cm along the table while the wearer watches
  B out-of-view move   wallet moved to another table while the wearer looks away; wearer then
                       looks at the old spot (should say "not there"), later at the new one
  C occlusion          a cereal box is put in front of the bottle (must NOT mark it gone)
  D far/marginal view  keys viewed from ~3.2 m where they are detected only sometimes
                       (must NOT mark them gone)
  E look-alike         real bottle taken away and a different bottle put on the same spot
                       (recogniser accepts the look-alike 10 % of the time) -> should say "not there"
  F walk-by blur       wearer turns quickly past the table (motion blur) -> must not mark gone
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
for p in ("emulators/arkit", "core"):
    sys.path.insert(0, str(ROOT / p))
from device import DetectorModel, Phone, chest_camera_pose, detect  # noqa: E402
from mapping import Memory  # noqa: E402
from scene import Box, Cylinder, demo_room  # noqa: E402

SIZES = {"bottle": 0.25, "keys": 0.08, "wallet": 0.11, "glasses_case": 0.16, "mug": 0.10}
P_CONFUSE = 0.10


def yaw_to(src, dst):
    return float(np.degrees(np.arctan2(dst[0] - src[0], -(dst[1] - src[1]))))


def run(scenario, seed):
    rng = np.random.default_rng(seed)
    room = demo_room()
    ph = Phone(room, rng)
    det = DetectorModel()
    mem = Memory(list(SIZES), det, SIZES)
    ev = dict(scenario=scenario, seed=seed)
    stand, look = (0.0, 0.0), (0.25, -2.1)
    tilt = 10.0
    if scenario == "B":
        stand = (0.3, 0.2)
        look = (1.65, -0.75)
    if scenario == "D":
        stand = (1.0, 0.85)
        look = (-0.26, -2.12)
    dur = {"A": 12, "B": 24, "C": 14, "D": 60, "E": 16, "F": 30}[scenario]
    prev_yaw = None
    for k, t in enumerate(np.arange(0, dur, 0.5)):
        yaw = yaw_to(stand, look) + 3 * np.sin(t)
        if scenario == "A" and abs(t - 5.0) < 1e-9:
            room.items["bottle"] = room.items["bottle"].moved_to([0.50, 0.45, -2.05])
            ev["t_move"] = t
        if scenario == "B":
            if 5 <= t < 11:
                yaw = yaw_to(stand, look) + 100  # facing away: neither table in view
            if abs(t - 6.0) < 1e-9:
                room.items["wallet"] = room.items["wallet"].moved_to([-2.3, 0.80, 0.55])
            if t >= 17:
                yaw = yaw_to(stand, (-2.3, 0.55))
        if scenario == "C" and abs(t - 5.0) < 1e-9:
            room.furniture[-1] = Box("cereal_box", [0.13, 0.45, -1.88], [0.37, 0.80, -1.82])
        if scenario == "E" and abs(t - 5.0) < 1e-9:
            room.items["bottle"] = room.items["bottle"].moved_to([-2.3, 0.80, 0.55])  # taken away
            room.items["bottle_other"] = Cylinder("bottle_other", 0.25, -2.1, 0.45, 0.70, 0.035, surface="coffee_table")
        if scenario == "F" and t > 5:
            yaw = yaw_to(stand, look) + 80 * np.sin(2 * np.pi * (t - 5) / 4.0)  # sweeping, up to ~125 deg/s
        ang = abs(yaw - prev_yaw) / 0.5 if prev_yaw is not None else 0.0
        if scenario == "F" and t > 5:
            ang = abs(80 * 2 * np.pi / 4.0 * np.cos(2 * np.pi * (t - 5) / 4.0))
        prev_yaw = yaw
        T = chest_camera_pose(stand, yaw, t, tilt_deg=tilt)
        for _ in range(29):
            ph.drift.update(T[:3, 3], 1 / 60)
        fr = ph.frame(T, t)
        dets = detect(fr, room, det, rng, ang_speed_deg_s=ang)
        for d in dets:
            if d["label"] == "bottle_other":
                d["label"] = "bottle" if rng.uniform() < P_CONFUSE else "unknown"
        mem.update(t, fr, dets, ang_speed_deg_s=ang)
        st = {n: (it.state, None if it.pos is None else it.pos.copy()) for n, it in mem.items.items()}
        if scenario == "A" and t > 5 and "t_update" not in ev and st["bottle"][1] is not None and np.linalg.norm((st["bottle"][1] - np.array([0.50, 0.45, -2.05]))[[0, 2]]) < 0.12:
            ev["t_update"] = t - 5.0
        if scenario == "B":
            if 11 <= t and "t_not_there" not in ev and st["wallet"][0] == "not_there":
                ev["t_not_there"] = t - 11.0
            if t >= 17 and "t_found_new" not in ev and st["wallet"][0] == "present" and np.linalg.norm((st["wallet"][1] - np.array([-2.3, 0.8, 0.55]))[[0, 2]]) < 0.2:
                ev["t_found_new"] = t - 17.0
        if scenario in "CDF" and t > 5 and st[{"C": "bottle", "D": "keys", "F": "bottle"}[scenario]][0] == "not_there":
            ev.setdefault("false_gone_t", t)
        if scenario == "E" and t > 5:
            if st["bottle"][0] == "not_there":
                ev.setdefault("t_not_there", t - 5.0)
            ev["final_state"] = st["bottle"][0]
    ev["learned"] = {n: it.state for n, it in mem.items.items()}
    return ev


def summarize(evs):
    out = {}
    A = [e for e in evs if e["scenario"] == "A"]
    out["A_in_view_move"] = dict(updated_pct=100 * np.mean(["t_update" in e for e in A]),
                                 median_update_s=float(np.median([e["t_update"] for e in A if "t_update" in e])) if any("t_update" in e for e in A) else None)
    B = [e for e in evs if e["scenario"] == "B"]
    out["B_out_of_view_move"] = dict(
        said_not_there_pct=100 * np.mean(["t_not_there" in e for e in B]),
        median_s_after_looking=float(np.median([e["t_not_there"] for e in B if "t_not_there" in e])) if any("t_not_there" in e for e in B) else None,
        relocated_pct=100 * np.mean(["t_found_new" in e for e in B]),
        median_relocate_s=float(np.median([e["t_found_new"] for e in B if "t_found_new" in e])) if any("t_found_new" in e for e in B) else None)
    for k, name in (("C", "C_occluded_must_stay"), ("D", "D_far_marginal_must_stay"), ("F", "F_walkby_blur_must_stay")):
        X = [e for e in evs if e["scenario"] == k]
        out[name] = dict(false_not_there_pct=100 * np.mean(["false_gone_t" in e for e in X]))
    E = [e for e in evs if e["scenario"] == "E"]
    out["E_lookalike"] = dict(said_not_there_pct=100 * np.mean(["t_not_there" in e for e in E]),
                              median_s=float(np.median([e["t_not_there"] for e in E if "t_not_there" in e])) if any("t_not_there" in e for e in E) else None,
                              ended_not_there_pct=100 * np.mean([e.get("final_state") == "not_there" for e in E]))
    return out


if __name__ == "__main__":
    evs = [run(s, seed) for s in "ABCDEF" for seed in range(30)]
    res = summarize(evs)
    print(json.dumps(res, indent=2))
    (ROOT / "reports" / "poc2_moved.json").write_text(json.dumps(res, indent=2))
