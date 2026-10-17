"""POC 24: detecting "the hand is touching THIS jar" from the chest iPhone, without false touches.

Scene: six identical spice jars (r 3.5 cm, 10 cm tall) in two rows on a kitchen counter, 8 cm apart, the
back row 11 cm behind the front row. The chest camera (30 deg tilt) sees them at ~0.5 m. A hand (palm +
index finger as boxes) is rendered into the emulated LiDAR depth, so it occludes and is occluded like a
real hand. Apple Vision hand pose is emulated: 2D joints with pixel noise, lower confidence and larger
error when the joint is hidden. The app knows each jar's position from memory, with 2 cm anchor error.

Scenarios (30 randomised trials each): touch a front lid, touch a back lid (reaching over the front
jar), hover 6 cm above a lid, hover in the gap BEHIND a front jar (the false positive you worried
about), hover 3.5 cm in front of a jar.
Detectors:
  2D overlap    fingertip pixel inside the jar's 2D box for 3 frames (the naive approach)
  3D naive      fingertip 3D from LiDAR depth at the fingertip pixel; within 2 cm of the jar's surface
  3D checked    3D naive + per-joint checks (depth jumps along the finger, low-confidence joints sitting
                on a jar's surface are rebuilt from the visible knuckles using bone lengths) + the
                hand must be nearly still + enter at 2 cm / leave at 5 cm
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "emulators" / "arkit"))
from device import CX, CY, DEP_H, DEP_W, FX, FY, IMG_H, IMG_W, SX, SY, Phone, chest_camera_pose, project, unproject  # noqa: E402
from scene import Box, Cylinder, Room, ray_cylinder  # noqa: E402

FPS = 30
R_JAR, H_JAR, TOP = 0.035, 0.10, 0.92
FRONT_Z, BACK_Z, XS = -0.55, -0.66, (-0.08, 0.0, 0.08)
FINGER = dict(w=0.018, h=0.018, l=0.08)   # index finger (x, y, z extents)
PALM = dict(w=0.08, h=0.025, l=0.09)
BONES = (0.022, 0.025, 0.035)             # tip-DIP, DIP-PIP, PIP-MCP along the finger


def jars(rng=None, jitter=0.0):
    out = {}
    for row, z in (("F", FRONT_Z), ("B", BACK_Z)):
        for k, x in enumerate(XS):
            j = rng.normal(0, jitter, 2) if rng is not None else (0, 0)
            out[f"{row}{k + 1}"] = Cylinder(f"{row}{k + 1}", x + j[0], z + j[1], TOP, TOP + H_JAR, R_JAR, is_item=False)
    return out


def hand_prims(tip, point):
    """Index finger + palm as boxes. point="forward": finger along -z, palm behind it (+z);
    point="down": finger along -y, palm above it, slightly toward the wearer. tip = the fingertip."""
    t = np.asarray(tip)
    hw = FINGER["w"] / 2
    if point == "forward":
        f = Box("finger", [t[0] - hw, t[1] - hw, t[2]], [t[0] + hw, t[1] + hw, t[2] + FINGER["l"]])
        pz = t[2] + FINGER["l"]
        p = Box("palm", [t[0] - 0.02, t[1] - hw, pz], [t[0] + 0.06, t[1] - hw + PALM["h"], pz + PALM["l"]])
    else:
        f = Box("finger", [t[0] - hw, t[1], t[2] - hw], [t[0] + hw, t[1] + FINGER["l"], t[2] + hw])
        py = t[1] + FINGER["l"]
        p = Box("palm", [t[0] - 0.02, py, t[2] - hw], [t[0] + 0.06, py + PALM["h"], t[2] - hw + PALM["l"]])
    return [f, p]


def joints(tip, point):
    """Index tip, DIP, PIP, MCP along the finger (toward the palm), then the wrist."""
    t = np.asarray(tip)
    axis = np.array([0, 0, 1.0]) if point == "forward" else np.array([0, 1.0, 0])
    pts = [t + axis * dz for dz in np.cumsum([0.0, *BONES])]
    wrist = (t + np.array([0.02, 0.004, FINGER["l"] + PALM["l"]]) if point == "forward"
             else t + np.array([0.02, FINGER["l"] + 0.012, PALM["l"] - 0.01]))
    pts.append(wrist)
    return np.array(pts)


def dist_to_jar(p, c):
    dr = max(0.0, np.hypot(p[0] - c.cx, p[2] - c.cz) - c.r)
    dy = max(0.0, c.y0 - p[1], p[1] - c.y1)
    return float(np.hypot(dr, dy))


def jar_box2d(T, c):
    uv, z = project(T, c.corners())
    return uv.min(0), uv.max(0), float(z.min())


def scenario_path(name, J, rng):
    """Fingertip waypoints and whether/which jar is truly touched at the end."""
    tgt, back = J["F2"], J["B2"]
    lid = TOP + H_JAR
    if name == "touch front lid":
        end, truth, point = np.array([tgt.cx, lid, tgt.cz]), "F2", "down"
    elif name == "touch back lid (over the front jar)":
        end, truth, point = np.array([back.cx, lid, back.cz]), "B2", "down"
    elif name == "hover 6 cm above a lid":
        end, truth, point = np.array([tgt.cx, lid + 0.06, tgt.cz]), None, "down"
    elif name == "hover 4 cm behind a jar (hidden)":
        # single row (no back jars): fingertip 4 cm behind F2's back surface, hidden from the chest camera
        end, truth, point = np.array([tgt.cx, TOP + 0.05, tgt.cz - tgt.r - 0.04 - FINGER["w"] / 2]), None, "down"
    else:  # hover 3.5 cm in front of a jar, finger pointing at it
        end, truth, point = np.array([tgt.cx, TOP + 0.06, tgt.cz + tgt.r + 0.035]), None, "forward"
    start = np.array([0.10 + rng.normal(0, 0.02), 1.10 + rng.normal(0, 0.02), -0.20])
    over = np.array([end[0], max(end[1], lid + 0.05), end[2] + (0.0 if point == "down" else 0.05)])
    return [start, over, end], truth, point


def sample_depth(fr, u, v, r=1, clean=False):
    """Median depth of a small window; clean=True also rejects windows that straddle a depth edge."""
    iu, iv = int(u * SX), int(v * SY)
    if not (0 <= iu < DEP_W and 0 <= iv < DEP_H):
        return None
    w = fr["depth"][max(iv - r, 0): iv + r + 1, max(iu - r, 0): iu + r + 1]
    c = fr["conf"][max(iv - r, 0): iv + r + 1, max(iu - r, 0): iu + r + 1]
    g = w[c >= 1]
    if not g.size or (clean and np.percentile(g, 90) - np.percentile(g, 10) > 0.03):
        return None
    return float(np.median(g))


def hand_behind(T, vj, fr, jar):
    """Is the hand behind this jar? Depth of the clean, visible knuckles (PIP, MCP, wrist) vs the jar's
    front surface on the fingertip's line of sight. A hand reaching a lid is at about the jar's centre;
    a hand behind the jar is more than a jar's width beyond its front surface."""
    zs = []
    for j in (2, 3, 4):
        u, v, conf, _ = vj[j]
        z = sample_depth(fr, u, v, clean=True)
        if z is not None and conf >= 0.5:
            zs.append(z)
    if not zs:
        return False
    u, v, _, _ = vj[0]
    o = T[:3, 3]
    d = T[:3, :3] @ np.array([(u - CX) / FX, -(v - CY) / FY, -1.0]); d /= np.linalg.norm(d)
    t = ray_cylinder(o[None], d[None], jar)[0]
    if not np.isfinite(t):
        return False
    z_front = float(project(T, (o + t * d)[None])[1][0])
    return float(np.median(zs)) > z_front + 2 * jar.r + 0.01


def vision_joints(fr, T, P, rng, hand_idx):
    """Emulated VNDetectHumanHandPoseRequest: 2D joints + confidence; hidden joints are noisier.
    A joint is hidden when what the camera sees at its pixel is not the hand."""
    uv, z = project(T, P)
    out = []
    for (u, v), zz in zip(uv, z):
        iu, iv = int(u * SX), int(v * SY)
        hidden = not (0 <= iu < DEP_W and 0 <= iv < DEP_H) or int(fr["gt_idx"][iv, iu]) not in hand_idx
        sd, conf = (12.0, rng.uniform(0.15, 0.45)) if hidden else (4.0, rng.uniform(0.6, 0.95))
        out.append((u + rng.normal(0, sd), v + rng.normal(0, sd), conf, hidden))
    return out


def detect_2d(T, J_mem, vj):
    u, v, _, _ = vj[0]
    hits = []
    for k, c in J_mem.items():
        lo, hi, _ = jar_box2d(T, c)
        if lo[0] <= u <= hi[0] and lo[1] <= v <= hi[1]:
            hits.append((np.hypot(u - (lo[0] + hi[0]) / 2, v - (lo[1] + hi[1]) / 2), k))
    return min(hits)[1] if hits else None


def tip3d_naive(fr, T, vj):
    u, v, _, _ = vj[0]
    z = sample_depth(fr, u, v)
    return None if z is None else unproject(T, u, v, z)


def tip3d_checked(fr, T, vj):
    """Fingertip 3D that does not trust the depth under a hidden fingertip.

    Vision marks joints it cannot see with low confidence. For those, the LiDAR pixel shows whatever is in
    front (the jar), so the joint is rebuilt instead: it lies on its own camera ray, at the finger's bone
    length from the nearest trusted joint toward the palm, and BEHIND the surface the camera sees there
    (that is why it is hidden). Returns None if no joint toward the palm is trusted."""
    pts, ok = [], []
    for (u, v, conf, _) in vj:
        z = sample_depth(fr, u, v)
        pts.append(None if z is None else unproject(T, u, v, z))
        ok.append(z is not None and conf >= 0.5)
    if ok[0]:
        return pts[0]
    cum = np.cumsum([0.0, *BONES])                   # tip -> DIP -> PIP -> MCP distances
    anchor = next((j for j in (1, 2, 3) if ok[j]), None)
    if anchor is None:
        return None
    P, L = pts[anchor], float(cum[anchor])
    u, v, _, _ = vj[0]
    o = T[:3, 3]
    d = T[:3, :3] @ np.array([(u - CX) / FX, -(v - CY) / FY, -1.0]); d /= np.linalg.norm(d)
    # |o + t d - P| = L  ->  t^2 - 2 t d.(P - o) + |P - o|^2 - L^2 = 0
    w = P - o
    bq, cq = float(d @ w), float(w @ w) - L * L
    disc = bq * bq - cq
    if disc < 0:
        return o + d * bq                            # closest point on the ray
    t_far = bq + np.sqrt(disc)
    return o + d * t_far                             # the hidden tip is behind the visible surface


def pixel_speed(hist2d):
    """Median pixel motion per frame of the knuckles over the last 4 frames (2D is far less noisy than depth)."""
    if len(hist2d) < 4:
        return np.inf
    a = np.array(hist2d[-4:])
    return float(np.median(np.linalg.norm(np.diff(a, axis=0), axis=1)))


def run_trial(name, rng, method):
    J_true = jars(rng, jitter=0.004)
    if name.startswith("hover 4 cm behind"):
        J_true = {k: c for k, c in J_true.items() if k.startswith("F")}   # one row: nothing behind the jar
    J_mem = {k: Cylinder(k, c.cx + rng.normal(0, 0.02 / np.sqrt(2)), c.cz + rng.normal(0, 0.02 / np.sqrt(2)), c.y0, c.y1, c.r, is_item=False)
             for k, c in J_true.items()}          # memory knows each jar with ~2 cm anchor error
    path, truth, point = scenario_path(name, J_true if "B2" in J_true else {**J_true, "B2": jars()["B2"]}, rng)
    counter = Box("counter", [-0.6, 0.0, -0.95], [0.6, TOP, -0.35])
    T = chest_camera_pose((0.0, 0.05), 0.0, 0.0, tilt_deg=30.0)
    room = Room(furniture=[counter], items={})
    phone = Phone(room, rng)
    seg_t = [0.45, 0.35]                             # start->over, over->end (s); then hold 0.6 s
    times = np.arange(0, sum(seg_t) + 0.6, 1 / FPS)
    streak, current, reported, first_t = 0, None, [], None
    hist, hist2d = [], []
    for t in times:
        if t < seg_t[0]:
            tip = path[0] + (path[1] - path[0]) * (t / seg_t[0])
        elif t < sum(seg_t):
            tip = path[1] + (path[2] - path[1]) * ((t - seg_t[0]) / seg_t[1])
        else:
            tip = path[2]
        room.furniture = [counter, *hand_prims(tip, point)]
        room.items = J_true
        fr = phone.frame(T, t, dt=1 / FPS)
        P = joints(tip, point)
        vj = vision_joints(fr, T, P, rng, hand_idx=(1, 2))
        if method == "2D overlap":
            hit = detect_2d(T, J_mem, vj)
        else:
            if method == "3D, visible fingertip only":
                p = tip3d_naive(fr, T, vj) if vj[0][2] >= 0.5 else None   # Vision can't see the tip: no touch
            else:
                p = tip3d_naive(fr, T, vj) if method == "3D naive" else tip3d_checked(fr, T, vj)
            hist.append(p)
            hist2d.append(np.array(vj[3][:2]))
            if method in ("3D checked", "3D, visible fingertip only") and p is not None:
                recent = [q for q in hist[-3:] if q is not None]
                p = np.median(np.array(recent), axis=0)                         # 3-frame median of the fingertip
            if p is None:
                hit = None
            else:
                ds = {k: dist_to_jar(p, c) for k, c in J_mem.items()}
                k = min(ds, key=ds.get)
                enter, leave = (0.02, 0.02) if method == "3D naive" else (0.02, 0.05)
                lim = leave if current == k else enter
                hit = k if ds[k] < lim else None
                if method != "3D naive" and hit is not None and current != k and pixel_speed(hist2d) > 8.0:
                    hit = None                     # knuckles still moving (> 8 px/frame): not a touch yet
                if method == "3D checked" and hit is not None and hand_behind(T, vj, fr, J_mem[hit]):
                    hit = None                     # the fingertip's depth is the jar's; the hand is behind it
        streak = streak + 1 if (hit is not None and hit == current) else (1 if hit is not None else 0)
        current = hit
        if streak == 3 and hit not in reported:
            reported.append(hit)
            if first_t is None:
                first_t = t
    contact_t = sum(seg_t)
    return dict(truth=truth, reported=reported, latency_ms=None if first_t is None or truth is None else round(1000 * (first_t - contact_t)))


if __name__ == "__main__":
    scen = ["touch front lid", "touch back lid (over the front jar)", "hover 6 cm above a lid",
            "hover 4 cm behind a jar (hidden)", "hover 3.5 cm in front of a jar"]
    methods = sys.argv[1:] or ["2D overlap", "3D naive", "3D checked", "3D, visible fingertip only"]
    res = {}
    for m in methods:
        res[m] = {}
        for s in scen:
            rng = np.random.default_rng(7)
            trials = [run_trial(s, rng, m) for _ in range(30)]
            truth = trials[0]["truth"]
            if truth:
                right = np.mean([truth in t["reported"] for t in trials])
                wrong = np.mean([any(r != truth for r in t["reported"]) for t in trials])
                lat = [t["latency_ms"] for t in trials if t["latency_ms"] is not None and truth in t["reported"]]
                res[m][s] = dict(correct_jar_pct=round(100 * right, 1), wrong_jar_reported_pct=round(100 * wrong, 1),
                                 median_ms_after_contact=float(np.median(lat)) if lat else None)
            else:
                res[m][s] = dict(false_touch_pct=round(100 * np.mean([len(t["reported"]) > 0 for t in trials]), 1))
            print(f"{m:11} | {s:38} | {res[m][s]}", flush=True)
    (ROOT / "reports" / "poc24_touch_3d.json").write_text(json.dumps(res, indent=2))
