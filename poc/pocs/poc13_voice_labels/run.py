"""POC 13: Spatial voice labels -- "Marco, this is the cumin", and later the jar speaks when your hand
comes near. Can it tell adjacent, identical-looking jars apart days later?

Setup: a row of 8 identical spice jars (4.4 cm wide, 5.5 cm apart) on a counter (0.92 m), wearer
standing ~0.45 m away with the tilted chest phone (30 deg, portrait 48 x 62 deg FOV).
Labelling (day 0): the wearer touches each jar and names it; Marco stores the label at the jar
position (detected jar box + LiDAR), plus the jar's place in the row.
Recall (days later): ARKit relocalises with an anchor error (swept 1-8 cm; research: saved anchors
3-8 cm, older relocalisation 16-18 cm). The wearer reaches for jar j; Vision hand pose + LiDAR give
the fingertip; the label is spoken for the jar the finger is on.

Methods:
  position only     nearest stored anchor to the fingertip (in the relocalised map)
  row matching      align the stored row to the jars detected in the current frame (1-D, inlier
                    count + a prior on the relocalisation error), then use the jar under the finger.
                    Jar positions within one frame are mm-accurate relative to each other, so this
                    cancels the map error.
Perturbations: 5 % of jars missed by the detector per frame; optional: the row's end jars outside
the camera view (then the row is periodic and matching relies on the prior).
"""
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SPACING, N = 0.055, 8
NAMES = ["cumin", "paprika", "turmeric", "oregano", "cinnamon", "chili", "pepper", "garlic"]


def detect_row(true_x, rng, p_miss=0.05, sd=0.002, visible=(-1e9, 1e9)):
    xs = [x + rng.normal(0, sd) for x in true_x if visible[0] <= x <= visible[1] and rng.uniform() > p_miss]
    return np.array(sorted(xs))


def align(stored, current, prior_sd, view, tol=0.015):
    """Best 1-D shift mapping stored anchor x -> current frame x.

    Score = matched jars - stored jars that would land on empty, visible space - prior on the shift.
    Penalising "a jar should be here but isn't" stops the row sliding by one jar at its ends.
    """
    best, best_score = 0.0, -1e9
    for s in stored:
        for c in current:
            shift = c - s
            moved = stored + shift
            d = np.min(np.abs(moved[:, None] - current[None, :]), axis=1)
            in_view = (moved >= view[0]) & (moved <= view[1])
            inl = np.sum(d < tol)
            empty = np.sum(in_view & (d >= tol))
            score = inl - 1.0 * empty - 0.5 * (shift / prior_sd) ** 2
            if score > best_score:
                best, best_score = shift, score
    return best


def trial(rng, reloc_sd, ends_visible=True, finger_sd=0.004):
    true_x = np.arange(N) * SPACING                     # true jar centres along the row (m)
    # day 0: labels stored at detected jar positions (map frame at labelling time)
    stored = true_x + rng.normal(0, 0.003, N)
    # later: relocalised map is offset by the anchor error (mostly a shift along the row here)
    err = rng.normal(0, reloc_sd)
    j = rng.integers(N)                                 # jar the user reaches for
    finger = true_x[j] + rng.normal(0, finger_sd)       # fingertip, current frame (true coordinates)
    vis = (-1e9, 1e9) if ends_visible else (true_x[1] - 0.01, true_x[-2] + 0.01)
    # ~1 s reach at 2-5 Hz: merge detections from 4 frames (misses are independent per frame)
    frames = [detect_row(true_x, rng, visible=vis) for _ in range(4)]
    allx = np.sort(np.concatenate(frames))
    cur = np.array([g.mean() for g in np.split(allx, np.where(np.diff(allx) > 0.02)[0] + 1) if len(g)])
    # The app sees stored anchors at stored + err in the current tracking frame.
    stored_now = stored + err
    pos_pick = int(np.argmin(np.abs(stored_now - finger)))
    # Row matching: shift stored_now onto the detected jars, then pick the stored jar under the finger.
    view = (vis[0], vis[1]) if not ends_visible else (true_x[0] - 0.2, true_x[-1] + 0.2)
    shift = align(stored_now, cur, prior_sd=max(reloc_sd, 0.01), view=view) if len(cur) >= 2 else 0.0
    row_pick = int(np.argmin(np.abs(stored_now + shift - finger)))
    return pos_pick == j, row_pick == j


if __name__ == "__main__":
    rng = np.random.default_rng(0)
    res = {}
    for ends in (True, False):
        for sd_cm in (1, 2, 3, 5, 8, 16):
            r = np.array([trial(rng, sd_cm / 100, ends) for _ in range(4000)])
            key = f"anchor error {sd_cm} cm, row ends {'visible' if ends else 'NOT visible'}"
            res[key] = dict(position_only_pct=round(100 * r[:, 0].mean(), 1), row_matching_pct=round(100 * r[:, 1].mean(), 1))
            print(f"{key:48} correct label: position only {res[key]['position_only_pct']:5.1f}%   row matching {res[key]['row_matching_pct']:5.1f}%")
    # Can the chest camera see the hand at the jars? Counter 0.92 m, shelf 1.20 m, wall rack 1.50 m.
    for h in (0.92, 1.20, 1.50):
        for d in (0.35, 0.45, 0.55):
            ang = np.degrees(np.arctan2(1.30 - h, d))  # degrees below horizontal from the chest camera
            res[f"jar at {h} m high, {d} m ahead: in view at 30 deg tilt"] = bool(-1 <= ang <= 61)
    print({k: v for k, v in res.items() if "in view" in k})
    (ROOT / "reports" / "poc13_voice_labels.json").write_text(json.dumps(res, indent=2))
