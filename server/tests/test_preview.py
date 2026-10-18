"""The dashboard's live view (marco/preview.py): the phone sends small JPEGs on /v1/preview only while a dashboard
watches /preview, frames pass through untouched and newest-first, junk is refused, and both sockets are gated."""
import asyncio
import importlib

import pytest
from fastapi.testclient import TestClient

from helpers import jpeg_bytes
from marco.preview import MAX_BYTES, PreviewRelay

JPEG = jpeg_bytes(48, 36)


@pytest.fixture()
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("MARCO_DATA", str(tmp_path))
    monkeypatch.setenv("MARCO_MODE", "stub")
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
    import marco.app
    m = importlib.reload(marco.app)
    m.preview.min_gap_s = 0.0                     # tests send faster than 10 a second
    return m, TestClient(m.app)


def test_the_phone_sends_only_while_a_dashboard_watches_and_frames_pass_through(app):
    m, c = app
    with c.websocket_connect("/v1/preview") as phone:
        assert phone.receive_json() == dict(type="preview", want=False, hz=10.0)       # nobody watching yet
        with c.websocket_connect("/api/preview") as dash:
            assert phone.receive_json()["want"] is True
            phone.send_bytes(JPEG)
            assert dash.receive_bytes() == JPEG                                       # untouched
            second = jpeg_bytes(64, 48)
            phone.send_bytes(second)
            assert dash.receive_bytes() == second
        assert phone.receive_json()["want"] is False                                  # the last watcher left
    assert m.preview.received == 2


def test_a_dashboard_that_opens_late_gets_the_latest_frame_at_once(app):
    m, c = app
    with c.websocket_connect("/v1/preview") as phone:
        phone.receive_json()
        with c.websocket_connect("/preview") as first:
            phone.receive_json()
            phone.send_bytes(JPEG)
            assert first.receive_bytes() == JPEG
            with c.websocket_connect("/preview") as second:
                assert second.receive_bytes() == JPEG                                 # no wait for the next one


def test_junk_and_floods_are_refused():
    t = [0.0]
    r = PreviewRelay(hz=10, now=lambda: t[0])
    assert not r.accept(b"not a jpeg")
    assert not r.accept(b"\xff\xd8" + b"x" * MAX_BYTES)                               # too big for a preview
    assert r.accept(JPEG)
    t[0] += 0.01
    assert not r.accept(JPEG)                                                         # faster than 10 a second
    t[0] += 0.1
    assert r.accept(JPEG) and r.received == 2 and r.refused == 3
    assert not PreviewRelay(hz=0).want_message()["want"]                              # MARCO_PREVIEW_HZ=0: off


def test_a_slow_dashboard_gets_only_the_newest_frame():
    async def run():
        r = PreviewRelay(hz=10)
        r.min_gap_s = 0.0
        sent, gate = [], asyncio.Event()

        class SlowDashboard:
            async def receive(self):
                await asyncio.sleep(3600)

            async def send_bytes(self, data):
                sent.append(data)
                await gate.wait()                     # stuck sending the first frame
                gate.clear()

        task = asyncio.ensure_future(r.serve_dashboard(SlowDashboard()))
        await asyncio.sleep(0)
        frames = [jpeg_bytes(16 + i, 12) for i in range(5)]
        r.accept(frames[0])
        await asyncio.sleep(0.01)
        for f in frames[1:]:
            r.accept(f)                               # arrive while the dashboard is busy
        gate.set()
        await asyncio.sleep(0.01)
        gate.set()
        await asyncio.sleep(0.01)
        task.cancel()
        return sent

    sent = asyncio.run(run())
    assert sent[0] == jpeg_bytes(16, 12) and sent[1] == jpeg_bytes(20, 12) and len(sent) == 2   # 1-3 skipped


def test_both_preview_sockets_are_gated(tmp_path, monkeypatch):
    monkeypatch.setenv("MARCO_DATA", str(tmp_path))
    monkeypatch.delenv("AUTH_TEST_BYPASS", raising=False)
    monkeypatch.delenv("MARCO_AUTH", raising=False)
    import marco.app
    c = TestClient(importlib.reload(marco.app).app)
    from starlette.websockets import WebSocketDisconnect
    for path in ("/v1/preview", "/preview", "/api/preview"):
        with pytest.raises(WebSocketDisconnect):
            with c.websocket_connect(path) as ws:
                ws.receive_json()
