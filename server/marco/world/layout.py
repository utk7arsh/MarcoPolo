"""Room layout for the dashboard map: walls and furniture shapes, summarised from the LiDAR room map.

Geometry only: no model and no GPU, and nothing the item pipeline reads. It is drawn on the dashboard and never used
for guidance or speech (a drawn wall can be a doorway the scan hasn't seen through yet).

ColumnGrid counts, for each 10 cm x 10 cm column of the floor plan and each 10 cm height slice, in how many frames
LiDAR points fell there, and in how many of those frames they were green. summarize() reads it as
  walls    straight runs of tall vertical surfaces: room walls, fences, railings, the sides of tall cabinets
  objects  a kind, a centre, a size and a facing: table, chair, sofa, bench, storage, plant, tree
Heights are measured from the floor (RoomMap.floor_y). Facing uses the dashboard's yaw: 0 = world -z, 90 = world +x.
"""
import math

import numpy as np
from scipy import ndimage

CELL = 0.10                       # plan columns and height slices (m)
Y_LO, Y_HI = -3.0, 3.0            # world heights kept; ARKit's origin is the phone's start, ~1.3 m above the floor
NY = int(round((Y_HI - Y_LO) / CELL))
MAX_SIDE = 400                    # columns per side (40 m): past that the grid stops growing and drops points
GROW = 20                         # grow by 2 m at a time
MIN_HITS = 1                      # walls: one frame is enough (far walls are sampled sparsely)
OBJECT_HITS = 2                   # furniture: seen in two frames, which drops LiDAR speckle and most passers-by
FLOOR_CLEAR = 0.15                # the floor slab and its noise
TOP = 2.5                         # ceilings and lamps above this are ignored
SEAT = (0.30, 0.62)               # surface heights above the floor
TABLE = (0.62, 1.15)
ON_TOP = 0.55                     # a column whose lowest point is this high is something lying on a surface
VERTICAL_RUN, VERTICAL_TOP = 0.6, 1.0   # a vertical surface: 60 cm without a gap, reaching 1 m
WALL_MIN_M, WALL_GAP_M, WALL_TOL_M = 1.0, 0.41, 0.12   # a gap of 4 empty cells (40 cm) splits a wall
MAX_WALLS = 48
SNAP_DEG = 12.0                   # walls and furniture this close to the room's main direction are squared to it
MIN_AREA = dict(seat=0.06, table=0.12, tall=0.06)
MAX_PARTS = 400                   # per height band: the biggest are kept (bounds the time on a huge map)
MAX_OBJECTS = MAX_WALL_SEGMENTS = 200   # the biggest, so a huge map's snapshot stays small (about 40 KB at most)


def _green(rgb):
    rgb = np.asarray(rgb, int)
    r, g, b = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    return (g > r + 8) & (g > b + 8) & (g > 40)


class ColumnGrid:
    def __init__(self):
        self.i0 = self.k0 = 0                 # grid index of world column [i0 * CELL, k0 * CELL]
        self.hits = None                      # (nx, nz, NY) uint8: frames with points in each slice (saturates)
        self.green = None                     # same, counting only frames where some of those points were green
        self.dropped = 0

    def add(self, pts, rgb=None):
        """One frame's LiDAR points (N, 3) in world coordinates, and their colours (N, 3) if known."""
        p = np.asarray(pts, float).reshape(-1, 3)
        ok = np.isfinite(p).all(1) & (p[:, 1] >= Y_LO) & (p[:, 1] < Y_HI)
        if not ok.any():
            return
        ix = np.floor(p[ok, 0] / CELL).astype(np.int64)
        iz = np.floor(p[ok, 2] / CELL).astype(np.int64)
        iy = np.floor((p[ok, 1] - Y_LO) / CELL).astype(np.int64).clip(0, NY - 1)
        g = _green(np.asarray(rgb)[ok]) if rgb is not None else np.zeros(len(ix), bool)
        self._fit(ix, iz)
        nx, nz = self.hits.shape[:2]
        ix, iz = ix - self.i0, iz - self.k0
        inside = (ix >= 0) & (ix < nx) & (iz >= 0) & (iz < nz)
        self.dropped += int((~inside).sum())
        flat = ((ix * nz + iz) * NY + iy)[inside]
        g = g[inside]
        for arr, idx in ((self.hits, flat), (self.green, flat[g])):
            u = np.unique(idx)
            v = arr.reshape(-1)
            v[u] = np.minimum(v[u].astype(np.uint16) + 1, 255).astype(np.uint8)

    def _fit(self, ix, iz):
        lo_x, hi_x, lo_z, hi_z = int(ix.min()), int(ix.max()) + 1, int(iz.min()), int(iz.max()) + 1
        if self.hits is None:
            self.i0, self.k0 = lo_x - GROW, lo_z - GROW
            shape = (min(hi_x - lo_x + 2 * GROW, MAX_SIDE), min(hi_z - lo_z + 2 * GROW, MAX_SIDE), NY)
            self.hits, self.green = np.zeros(shape, np.uint8), np.zeros(shape, np.uint8)
            return
        nx, nz = self.hits.shape[:2]
        a0, a1 = self.i0, self.i0 + nx
        b0, b1 = self.k0, self.k0 + nz
        n0, n1 = (min(a0, lo_x - GROW), max(a1, hi_x + GROW)) if (lo_x < a0 or hi_x > a1) else (a0, a1)
        m0, m1 = (min(b0, lo_z - GROW), max(b1, hi_z + GROW)) if (lo_z < b0 or hi_z > b1) else (b0, b1)
        if (n0, n1, m0, m1) == (a0, a1, b0, b1):
            return
        if n1 - n0 > MAX_SIDE:                    # keep the old window, then add what fits on the side needed
            n0, n1 = (a0, min(n1, a0 + MAX_SIDE)) if hi_x > a1 else (max(n0, a1 - MAX_SIDE), a1)
        if m1 - m0 > MAX_SIDE:
            m0, m1 = (b0, min(m1, b0 + MAX_SIDE)) if hi_z > b1 else (max(m0, b1 - MAX_SIDE), b1)
        if (n0, n1, m0, m1) == (a0, a1, b0, b1):
            return
        for name in ("hits", "green"):
            new = np.zeros((n1 - n0, m1 - m0, NY), np.uint8)
            new[a0 - n0:a1 - n0, b0 - m0:b1 - m0] = getattr(self, name)
            setattr(self, name, new)
        self.i0, self.k0 = n0, m0

    def nbytes(self):
        return 0 if self.hits is None else self.hits.nbytes + self.green.nbytes

    def view(self):
        """The grid as it is now, to read on another thread. It shares the arrays: add() only writes them in place
        (a count can be a frame ahead) or swaps in new ones when the grid grows, which leaves this view's alone."""
        v = ColumnGrid.__new__(ColumnGrid)
        v.i0, v.k0, v.hits, v.green, v.dropped = self.i0, self.k0, self.hits, self.green, self.dropped
        return v


# ---------------------------------------------------------------- summary
def summarize(grid: ColumnGrid, floor_y, min_hits=MIN_HITS, object_hits=OBJECT_HITS):
    """{"walls": [((x0, z0), (x1, z1)), ...], "objects": [dict(kind, x, z, width, depth, yaw, height, shape)]}"""
    out = dict(walls=[], objects=[])
    if floor_y is None or grid.hits is None:
        return out
    hk = Y_LO + (np.arange(NY) + 0.5) * CELL - floor_y          # slice centre heights above the floor
    ks = np.nonzero((hk >= FLOOR_CLEAR) & (hk <= TOP))[0]
    if not len(ks):
        return out
    hits, h = grid.hits[:, :, ks], hk[ks]
    seen, top, _, run = _columns(hits >= min_hits, h)
    if not seen.any():
        return out
    vertical = seen & (run >= VERTICAL_RUN - 1e-6) & (top >= VERTICAL_TOP)
    ctx = dict(x0=grid.i0 * CELL, z0=grid.k0 * CELL)
    walls, wall_cells = _walls(vertical, ctx)
    room = _room_direction(walls)
    out["walls"] = [_snap_segment(w, room) for w in walls]

    occ = hits >= object_hits                                   # objects: slices seen in more frames than walls need
    seen, top, bottom, _ = _columns(occ, h)
    green = (grid.green[:, :, ks] * occ).sum(2) / np.maximum((hits * occ).sum(2), 1)
    person_like = vertical & (green < 0.35)                     # a standing or seated person, a pole, a wall's end
    keep = seen & ~person_like & ~ndimage.binary_dilation(wall_cells, iterations=1)
    eff = np.where((top >= TABLE[1]) & (bottom >= ON_TOP), bottom, top)   # a bag on a table counts as the table
    ctx.update(top=top, eff=eff, green=green)
    bands = dict(seat=keep & (eff >= SEAT[0]) & (eff < SEAT[1]), table=keep & (eff >= TABLE[0]) & (eff < TABLE[1]),
                 tall=keep & (eff >= TABLE[1]))
    out["objects"] = _objects(bands, ctx, room, out["walls"])[:MAX_OBJECTS]
    out["walls"] = sorted(out["walls"], key=lambda w: -math.dist(*w))[:MAX_WALL_SEGMENTS]
    return out


def _columns(occ, h):
    """Per column: anything there, the top and bottom heights, and the longest gap-free vertical run (m)."""
    seen = occ.any(2)
    top = np.where(seen, h[len(h) - 1 - np.argmax(occ[:, :, ::-1], 2)], -1.0)
    bottom = np.where(seen, h[np.argmax(occ, 2)], -1.0)
    run, cur = np.zeros(seen.shape), np.zeros(seen.shape)
    for j in range(len(h)):
        cur = np.where(occ[:, :, j], cur + CELL, 0.0)
        np.maximum(run, cur, out=run)
    return seen, top, bottom, run


def _centres(mask, ctx):
    ii, kk = np.nonzero(mask)
    return np.stack([ctx["x0"] + (ii + 0.5) * CELL, ctx["z0"] + (kk + 0.5) * CELL], 1)


def _walls(vertical, ctx):
    """Straight runs of vertical columns: Hough lines, split where the run has a gap (a door, a gap in the scan)."""
    pts = _centres(vertical, ctx)
    ii, kk = np.nonzero(vertical)
    used = np.zeros(len(pts), bool)
    wall_cells = np.zeros(vertical.shape, bool)
    segs = []
    if len(pts) < WALL_MIN_M / CELL:
        return segs, wall_cells
    ang = np.deg2rad(np.arange(0.0, 180.0, 2.0))
    cs, sn = np.cos(ang), np.sin(ang)
    rmax = float(np.abs(pts).sum(1).max()) + 1.0
    nr = int(2 * rmax / CELL) + 1

    def votes(P, sign):
        r = ((P[:, :1] * cs + P[:, 1:] * sn + rmax) / CELL).astype(np.int64)
        flat = (np.arange(len(ang)) * nr + r).ravel()
        acc.reshape(-1)[:] += sign * np.bincount(flat, minlength=acc.size).astype(np.int32)

    acc = np.zeros((len(ang), nr), np.int32)
    votes(pts, 1)
    for _ in range(MAX_WALLS):
        a, rb = np.unravel_index(int(np.argmax(acc)), acc.shape)
        if acc[a, rb] < WALL_MIN_M / CELL:
            break
        n = np.array([cs[a], sn[a]])
        d = np.array([-n[1], n[0]])
        rest = np.nonzero(~used)[0]
        rho = pts[rest] @ n
        near = rest[np.abs(rho - ((rb + 0.5) * CELL - rmax)) <= WALL_TOL_M + CELL / 2]
        if len(near) == 0:
            acc[a, rb] = 0
            continue
        r0 = float(np.median(pts[near] @ n))
        inl = rest[np.abs(rho - r0) <= WALL_TOL_M]
        if len(inl) == 0:
            inl = near
        used[inl] = True
        votes(pts[inl], -1)
        t = pts[inl] @ d
        order = np.argsort(t)
        t, inl = t[order], inl[order]
        cuts = np.nonzero(np.diff(t) > WALL_GAP_M)[0] + 1
        for tr, ir in zip(np.split(t, cuts), np.split(inl, cuts)):
            length = tr[-1] - tr[0] + CELL
            cover = len(np.unique(np.round((tr - tr[0]) / CELL))) * CELL / length
            if length < WALL_MIN_M or cover < 0.6:          # a wall is continuous, not blobs lined up (a tree)
                continue
            segs.append(_fit_segment(pts[ir], d))
            wall_cells[ii[ir], kk[ir]] = True
    return segs, wall_cells


def _fit_segment(p, d):
    """Least-squares line through a wall's cells (the Hough direction is only good to a degree or two)."""
    c = p.mean(0)
    ev, vec = np.linalg.eigh(np.cov((p - c).T))
    u = vec[:, 1] if ev[1] > 4 * ev[0] else np.asarray(d, float)
    t = (p - c) @ u
    return c + u * (t.min() - CELL / 2), c + u * (t.max() + CELL / 2)


def _room_direction(walls):
    """The room's main direction (radians, mod 90 degrees) from the walls, weighted by length; None without walls."""
    if not walls:
        return None
    v = np.array([np.subtract(b, a) for a, b in walls])
    w = np.hypot(v[:, 0], v[:, 1])
    th = np.arctan2(v[:, 1], v[:, 0])
    z = (w * np.exp(4j * th)).sum()
    return float(np.angle(z) / 4) if abs(z) > 0.3 * w.sum() else None


def _snap_angle(theta, room):
    """theta (radians) squared to the room's main direction if within SNAP_DEG."""
    if room is None:
        return theta
    k = round((theta - room) / (math.pi / 2))
    snapped = room + k * math.pi / 2
    return snapped if abs(theta - snapped) <= math.radians(SNAP_DEG) else theta


def _snap_segment(seg, room):
    a, b = np.asarray(seg[0], float), np.asarray(seg[1], float)
    v = b - a
    th = math.atan2(v[1], v[0])
    s = _snap_angle(th, room)
    if s != th:
        m, half = (a + b) / 2, np.hypot(*v) / 2
        u = np.array([math.cos(s), math.sin(s)])
        a, b = m - u * half, m + u * half
    return (tuple(round(float(c), 3) for c in a), tuple(round(float(c), 3) for c in b))


class _Part:
    """One connected part of a mask, kept as its bounding window (whole-grid masks made big maps slow)."""
    __slots__ = ("i0", "k0", "m")

    def __init__(self, i0, k0, m):
        self.i0, self.k0, self.m = i0, k0, m

    @property
    def cells(self):
        return int(self.m.sum())

    @property
    def area(self):
        return self.cells * CELL * CELL

    def window(self, arr):
        return arr[self.i0:self.i0 + self.m.shape[0], self.k0:self.k0 + self.m.shape[1]]

    def values(self, arr):
        return self.window(arr)[self.m]

    def centres(self, ctx):
        ii, kk = np.nonzero(self.m)
        return np.stack([ctx["x0"] + (ii + self.i0 + 0.5) * CELL, ctx["z0"] + (kk + self.k0 + 0.5) * CELL], 1)

    def grown(self, n):
        return _Part(self.i0 - n, self.k0 - n, ndimage.binary_dilation(np.pad(self.m, n), iterations=n))

    def overlap(self, other):
        """Cells in both parts."""
        i0, k0 = max(self.i0, other.i0), max(self.k0, other.k0)
        i1 = min(self.i0 + self.m.shape[0], other.i0 + other.m.shape[0])
        k1 = min(self.k0 + self.m.shape[1], other.k0 + other.m.shape[1])
        if i1 <= i0 or k1 <= k0:
            return 0
        a = self.m[i0 - self.i0:i1 - self.i0, k0 - self.k0:k1 - self.k0]
        b = other.m[i0 - other.i0:i1 - other.i0, k0 - other.k0:k1 - other.k0]
        return int((a & b).sum())

    def union(self, other):
        i0, k0 = min(self.i0, other.i0), min(self.k0, other.k0)
        i1 = max(self.i0 + self.m.shape[0], other.i0 + other.m.shape[0])
        k1 = max(self.k0 + self.m.shape[1], other.k0 + other.m.shape[1])
        m = np.zeros((i1 - i0, k1 - k0), bool)
        for p in (self, other):
            m[p.i0 - i0:p.i0 - i0 + p.m.shape[0], p.k0 - k0:p.k0 - k0 + p.m.shape[1]] |= p.m
        return _Part(i0, k0, m)

    def thin(self, cells=3):
        """At most about 2 * cells cells across (a chair's back, a sofa's arms)."""
        return ndimage.distance_transform_edt(np.pad(self.m, 1)).max() <= cells


def _parts(mask, min_cells=3, bridge=False, keep=MAX_PARTS):
    """Connected parts of a mask (4-neighbour, so a diagonal speck doesn't bridge two objects), biggest first.
    bridge: also join parts one empty cell apart (a tabletop broken up by black laptops and bags)."""
    lab, _ = ndimage.label(mask | ndimage.binary_closing(mask) if bridge else mask)
    out = []
    for j, sl in enumerate(ndimage.find_objects(lab), 1):
        if sl is None:
            continue
        sub = (lab[sl] == j) & mask[sl]
        if sub.sum() >= min_cells:
            out.append(_Part(sl[0].start, sl[1].start, sub))
    out.sort(key=lambda p: -p.cells)
    return out[:keep]


def _box(pts, theta):
    """Oriented box of points around direction theta: centre, length along theta, width across."""
    u = np.array([math.cos(theta), math.sin(theta)])
    w = np.array([-u[1], u[0]])
    a, b = pts @ u, pts @ w
    c = u * (a.min() + a.max()) / 2 + w * (b.min() + b.max()) / 2
    return c, float(a.max() - a.min() + CELL), float(b.max() - b.min() + CELL)


def _axis(pts, room):
    """Main direction of a footprint (radians), squared to the room when close; the room's (or 0) when round-ish."""
    if len(pts) >= 3:
        ev, vec = np.linalg.eigh(np.cov((pts - pts.mean(0)).T))
        if ev[1] > 1.3 * max(ev[0], 1e-9):
            return _snap_angle(math.atan2(vec[1, 1], vec[0, 1]), room)
    return room if room is not None else 0.0


def _yaw(f):
    """Dashboard yaw (degrees) of a facing direction f = (dx, dz): 0 = -z, 90 = +x."""
    return math.degrees(math.atan2(f[0], -f[1]))


def _facing_box(pts, facing, room):
    """Box whose depth runs along `facing`: squared to the footprint's own axes when the facing is close to one."""
    th = math.atan2(facing[1], facing[0])
    ax = _axis(pts, room)
    for k in range(4):
        cand = ax + k * math.pi / 2
        if abs(math.remainder(th - cand, 2 * math.pi)) <= math.radians(35):
            th = cand
            break
    c, depth, width = _box(pts, th)
    return c, width, depth, (math.cos(th), math.sin(th))


def _objects(bands, ctx, room, walls):
    eff, top, green = ctx["eff"], ctx["top"], ctx["green"]
    objs = []
    seats = [p for p in _parts(bands["seat"]) if p.area >= MIN_AREA["seat"]]
    seat_h = [float(np.median(p.values(eff))) for p in seats]
    tables, backs = [], {}
    for p in _parts(bands["table"], bridge=True):
        h = float(np.median(p.values(eff)))
        touch = []
        if p.thin():
            grown = p.grown(2)
            touch = [(grown.overlap(s), j) for j, s in enumerate(seats) if h - seat_h[j] >= 0.25]
            touch = [t for t in touch if t[0] > 0]
        if touch:                                          # a chair's or sofa's back (and arms)
            j = max(touch)[1]
            backs[j] = backs[j].union(p) if j in backs else p
        elif p.area >= MIN_AREA["table"]:
            tables.append(p)

    centres = []
    for p in tables:
        pts = p.centres(ctx)
        th = _axis(pts, room)
        c, length, width = _box(pts, th)
        if width < 0.25 or length > 3.0:                   # a rail or ledge, or several things run together
            continue
        fill = len(pts) / max(round(length / CELL) * round(width / CELL), 1)
        rnd = fill <= 0.84 and length <= 1.3 * width and len(pts) >= 12 and _full_corners(pts, c, th, length, width) <= 1
        if rnd:
            length = width = (length + width) / 2
        objs.append(_obj("table", c, length, width, _yaw((-math.sin(th), math.cos(th))), np.percentile(p.values(top), 75),
                         "round" if rnd else "rect"))
        centres.append(c)

    for j, p in enumerate(seats):
        sp = p.centres(ctx)
        sth = _axis(sp, room)
        sc, slen, swid = _box(sp, sth)
        u = np.array([math.cos(sth), math.sin(sth)])
        w = np.array([-u[1], u[0]])
        back, f = backs.get(j), None
        if back is not None:                       # a back runs along the side behind the sitter
            bp = back.centres(ctx)
            rel = bp.mean(0) - sc
            cands = [w, -w] + ([u, -u] if slen <= 1.3 * swid else [])
            f = max(cands, key=lambda v: -float(rel @ v))
            side = np.array([-f[1], f[0]])
            cover = (np.ptp(bp @ side) + CELL) / (np.ptp(sp @ side) + CELL)
            if cover < 0.5 or float(rel @ f) >= 0:
                back, f = None, None
        if f is None and centres:                  # no back seen: a seat faces the nearest table
            near = min(centres, key=lambda c: float(np.hypot(*(c - sc))))
            if 1e-6 < float(np.hypot(*(near - sc))) <= 1.5:
                f = (near - sc) / float(np.hypot(*(near - sc)))
        if f is None:
            f = w
        whole = p.union(back) if back is not None else p
        c, width, depth, f = _facing_box(whole.centres(ctx), f, room)
        if min(width, depth) >= 1.3 and whole.area >= 1.8:
            kind = "bed"
        elif back is not None:
            kind = "sofa" if width >= 0.9 else "chair"
        elif width <= 0.75 and depth <= 0.75:
            kind = "chair"
        elif depth >= 0.45 and width <= 1.6:
            kind = "table"                                 # low: a coffee table or an ottoman
        else:
            kind = "bench"                                 # long and backless: a bench, a ledge, a step
        objs.append(_obj(kind, c, width, depth, _yaw(f), np.percentile(whole.values(top), 75)))

    for p in _parts(bands["tall"]):
        if p.area < MIN_AREA["tall"]:
            continue
        pts = p.centres(ctx)
        th = _axis(pts, room)
        c, length, width = _box(pts, th)
        height = float(p.values(top).max())
        if float(np.average(p.values(green))) >= 0.35:
            size = max(length, width)
            kind = "tree" if height >= 1.6 or size >= 0.8 else "plant"
            objs.append(_obj(kind, c, size, size, 0.0, height, "round"))
            continue
        wall = _nearest_wall(c, walls)
        if wall is None or p.area < 0.12 or length < 0.3:
            continue                                       # a free-standing pole or a person: left out
        c, width, depth, f = _facing_box(pts, _away_from(wall, c), room)
        objs.append(_obj("storage", c, width, depth, _yaw(f), height))
    return _no_overlaps(objs)


def _full_corners(pts, c, th, length, width):
    """How many corners of the box are filled in: a round top leaves all four empty, while a rectangle seen in part
    still fills two or more."""
    u = np.array([math.cos(th), math.sin(th)])
    a, b = (pts - c) @ u, (pts - c) @ np.array([-u[1], u[0]])
    ea, eb = 0.35 * length, 0.35 * width
    cap = max((0.15 * length) * (0.15 * width) / (CELL * CELL), 1.0)
    return sum(int(((sa * a > ea) & (sb * b > eb)).sum() >= 0.5 * cap) for sa in (1, -1) for sb in (1, -1))


def _no_overlaps(objs):
    """Where two shapes cover the same floor (a sofa's seat and its back seen as two things), keep the bigger. A chair
    may tuck under a table by up to half."""
    g = (np.arange(7) + 0.5) / 7 - 0.5
    A, B = (v.ravel() for v in np.meshgrid(g, g, indexing="ij"))
    keep = []                                      # (object, centre, facing, side, radius)
    for o in sorted(objs, key=lambda o: -o["width"] * o["depth"]):
        yaw = math.radians(o["yaw"])
        c, f = np.array([o["x"], o["z"]]), np.array([math.sin(yaw), -math.cos(yaw)])
        r = np.array([-f[1], f[0]])
        rad = math.hypot(o["width"], o["depth"]) / 2
        pts = c + np.outer(A * o["width"], r) + np.outer(B * o["depth"], f)
        ok = True
        for k, kc, kf, kr, krad in keep:
            if math.hypot(*(c - kc)) >= rad + krad:
                continue
            a, b = (pts - kc) @ kr / (k["width"] / 2), (pts - kc) @ kf / (k["depth"] / 2)
            inside = a * a + b * b <= 1 if k["shape"] == "round" else (np.abs(a) <= 1) & (np.abs(b) <= 1)
            if inside.mean() > (0.6 if "chair" in (o["kind"], k["kind"]) else 0.3):
                ok = False
                break
        if ok:
            keep.append((o, c, f, r, rad))
    return [k[0] for k in keep]


def _nearest_wall(c, walls, max_m=0.6):
    best, bd = None, max_m
    for a, b in walls:
        a, b = np.asarray(a), np.asarray(b)
        v = b - a
        t = np.clip((c - a) @ v / max(v @ v, 1e-9), 0, 1)
        dist = float(np.hypot(*(c - (a + t * v))))
        if dist <= bd:
            best, bd = (a, b), dist
    return best


def _away_from(wall, c):
    a, b = wall
    v = (b - a) / max(np.hypot(*(b - a)), 1e-9)
    n = np.array([-v[1], v[0]])
    return n if (c - a) @ n >= 0 else -n


def _obj(kind, c, width, depth, yaw, height, shape="rect"):
    return dict(kind=kind, x=round(float(c[0]), 3), z=round(float(c[1]), 3), width=round(max(float(width), CELL), 2),
                depth=round(max(float(depth), CELL), 2), yaw=round(float(yaw) % 360.0, 1), height=round(float(height), 2),
                shape=shape)
