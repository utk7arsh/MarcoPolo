"""The room layout drawn on the dashboard map (marco/world/layout.py): walls and furniture from the LiDAR column grid,
and how it reaches the dashboard (RealBrain room_layout -> Dashboard map.walls / map.landmarks)."""
import importlib.util
import io
import math
import sys
import time
from pathlib import Path

import numpy as np
import pytest

from marco import codec, geometry as G
from marco.world import layout as L
from marco.world.roommap import RoomMap

GREY, GREEN = (128, 128, 128), (60, 140, 50)


def box(lo, hi, step=0.03):
    """LiDAR-like points on an axis-aligned box: its top and its four sides."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    xs, ys, zs = (np.arange(a, b + 1e-9, step) for a, b in ((x0, x1), (y0, y1), (z0, z1)))
    X, Z = np.meshgrid(xs, zs, indexing="ij")
    out = [np.stack([X.ravel(), np.full(X.size, y1), Z.ravel()], 1)]
    for x in (x0, x1):
        Y, Zs = np.meshgrid(ys, zs, indexing="ij")
        out.append(np.stack([np.full(Y.size, x), Y.ravel(), Zs.ravel()], 1))
    for z in (z0, z1):
        Xs, Y = np.meshgrid(xs, ys, indexing="ij")
        out.append(np.stack([Xs.ravel(), Y.ravel(), np.full(Y.size, z)], 1))
    return np.vstack(out)


def wall(a, b, height=1.6, step=0.03):
    a, b = np.asarray(a, float), np.asarray(b, float)
    t = np.arange(0, 1 + 1e-9, step / np.hypot(*(b - a)))
    y = np.arange(0, height + 1e-9, step)
    T, Y = np.meshgrid(t, y, indexing="ij")
    xz = a + np.outer(T.ravel(), b - a)
    return np.stack([xz[:, 0], Y.ravel(), xz[:, 1]], 1)


def floor(x0, x1, z0, z1, step=0.05):
    X, Z = np.meshgrid(np.arange(x0, x1, step), np.arange(z0, z1, step), indexing="ij")
    return np.stack([X.ravel(), np.zeros(X.size), Z.ravel()], 1)


def cylinder(cx, cz, r, y0, y1, step=0.03):
    th = np.arange(0, 2 * math.pi, step / r)
    y = np.arange(y0, y1 + 1e-9, step)
    T, Y = np.meshgrid(th, y, indexing="ij")
    side = np.stack([cx + r * np.cos(T.ravel()), Y.ravel(), cz + r * np.sin(T.ravel())], 1)
    rr, tt = np.meshgrid(np.arange(0, r, step), th, indexing="ij")
    cap = np.stack([cx + (rr * np.cos(tt)).ravel(), np.full(rr.size, y1), cz + (rr * np.sin(tt)).ravel()], 1)
    return np.vstack([side, cap])


def rotate(p, deg):
    c, s = math.cos(math.radians(deg)), math.sin(math.radians(deg))
    return np.stack([c * p[:, 0] - s * p[:, 2], p[:, 1], s * p[:, 0] + c * p[:, 2]], 1)


def room(deg=0.0):
    """A 4 m x 5 m room: walls, a table, a chair with its back to +z, a sofa with its back to -z, a bag on the table."""
    parts = [(wall((0, 0), (4, 0)), GREY), (wall((4, 0), (4, 5)), GREY), (wall((4, 5), (0, 5)), GREY),
             (wall((0, 5), (0, 0)), GREY), (floor(0, 4, 0, 5), GREY),
             (box((1.5, 0, 2.0), (2.7, 0.75, 2.8)), GREY),                                        # table
             (box((1.8, 0.75, 2.2), (2.1, 1.25, 2.45)), GREY),                                    # bag on it
             (box((1.9, 0, 3.0), (2.35, 0.45, 3.45)), GREY), (box((1.9, 0.45, 3.4), (2.35, 0.9, 3.5)), GREY),  # chair
             (box((1.0, 0, 0.3), (3.0, 0.45, 1.1)), GREY), (box((1.0, 0.45, 0.3), (3.0, 0.85, 0.55)), GREY)]   # sofa
    return [(rotate(p, deg), c) for p, c in parts]


def grid_of(parts, frames=2, jitter=0.004, seed=0):
    rng = np.random.default_rng(seed)
    g = L.ColumnGrid()
    pts = np.vstack([p for p, _ in parts])
    rgb = np.vstack([np.tile(c, (len(p), 1)) for p, c in parts])
    for _ in range(frames):
        g.add(pts + rng.normal(0, jitter, pts.shape), rgb)
    return g


def by_kind(objs, kind):
    return [o for o in objs if o["kind"] == kind]


def test_walls_of_a_room_are_found_and_squared():
    out = L.summarize(grid_of(room()), 0.0)
    truth = [((0, 0), (4, 0)), ((4, 0), (4, 5)), ((4, 5), (0, 5)), ((0, 5), (0, 0))]
    assert len(out["walls"]) >= 4
    for a, b in truth:
        mid = np.add(a, b) / 2
        best = min(out["walls"], key=lambda w: np.hypot(*(np.add(w[0], w[1]) / 2 - mid)))
        assert np.hypot(*(np.add(best[0], best[1]) / 2 - mid)) < 0.2
        assert abs(np.hypot(*np.subtract(best[1], best[0])) - np.hypot(*np.subtract(b, a))) < 0.4
    for a, b in out["walls"]:                                            # squared to the room
        assert abs(G.wrap180(2 * math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 180 - 0.0)) < 1.0


def test_furniture_kinds_positions_and_facing():
    objs = L.summarize(grid_of(room()), 0.0)["objects"]
    tables, chairs, sofas = by_kind(objs, "table"), by_kind(objs, "chair"), by_kind(objs, "sofa")
    assert len(tables) == 1 and len(chairs) == 1 and len(sofas) == 1, objs
    t, c, s = tables[0], chairs[0], sofas[0]
    assert np.hypot(t["x"] - 2.1, t["z"] - 2.4) < 0.15 and abs(t["width"] - 1.2) < 0.25 and abs(t["depth"] - 0.8) < 0.25
    assert np.hypot(c["x"] - 2.125, c["z"] - 3.25) < 0.15
    assert abs(G.wrap180(c["yaw"] - 0.0)) < 20                         # back at +z: faces -z (yaw 0)
    assert np.hypot(s["x"] - 2.0, s["z"] - 0.7) < 0.15 and abs(s["width"] - 2.0) < 0.3
    assert abs(G.wrap180(s["yaw"] - 180.0)) < 20                       # back at -z: faces +z
    assert not by_kind(objs, "storage")                                # the bag counts as part of the table


def test_a_rotated_room_keeps_its_shapes():
    out = L.summarize(grid_of(room(25.0)), 0.0)
    angles = {round(math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))) % 90 for a, b in out["walls"]}
    assert angles <= {24, 25, 26}, angles
    kinds = sorted(o["kind"] for o in out["objects"])
    assert kinds == ["chair", "sofa", "table"], out["objects"]
    s = by_kind(out["objects"], "sofa")[0]
    assert abs(G.wrap180(s["yaw"] - (180.0 + 25.0))) < 20


def test_green_and_tall_is_a_tree_but_a_person_is_left_out():
    parts = [(floor(-3, 3, -3, 3), GREY), (cylinder(1.5, 0.0, 0.12, 0.0, 1.2), GREEN), (cylinder(1.5, 0.0, 0.6, 1.2, 2.3), GREEN),
             (cylinder(-1.5, 0.0, 0.2, 0.0, 1.75), GREY)]
    objs = L.summarize(grid_of(parts), 0.0)["objects"]
    trees = by_kind(objs, "tree")
    assert len(trees) == 1 and np.hypot(trees[0]["x"] - 1.5, trees[0]["z"]) < 0.2 and trees[0]["width"] >= 0.8
    assert all(np.hypot(o["x"] + 1.5, o["z"]) > 0.5 for o in objs)    # nothing drawn where the person stands


def test_furniture_needs_two_frames_but_walls_one():
    parts = [(floor(0, 4, 0, 5), GREY), (wall((0, 0), (4, 0)), GREY), (box((1.5, 0, 2.0), (2.7, 0.75, 2.8)), GREY)]
    once = L.summarize(grid_of(parts, frames=1), 0.0)
    assert once["walls"] and not once["objects"]
    twice = L.summarize(grid_of(parts, frames=2), 0.0)
    assert by_kind(twice["objects"], "table")


def test_nothing_without_a_floor_or_points():
    assert L.summarize(L.ColumnGrid(), 0.0) == dict(walls=[], objects=[])
    assert L.summarize(grid_of(room()), None) == dict(walls=[], objects=[])
    g = L.ColumnGrid()
    g.add(np.zeros((0, 3)))
    g.add(np.array([[0.0, 9.0, 0.0], [np.nan, 0.0, 0.0]]))           # out of height range, not finite
    assert g.hits is None


def test_grid_grows_keeps_counts_and_stops_at_its_cap():
    g = L.ColumnGrid()
    g.add(np.array([[0.05, 0.05, 0.05]]))
    g.add(np.array([[12.0, 0.05, -9.0]]))                               # grows in +x and -z
    g.add(np.array([[0.05, 0.05, 0.05]]))
    i, k, y = int(0.05 // L.CELL) - g.i0, int(0.05 // L.CELL) - g.k0, int((0.05 - L.Y_LO) // L.CELL)
    assert g.hits[i, k, y] == 2
    g.add(np.array([[60.0, 0.0, 0.0]]))                                # beyond 40 m: dropped, the grid stays capped
    assert g.hits.shape[0] <= L.MAX_SIDE and g.dropped == 1
    for _ in range(300):
        g.add(np.array([[0.05, 0.05, 0.05]]))
    assert g.hits[i, k, y] == 255                                       # saturates, never wraps


def _old_add(cells, fr, rgb, jpeg_scale, voxel=0.05, step=4):
    """RoomMap.add before the column grid, kept here to prove the map points didn't change."""
    pts, uvs = fr.point_cloud(step=step)
    keys = np.floor(pts / voxel).astype(np.int64)
    h, w = rgb.shape[:2]
    new = []
    for key, p, (u, v) in zip(map(tuple, keys), pts, uvs):
        if key in cells:
            continue
        iu, iv = min(int(u * jpeg_scale), w - 1), min(int(v * jpeg_scale), h - 1)
        r, g, b = (int(c) for c in rgb[iv, iu][:3])
        cell = [round(float(p[0]), 3), round(float(p[1]), 3), round(float(p[2]), 3), r, g, b]
        cells[key] = cell
        new.append(cell)
    return new


TOOLS = Path(__file__).resolve().parents[1] / "tools"


@pytest.fixture(scope="module")
def fake(tmp_path_factory):
    spec = importlib.util.spec_from_file_location("fake_session", TOOLS / "fake_session.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules["fake_session"] = m
    spec.loader.exec_module(m)
    d = tmp_path_factory.mktemp("layout") / "fake"
    m.main(str(d))
    return d


def frames(path):
    from PIL import Image
    from marco.session import Session
    s = Session(path)
    for meta in s.frames:
        jpeg, d, c = s.frame_bytes(meta)
        yield meta, jpeg, codec.decode_depth(d), codec.decode_conf(c), np.asarray(Image.open(io.BytesIO(jpeg)).convert("RGB"))


def test_room_map_points_are_unchanged(fake):
    rm, old = RoomMap(), {}
    for meta, _, depth, conf, rgb in frames(fake):
        fr = G.Frame(G.mat4(meta["camera_transform"]), G.mat3(meta["intrinsics"]), tuple(meta["image_resolution"]), depth, conf)
        assert rm.add(fr, rgb, meta["jpeg_scale"]) == _old_add(old, fr, rgb, meta["jpeg_scale"])
    assert rm.cells == old
    assert rm.grid.hits is not None


class NoDetector:
    def detect(self, *a, **k):
        return []

    def register(self, *a, **k):
        return dict(quality="ok", reason="", box=[0, 0, 1, 1])


def test_brain_sends_the_layout_every_few_frames_and_resets_on_a_new_map(fake, monkeypatch):
    from marco import brain as B
    monkeypatch.setattr(B, "LAYOUT_EVERY", 3)
    monkeypatch.setattr(B, "LAYOUT_ASYNC", False)
    b = B.RealBrain(NoDetector())
    sent = []
    for n, (meta, jpeg, depth, conf, _) in enumerate(frames(fake), 1):
        out = b.on_frame(meta, jpeg, depth, conf)
        sent += [(n, m) for ch, m in out if ch == "dashboard" and m.get("type") == "room_layout"]
    assert sent and all((n - 1) % 3 == 0 for n, _ in sent)
    last = sent[-1][1]
    assert last["map_id"] == meta.get("map_id") and len(last["walls"]) >= 3
    assert {"table", "sofa"} <= {o["kind"] for o in last["objects"]}
    cells = len(b.roommap.cells)
    b.on_frame(dict(meta, map_id="another-map"), jpeg, depth, conf)
    assert len(b.roommap.cells) < cells                                # the old map's voxels are gone


def test_layout_off_sends_nothing(fake, monkeypatch):
    from marco import brain as B
    monkeypatch.setattr(B, "LAYOUT_EVERY", 0)
    monkeypatch.setattr(B, "LAYOUT_ASYNC", False)
    b = B.RealBrain(NoDetector())
    for meta, jpeg, depth, conf, _ in frames(fake):
        assert not [m for ch, m in b.on_frame(meta, jpeg, depth, conf) if m.get("type") == "room_layout"]


def test_the_layout_thread_never_holds_up_a_frame_and_drops_a_stale_map(fake, monkeypatch):
    import threading
    from marco import brain as B
    monkeypatch.setattr(B, "LAYOUT_EVERY", 1)
    monkeypatch.setattr(B, "LAYOUT_ASYNC", True)
    gate = threading.Event()
    real = B.summarize
    monkeypatch.setattr(B, "summarize", lambda *a: (gate.wait(5), real(*a))[1])   # a layout that takes "forever"
    b = B.RealBrain(NoDetector())
    got = []
    for meta, jpeg, depth, conf, _ in frames(fake):
        t0 = time.perf_counter()
        got += [m for _, m in b.on_frame(meta, jpeg, depth, conf) if m.get("type") == "room_layout"]
        assert time.perf_counter() - t0 < 2.0                          # the frame didn't wait for it
    assert got == [] and b._layout is not None                          # one job at a time, still running
    gate.set()
    b._layout[0].result(5)
    got = [m for _, m in b.on_frame(meta, jpeg, depth, conf) if m.get("type") == "room_layout"]
    assert len(got) == 1 and got[0]["walls"]                            # delivered with the next frame
    gate.clear()
    b.on_frame(meta, jpeg, depth, conf)                                 # starts another
    job = b._layout
    b.on_frame(dict(meta, map_id="another-map"), jpeg, depth, conf)     # the map changes meanwhile
    gate.set()
    job[0].result(5)
    assert not [m for _, m in b.on_frame(dict(meta, map_id="another-map"), jpeg, depth, conf)
                if m.get("type") == "room_layout" and m["map_id"] != "another-map"]
