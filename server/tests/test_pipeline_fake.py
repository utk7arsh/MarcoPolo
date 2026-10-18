"""End to end on a synthetic session (tools/fake_session.py): frames + poses + hand stream through the real brain with
the ground-truth detector. Checks 3D placement, the touch, and that nothing false happens."""
import importlib.util
import sys
from pathlib import Path

import pytest

TOOLS = Path(__file__).resolve().parents[1] / "tools"


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


@pytest.fixture(scope="module")
def report(tmp_path_factory):
    d = tmp_path_factory.mktemp("sessions") / "fake"
    load("fake_session").main(str(d))
    return load("run_offline").run_session(str(d), detector="truth", pictures=False)


def test_every_item_is_placed_within_10_cm(report):
    assert set(report["vs_truth"]) == {"bottle", "keys", "wallet", "glasses_case", "mug", "jar"}
    for name, v in report["vs_truth"].items():
        assert v["horizontal_err_cm"] < 10 and abs(v["height_err_cm"]) < 10, (name, v)


def test_the_jar_touch_is_detected_once_and_on_time(report):
    touches = [t for t in report["touches"] if t.get("name")]
    assert [t["name"] for t in touches] == ["jar"]
    truth_t = report["truth_touches"][0]["t_device"]
    assert 0 <= touches[0]["at_t"] - truth_t <= 0.5        # within half a second after contact


def test_nothing_false_happens(report):
    kinds = {e["kind"] for e in report["events"]}
    assert kinds <= {"seen"}, kinds                          # no false moved / missing / picked_up
    assert not report["errors"]


def test_find_keys_answers_from_memory(report):
    a = [x for x in report["answers"] if x["kind"] == "find"][0]
    assert a["found"] and a["name"] == "keys" and a["state"] == "present"
