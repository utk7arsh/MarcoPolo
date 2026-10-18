"""POST /v1/frames answers 202 before the brain runs (INTERFACES.md 3.1), and frames still go through one at a time,
newest first. The rest of the suite runs with MARCO_FRAMES_ASYNC=0 (conftest.py); these tests switch it back on."""
import importlib
import logging
import threading
import time

import pytest
from fastapi.testclient import TestClient

from helpers import frame_parts


@pytest.fixture()
def app_mod(tmp_path, monkeypatch):
    monkeypatch.setenv("MARCO_DATA", str(tmp_path))
    monkeypatch.setenv("MARCO_MODE", "stub")
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
    import marco.app
    mod = importlib.reload(marco.app)
    monkeypatch.setattr(mod, "FRAMES_ASYNC", True)
    return mod


def wait_for(cond, s=5.0):
    end = time.monotonic() + s
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def post(c, fid):
    data, files, _ = frame_parts(frame_id=fid)
    return c.post("/v1/frames", data=data, files=files)


def test_a_frame_is_answered_while_the_brain_is_still_on_it(app_mod, monkeypatch):
    release, started, done = threading.Event(), [], []

    def slow_brain(m, jpeg, d, c):
        started.append(m["frame_id"])
        release.wait(5)
        done.append(m["frame_id"])
        return []

    monkeypatch.setattr(app_mod.brain, "on_frame", slow_brain)
    with TestClient(app_mod.app) as c:
        r = post(c, 1)
        assert r.status_code == 202 and r.json() == {"frame_id": 1, "status": "accepted"}
        assert done == []                               # answered before the brain finished frame 1
        assert wait_for(lambda: started == [1])
        assert post(c, 2).status_code == post(c, 3).status_code == 202   # both wait behind frame 1
        release.set()
        assert wait_for(lambda: not app_mod.frame_tasks)
    assert done == [1, 3]                               # frame 2 was superseded by 3 while it waited


def test_a_brain_failure_is_logged_and_the_next_frame_still_runs(app_mod, monkeypatch, caplog):
    ran = []

    def brain(m, jpeg, d, c):
        ran.append(m["frame_id"])
        if m["frame_id"] == 7:
            raise RuntimeError("model fell over")
        return []

    monkeypatch.setattr(app_mod.brain, "on_frame", brain)
    with caplog.at_level(logging.ERROR, logger="marco"), TestClient(app_mod.app) as c:
        assert post(c, 7).status_code == 202
        assert wait_for(lambda: not app_mod.frame_tasks)
        assert post(c, 8).status_code == 202
        assert wait_for(lambda: not app_mod.frame_tasks)
    assert ran == [7, 8]
    assert "frame 7 of session s1 failed in the brain" in caplog.text and "model fell over" in caplog.text
