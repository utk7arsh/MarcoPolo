"""Two fixes found on the first real iPhone recordings: ARKit's origin is where the phone started (so surfaces are
named from the floor seen in the LiDAR map), and far detections must not move items (range gate)."""
import numpy as np

from marco import geometry as G
from marco.brain import MAX_RANGE_M, RealBrain
from marco.perception.detector import TruthDetector
from marco.world.memory import CHEST_M, World
from marco.world.roommap import RoomMap


def test_floor_is_the_lowest_dense_level_of_the_map():
    m = RoomMap()
    rng = np.random.default_rng(0)
    floor = [(x, -1.31, z) for x, z in rng.uniform(-2, 2, (3000, 2))]          # 1.31 m below the start pose
    table = [(x, -0.62, z) for x, z in rng.uniform(-0.5, 0.5, (400, 2))]
    wall = [(-2.0, y, z) for y, z in zip(rng.uniform(-1.3, 1.0, 1500), rng.uniform(-2, 2, 1500))]
    noise = [(0.0, -1.6, 0.0)] * 3                                               # a few stray points below it
    for i, p in enumerate(floor + table + wall + noise):
        m.cells[i] = [p[0], p[1], p[2], 0, 0, 0]
    assert abs(m.floor_y() - (-1.31)) < 0.05
    assert RoomMap().floor_y() is None                                           # not enough map yet


def test_surfaces_are_named_from_the_floor_not_the_arkit_origin():
    w = World()
    T = np.eye(4)
    T[1, 3] = 0.0                                                                # ARKit: the phone starts at y = 0
    w.observe_camera(T)
    assert w.surface_for(-0.62) == G.surface_name(CHEST_M - 0.62) == "table"    # before the floor is known: a guess
    w.add_item("wallet", item_id="w")
    w.sighting("w", [0.3, -0.63, -1.2], t=1.0)
    w.set_floor(-1.31)                                                           # the map found the floor
    assert w.items["w"].surface == "table"                                       # 0.68 m above the floor
    assert w.surface_for(-1.30) == "floor" and w.surface_for(-0.35) == "counter"
    assert G.surface_name(-0.63) == "floor"                                      # what the old code said


def frame_at(depth_m):
    T = np.eye(4)
    K = np.array([[1350.0, 0, 960], [0, 1350, 720], [0, 0, 1]])
    d = np.full((192, 256), depth_m, np.float32)
    return G.Frame(T, K, (1920, 1440), d, np.full((192, 256), 2, np.uint8))


def test_detections_beyond_lidar_range_are_not_placed():
    b = RealBrain(TruthDetector({}))
    box = [900, 1100, 1020, 1300]                                                # low in the image: looking down
    near = b.place(box, frame_at(1.5))
    assert near is not None and np.all(np.isfinite(near))
    assert b.place(box, frame_at(MAX_RANGE_M + 2.0)) is None
