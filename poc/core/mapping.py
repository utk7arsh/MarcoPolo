"""App logic under test: turn detections + LiDAR depth + ARKit pose into item positions, and keep
a memory that notices when items move. Everything here only uses what a real app would have
(ARKit's *estimated* pose, the noisy depth/confidence maps, detector boxes), never ground truth.
This is the logic we would port to Swift.
"""
from dataclasses import dataclass, field

import numpy as np

from device import CX, CY, DEP_H, DEP_W, FX, FY, IMG_H, IMG_W, SX, SY, DetectorModel, project, unproject  # noqa: F401


def _depth_at(depth, conf, u, v, r=1, min_conf=2):
    iu, iv = int(u * SX), int(v * SY)
    if not (0 <= iu < DEP_W and 0 <= iv < DEP_H):
        return None
    win = depth[max(iv - r, 0): iv + r + 1, max(iu - r, 0): iu + r + 1]
    cw = conf[max(iv - r, 0): iv + r + 1, max(iu - r, 0): iu + r + 1]
    good = win[cw >= min_conf]
    return float(np.median(good)) if good.size else float(np.median(win))


def world_ray(T, u, v):
    d = T[:3, :3] @ np.array([(u - CX) / FX, -(v - CY) / FY, -1.0])
    return T[:3, 3], d / np.linalg.norm(d)


def locate_center(det, frame):
    """Method A: LiDAR depth at the box centre."""
    u0, v0, u1, v1 = det["bbox"]
    u, v = (u0 + u1) / 2, (v0 + v1) / 2
    z = _depth_at(frame["depth"], frame["conf"], u, v, r=0, min_conf=0)
    return None if z is None else unproject(frame["T_arkit"], u, v, z)


def locate_median(det, frame):
    """Method B: median of high-confidence depth over the inner half of the box."""
    u0, v0, u1, v1 = det["bbox"]
    cu, cv, hw, hh = (u0 + u1) / 2, (v0 + v1) / 2, (u1 - u0) / 4, (v1 - v0) / 4
    iu0, iu1 = int(max(cu - hw, 0) * SX), int(min(cu + hw, IMG_W - 1) * SX) + 1
    iv0, iv1 = int(max(cv - hh, 0) * SY), int(min(cv + hh, IMG_H - 1) * SY) + 1
    d = frame["depth"][iv0:iv1, iu0:iu1]
    c = frame["conf"][iv0:iv1, iu0:iu1]
    vals = d[c == 2] if (c == 2).any() else d.ravel()
    if vals.size == 0:
        return None
    return unproject(frame["T_arkit"], cu, cv, float(np.median(vals)))


def locate_footprint(det, frame):
    """Method C: find where the object touches its supporting surface.

    1. Pick the box edge that is lowest in the world (works for any phone orientation).
    2. Estimate the supporting surface height from LiDAR points just beyond that edge
       (a table top is large, opaque and well measured, unlike a small or glass object).
    3. Intersect the camera ray through the contact point with that horizontal plane.
    (On device: ARSession.raycast against an estimated horizontal plane does the same.)
    """
    T = frame["T_arkit"]
    u0, v0, u1, v1 = det["bbox"]
    cu, cv = (u0 + u1) / 2, (v0 + v1) / 2
    edges = {"u1": (u1, cv), "u0": (u0, cv), "v1": (cu, v1), "v0": (cu, v0)}
    lows = {k: world_ray(T, *uv)[1][1] for k, uv in edges.items()}
    k = min(lows, key=lows.get)
    bu, bv = edges[k]
    du, dv = {"u1": (1, 0), "u0": (-1, 0), "v1": (0, 1), "v0": (0, -1)}[k]
    size = max(u1 - u0, v1 - v0)
    ys = []
    for s in np.linspace(0.08, 0.35, 6) * max(size, 60):
        for lat in np.linspace(-0.5, 0.5, 5) * max(size, 60):
            u = bu + du * s + (lat if du == 0 else 0)
            v = bv + dv * s + (lat if dv == 0 else 0)
            if not (0 <= u < IMG_W and 0 <= v < IMG_H):
                continue
            z = _depth_at(frame["depth"], frame["conf"], u, v, r=0, min_conf=2)
            if z is not None:
                ys.append(unproject(T, u, v, z)[1])
    if len(ys) < 4:
        return locate_median(det, frame)
    h = float(np.median(ys))
    o, d = world_ray(T, bu, bv)
    if d[1] > -0.05:
        return locate_median(det, frame)
    t = (h - o[1]) / d[1]
    p = o + t * d
    return p if 0.1 < t < 6 else locate_median(det, frame)


METHODS = {"center_depth": locate_center, "median_depth": locate_median, "footprint": locate_footprint}


@dataclass
class ItemState:
    name: str
    pos: np.ndarray = None
    state: str = "never_seen"        # never_seen | present | not_there
    log_odds: float = 0.0            # belief that the item is at `pos`
    last_seen_t: float = np.nan
    obs: list = field(default_factory=list)       # recent (t, pos) sightings at the stored spot
    pending: list = field(default_factory=list)   # sightings elsewhere (candidate move)
    history: list = field(default_factory=list)   # (t, event, pos)

    @property
    def p_present(self):
        return 1 / (1 + np.exp(-self.log_odds))


class Memory:
    """Item memory with move detection, as accumulated evidence (log-odds), never a single frame.

    Evidence at the stored spot, per detector run:
      * matching sighting there          -> + log(LR_HIT)   (a look-alike is only rarely accepted)
      * spot clearly in view but missed  -> + log(1 - p_d)  (p_d = our detector's own expected
                                                              detection probability for that view)
      * spot out of view, too far/small, occluded per LiDAR, or blurred -> no evidence at all
    Sightings somewhere else are a candidate move, confirmed by two consistent sightings.
    State: "present" above p=0.5, "not_there" below p=0.2 (hysteresis in between).
    """

    LR_HIT = 10.0
    MIN_PD = 0.6        # ignore marginal views as negative evidence
    MAX_PD = 0.9        # cap per-frame evidence: going from "present" to "not there" takes >= 2 misses
    CLAMP = 5.0

    def __init__(self, names, det_model: DetectorModel, sizes, method="footprint", move_radius=0.15, keep=5):
        self.items = {n: ItemState(n) for n in names}
        self.det = det_model
        self.sizes = sizes  # longest physical dimension (m) per item, from enrolment
        self.locate = METHODS[method]
        self.move_radius = move_radius
        self.keep = keep    # position = median of this many most recent sightings
        self.p_fp_at_spot = 0.01

    def update(self, t, frame, detections, ang_speed_deg_s=0.0):
        hit_here = set()
        for d in detections:
            it = self.items.get(d["label"])
            if it is None:
                continue
            if it.pos is not None and self._box_covers_spot(d, it, frame):
                hit_here.add(it.name)  # seen where we expected, even if this depth estimate is an outlier
            p = self.locate(d, frame)
            if p is None:
                continue
            if self._sighting(it, t, p):
                hit_here.add(it.name)
        for it in self.items.values():
            if it.pos is None:
                continue
            if it.name in hit_here:
                it.log_odds = min(it.log_odds + np.log(self.LR_HIT), self.CLAMP)
            else:
                pd = self.observable(it, frame, ang_speed_deg_s)
                if pd >= self.MIN_PD:
                    pd = min(pd, self.MAX_PD)  # detector misses are correlated: never trust one frame fully
                    it.log_odds = max(it.log_odds + np.log((1 - pd) / (1 - self.p_fp_at_spot)), -self.CLAMP)
            self._set_state(it, t)

    def _box_covers_spot(self, d, it, frame, pad=0.15):
        uv, z = project(frame["T_arkit"], it.pos[None])
        if z[0] <= 0:
            return False
        u0, v0, u1, v1 = d["bbox"]
        pu, pv = pad * (u1 - u0) + 10, pad * (v1 - v0) + 10
        return (u0 - pu <= uv[0, 0] <= u1 + pu) and (v0 - pv <= uv[0, 1] <= v1 + pv)

    def _set_state(self, it, t):
        p = it.p_present
        if it.state != "present" and p > 0.5:
            it.state = "present"
            it.history.append((t, "present", it.pos.copy()))
        elif it.state == "present" and p < 0.2:
            it.state = "not_there"
            it.history.append((t, "not_there", it.pos.copy()))

    def _sighting(self, it, t, p):
        """Returns True if this sighting is at the stored spot."""
        if it.pos is None:
            it.pos, it.obs, it.log_odds, it.last_seen_t = p, [(t, p)], 1.5, t
            return False
        if np.linalg.norm((p - it.pos)[[0, 2]]) < self.move_radius:
            it.obs = (it.obs + [(t, p)])[-self.keep:]
            it.pos = np.median(np.array([o[1] for o in it.obs]), axis=0)
            it.last_seen_t, it.pending = t, []
            return True
        it.pending = [o for o in it.pending if t - o[0] < 3 and np.linalg.norm((o[1] - p)[[0, 2]]) < self.move_radius] + [(t, p)]
        if len(it.pending) >= 2:
            it.obs = list(it.pending)
            it.pos = np.median(np.array([o[1] for o in it.obs]), axis=0)
            it.history.append((t, "moved", it.pos.copy()))
            it.log_odds, it.last_seen_t, it.pending = 2.0, t, []
        return False

    def observable(self, it, frame, ang_speed_deg_s=0.0):
        """Detection probability we'd expect if the item were still at its stored position."""
        T = frame["T_arkit"]
        uv, z = project(T, it.pos[None] + np.array([[0, 0.02, 0]]))
        (u, v), z = uv[0], z[0]
        margin = 40
        if z <= 0.15 or not (margin < u < IMG_W - margin and margin < v < IMG_H - margin):
            return 0.0
        # Look at LiDAR points around where the item should be. An occluder is something above the
        # supporting surface AND clearly nearer to us than the spot; then we learn nothing. Points
        # at the spot (the bare surface, or some other object standing there) are a valid view.
        r = 6
        iu, iv = int(u * SX), int(v * SY)
        vv, uu = np.mgrid[max(iv - r, 0): min(iv + r + 1, DEP_H), max(iu - r, 0): min(iu + r + 1, DEP_W)]
        zz = frame["depth"][vv, uu].ravel()
        if zz.size == 0:
            return 0.0
        uf, vf = (uu.ravel() + 0.5) / SX, (vv.ravel() + 0.5) / SY
        pc = np.stack([(uf - CX) / FX * zz, -(vf - CY) / FY * zz, -zz], 1)
        pw = pc @ T[:3, :3].T + T[:3, 3]
        cam = T[:3, 3]
        d_spot = np.linalg.norm((it.pos - cam)[[0, 2]])
        d_pts = np.linalg.norm((pw - cam)[:, [0, 2]], axis=1)
        above = pw[:, 1] > it.pos[1] + 0.03
        if np.mean(above & (d_pts < d_spot - 0.10)) > 0.2:
            return 0.0  # occluded
        near_spot = np.linalg.norm((pw - it.pos)[:, [0, 2]], axis=1) < 0.25
        if near_spot.mean() < 0.3:
            return 0.0  # depth doesn't show the spot (e.g. registration/drift error): no evidence
        h = self.sizes[it.name] * FX / z
        blur = ang_speed_deg_s * self.det.exposure_s * FX * np.pi / 180
        return float(self.det.p_detect(it.name, h, 1.0, blur))
