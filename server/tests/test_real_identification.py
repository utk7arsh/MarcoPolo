"""The real brain's identification gate, using synthetic sensor inputs, not OWLv2 or hardware."""
import numpy as np
import pytest

from helpers import frame_parts, jpeg_bytes, pose_msg
from marco.brain import RealBrain
from marco.perception.detector import TruthDetector
from test_touch import K, hand_msg


@pytest.fixture
def brain(tmp_path):
    brain = RealBrain(TruthDetector({}), tmp_path)
    depth = np.full((192, 256), 1.5, np.float32)
    conf = np.full((192, 256), 2, np.uint8)
    _, _, meta = frame_parts(T=np.eye(4), K=K, depth=depth, conf=conf)
    brain.on_frame(meta, jpeg_bytes(), depth, conf)
    brain.on_phone(pose_msg(np.eye(4)))
    return brain


def identify(brain):
    # This is the actual iOS QueryMsg shape: it has no t_device.
    return brain.on_phone(dict(type="query", session_id="s1", query_id="q1", kind="what_is_this"))


def hand(brain):
    brain.on_phone(dict(hand_msg([0.0, -0.2, -1.5]), t_device=1000.0))


def test_real_unknown_finger_produces_the_photon_request_and_crop(brain):
    hand(brain)
    out = identify(brain)
    assert out[0][0] == "phone" and out[0][1]["status"] == "unknown"
    channel, request = out[1]
    assert channel == "photon" and request["touch_id"] == out[0][1]["touch_id"]
    assert brain.touches[request["touch_id"]]["crop_jpeg"].startswith(b"\xff\xd8")


def test_real_no_finger_produces_no_caretaker_request(brain):
    out = identify(brain)
    assert len(out) == 1 and out[0][1]["status"] == "no_touch"


def test_a_query_without_timestamp_must_not_keep_a_stale_finger_alive(brain):
    hand(brain)
    brain.on_phone(pose_msg(np.eye(4), t=1010))
    out = identify(brain)
    assert len(out) == 1 and out[0][1]["status"] == "no_touch"


def test_a_query_without_timestamp_must_not_report_an_old_known_touch(brain):
    item = brain.world.add_item("cumin")
    brain.last_touch = ("old", item.item_id, 1000.0)
    brain.on_phone(pose_msg(np.eye(4), t=1010))
    out = identify(brain)
    assert len(out) == 1 and out[0][1]["status"] == "no_touch"


def test_finger_expires_when_the_sensor_stream_stops(brain, monkeypatch):
    clock = [100.0]
    monkeypatch.setattr("marco.brain.time.monotonic", lambda: clock[0])
    hand(brain)
    clock[0] += 4.0
    out = identify(brain)
    assert len(out) == 1 and out[0][1]["status"] == "no_touch"
