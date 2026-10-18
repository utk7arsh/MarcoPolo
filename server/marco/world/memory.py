"""The world model: where every registered item is (world coordinates), where the user is, and what happened.

Rules (POC 2, POC 25):
  - an item's first sighting places it ("seen")
  - a sighting near the stored spot (within NEAR_M) refreshes it
  - a sighting elsewhere only moves the item after CONFIRM sightings that agree (within NEAR_M of each other)
    inside CONFIRM_WINDOW_S: false detections are common, false moves are worse than late ones
      -> "moved", or "put_down" if the item had been picked up or was missing
  - the stored spot in view, not occluded, and no detection MISSES frames in a row -> "missing"
    ("picked_up" instead if a hand touched it in the last TOUCH_PICKUP_S)
  - the user enters the door zone while a CARRY item still sits on a surface -> "left_behind" (once per visit)
  - a new map (failed relocalisation) makes every stored position "stale" until the item is seen again
"""
import time
import uuid
from dataclasses import dataclass, field

import numpy as np

from .. import geometry as G

NEAR_M = 0.25
CONFIRM = 2
CONFIRM_WINDOW_S = 10.0
MISSES = 3
TOUCH_PICKUP_S = 10.0
CARRY = {"keys", "wallet", "phone", "glasses", "sunglasses", "cane"}
CHEST_M = 1.30                 # a chest-mounted (or hand-held) phone sits about this far above the floor


def now_wall():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{int(time.time() * 1000) % 1000:03d}Z"


@dataclass
class Item:
    item_id: str
    name: str
    position: np.ndarray | None = None
    surface: str | None = None
    size_m: float = 0.10
    state: str = "registered"          # registered | present | missing | picked_up | stale
    last_seen_t: float | None = None
    last_seen_wall: str | None = None
    label_text: str | None = None
    label_audio_url: str | None = None
    confidence: float = 0.0
    pending: list = field(default_factory=list)   # (t, position) sightings away from the stored spot
    misses: int = 0
    touched_t: float | None = None

    def public(self):
        return dict(item_id=self.item_id, name=self.name,
                    position=None if self.position is None else [round(float(v), 3) for v in self.position],
                    surface=self.surface, state=self.state, last_seen_wall=self.last_seen_wall,
                    label_text=self.label_text, label_audio_url=self.label_audio_url, size_m=round(self.size_m, 3))


class World:
    def __init__(self):
        self.items: dict[str, Item] = {}
        self.events: list[dict] = []
        self.user_T = None
        self.user_t = None
        self.trajectory = []
        self.door = None                   # (position, radius) once set
        self.in_door = False
        self.map_id = None
        self.floor_y = None                # from the room map; until then, CHEST_M below the first camera pose
        self.first_cam_y = None

    def observe_camera(self, T):
        if self.first_cam_y is None:
            self.first_cam_y = float(T[1, 3])

    def surface_for(self, y):
        """Surface name for an item resting at world height y, measured from the floor."""
        floor = self.floor_y if self.floor_y is not None else (self.first_cam_y - CHEST_M if self.first_cam_y is not None else 0.0)
        return G.surface_name(float(y) - floor)

    def set_floor(self, floor_y):
        """A new floor estimate: rename the surfaces of items already placed."""
        if floor_y is None or (self.floor_y is not None and abs(floor_y - self.floor_y) < 0.03):
            return
        self.floor_y = floor_y
        for it in self.items.values():
            if it.position is not None:
                it.surface = self.surface_for(it.position[1])

    # ---------------------------------------------------------------- items
    def add_item(self, name, item_id=None, **kw):
        iid = item_id or uuid.uuid4().hex[:12]
        self.items[iid] = Item(item_id=iid, name=name, **kw)
        return self.items[iid]

    def find(self, name):
        n = (name or "").strip().lower()
        stem = n[:-1] if n.endswith("s") else n
        for it in self.items.values():
            m = it.name.lower()
            if m == n or m.rstrip("s") == stem or (stem and stem in m):
                return it
        return None

    def _event(self, kind, it: Item, **extra):
        e = dict(type="event", kind=kind, item_id=it.item_id, name=it.name,
                 position=None if it.position is None else [round(float(v), 3) for v in it.position],
                 surface=it.surface, t_wall=now_wall(), **extra)
        self.events.append(e)
        return e

    def sighting(self, item_id, pos, t, size_m=None, confidence=1.0):
        """One detection placed in 3D. Returns the events it causes."""
        it = self.items[item_id]
        pos = np.asarray(pos, float)
        it.misses = 0
        if size_m:
            it.size_m = 0.7 * it.size_m + 0.3 * size_m
        def refresh(p):
            it.position = p
            it.surface = self.surface_for(p[1])
            it.last_seen_t, it.last_seen_wall, it.confidence = t, now_wall(), confidence
        if it.position is None or it.state == "stale":     # first sighting, or first since a new map
            refresh(pos)
            it.state = "present"
            it.pending.clear()
            return [self._event("seen", it)]
        if np.linalg.norm(pos - it.position) <= NEAR_M:
            was = it.state
            refresh(0.7 * it.position + 0.3 * pos)
            it.pending.clear()
            it.state = "present"
            return [self._event("seen", it)] if was in ("stale", "missing", "picked_up") else []
        it.pending = [(tt, p) for tt, p in it.pending if t - tt <= CONFIRM_WINDOW_S] + [(t, pos)]
        agree = [p for _, p in it.pending if np.linalg.norm(p - pos) <= NEAR_M]
        if len(agree) < CONFIRM:
            return []
        old, was = it.position.copy(), it.state
        refresh(np.median(np.array(agree), axis=0))
        it.pending.clear()
        it.state = "present"
        kind = "put_down" if was in ("picked_up", "missing") else "moved"
        return [self._event(kind, it, from_position=[round(float(v), 3) for v in old])]

    def check_absence(self, fr: G.Frame, detected_ids, t):
        """Items whose stored spot is in view (and not hidden behind something nearer) but were not detected."""
        out = []
        for it in self.items.values():
            if it.item_id in detected_ids or it.position is None or it.state not in ("present",):
                continue
            uv, z = fr.project(it.position[None])
            (u, v), z = uv[0], float(z[0])
            if not (0.15 < z < 4.0) or not (0.05 * fr.W < u < 0.95 * fr.W and 0.05 * fr.H < v < 0.95 * fr.H):
                continue
            seen_z = fr.depth_at(u, v, r=1, min_conf=1)
            if seen_z is not None and seen_z < z - 0.15:
                continue                                    # something nearer hides the spot
            it.misses += 1
            if it.misses >= MISSES:
                it.misses = 0
                touched = it.touched_t is not None and t - it.touched_t <= TOUCH_PICKUP_S
                it.state = "picked_up" if touched else "missing"
                out.append(self._event(it.state, it))
        return out

    def touched(self, item_id, t):
        if item_id in self.items:
            self.items[item_id].touched_t = t

    # ---------------------------------------------------------------- user
    def user_pose(self, T, t):
        self.observe_camera(T)
        self.user_T, self.user_t = T, t
        self.trajectory.append([round(float(T[0, 3]), 3), round(float(T[2, 3]), 3), t])
        if len(self.trajectory) > 20000:
            self.trajectory = self.trajectory[-10000:]
        if self.door is None:
            return []
        door, r = self.door
        inside = G.horizontal_distance(T[:3, 3], door) <= r
        out = []
        if inside and not self.in_door:
            for it in self.items.values():
                if it.name.lower().rstrip("s") in {c.rstrip("s") for c in CARRY} and it.state == "present" and it.position is not None:
                    if G.horizontal_distance(it.position, door) > r:   # still on a surface elsewhere in the room
                        out.append(self._event("left_behind", it))
        self.in_door = inside
        return out

    def set_door(self, position, radius=0.8):
        self.door = (np.asarray(position, float), radius)

    def new_map(self, map_id):
        self.map_id = map_id
        for it in self.items.values():
            if it.position is not None:
                it.state = "stale"

    def relocalized(self, map_id):
        self.map_id = map_id

    # ---------------------------------------------------------------- views
    def user_public(self):
        if self.user_T is None:
            return None
        return dict(position=[round(float(v), 3) for v in self.user_T[:3, 3]], heading_deg=round(G.heading_deg(self.user_T), 1))

    def snapshot(self):
        return dict(type="world", items=[it.public() for it in self.items.values()], user=self.user_public(),
                    trajectory=self.trajectory[-3000:])

    def answer_find(self, query_id, name):
        it = self.find(name)
        if it is None:
            return dict(type="answer", query_id=query_id, kind="find", found=False, reason="not_registered", name=name)
        if it.position is None:
            return dict(type="answer", query_id=query_id, kind="find", found=False, reason="never_seen", item_id=it.item_id, name=it.name)
        if it.state == "missing":
            return dict(type="answer", query_id=query_id, kind="find", found=False, reason="not_where_last_seen",
                        item_id=it.item_id, name=it.name, last_position=[round(float(v), 3) for v in it.position], surface=it.surface)
        seen_ago = None if it.last_seen_t is None or self.user_t is None else round(self.user_t - it.last_seen_t, 1)
        return dict(type="answer", query_id=query_id, kind="find", found=True, item_id=it.item_id, name=it.name,
                    position=[round(float(v), 3) for v in it.position], surface=it.surface, seen_ago_s=seen_ago,
                    confidence=round(float(it.confidence), 3), state=it.state)
