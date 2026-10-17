"""POC 12: Mapping features -- obstacle-aware "breadcrumb" routing and floor-hazard warning.

1. Routing: in the furnished demo room, how often does the straight line from the wearer to the
   item pass through furniture (a coffee table at shin height is the classic one)? With the
   LiDAR/RoomPlan map we can instead plan a path (A* on an occupancy grid inflated by body
   radius) and play the "Polo" from the next waypoint: breadcrumbs around obstacles.
2. Floor hazards: with a tilted chest camera, how much warning does a walker get for a bag on the
   floor ahead (LiDAR sees it when it enters the field of view)?
"""
import heapq
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "emulators" / "arkit"))
from scene import demo_room  # noqa: E402

RES = 0.05
BODY_R = 0.25
ROOM = demo_room()
X0, Z0 = ROOM.lo[0], ROOM.lo[2]
NX, NZ = int((ROOM.hi[0] - X0) / RES), int((ROOM.hi[2] - Z0) / RES)


def occupancy(inflate=BODY_R):
    occ = np.zeros((NX, NZ), bool)
    xs = X0 + (np.arange(NX) + 0.5) * RES
    zs = Z0 + (np.arange(NZ) + 0.5) * RES
    X, Z = np.meshgrid(xs, zs, indexing="ij")
    for f in ROOM.furniture:
        if f.hi[1] < 0.05 or f.lo[0] > ROOM.hi[0]:
            continue
        dx = np.maximum(np.maximum(f.lo[0] - X, X - f.hi[0]), 0)
        dz = np.maximum(np.maximum(f.lo[2] - Z, Z - f.hi[2]), 0)
        occ |= np.hypot(dx, dz) <= inflate  # distance 0 = inside the footprint
    wall = (X - X0 < inflate) | (ROOM.hi[0] - X < inflate) | (Z - Z0 < inflate) | (ROOM.hi[2] - Z < inflate)
    return occ | wall


OCC = occupancy()
OCC_RAW = occupancy(0.0)


def cell(p):
    return int((p[0] - X0) / RES), int((p[1] - Z0) / RES)


def line_hits(a, b, occ):
    n = int(np.hypot(*(np.array(b) - a)) / (RES / 2)) + 2
    for s in np.linspace(0, 1, n):
        i, j = cell(np.array(a) + s * (np.array(b) - a))
        if 0 <= i < NX and 0 <= j < NZ and occ[i, j]:
            return True
    return False


def astar(a, b):
    s, g = cell(a), cell(b)
    openq = [(0, s)]
    came, cost = {s: None}, {s: 0.0}
    nbr = [(1, 0), (-1, 0), (0, 1), (0, -1), (1, 1), (1, -1), (-1, 1), (-1, -1)]
    while openq:
        _, c = heapq.heappop(openq)
        if c == g:
            break
        for di, dj in nbr:
            n = (c[0] + di, c[1] + dj)
            if not (0 <= n[0] < NX and 0 <= n[1] < NZ) or OCC[n]:
                continue
            nc = cost[c] + np.hypot(di, dj)
            if nc < cost.get(n, 1e9):
                cost[n], came[n] = nc, c
                heapq.heappush(openq, (nc + np.hypot(n[0] - g[0], n[1] - g[1]), n))
    if g not in came:
        return None
    path, c = [], g
    while c is not None:
        path.append((X0 + (c[0] + 0.5) * RES, Z0 + (c[1] + 0.5) * RES))
        c = came[c]
    path = path[::-1]
    # line-of-sight smoothing -> breadcrumbs
    way, i = [path[0]], 0
    while i < len(path) - 1:
        j = len(path) - 1
        while j > i + 1 and line_hits(path[i], path[j], OCC):
            j -= 1
        way.append(path[j])
        i = j
    return way


TARGETS = {  # where you stand to reach each surface
    "entry table": (-1.75, 0.55), "coffee table (far side)": (0.2, -2.75), "dining table": (1.0, -0.7),
    "kitchen counter": (1.6, -3.5), "sofa seat": (0.5, -2.95), "shelf": (-1.8, -1.1),
}

if __name__ == "__main__":
    rng = np.random.default_rng(0)
    free = np.argwhere(~OCC)
    rows, res = [], {}
    for _ in range(400):
        i, j = free[rng.integers(len(free))]
        start = (X0 + (i + 0.5) * RES, Z0 + (j + 0.5) * RES)
        name = list(TARGETS)[rng.integers(len(TARGETS))]
        goal = TARGETS[name]
        if OCC[cell(goal)]:
            continue
        straight = float(np.hypot(goal[0] - start[0], goal[1] - start[1]))
        if straight < 1.0:
            continue
        hits = line_hits(start, goal, OCC_RAW)
        way = astar(start, goal)
        if way is None:
            continue
        L = float(sum(np.hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(way, way[1:])))
        rows.append((hits, L / straight, len(way) - 2))
    hits = np.array([r[0] for r in rows])
    res["straight line to item passes through furniture"] = f"{100 * hits.mean():.0f}% of {len(rows)} random start/target pairs"
    res["planned path length vs straight line (when blocked)"] = f"+{100 * (np.median([r[1] for r in rows if r[0]]) - 1):.0f}% median"
    res["breadcrumb waypoints needed (when blocked)"] = f"median {np.median([r[2] for r in rows if r[0]]):.0f}, max {max(r[2] for r in rows if r[0])}"
    # Floor-hazard warning time for a tilted chest camera (0.6 m/s cautious walk, 1.0 m/s normal).
    for tilt in (0, 25, 35):
        th = np.radians(tilt)
        near = 1.30 / np.tan(np.radians(31) + th)  # lower edge of the 62 deg vertical FOV
        far = min(1.30 / np.tan(th - np.radians(31)) if tilt > 31 else 5.0, 5.0)
        res[f"floor visible ahead, tilt {tilt} deg"] = f"{near:.2f}-{far:.1f} m -> {far / 0.6:.1f} s warning at 0.6 m/s, {far / 1.0:.1f} s at 1.0 m/s"
    print(json.dumps(res, indent=2))
    (ROOT / "reports" / "poc12_routing.json").write_text(json.dumps(res, indent=2))
