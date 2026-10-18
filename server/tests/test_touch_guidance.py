"""Being guided to an item and touching it must end the search (docs/INTERFACES.md §7 step 7): the server has to send
`touch` for the target. Close up, the detector usually can't see the item (the hand and arm are over it), and that
must not mark it `missing` first: a missing item drops out of touch matching, so the touch never comes."""
import numpy as np

from helpers import jpeg_bytes
from marco import geometry as G
from marco.brain import RealBrain
from test_touch import K, hand_msg

JAR = np.array([0.0, -0.2, -0.8])          # 20 cm below and 80 cm ahead of the camera: in view, nothing nearer
JPEG = jpeg_bytes()


class Blind:
    """The detector never sees the item (covered by the hand, or simply missed)."""

    def detect(self, *a, **k):
        return []

    def register(self, *a, **k):
        return dict(quality="ok", reason="", box=[0, 0, 1, 1])


def frame(b, t):
    meta = dict(session_id="s1", map_id="m1", frame_id=int(t * 10), t_device=t, camera_transform=G.flat_colmajor(np.eye(4)),
                intrinsics=G.flat_colmajor(K), image_resolution=[1920, 1440], jpeg_scale=0.5)
    depth = np.full((192, 256), float(-JAR[2]), np.float32)      # LiDAR sees the item's spot itself
    return b.on_frame(meta, JPEG, depth, np.full((192, 256), 2, np.uint8))


def hand(b, t, tip, **kw):
    return b.on_phone(dict(hand_msg(tip, **kw), session_id="s1", map_id="m1", t_device=t))


def guided_brain():
    b = RealBrain(Blind())
    b.touch.set_camera(K, (1920, 1440))                            # as after the session's first frame
    it = b.world.add_item("jar")
    b.world.sighting(it.item_id, JAR, t=0.0)
    it.size_m = 0.07
    b.on_phone(dict(type="guidance", session_id="s1", item_id=it.item_id, phase="approach", rel_azimuth_deg=0.0,
                    distance_m=0.6))
    return b, it


def events(out, kind):
    return [m for ch, m in out if ch == "phone" and m.get("type") == kind]


def test_touching_the_target_after_the_hand_covered_it_for_a_few_frames_ends_the_search():
    b, it = guided_brain()
    lid = JAR + [0, 0.07 + 0.005, 0]
    out = []
    for k in range(4):                                             # 4 s reaching: the item is never detected
        out += frame(b, 1.0 + k)
        for i in range(15):
            out += hand(b, 1.0 + k + i / 15, lid + [0, 0.12, 0], beyond_gap=0.3)   # hovering 12 cm above it
    assert not [e for e in events(out, "event") if e["kind"] in ("missing", "picked_up")], "the hand hid it"
    for i in range(8):
        out += hand(b, 5.0 + i / 15, lid)                         # the fingertip on the lid, the hand still
    touches = events(out, "touch")
    assert touches and touches[0]["item_id"] == it.item_id


def test_an_item_that_is_really_gone_still_goes_missing():
    b, it = guided_brain()
    out = []
    for k in range(4):
        out += frame(b, 1.0 + k)                                   # no hand anywhere near it
    assert [e for e in events(out, "event") if e["kind"] == "missing"]


def test_touching_the_empty_spot_of_an_item_that_really_went_missing_is_not_a_find():
    b, it = guided_brain()
    out = []
    for k in range(4):
        out += frame(b, 1.0 + k)                                   # the spot is seen empty before the hand arrives
    for i in range(8):
        out += hand(b, 5.0 + i / 15, JAR + [0, 0.075, 0])
    assert it.state == "missing" and not events(out, "touch")      # no false "Got it"


def test_lifting_the_item_after_the_hand_was_at_it_is_a_pickup_not_a_loss():
    b, it = guided_brain()
    out = []
    for i in range(15):
        out += hand(b, 1.0 + i / 15, JAR + [0, 0.15, 0], beyond_gap=0.3)
    out += frame(b, 2.0)                                           # the hand over it: not a miss
    for k in range(3):
        out += frame(b, 4.0 + k)                                   # the hand gone, and the item with it
    assert [e["kind"] for e in events(out, "event")] == ["picked_up"]


def test_hand_proximity_comes_from_the_knuckles_when_the_fingertip_is_hidden():
    b, it = guided_brain()
    frame(b, 1.0)
    out = hand(b, 1.1, JAR + [0, 0.30, 0], tip_conf=0.2, beyond_gap=0.3)    # the back of the hand hides the tip
    prox = [m for ch, m in out if m.get("type") == "hand_proximity"]
    assert prox and prox[0]["item_id"] == it.item_id
