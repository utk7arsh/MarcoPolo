"""What the wearer hears, relayed to the dashboard (INTERFACES.md §3.2 sound / sound_field, §6 dashboard.sound): the
conversion to the browser's shape, what gets dropped, the per-connection queues, the latest field for a new /events
connection, navigation.spokenInstruction, and the /events socket carrying sounds between its snapshots. The adapter
alone runs on a fake clock; the end-to-end tests share one event loop for every socket, as under uvicorn."""
import asyncio
import importlib
import threading
import time
from datetime import datetime
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

import marco.dashboard as D
from helpers import emulated, pose_msg
from test_dashboard import valid

BEEP = dict(type="sound", session_id="s1", t_device=81235.2, cue="beep", source="beacon", anchor="item",
            az_deg=-150.0, el_deg=-12.0, distance_m=1.6, muffled=True)
SAY = dict(type="sound", session_id="s1", t_device=81234.9, cue="say", source="voice", anchor="item", az_deg=-150.0,
           el_deg=-12.0, distance_m=1.6, text="Polo! Behind you, two steps, on the table.", duration_s=2.9)
FIELD = dict(type="sound_field", session_id="s1", t_device=81235.3, head_yaw_deg=12.3,
             beacon=dict(az_deg=-150.0, el_deg=-12.0, distance_m=1.6, muffled=True),
             voice=dict(az_deg=0.0, el_deg=0.0, distance_m=1.0, anchor="ahead"))


class Clock:
    """Stands in for the adapter's `time` module only (asyncio keeps the real one)."""

    def __init__(self):
        self.mono = 1000.0

    def monotonic(self):
        return self.mono

    def time(self):
        return 1_792_000_000.0 + self.mono


@pytest.fixture()
def clock(monkeypatch):
    c = Clock()
    monkeypatch.setattr(D, "time", c)
    return c


@pytest.fixture()
def dash(clock):
    return D.Dashboard(SimpleNamespace(items_public=lambda: []), room_id="r", room_name="Room")


PHONE = object()                                    # the phone's socket, as far as the adapter cares


def heard(dash, *msgs):
    """Feed phone messages to the adapter; return the dashboard.sound envelopes one subscriber got."""
    q = dash.subscribe()
    for m in msgs:
        dash.observe_phone(PHONE, m)
    got = []
    while not q.empty():
        got.append(q.get_nowait())
    dash.unsubscribe(q)
    return got


# ---------------------------------------------------------------- the adapter alone
def test_a_beep_and_a_say_become_the_documented_browser_shape(dash):
    (b,) = heard(dash, BEEP)
    assert b == {"type": "dashboard.sound", "schemaVersion": 1, "streamId": dash.stream_id, "sentAt": b["sentAt"],
                 "sound": {"kind": "cue", "tDevice": 81235.2, "cue": "beep", "source": "beacon", "anchor": "item",
                           "azimuthDeg": -150.0, "elevationDeg": -12.0, "distanceM": 1.6, "muffled": True,
                           "text": None, "durationS": None, "audioUrl": None}}
    assert D.ISO_RE.match(b["sentAt"])
    (s,) = heard(dash, SAY)
    assert s["sound"] == {"kind": "cue", "tDevice": 81234.9, "cue": "say", "source": "voice", "anchor": "item",
                          "azimuthDeg": -150.0, "elevationDeg": -12.0, "distanceM": 1.6, "muffled": None,
                          "text": SAY["text"], "durationS": 2.9, "audioUrl": None}


def test_directions_are_wrapped_clamped_and_rounded_and_label_audio_is_aliased(dash):
    label = dict(SAY, cue="label", anchor="room", az_deg=190.04, el_deg=-95.0, distance_m=0.6049, text="x" * 400,
                 duration_s=1.8, audio_url="/v1/audio/abc123")
    edge = dict(BEEP, az_deg=179.96, el_deg=90.2, distance_m=0.0, muffled=None)
    left = dict(BEEP, az_deg=-180.0, el_deg=-0.04, distance_m=50.0)
    far = dict(BEEP, az_deg=540.0 + 30.04, el_deg=12.345)
    away = dict(SAY, cue="label", audio_url="https://elsewhere.example/a.m4a")
    a, b, c, d, e = (env["sound"] for env in heard(dash, label, edge, left, far, away))
    assert (a["azimuthDeg"], a["elevationDeg"], a["distanceM"]) == (-170.0, -90.0, 0.6)
    assert a["audioUrl"] == "/media/audio/abc123" and a["text"] == "x" * 300 and a["anchor"] == "room"
    assert (b["azimuthDeg"], b["elevationDeg"], b["distanceM"], b["muffled"]) == (-180.0, 90.0, 0.0, None)
    assert (c["azimuthDeg"], c["elevationDeg"], c["distanceM"]) == (-180.0, 0.0, 50.0)
    assert (d["azimuthDeg"], d["elevationDeg"]) == (-150.0, 12.3)          # 570 degrees is -150; to 0.1
    assert e["audioUrl"] is None                                             # only the server's own audio paths
    for s in (a, b, c, d, e):
        assert -180.0 <= s["azimuthDeg"] < 180.0


def test_malformed_sounds_are_dropped_and_counted(dash):
    no_t = dict(BEEP)
    del no_t["t_device"]
    bad = [dict(BEEP, cue="boop"), dict(BEEP, az_deg=float("nan")), no_t, dict(BEEP, anchor="pocket"),
           dict(BEEP, source="speaker"), dict(BEEP, el_deg=float("inf")), dict(BEEP, distance_m=-0.1),
           dict(BEEP, distance_m=50.5), dict(BEEP, muffled="yes"), dict(SAY, text=5), dict(SAY, duration_s=61),
           dict(SAY, duration_s=-1), dict(BEEP, t_device=True), dict(BEEP, t_device="81235"), dict(BEEP, az_deg=10 ** 400),
           dict(BEEP, cue=["beep"]), dict(BEEP, anchor={"item": 1}),
           dict(FIELD, t_device=None), dict(FIELD, head_yaw_deg=float("nan")), dict(FIELD, beacon=[1, 2, 3]),
           dict(FIELD, beacon=dict(FIELD["beacon"], muffled="no")), dict(FIELD, voice=dict(az_deg=0, el_deg=0, distance_m=1)),
           dict(FIELD, voice=dict(FIELD["voice"], anchor="room!")), dict(FIELD, beacon=dict(az_deg=0, el_deg=0))]
    assert heard(dash, *bad) == []
    assert dash.sound_dropped == len(bad)
    assert dash.phone_connected()                                            # the phone still counts as alive
    assert len(heard(dash, BEEP, FIELD)) == 2 and dash.sound_dropped == len(bad)


def test_a_sound_field_with_null_or_absent_sources(dash):
    quiet = dict(type="sound_field", session_id="s1", t_device=81236.0)            # no head yaw, no sources
    beacon_only = dict(FIELD, voice=None, head_yaw_deg=-12.34, beacon=dict(az_deg=-200.0, el_deg=-12.04, distance_m=1.6049))
    a, b, c = (env["sound"] for env in heard(dash, FIELD, quiet, beacon_only))
    assert a == {"kind": "field", "tDevice": 81235.3, "headYawDeg": 12.3,
                 "beacon": {"azimuthDeg": -150.0, "elevationDeg": -12.0, "distanceM": 1.6, "muffled": True},
                 "voice": {"azimuthDeg": 0.0, "elevationDeg": 0.0, "distanceM": 1.0, "anchor": "ahead"}}
    assert b == {"kind": "field", "tDevice": 81236.0, "headYawDeg": None, "beacon": None, "voice": None}
    assert c["headYawDeg"] == -12.3 and c["voice"] is None
    assert c["beacon"] == {"azimuthDeg": 160.0, "elevationDeg": -12.0, "distanceM": 1.6, "muffled": None}


def test_the_latest_field_is_offered_for_under_a_second(dash, clock):
    assert dash.fresh_field() is None
    (env,) = heard(dash, FIELD)
    clock.mono += 0.9
    assert dash.fresh_field() is env
    clock.mono += 0.2
    assert dash.fresh_field() is None


def test_spoken_instruction_is_the_say_line_while_it_plays_and_3_s_after(dash, clock):
    def nav():
        return valid(dash.snapshot())["navigation"]["spokenInstruction"]

    assert nav() is None
    ev = dash._changed
    heard(dash, FIELD)
    assert dash._changed is ev                                               # the 10/s field doesn't bump snapshots
    heard(dash, SAY)
    assert dash._changed is not ev                                           # a new caption does
    assert nav() == SAY["text"]
    clock.mono += 2.9 + 3.0 - 0.05
    heard(dash, BEEP, dict(SAY, cue="label", text="That's the cumin, love"))  # other cues don't change it
    assert nav() == SAY["text"]
    clock.mono += 0.1
    assert nav() is None
    heard(dash, dict(SAY, text="Got it.", duration_s=None))                   # no duration: 3 s from the start
    clock.mono += 2.95
    assert nav() == "Got it."
    clock.mono += 0.1
    assert nav() is None


def test_each_connection_keeps_its_newest_300(dash):
    q1, q2 = dash.subscribe(), dash.subscribe()
    for i in range(305):
        dash.observe_phone(PHONE, dict(BEEP, t_device=float(i)))
    assert q1.qsize() == q2.qsize() == 300
    got = [q1.get_nowait()["sound"]["tDevice"] for _ in range(300)]
    assert got == [float(i) for i in range(5, 305)]                         # the oldest five were dropped
    dash.unsubscribe(q1)
    dash.observe_phone(PHONE, BEEP)
    assert q1.empty() and q2.qsize() == 300


def test_only_the_bound_session_is_heard_and_a_new_one_starts_clean(dash):
    heard(dash, SAY, FIELD)
    assert dash.spoken is not None and dash.fresh_field() is not None
    unbound = dict(BEEP)
    del unbound["session_id"]
    assert heard(dash, unbound) == [] and dash.sound_dropped == 1            # no session: not the bound phone's
    _, T, _, _ = emulated()
    q = dash.subscribe()
    dash.observe_phone(object(), pose_msg(T, t=2000.0, session="s2"))        # the app restarted
    assert dash.session_id == "s2" and dash.spoken is None and dash.fresh_field() is None
    assert valid(dash.snapshot())["navigation"]["spokenInstruction"] is None
    dash.observe_phone(object(), dict(BEEP, session_id="s2", t_device=2000.1))
    assert [q.get_nowait()["sound"]["tDevice"] for _ in range(q.qsize())] == [2000.1]


# ---------------------------------------------------------------- end to end, through the server
@pytest.fixture()
def server(tmp_path, monkeypatch):
    monkeypatch.setenv("MARCO_DATA", str(tmp_path))
    monkeypatch.setenv("MARCO_MODE", "stub")
    monkeypatch.setenv("STUB_SPEEDUP", "200")
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
    monkeypatch.delenv("MARCO_DASHBOARD_DIR", raising=False)
    import marco.app
    import marco.stub
    importlib.reload(marco.stub)
    app_mod = importlib.reload(marco.app)
    with TestClient(app_mod.app) as c:                 # one event loop for every socket, as under uvicorn
        yield app_mod, c


def synced(ws, session="s1", n=[0]):
    """Everything sent on this phone socket so far has been handled. Returns what the server sent back meanwhile."""
    n[0] += 1
    qid = f"sync-{n[0]}"
    ws.send_json(dict(type="query", session_id=session, query_id=qid, kind="find", name="mug"))
    replies = []
    while not replies or replies[-1].get("query_id") != qid:
        replies.append(ws.receive_json())
    return replies


def take(ev, n, timeout=5.0):
    """Read /events until n dashboard.sound envelopes arrived: (sounds, snapshots)."""
    sounds, snaps, end = [], [], time.monotonic() + timeout
    while len(sounds) < n:
        assert time.monotonic() < end, f"only {len(sounds)} of {n} sounds"
        m = ev.receive_json()                          # a snapshot comes at least once a second
        (sounds if m["type"] == "dashboard.sound" else snaps).append(m)
    return sounds, snaps


def test_sounds_reach_events_at_once_and_never_the_brain(server, monkeypatch):
    app_mod, c = server
    seen = []
    on_phone = app_mod.brain.on_phone
    monkeypatch.setattr(app_mod.brain, "on_phone", lambda m: (seen.append(m.get("type")), on_phone(m))[1])
    _, T, _, _ = emulated()
    with c.websocket_connect("/events") as ev:
        first = ev.receive_json()
        assert first["type"] == "dashboard.snapshot"
        with c.websocket_connect("/v1/phone") as ws:
            ws.send_json(pose_msg(T))
            for m in (BEEP, SAY, FIELD, dict(BEEP, cue="boop")):
                ws.send_json(m)
            replies = synced(ws)
            sounds, _ = take(ev, 3)
            snap = c.get("/dashboard/snapshot").json()
    assert [r for r in replies if r.get("type") == "error"] == []           # no "unknown message type" back
    assert seen == ["pose", "query"]                                        # the brain never saw a sound
    assert [s["sound"].get("cue", "field") for s in sounds] == ["beep", "say", "field"]
    assert all(s["streamId"] == first["streamId"] == snap["streamId"] and s["schemaVersion"] == 1 for s in sounds)
    assert sounds[0]["sound"] == {"kind": "cue", "tDevice": 81235.2, "cue": "beep", "source": "beacon", "anchor": "item",
                                  "azimuthDeg": -150.0, "elevationDeg": -12.0, "distanceM": 1.6, "muffled": True,
                                  "text": None, "durationS": None, "audioUrl": None}
    assert sounds[2]["sound"]["voice"] == {"azimuthDeg": 0.0, "elevationDeg": 0.0, "distanceM": 1.0, "anchor": "ahead"}
    assert valid(snap)["navigation"]["spokenInstruction"] == SAY["text"]
    assert app_mod.dash.sound_dropped == 1
    rec = (app_mod.DATA / "sessions" / "s1" / "phone.jsonl").read_text()   # still recorded, like every phone message
    assert rec.count('"type": "sound"') == 3 and rec.count('"type": "sound_field"') == 1


def test_a_new_events_connection_gets_the_field_only_while_it_is_fresh(server):
    app_mod, c = server
    _, T, _, _ = emulated()
    with c.websocket_connect("/v1/phone") as ws:
        ws.send_json(pose_msg(T))
        ws.send_json(FIELD)
        synced(ws)
        with c.websocket_connect("/api/events") as ev:
            a, b = ev.receive_json(), ev.receive_json()
        assert a["type"] == "dashboard.snapshot" and b["type"] == "dashboard.sound"
        assert b["sound"]["kind"] == "field" and b["sound"]["tDevice"] == FIELD["t_device"]
        valid(a)
        time.sleep(1.05)
        with c.websocket_connect("/events") as ev:
            a, b = ev.receive_json(), ev.receive_json()                     # the heartbeat, not a stale field
        assert a["type"] == b["type"] == "dashboard.snapshot"
    assert not app_mod.dash.sound_subs                                      # every connection unsubscribed


def test_events_keeps_its_snapshot_pace_while_sounds_stream(server):
    _, c = server
    _, T, _, _ = emulated()
    with c.websocket_connect("/v1/phone") as ws, c.websocket_connect("/events") as ev:
        ws.send_json(pose_msg(T))
        synced(ws)
        ev.receive_json()

        def phone():                                                        # 20 fields a second for 1.5 s
            for i in range(30):
                ws.send_json(dict(FIELD, t_device=3000.0 + i * 0.05))
                time.sleep(0.05)

        th = threading.Thread(target=phone)
        th.start()
        sounds, snaps = take(ev, 30)
        th.join()
        snaps.append(ev.receive_json())
    assert [s["sound"]["tDevice"] for s in sounds] == [3000.0 + i * 0.05 for i in range(30)]   # all, in order
    sent = [datetime.fromisoformat(s["sentAt"].replace("Z", "+00:00")).timestamp() for s in snaps]
    seqs = [s["sequence"] for s in snaps]
    assert len(snaps) >= 2 and seqs == sorted(set(seqs))
    gaps = [b - a for a, b in zip(sent, sent[1:])]
    assert all(0.19 <= g < 1.6 for g in gaps), gaps                         # at most 5/s, at least once a second
    for s in snaps:
        valid(s)


class FakeBrowser:
    """The /events socket as the handler sees it: every send recorded with the loop's clock; it breaks after `limit`."""

    def __init__(self, limit=None):
        self.headers, self.sent, self.limit, self.busy = {}, [], limit, 0

    async def accept(self):
        pass

    async def close(self, code=1000, reason=None):
        pass

    async def send_json(self, m):
        self.busy += 1
        assert self.busy == 1, "two sends at once on one socket"
        await asyncio.sleep(0.001)
        self.busy -= 1
        if self.limit is not None and len(self.sent) >= self.limit:
            raise RuntimeError("the browser went away")
        self.sent.append((asyncio.get_running_loop().time(), m))


@pytest.fixture()
def app_mod(tmp_path, monkeypatch):
    monkeypatch.setenv("MARCO_DATA", str(tmp_path))
    monkeypatch.setenv("MARCO_MODE", "stub")
    monkeypatch.setenv("AUTH_TEST_BYPASS", "1")
    import marco.app
    import marco.stub
    importlib.reload(marco.stub)
    return importlib.reload(marco.app)


def test_the_events_loop_sends_each_sound_before_the_next_snapshot(app_mod):
    dash = app_mod.dash
    _, T, _, _ = emulated()

    async def go():
        dash.observe_phone(PHONE, pose_msg(T))                      # bound before the browser connects
        dash.observe_phone(PHONE, FIELD)                            # fresh: it follows the first snapshot
        ws = FakeBrowser()
        task = asyncio.ensure_future(app_mod.dashboard_events(ws))
        await asyncio.sleep(0.05)
        dash.observe_phone(PHONE, dict(BEEP, t_device=1.0))         # no change to the snapshot: out at once anyway
        await asyncio.sleep(0.05)
        dash.observe_phone(PHONE, dict(SAY, t_device=2.0))          # a change: a snapshot follows, after 0.2 s
        for _ in range(100):
            if sum(m["type"] == "dashboard.snapshot" for _, m in ws.sent) >= 2:
                break
            await asyncio.sleep(0.02)
        broken = FakeBrowser(limit=1)                               # a browser that goes away after one message
        gone = asyncio.ensure_future(app_mod.dashboard_events(broken))
        await asyncio.wait_for(gone, 2.0)                            # the handler ends on a failed send
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return ws.sent

    sent = asyncio.run(go())
    kinds = [m["sound"]["tDevice"] if m["type"] == "dashboard.sound" else "snapshot" for _, m in sent]
    assert kinds[:5] == ["snapshot", FIELD["t_device"], 1.0, 2.0, "snapshot"]
    snaps = [t for t, m in sent if m["type"] == "dashboard.snapshot"]
    assert snaps[1] - snaps[0] >= app_mod.MIN_PUSH_S - 0.01
    assert sent[4][1]["data"]["navigation"]["spokenInstruction"] == SAY["text"]
    assert not dash.sound_subs                                      # both handlers unsubscribed
