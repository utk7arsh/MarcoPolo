"""Per-frame timing against the 1 frame/s budget, and the benchmark's plumbing (with the ground-truth detector)."""
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
def fake(tmp_path_factory):
    d = tmp_path_factory.mktemp("bench") / "fake"
    load("fake_session").main(str(d))
    return d


def test_timing_summary_judges_the_p95_against_one_second():
    ro = load("run_offline")
    assert ro.timing_summary([]) == {"frames": 0}
    ok = ro.timing_summary([0.3] * 19 + [0.9])
    assert ok["frames"] == 20 and ok["p50_s"] == 0.3 and ok["max_s"] == 0.9 and ok["within_budget"]
    slow = ro.timing_summary([0.4] * 10 + [1.4] * 2)
    assert not slow["within_budget"]


def test_bench_times_every_frame_for_each_item_count(fake):
    from marco.perception.detector import TruthDetector
    from marco.session import Session
    sys.path.insert(0, str(TOOLS))
    truth = Session(fake).truth["items"]
    rows = load("bench_frame").bench(str(fake), counts=(1, 3), detector=TruthDetector(truth), rounds=1, min_px=20)
    n = len(Session(fake).frames)
    assert [r["items"] for r in rows] == [1, 3]
    assert all(r["frames"] == n - 2 and r["mean_s"] > 0 for r in rows)


def test_offline_report_includes_timing(fake, tmp_path):
    rep = load("run_offline").run_session(str(fake), detector="truth", out_dir=str(tmp_path / "off"), pictures=False)
    assert rep["timing"]["frames"] > 10 and rep["timing"]["within_budget"]
