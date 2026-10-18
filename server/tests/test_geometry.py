import numpy as np
import pytest

from marco import geometry as G


def rot_y(deg):
    a = np.radians(deg)
    return np.array([[np.cos(a), 0, np.sin(a)], [0, 1, 0], [-np.sin(a), 0, np.cos(a)]])


def test_column_major_round_trip_matches_simd_layout():
    T = np.eye(4)
    T[:3, :3] = rot_y(30)
    T[:3, 3] = [1, 2, 3]
    flat = G.flat_colmajor(T)
    assert flat[12:15] == [1, 2, 3]                 # simd: columns.3 holds the translation
    assert np.allclose(G.mat4(flat), T)


def test_check_pose_catches_row_major_matrices():
    T = np.eye(4)
    T[:3, 3] = [1, 2, 3]
    with pytest.raises(ValueError):
        G.check_pose(G.mat4(T.reshape(-1).tolist()))   # row-major flattening puts the translation in the last row


def test_upright_turns_portrait_vest_and_other_mounts():
    from device import chest_camera_pose                # emulator: portrait, sensor long axis pointing down
    T = chest_camera_pose((0, 0), 0, 0, tilt_deg=30)
    assert G.upright_turns(T) == 1
    flip = np.eye(4)
    flip[:3, :3] = np.diag([-1, -1, 1])                 # phone upside down in the vest (rotate 180 about the optical axis)
    assert G.upright_turns(T @ flip) == 3
    land = np.eye(4)                                    # landscape, camera level: image already upright
    assert G.upright_turns(land) == 0


@pytest.mark.parametrize("k", [0, 1, 2, 3])
def test_rotate_unrotate_box_round_trip(k):
    w, h = 960, 720
    b = [100.0, 50.0, 300.0, 400.0]
    r = G.rotate_box(b, k, w, h)
    assert np.allclose(G.unrotate_box(r, k, w, h), b)
    rw, rh = (h, w) if k % 2 else (w, h)
    assert 0 <= r[0] < r[2] <= rw and 0 <= r[1] < r[3] <= rh


def test_rotate_clockwise_moves_left_edge_to_top():
    w, h = 960, 720
    x, y = G.rotate_point(0, h / 2, 1, w, h)          # middle of the left edge
    assert (x, y) == (h / 2, 0)                        # becomes the middle of the top edge


def test_detector_box_to_sensor_scales_and_rotates_back():
    sensor = [400.0, 300.0, 600.0, 500.0]              # full-res sensor pixels
    jpeg = [v * 0.5 for v in sensor]
    up = G.rotate_box(jpeg, 1, 960, 720)
    assert np.allclose(G.detector_box_to_sensor(up, 1, 960, 720, 0.5), sensor)


def emulated_frame(seed=0):
    from device import K, Phone, chest_camera_pose
    from scene import demo_room
    rng = np.random.default_rng(seed)
    room = demo_room()
    T = chest_camera_pose((0.0, -1.2), 0.0, 0.0, tilt_deg=30)
    fr = Phone(room, rng).frame(T, 0.0)
    return room, fr, G.Frame(fr["T_true"], K, (1920, 1440), fr["depth"], fr["conf"])


def test_project_unproject_inverse():
    _, _, F = emulated_frame()
    p = np.array([0.2, 0.5, -2.0])
    (u, v), z = F.project(p[None])[0][0], F.project(p[None])[1][0]
    assert np.allclose(F.unproject(u, v, z), p, atol=1e-9)


def test_locate_footprint_places_bottle_on_the_coffee_table():
    room, fr, F = emulated_frame()
    bottle = room.items["bottle"]
    uv, z = F.project(bottle.corners())
    box = [*uv.min(0), *uv.max(0)]
    p = G.locate_footprint(box, F)
    assert p is not None
    assert np.linalg.norm((p - bottle.base)[[0, 2]]) < 0.15     # POC 1: 5-14 cm
    assert abs(p[1] - bottle.base[1]) < 0.10


def test_heading_relative_azimuth_clock_and_steps():
    from device import chest_camera_pose
    T = chest_camera_pose((0, 0), 90.0, 0, tilt_deg=30)        # torso turned right: facing +x
    assert G.heading_deg(T) == pytest.approx(90.0, abs=0.5)
    user = T[:3, 3]
    assert G.clock_position(G.relative_azimuth_deg(user, 90.0, user + [2, 0, 0])) == 12   # ahead
    assert G.clock_position(G.relative_azimuth_deg(user, 90.0, user + [0, 0, 2])) == 3    # right of +x is +z
    assert G.clock_position(G.relative_azimuth_deg(user, 90.0, user + [-2, 0, 0])) == 6   # behind
    assert G.clock_position(G.relative_azimuth_deg(user, 90.0, user + [0, 0, -2])) == 9   # left
    assert G.steps(1.4) == 2 and G.steps(0.2) == 1


def test_surface_names_by_height():
    assert [G.surface_name(h) for h in (0.0, 0.45, 0.75, 0.92, 1.3)] == ["floor", "seat", "table", "counter", "shelf"]
