"""tools/sound_demo.py, the SIMULATED phone for rehearsing the dashboard: its scripted run is valid for the adapter,
geometrically consistent (head-relative azimuth 0 ahead, +90 right; the keys 0.8 m below the ears), follows the
app's beep rules, and plays end to end into the server, in-process and over a real loopback socket."""
import asyncio
import importlib
import importlib.util
import json
import math
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import websockets
from fastapi.testclient import TestClient

from marco import geometry as G
from marco.dashboard import Dashboard
from test_dashboard import valid

TOOLS = Path(__file__).resolve().parents[1] / "tools"


def load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


S = load("sound_demo")
RUN = S.scenario("s1", t0_device=5000.0)
SOUNDS = [(t, m) for t, m in RUN if m["type"] == "sound"]
CUES = [m["cue"] for _, m in SOUNDS]


def keys_from_first_pose(run):
    """Where the stub seeds its keys: 2 m behind the first pose it sees, on a 0.75 m table."""
    T = G.mat4(next(m for _, m in run if m["type"] == "pose")["camera_transform"])
    h = math.radians(G.heading_deg(T))
    k = T[:3, 3] - 2.0 * np.array([math.sin(h), 0.0, -math.cos(h)])
    k[1] = 0.75
    return k


def test_every_message_is_valid_for_the_dashboard_adapter():
    dash = Dashboard(SimpleNamespace(items_public=lambda: []))
    q = dash.subscribe()
    phone, n = object(), 0
    for _, m in RUN:
        dash.observe_phone(phone, m)
        if m["type"] in ("sound", "sound_field"):
            n += 1
            assert q.get_nowait()["sound"]["tDevice"] == m["t_device"]
        if m["type"] == "pose":
            G.check_pose(G.mat4(m["camera_transform"]))
            assert G.upright_turns(G.mat4(m["camera_transform"])) == 1          # the portrait vest mount
            assert m["head_source"] == "fusion" and -180 <= m["head_yaw_deg"] < 180
        assert m["session_id"] == "s1"
    assert dash.sound_dropped == 0 and q.empty() and n > 150
    valid(dash.snapshot())
    json.dumps(RUN, allow_nan=False)                                            # plain JSON, no NaN


def test_times_increase_and_t_device_follows_them():
    ts = [t for t, _ in RUN]
    assert all(b > a for a, b in zip(ts, ts[1:])) and ts[0] == 0.0 and 29.9 <= ts[-1] <= 30.1
    for t, m in RUN:
        if "t_device" in m:
            assert abs(m["t_device"] - (5000.0 + t)) < 1e-6
    poses = [t for t, m in RUN if m["type"] == "pose"]
    assert len(poses) == 301 and all(abs((b - a) - 0.1) < 1e-6 for a, b in zip(poses, poses[1:]))   # 10/s
    assert S.scenario("s1", t0_device=5000.0) == RUN                             # pure


def test_the_story_plays_in_order():
    says = [(t, m) for t, m in SOUNDS if m["cue"] == "say"]
    assert [m["text"] for _, m in says] == ["Polo! Behind you, two steps, on the table.", "Within reach, on the table.",
                                            "Got it."]
    assert abs(says[0][0] - 0.5) < 0.01 and says[0][1]["duration_s"] == 2.9 and says[0][1]["az_deg"] == 150.0
    assert all(m["anchor"] == "item" and m["source"] == "voice" for _, m in says)
    first_beep = next(t for t, m in SOUNDS if m["cue"] == "beep")
    assert abs(first_beep - 3.5) < 0.01
    order = [c for c in CUES if c != "beep"]
    assert order == ["say", "ding", "say", "tone_on", "tone_off", "silence", "say"]
    assert all(m["source"] == "beacon" for _, m in SOUNDS if m["cue"] != "say")
    ding = next(m for _, m in SOUNDS if m["cue"] == "ding")
    assert abs(ding["az_deg"]) <= 12
    fields = [m for _, m in RUN if m["type"] == "sound_field"]
    before = [f for f in fields if f["t_device"] < ding["t_device"]][-1]
    assert abs(before["beacon"]["az_deg"]) > 12                                  # the ding is the moment it locks on
    phases = []
    for _, m in RUN:
        if m["type"] == "guidance" and (not phases or phases[-1] != m["phase"]):
            phases.append(m["phase"])
    assert phases == ["behind", "turning", "facing", "approach", "reach", "touched", "off"]
    flat = {m["phase"]: m["distance_m"] for _, m in RUN if m["type"] == "guidance"}   # each phase's last distance
    assert flat["behind"] == 2.0 and flat["touched"] == 0.25
    dist_at = {t: m["distance_m"] for t, m in RUN if m["type"] == "guidance"}

    def floor_distance(when):                                                    # the guidance message nearest then
        return dist_at[min(dist_at, key=lambda t: abs(t - when))]

    near = next(t for t, m in SOUNDS if m.get("text") == "Within reach, on the table.")
    tone = next(t for t, m in SOUNDS if m["cue"] == "tone_on")
    assert abs(floor_distance(near) - 0.6) <= 0.02 and abs(floor_distance(tone) - 0.30) <= 0.02
    assert fields[-1]["beacon"] is None and fields[-1]["voice"] is None          # it goes quiet, once
    assert all(f["beacon"] or f["voice"] for f in fields[:-1])
    last_guidance = max(t for t, m in RUN if m["type"] == "guidance")
    assert [t for t, m in RUN if m["type"] == "sound_field"][-1] > last_guidance  # off, then the quiet field
    assert not any(m["type"] == "guidance" and m["phase"] == "off" for t, m in RUN if t < last_guidance)


def test_beep_gaps_follow_the_formula_and_speech_pauses_them():
    beat = [(t, m) for t, m in SOUNDS if m["cue"] in ("beep", "ding", "say", "tone_on")]
    checked = 0
    for (t0, a), (t1, b) in zip(beat, beat[1:]):
        if b["cue"] != "beep" or a["cue"] not in ("beep", "ding"):
            continue
        flat = b["distance_m"] * math.cos(math.radians(b["el_deg"]))           # the floor distance, from the message
        assert abs((t1 - t0) - S.beep_gap(flat)) <= 0.02, (t0, t1, flat)
        checked += 1
    assert checked >= 12
    for t, m in SOUNDS:
        if m["cue"] == "say":                                                    # none over the first 1.2 s of a line
            assert not [u for u, b in SOUNDS if b["cue"] == "beep" and t < u < t + 1.2]
    tone = next(t for t, m in SOUNDS if m["cue"] == "tone_on")
    assert not [t for t, m in SOUNDS if m["cue"] == "beep" and t > tone]      # the steady tone replaces them


def test_muffled_matches_behind_the_head():
    beeps = [m for _, m in SOUNDS if m["cue"] == "beep"]
    assert all(m["muffled"] == (abs(m["az_deg"]) > 90) for m in beeps)
    assert {m["muffled"] for m in beeps} == {True, False}
    assert all("muffled" not in m for _, m in SOUNDS if m["cue"] != "beep")
    for _, m in RUN:
        if m["type"] == "sound_field" and m["beacon"]:
            assert m["beacon"]["muffled"] == (abs(m["beacon"]["az_deg"]) > 90)


def test_directions_are_head_relative_and_agree_with_the_poses():
    keys = keys_from_first_pose(RUN)
    assert np.allclose(keys, S.KEYS)
    pose = None
    checked = 0
    for t, m in RUN:
        if m["type"] == "pose":
            pose = m
            continue
        src = (m.get("beacon") if m["type"] == "sound_field" else m if m["type"] == "sound" else None)
        if not src:
            if m["type"] == "guidance" and m["phase"] != "off":
                T = G.mat4(pose["camera_transform"])
                assert abs(m["distance_m"] - G.horizontal_distance(T[:3, 3], keys)) < 0.03
            continue
        T = G.mat4(pose["camera_transform"])
        ear = T[:3, 3] + np.array([0.0, 0.45, 0.0])
        az = G.relative_azimuth_deg(ear, pose["head_yaw_deg"], keys)            # the pose is at most 0.1 s older
        el = math.degrees(math.atan2(keys[1] - ear[1], G.horizontal_distance(ear, keys)))
        field = m["type"] == "sound_field"                                      # 4 ms after its pose; a cue up to 0.1 s
        assert abs(G.wrap180(src["az_deg"] - az)) <= (1.0 if field else 8.0), (t, src["az_deg"], az)
        assert abs(src["el_deg"] - el) <= (0.3 if field else 4.0), (t, src["el_deg"], el)
        assert abs(src["distance_m"] * math.sin(math.radians(src["el_deg"])) + 0.8) < 0.01   # 0.8 m below the ears
        checked += 1
    assert checked > 150
    beacon = [m["beacon"]["az_deg"] for _, m in RUN if m["type"] == "sound_field" and m["beacon"]]
    assert beacon[0] == 150.0 and max(beacon) <= 150.0 and abs(beacon[-1]) < 10   # behind-right, turning to ahead
    yaw = [m["head_yaw_deg"] for _, m in RUN if m["type"] == "pose"]
    assert yaw[0] == -60.0 and abs(yaw[100] - 90.0) < 5                         # head turned right by 150 degrees
    T0 = G.mat4(next(m for _, m in RUN if m["type"] == "pose")["camera_transform"])
    assert abs(G.relative_azimuth_deg(T0[:3, 3], G.heading_deg(T0), keys)) == 180.0   # "behind you" for the body


def test_the_sender_paces_prints_and_keeps_one_session_across_runs():
    class FakeSocket:
        def __init__(self):
            self.sent = []

        async def send(self, s):
            self.sent.append(json.loads(s))

        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.Event().wait()

    sock, seen = FakeSocket(), {}

    class Connect:
        def __init__(self, url, additional_headers=None):
            seen.update(url=url, headers=additional_headers)

        async def __aenter__(self):
            return sock

        async def __aexit__(self, *exc):
            return False

    lines = []
    t = time.monotonic()
    rep = asyncio.run(S.run("https://box.example.ts.net/", {"X-Test": "1"}, runs=2, speed=300, out=lines.append,
                            connect=Connect))
    assert time.monotonic() - t >= 2 * 30.0 / 300                                # paced, not dumped
    assert seen == dict(url="wss://box.example.ts.net/v1/phone", headers={"X-Test": "1"})
    assert rep["runs"] == 2 and rep["sent"] == len(sock.sent) == 2 * len(RUN) and rep["errors"] == []
    assert {m["session_id"] for m in sock.sent} == {rep["session_id"]} and rep["session_id"].startswith("sim-")
    td = [m["t_device"] for m in sock.sent if "t_device" in m]
    assert all(b > a for a, b in zip(td, td[1:]))                                # the second run carries on
    assert all("SIMULATED" in line for line in lines) and sum("beep" in line for line in lines) > 20
    assert S.phone_url("http://127.0.0.1:8000") == "ws://127.0.0.1:8000/v1/phone"
    assert S.parse_headers(["Tailscale-User-Login: you@github"]) == {"Tailscale-User-Login": "you@github"}


@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("MARCO_DATA", str(tmp_path))
    monkeypatch.setenv("MARCO_MODE", "stub")
    monkeypatch.setenv("STUB_SPEEDUP", "200")
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
    import marco.app
    import marco.stub
    importlib.reload(marco.stub)
    return importlib.reload(marco.app)


# The end-to-end runs guide to an id the stub doesn't know, so its own fake hand (a burst of hand_proximity and a
# touch for each guided stub item) stays out of the timing. The default, fake-keys, is the stub's seeded keys.
def test_the_first_seconds_play_into_the_stub_and_out_on_events(server):
    head = [(t, m) for t, m in S.scenario("s1", item_id="sim-keys") if t <= 4.0]
    n = sum(m["type"] in ("sound", "sound_field") for _, m in head)
    with TestClient(server.app) as c, c.websocket_connect("/events") as ev, c.websocket_connect("/v1/phone") as ws:
        ev.receive_json()
        for _, m in head:
            ws.send_json(m)
        ws.send_json(dict(type="query", session_id="s1", query_id="done", kind="find", name="keys"))
        replies = [ws.receive_json()]
        while replies[-1].get("query_id") != "done":
            replies.append(ws.receive_json())
        d = valid(c.get("/dashboard/snapshot").json())
        got, end = [], time.monotonic() + 10
        while len(got) < n and time.monotonic() < end:
            m = ev.receive_json()
            if m["type"] == "dashboard.sound":
                got.append(m["sound"])
    assert len(got) == n and [r for r in replies if r.get("type") == "error"] == []
    assert got[0]["kind"] == "cue" and got[0]["cue"] == "say" and got[0]["text"].startswith("Polo!")
    assert got[0]["azimuthDeg"] == 150.0 and got[0]["elevationDeg"] == -21.8 and got[0]["durationS"] == 2.9
    beep = next(s for s in got if s.get("cue") == "beep")
    assert beep["muffled"] is True and beep["source"] == "beacon"
    fields = [s for s in got if s["kind"] == "field"]
    assert fields and fields[0]["beacon"]["muffled"] is True and fields[0]["voice"]["anchor"] == "item"
    assert server.dash.sound_dropped == 0
    nav = d["navigation"]
    assert nav["spokenInstruction"].startswith("Polo!") and nav["state"] == "guiding" and nav["targetItemId"] == "sim-keys"
    assert abs(nav["bearingDeg"] - 150.0) < 1 and nav["distanceM"] == 2.0
    assert d["wearer"]["bodyYawDeg"] == -90.0 and d["wearer"]["headYawDeg"] == -60.0
    keys = next(it for it in d["items"] if it["id"] == "fake-keys")["lastSeen"]["position"]   # the stub's own keys
    assert np.allclose([keys["x"], keys["y"], keys["z"]], S.KEYS, atol=1e-3)
    assert next(m for _, m in RUN if m["type"] == "guidance")["item_id"] == "fake-keys"   # the tool's default target


def test_the_tool_against_a_running_loopback_server(server):
    import uvicorn
    from test_tools import free_port
    port = free_port()
    uv = uvicorn.Server(uvicorn.Config(server.app, host="127.0.0.1", port=port, log_level="warning"))
    th = threading.Thread(target=uv.run, daemon=True)
    th.start()
    for _ in range(100):
        if uv.started:
            break
        time.sleep(0.05)

    expected = sum(m["type"] in ("sound", "sound_field") for _, m in RUN)

    async def main():
        heard = []
        async with websockets.connect(f"ws://127.0.0.1:{port}/events") as ev:
            async def listen():
                async for raw in ev:
                    m = json.loads(raw)
                    if m["type"] == "dashboard.sound":
                        heard.append(m["sound"])
            task = asyncio.ensure_future(listen())
            rep = await S.run(f"http://127.0.0.1:{port}", speed=25, item_id="sim-keys", out=lambda line: None)
            for _ in range(200):                                                 # the server may trail a little
                if len(heard) >= expected:
                    break
                await asyncio.sleep(0.05)
            task.cancel()
        return rep, heard

    try:
        rep, heard = asyncio.run(main())
    finally:
        uv.should_exit = True
        th.join(timeout=10)
    assert rep["errors"] == [] and rep["runs"] == 1
    cues = [s["cue"] for s in heard if s["kind"] == "cue"]
    assert cues == CUES                                                          # every cue, in order
    assert [s["text"] for s in heard if s.get("cue") == "say"][-1] == "Got it."
    last = [s for s in heard if s["kind"] == "field"][-1]
    assert last["beacon"] is None and last["voice"] is None
    assert len(heard) == expected
