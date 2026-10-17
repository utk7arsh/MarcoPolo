"""A furnished room made of simple primitives, plus vectorised ray casting.

World frame follows ARKit: metres, +x right, +y up (gravity), +z toward the viewer (so the
initial "forward" is -z). Primitives are axis-aligned boxes and vertical cylinders; that is
enough to reproduce the depth phenomena that matter here (occlusion, edges, thin and small
objects, transparent and dark materials, items on tables, shelves, sofas and the floor).
"""
from dataclasses import dataclass, field

import numpy as np


@dataclass
class Box:
    name: str
    lo: np.ndarray
    hi: np.ndarray
    material: str = "matte"  # matte | dark | specular | transparent
    is_item: bool = False
    surface: str = ""        # what an item rests on, or the furniture's own category

    def __post_init__(self):
        self.lo = np.asarray(self.lo, float)
        self.hi = np.asarray(self.hi, float)

    @property
    def center(self):
        return (self.lo + self.hi) / 2

    @property
    def base(self):
        c = self.center
        return np.array([c[0], self.lo[1], c[2]])

    def corners(self):
        return np.array([[x, y, z] for x in (self.lo[0], self.hi[0]) for y in (self.lo[1], self.hi[1]) for z in (self.lo[2], self.hi[2])])

    def moved_to(self, base_xyz):
        half = (self.hi - self.lo) / 2
        b = np.asarray(base_xyz, float)
        lo = np.array([b[0] - half[0], b[1], b[2] - half[2]])
        return Box(self.name, lo, lo + 2 * half, self.material, self.is_item, self.surface)


@dataclass
class Cylinder:
    name: str
    cx: float
    cz: float
    y0: float
    y1: float
    r: float
    material: str = "matte"
    is_item: bool = True
    surface: str = ""

    @property
    def center(self):
        return np.array([self.cx, (self.y0 + self.y1) / 2, self.cz])

    @property
    def base(self):
        return np.array([self.cx, self.y0, self.cz])

    def corners(self):
        return np.array([[self.cx + sx * self.r, y, self.cz + sz * self.r] for sx in (-1, 1) for y in (self.y0, self.y1) for sz in (-1, 1)])

    def moved_to(self, base_xyz):
        b = np.asarray(base_xyz, float)
        return Cylinder(self.name, b[0], b[2], b[1], b[1] + (self.y1 - self.y0), self.r, self.material, self.is_item, self.surface)


def ray_box(o, d, b: Box):
    """Entry distance of rays (N,3) into box, inf if missed (rays start outside)."""
    with np.errstate(divide="ignore", invalid="ignore"):
        inv = 1.0 / d
        t1 = (b.lo - o) * inv
        t2 = (b.hi - o) * inv
    tmin = np.nanmax(np.minimum(t1, t2), axis=1)
    tmax = np.nanmin(np.maximum(t1, t2), axis=1)
    hit = (tmax >= np.maximum(tmin, 1e-6))
    t = np.where(tmin > 1e-6, tmin, np.inf)
    return np.where(hit, t, np.inf)


def ray_room_exit(o, d, lo, hi):
    """Distance at which rays starting inside the room hit a wall, floor or ceiling."""
    with np.errstate(divide="ignore", invalid="ignore"):
        inv = 1.0 / d
        t1 = (lo - o) * inv
        t2 = (hi - o) * inv
    return np.nanmin(np.maximum(t1, t2), axis=1)


def ray_cylinder(o, d, c: Cylinder):
    ox, oz = o[:, 0] - c.cx, o[:, 2] - c.cz
    dx, dz = d[:, 0], d[:, 2]
    a = dx * dx + dz * dz
    bq = 2 * (ox * dx + oz * dz)
    cq = ox * ox + oz * oz - c.r * c.r
    disc = bq * bq - 4 * a * cq
    t = np.full(len(o), np.inf)
    ok = (disc >= 0) & (a > 1e-12)
    sq = np.sqrt(np.where(ok, disc, 0))
    t_side = np.where(ok, (-bq - sq) / (2 * np.where(a > 1e-12, a, 1)), np.inf)
    y = o[:, 1] + t_side * d[:, 1]
    side_ok = ok & (t_side > 1e-6) & (y >= c.y0) & (y <= c.y1)
    t = np.where(side_ok, t_side, t)
    with np.errstate(divide="ignore", invalid="ignore"):
        t_top = (c.y1 - o[:, 1]) / d[:, 1]
    px = o[:, 0] + t_top * d[:, 0] - c.cx
    pz = o[:, 2] + t_top * d[:, 2] - c.cz
    top_ok = (t_top > 1e-6) & (px * px + pz * pz <= c.r * c.r) & (o[:, 1] > c.y1)
    return np.where(top_ok & (t_top < t), t_top, t)


def intersect(prim, o, d):
    return ray_cylinder(o, d, prim) if isinstance(prim, Cylinder) else ray_box(o, d, prim)


@dataclass
class Room:
    lo: np.ndarray = field(default_factory=lambda: np.array([-2.5, 0.0, -5.0]))
    hi: np.ndarray = field(default_factory=lambda: np.array([2.5, 2.6, 1.0]))
    furniture: list = field(default_factory=list)
    items: dict = field(default_factory=dict)

    def prims(self):
        return list(self.furniture) + list(self.items.values())

    def cast(self, o, d, exclude_items=False, only=None):
        """Return (t, index) for rays; index -1 = room shell, else index into prims()."""
        prims = self.prims() if only is None else only
        t = ray_room_exit(o, d, self.lo, self.hi)
        idx = np.full(len(o), -1)
        for i, p in enumerate(prims):
            if exclude_items and getattr(p, "is_item", False):
                continue
            ti = intersect(p, o, d)
            closer = ti < t
            t = np.where(closer, ti, t)
            idx = np.where(closer, i, idx)
        return t, idx


def demo_room():
    """Living room / kitchen: 5 m x 6 m. Forward (-z) from the start position faces the sofa wall."""
    f = [
        Box("coffee_table", [-0.6, 0.0, -2.4], [0.6, 0.45, -1.8], surface="table"),
        Box("dining_table", [1.2, 0.0, -1.2], [2.3, 0.75, -0.2], surface="table"),
        Box("sofa_seat", [-1.5, 0.0, -4.0], [1.5, 0.45, -3.2], surface="seat"),
        Box("sofa_back", [-1.5, 0.45, -4.0], [1.5, 0.85, -3.75], surface="seat"),
        Box("shelf", [-2.5, 0.0, -1.6], [-2.15, 1.20, -0.6], surface="storage"),
        Box("entry_table", [-2.5, 0.0, 0.2], [-2.1, 0.80, 0.9], surface="table"),
        Box("kitchen_counter", [1.9, 0.0, -4.95], [2.5, 0.92, -2.4], surface="table"),
        Box("cereal_box", [5.0, 0.0, 5.0], [5.2, 0.3, 5.06]),  # parked outside; used as an occluder
    ]
    items = {
        "bottle": Cylinder("bottle", 0.25, -2.1, 0.45, 0.70, 0.035, surface="coffee_table"),
        "keys": Box("keys", [-0.30, 0.45, -2.15], [-0.22, 0.465, -2.10], is_item=True, surface="coffee_table"),
        "wallet": Box("wallet", [1.6, 0.75, -0.8], [1.71, 0.77, -0.71], is_item=True, surface="dining_table"),
        "glasses_case": Box("glasses_case", [-0.5, 0.45, -3.6], [-0.34, 0.49, -3.54], material="dark", is_item=True, surface="sofa_seat"),
        "mug": Cylinder("mug", -2.32, -1.0, 1.20, 1.30, 0.045, surface="shelf"),
    }
    return Room(furniture=f, items=items)
