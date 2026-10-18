import numpy as np

from marco import codec, geometry as G
from marco.touch import JOINTS, TouchDetector

K = np.array([[1600.0, 0, 960], [0, 1600, 720], [0, 0, 1]])
ITEMS = {"jar": (np.array([0.0, -0.3, -0.6]), 0.07)}     # 7 cm jar standing 30 cm below the camera, 60 cm ahead


def hand_msg(tip_world, tip_conf=0.9, knuckle_px=(900, 700), beyond_gap=0.0):
    """A hand message: finger pointing down in the image; the depth just past the fingertip is the fingertip's
    depth + beyond_gap (0 = touching a surface; a few cm = hovering in front of it)."""
    T = np.eye(4)                                   # camera at the origin, looking down -z
    F = G.Frame(T, K, (1920, 1440), np.zeros((1, 1), np.float32), np.zeros((1, 1), np.uint8))
    (u, v), z = F.project(np.asarray(tip_world)[None])[0][0], F.project(np.asarray(tip_world)[None])[1][0]
    joints = []
    for name in JOINTS:
        if name == "indexTip":
            joints.append(dict(name=name, x=u / 1920, y=1 - v / 1440, conf=tip_conf))
        elif name == "indexDIP":
            joints.append(dict(name=name, x=u / 1920, y=1 - (v - 40) / 1440, conf=0.9))    # 40 px above the tip
        elif name == "indexMCP":
            joints.append(dict(name=name, x=knuckle_px[0] / 1920, y=1 - knuckle_px[1] / 1440, conf=0.9))
        else:
            joints.append(dict(name=name, x=0.5, y=0.5, conf=0.9))
    dp = np.full((21, 9, 9), z, np.float32)
    dp[JOINTS.index("indexTip"), 6:9, :] = z + beyond_gap      # rows past the tip (the finger points down the image)
    cp = np.full((21, 9, 9), 2, np.uint8)
    return dict(type="hand", camera_transform=G.flat_colmajor(T), joints=joints, patch=9,
                depth_patches_f16_b64=codec.encode_patches(dp, "f16"), conf_patches_u8_b64=codec.encode_patches(cp, "u8"))


def run(det, msgs, target=None, with_index=False):
    out = []
    for i, m in enumerate(msgs):
        o, _ = det.update(m, ITEMS, t=i / 15, target_id=target)
        out += [(i, x) for x in o] if with_index else o
    return out


def touches(out):
    return [m for m in out if m["type"] == "touch"]


def lid():
    return [0.0, -0.3 + 0.07 + 0.005, -0.6]          # fingertip resting on the lid


def detector():
    d = TouchDetector()
    d.set_camera(K, (1920, 1440))
    return d


def test_touch_starts_after_the_streak_and_ends_when_the_hand_leaves():
    out = run(detector(), [hand_msg(lid())] * 4 + [hand_msg([0.0, 0.1, -0.6], beyond_gap=0.5)] * 3, with_index=True)
    t = [(i, m) for i, m in out if m["type"] == "touch"]
    assert len(t) == 1 and t[0][1]["item_id"] == "jar"
    assert t[0][0] == 3          # a hand that just appeared: 3 knuckle samples (0-2), then a 2-message streak (2-3)
    ends = [i for i, m in out if m["type"] == "touch_end"]
    assert ends and ends[0] == 4  # the fingertip jumped 40 cm away: ends at once


def test_brief_contact_dropouts_do_not_end_a_touch():
    msgs = [hand_msg(lid())] * 4 + [hand_msg(lid(), beyond_gap=0.05), hand_msg(lid())] * 3
    out = run(detector(), msgs)
    assert len(touches(out)) == 1 and not [m for m in out if m["type"] == "touch_end"]


def test_hovering_in_front_of_a_surface_is_not_a_touch():
    assert not touches(run(detector(), [hand_msg(lid(), beyond_gap=0.05)] * 8))      # 5 cm gap past the fingertip


def test_hidden_fingertip_never_touches():
    assert not touches(run(detector(), [hand_msg(lid(), tip_conf=0.3)] * 8))


def test_touching_something_that_is_not_a_registered_item_is_not_a_touch_on_it():
    assert not touches(run(detector(), [hand_msg([0.4, -0.3, -0.6])] * 8))             # 40 cm to the side of the jar


def test_moving_hand_does_not_start_a_touch():
    msgs = [hand_msg(lid(), knuckle_px=(900 + 60 * i, 700)) for i in range(8)]          # knuckles sweeping 60 px per message
    assert not touches(run(detector(), msgs))


def test_hand_proximity_reports_distance_to_the_guidance_target():
    out = run(detector(), [hand_msg([0.0, -0.3 + 0.07 + 0.25, -0.6], beyond_gap=0.3)], target="jar")
    prox = [m for m in out if m["type"] == "hand_proximity"]
    assert prox and abs(prox[0]["distance_m"] - 0.25) < 0.01


def test_fingertip_depth_is_the_near_cluster_at_an_edge():
    det = detector()
    m = hand_msg(lid())
    dp = codec.decode_patches(m["depth_patches_f16_b64"], "f16")
    k = JOINTS.index("indexTip")
    z = float(dp[k, 4, 4])
    dp[k, :, 5:] = z + 0.6                             # half the window is the wall 60 cm behind the finger
    m["depth_patches_f16_b64"] = codec.encode_patches(dp, "f16")
    p, _ = det.fingertip(m)
    assert p is not None and abs(float(-p[2]) - z) < 0.01
