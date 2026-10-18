"""The hub: one slow or dead socket must never hold up the others (a stalled dashboard used to stop the phone's
`find` answers and the frame route). Unit tests with fake sockets, plus a live loopback server with a dashboard that
connects and then never reads, so TCP backpressure is real."""
import asyncio
import base64
import importlib
import json
import os
import socket
import threading
import time

import httpx
from websockets.sync.client import connect

from helpers import emulated, frame_parts, pose_msg
from marco.hub import Hub
from test_tools import free_port


class FakeSocket:
    def __init__(self, stall=False, fail=False):
        self.got, self.stall, self.fail = [], stall, fail
        self.release = asyncio.Event()

    async def send_json(self, msg):
        if self.fail:
            raise RuntimeError("gone")
        if self.stall:
            await self.release.wait()
        self.got.append(msg)

    async def close(self, code=1000):
        pass


def test_a_stalled_socket_does_not_hold_up_the_others():
    async def run():
        hub = Hub()
        slow, dash, phone = FakeSocket(stall=True), FakeSocket(), FakeSocket()
        hub.join("dashboard", slow)
        hub.join("dashboard", dash)
        hub.join("phone", phone)
        t = time.monotonic()
        for i in range(200):
            await hub.send("dashboard", dict(n=i))
            await asyncio.sleep(0)                         # messages arrive over many loop turns, as from routes
        await hub.send("phone", dict(type="answer"))
        assert time.monotonic() - t < 0.1, "send never waits for a socket"
        await asyncio.sleep(0.05)
        assert phone.got == [dict(type="answer")]
        assert [m["n"] for m in dash.got] == list(range(200)), "in order, nothing lost on a healthy socket"
        assert hub.backlog(slow) <= Hub.LIMITS["dashboard"], "a stalled socket's backlog is bounded"
        slow.release.set()
        await asyncio.sleep(0.05)
        assert slow.got[-1] == dict(n=199), "it drops the oldest and keeps the newest"
        assert len(slow.got) <= Hub.LIMITS["dashboard"] + 1
    asyncio.run(run())


def test_failed_and_timed_out_sockets_are_dropped():
    async def run():
        hub = Hub(send_timeout_s=0.05)
        dead, stuck, ok = FakeSocket(fail=True), FakeSocket(stall=True), FakeSocket()
        for ws in (dead, stuck, ok):
            hub.join("phone", ws)
        await hub.send("phone", dict(a=1))
        await asyncio.sleep(0.2)
        assert hub.channels["phone"] == {ok} and ok.got == [dict(a=1)]
        hub.leave("phone", ok)
        assert hub.channels["phone"] == set() and hub.backlog(ok) == 0
        await hub.send("phone", dict(a=2))                 # nobody left: a no-op
    asyncio.run(run())


def stalled_dashboard(port):
    """A WebSocket client that does the handshake and then never reads: its receive buffer fills and the server's
    sends to it block, as with a dashboard on a laptop that went to sleep."""
    s = socket.socket()
    s.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 4096)
    s.connect(("127.0.0.1", port))
    key = base64.b64encode(os.urandom(16)).decode()
    s.sendall((f"GET /v1/dashboard HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\n"
               f"Sec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n").encode())
    head = b""
    while b"\r\n\r\n" not in head:
        head += s.recv(1)
    assert b" 101 " in head.split(b"\r\n")[0], head
    return s


def test_live_server_answers_the_phone_while_a_dashboard_is_stalled(tmp_path, monkeypatch):
    import uvicorn
    monkeypatch.setenv("MARCO_DATA", str(tmp_path / "data"))
    monkeypatch.setenv("MARCO_MODE", "stub")
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
    import marco.app
    import marco.stub
    importlib.reload(marco.stub)
    app_mod = importlib.reload(marco.app)
    port = free_port()
    base = f"http://127.0.0.1:{port}"
    server = uvicorn.Server(uvicorn.Config(app_mod.app, host="127.0.0.1", port=port, log_level="warning"))
    threading.Thread(target=server.run, daemon=True).start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    dash = stalled_dashboard(port)
    try:
        _, T, _, _ = emulated()
        with connect(f"ws://127.0.0.1:{port}/v1/phone") as ws, httpx.Client(timeout=3) as http:
            ws.send(json.dumps(pose_msg(T)))
            accepted = 0
            t = time.monotonic()
            _, files, meta = frame_parts()
            for i in range(40):                           # far past the TCP buffers of the stalled dashboard
                data = {"meta": json.dumps({**meta, "frame_id": i + 1})}
                try:
                    accepted += http.post(f"{base}/v1/frames", data=data, files=files).status_code == 202
                except httpx.TimeoutException:
                    break
            frames_s = time.monotonic() - t
            ws.send(json.dumps(dict(type="query", session_id="s1", query_id="k1", kind="find", name="keys")))
            answer = None
            deadline = time.monotonic() + 3
            while answer is None and time.monotonic() < deadline:
                m = json.loads(ws.recv(timeout=max(0.01, deadline - time.monotonic())))
                if m.get("type") == "answer" and m.get("query_id") == "k1":
                    answer = m
        assert accepted == 40, f"only {accepted} of 40 frames got through in {frames_s:.1f} s"
        assert answer is not None and answer["found"] and answer["name"] == "keys", answer
    finally:
        dash.close()
        server.should_exit = True
