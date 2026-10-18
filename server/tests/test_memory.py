import numpy as np

from marco import geometry as G
from marco.world import memory as M


def flat_frame(T=None, wall_m=3.0):
    """Camera at the origin looking down -z (world -z), constant wall depth; 1920x1440 intrinsics."""
    T = np.eye(4) if T is None else T
    K = np.array([[1600.0, 0, 960], [0, 1600, 720], [0, 0, 1]])
    return G.Frame(T, K, (1920, 1440), np.full((192, 256), wall_m, np.float32), np.full((192, 256), 2, np.uint8))


def test_first_sighting_places_item_and_nearby_sightings_refresh_quietly():
    w = M.World()
    keys = w.add_item("keys")
    assert [e["kind"] for e in w.sighting(keys.item_id, [0, 0.75, -1.5], 1.0)] == ["seen"]
    assert keys.surface == "table" and keys.state == "present"
    assert w.sighting(keys.item_id, [0.05, 0.75, -1.52], 2.0) == []


def test_move_needs_two_agreeing_sightings():
    w = M.World()
    mug = w.add_item("mug")
    w.sighting(mug.item_id, [0, 0.9, -1.0], 1.0)
    assert w.sighting(mug.item_id, [2.0, 1.2, -1.0], 2.0) == []          # one far sighting: could be a false detection
    ev = w.sighting(mug.item_id, [2.05, 1.2, -1.0], 3.0)
    assert [e["kind"] for e in ev] == ["moved"]
    assert ev[0]["from_position"] == [0.0, 0.9, -1.0] and mug.surface == "shelf"


def test_far_sightings_that_disagree_never_move_the_item():
    w = M.World()
    it = w.add_item("wallet")
    w.sighting(it.item_id, [0, 0.75, -1.0], 1.0)
    assert w.sighting(it.item_id, [2, 0.75, -1.0], 2.0) == []
    assert w.sighting(it.item_id, [-2, 0.75, -1.0], 3.0) == []
    assert np.allclose(it.position, [0, 0.75, -1.0])


def test_missing_after_three_unseen_looks_and_picked_up_after_a_touch():
    w = M.World()
    a, b = w.add_item("keys"), w.add_item("remote")
    w.sighting(a.item_id, [0, 0, -1.5], 1.0)
    w.sighting(b.item_id, [0.1, 0, -1.5], 1.0)
    w.touched(b.item_id, 1.5)
    fr = flat_frame()                                   # both spots in view, nothing nearer hides them
    kinds = []
    for t in (2.0, 3.0, 4.0):
        kinds += [(e["name"], e["kind"]) for e in w.check_absence(fr, set(), t)]
    assert ("keys", "missing") in kinds and ("remote", "picked_up") in kinds


def test_hidden_spot_does_not_count_as_missing():
    w = M.World()
    a = w.add_item("keys")
    w.sighting(a.item_id, [0, 0, -2.0], 1.0)
    fr = flat_frame(wall_m=1.0)                         # something at 1 m hides the spot at 2 m
    for t in (2.0, 3.0, 4.0, 5.0):
        assert w.check_absence(fr, set(), t) == []


def test_put_down_after_pickup():
    w = M.World()
    k = w.add_item("keys")
    w.sighting(k.item_id, [0, 0.75, -1.0], 1.0)
    k.state = "picked_up"
    w.sighting(k.item_id, [1.5, 0.92, -2.0], 5.0)
    assert [e["kind"] for e in w.sighting(k.item_id, [1.52, 0.92, -2.0], 6.0)] == ["put_down"]


def test_leaving_without_keys():
    w = M.World()
    k = w.add_item("keys")
    w.sighting(k.item_id, [0, 0.75, -2.0], 1.0)
    w.set_door([3.0, 0, 0.0], radius=0.8)
    T = np.eye(4)
    T[:3, 3] = [0, 1.3, 0]
    assert w.user_pose(T, 2.0) == []
    T[:3, 3] = [3.0, 1.3, 0.2]
    ev = w.user_pose(T, 3.0)
    assert [(e["kind"], e["name"]) for e in ev] == [("left_behind", "keys")]
    assert w.user_pose(T, 3.1) == []                    # once per visit


def test_new_map_makes_positions_stale_until_seen_again():
    w = M.World()
    k = w.add_item("keys")
    w.sighting(k.item_id, [0, 0.75, -2.0], 1.0)
    w.new_map("map-2")
    assert k.state == "stale"
    assert [e["kind"] for e in w.sighting(k.item_id, [5, 0.75, 5], 2.0)] == ["seen"]   # new coordinates, no 'moved'
    assert np.allclose(k.position, [5, 0.75, 5])


def test_find_answers():
    w = M.World()
    assert w.answer_find("q1", "keys")["reason"] == "not_registered"
    k = w.add_item("keys")
    assert w.answer_find("q2", "key")["reason"] == "never_seen"           # singular/plural both match
    w.sighting(k.item_id, [0, 0.75, -2.0], 1.0)
    a = w.answer_find("q3", "keys")
    assert a["found"] and a["surface"] == "table" and a["position"] == [0.0, 0.75, -2.0]
    k.state = "missing"
    assert w.answer_find("q4", "keys")["reason"] == "not_where_last_seen"
