"""SIMULATED phone, for rehearsing the dashboard without the iPhone. It connects to /v1/phone as the app does and plays
a scripted, made-up ~30 s "find the keys" run: pose and guidance at 10/s, a `sound` per cue and the 10/s
`sound_field` (docs/INTERFACES.md §3.2), so the dashboard's radar, beacon, cues and caption move as they will with
the real app. No phone, camera or AirPods are involved; everything it prints is marked SIMULATED.

  python tools/sound_demo.py                                    # the local server, http://127.0.0.1:8000
  python tools/sound_demo.py --server http://127.0.0.1:8000 --header "Tailscale-User-Login: you@github" --loop

The story, as the wearer hears it (head-relative: azimuth 0 ahead, +90 right; distances ear to source, in 3D):
  0.5 s   the keys are 2 m behind-right, on the table (azimuth +150): "Polo! Behind you, two steps, on the table."
  3.5 s   beeps from the keys, muffled while they are behind the head, one every clamp(0.15 + 0.35 d, 0.15, 1.0) s
  4.5 s   the wearer turns right toward them (3 s); a ding once they are within 12 degrees of ahead
  8 s     walks in, 2.0 m to 0.25 m in 7 s: "Within reach, on the table." at 0.6 m (no beeps for 1.2 s)
  14.4 s  the steady tone at 0.30 m; 15.4 s the touch: tone off, silence, "Got it.", then guidance off and quiet
then standing still until 30 s. d in the beep gap is the floor distance, chest to keys, as in the app (§7).
The head starts turned 30 degrees right of the body, so "behind you" is right for the body (§7: the spoken direction
is body-relative, the beacon head-relative). The keys sit where the stub server seeds its own (2 m behind the first
pose it sees, on a 0.75 m table, 0.8 m below the ears), so against a fresh stub the map, the radar and the sounds
agree. Use a server the real phone isn't streaming to: while this runs, its fake session is the dashboard's phone.
"""
import argparse
import asyncio
import json
import math
import sys
import time
import uuid
from pathlib import Path

import numpy as np
import websockets

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from marco import geometry as G  # noqa: E402

UP = np.array([0.0, 1.0, 0.0])
EAR_Y = 1.55                   # the wearer's ears
EAR_ABOVE_CHEST_M = 0.45       # where the app puts the listener above the chest phone (ios Config.earAboveChestM)
TABLE_Y = 0.75                 # the keys, 0.8 m below the ears
KEYS_BEHIND_M = 2.0
BODY_YAW0 = -90.0              # facing world -x at the start
HEAD_RIGHT0 = 30.0             # the head turned this far right of the body at the start
TILT_DEG = 20.0                # the vest tilts the chest camera down
END_S = 30.0
POLO = ("Polo! Behind you, two steps, on the table.", 0.5, 2.9)   # (text, at, s); §7 would count 3 steps for 2.0 m
WITHIN_REACH = ("Within reach, on the table.", 2.2)
GOT_IT = ("Got it.", 1.1)
BEEPS_FROM = 3.5
HEAD_TURN, BODY_TURN = (4.5, 7.5), (4.8, 7.8)
WALK_IN, PAUSE_AT, WALK_END = 8.0, 12.5, 15.0       # 2.0 m to 0.6 m, then 0.6 m to 0.25 m (reaching)
NEAR_M, REACH_M, END_M = 0.6, 0.30, 0.25
TOUCH_AT = 15.4
FACING_DEG, UNLOCK_DEG, BEHIND_DEG = 12.0, 20.0, 90.0                  # ios Guidance.swift
FACING_HOLD_S, TOUCHED_HOLD_S, QUIET_AFTER_SPEECH_S = 0.8, 1.5, 1.2
AUDIO_DT = 0.01                # the phone's audio loop (60 Hz there; 100 Hz here, offset from the 10/s streams)

CHEST0 = np.array([0.0, EAR_Y - EAR_ABOVE_CHEST_M, 0.0])


def _fwd(yaw):
    r = math.radians(yaw)
    return np.array([math.sin(r), 0.0, -math.cos(r)])


def _right(yaw):
    r = math.radians(yaw)
    return np.array([math.cos(r), 0.0, math.sin(r)])


TOWARD = -_fwd(BODY_YAW0)                                               # from the start toward the keys
KEYS = CHEST0 + KEYS_BEHIND_M * TOWARD
KEYS[1] = TABLE_Y


def smooth(x):
    x = min(max(x, 0.0), 1.0)
    return x * x * (3.0 - 2.0 * x)


def beep_gap(distance_m):
    """§7 step 5: the gap between beeps."""
    return min(max(0.15 + 0.35 * distance_m, 0.15), 1.0)


def head_yaw(t):
    """The listener's yaw in the world (heading convention): turns right to face the keys, then wobbles a little."""
    turn = smooth((t - HEAD_TURN[0]) / (HEAD_TURN[1] - HEAD_TURN[0]))
    s = t - HEAD_TURN[1]
    wobble = min(max(s, 0.0), 1.0) * (2.5 * math.sin(2 * math.pi * 0.4 * s) + 1.0 * math.sin(2 * math.pi * 1.1 * s))
    return BODY_YAW0 + HEAD_RIGHT0 + (180.0 - HEAD_RIGHT0) * turn + wobble


def body_yaw(t):
    return BODY_YAW0 + 180.0 * smooth((t - BODY_TURN[0]) / (BODY_TURN[1] - BODY_TURN[0]))


def flat_distance(t):
    """Chest (and ears) to the keys on the floor plane: a walk in, a stop at 0.6 m, then the last reach."""
    if t < PAUSE_AT:
        return KEYS_BEHIND_M - (KEYS_BEHIND_M - NEAR_M) * smooth((t - WALK_IN) / (PAUSE_AT - WALK_IN))
    return NEAR_M - (NEAR_M - END_M) * smooth((t - PAUSE_AT) / (WALK_END - PAUSE_AT))


def chest(t):
    p = KEYS - flat_distance(t) * TOWARD
    p[1] = CHEST0[1]
    return p


def ear(t):
    return chest(t) + EAR_ABOVE_CHEST_M * UP


def camera_transform(t):
    """Camera to world for the portrait chest phone, facing the body's heading, tilted down (like the emulator's)."""
    yaw, th = body_yaw(t), math.radians(TILT_DEG)
    f = math.cos(th) * _fwd(yaw) - math.sin(th) * UP                   # optical axis
    u = math.sin(th) * _fwd(yaw) + math.cos(th) * UP                   # image up; the sensor's x points down
    T = np.eye(4)
    T[:3, 0], T[:3, 1], T[:3, 2], T[:3, 3] = -u, _right(yaw), -f, chest(t)
    return T


def rel_azimuth(t):
    return G.relative_azimuth_deg(ear(t), head_yaw(t), KEYS)


def heard(t):
    """Where the keys sound for the wearer at t: az_deg, el_deg, distance_m (ear to keys), rounded as the app sends."""
    d = KEYS - ear(t)
    fwd, right = _fwd(head_yaw(t)), _right(head_yaw(t))
    x, y, z = float(d @ right), float(d[1]), float(-(d @ fwd))          # listener-relative: x right, y up, -z ahead
    flat = math.hypot(x, z)
    return dict(az_deg=round(math.degrees(math.atan2(x, -z)), 1), el_deg=round(math.degrees(math.atan2(y, flat)), 1),
                distance_m=round(math.hypot(flat, y), 2))


def scenario(session_id="sim", t0_device=1000.0, item_id="fake-keys", map_id="sim-map"):
    """The scripted run as [(t_s, message)], t from the start and strictly increasing. Pure: the same arguments give
    the same messages. The cues follow the app's guidance loop (ios Guidance.swift) on this made-up walk."""
    out = []
    lines = []                                                          # (start, end) of each spoken line
    st = dict(active=False, locked=False, locked_at=None, last_beep=-math.inf, quiet_until=BEEPS_FROM, near=False,
              reach=False, touched_at=None, audible=False)

    def put(t, msg):
        out.append((round(t, 3), msg))

    def cue(t, name, **extra):
        voice = name in ("say", "label", "blip")
        put(t, dict(type="sound", session_id=session_id, t_device=round(t0_device + t, 3), cue=name,
                    source="voice" if voice else "beacon", anchor="item", **heard(t), **extra))

    def say(t, text, seconds):
        lines.append((t, t + seconds))
        cue(t, "say", text=text, duration_s=seconds)

    def phase(t):
        if st["touched_at"] is not None:
            return "touched"
        if st["reach"]:
            return "reach"
        if st["locked"]:
            return "facing" if t - st["locked_at"] < FACING_HOLD_S else "approach"
        return "behind" if abs(rel_azimuth(t)) > BEHIND_DEG else "turning"

    def audio(t):                                                       # one step of the phone's guidance loop
        if not st["active"]:
            if t >= POLO[1] and st["touched_at"] is None:
                st["active"] = True
                say(t, POLO[0], POLO[2])
            return
        if st["touched_at"] is not None:
            if t - st["touched_at"] >= TOUCHED_HOLD_S:
                st["active"] = False
                put(t, dict(type="guidance", session_id=session_id, item_id=item_id, phase="off",
                            rel_azimuth_deg=round(rel_azimuth(t), 1), distance_m=round(flat_distance(t), 2)))
            return
        if t >= TOUCH_AT:
            st["touched_at"] = t
            if st["reach"]:
                cue(t, "tone_off")
            cue(t + 0.001, "silence")
            say(t + 0.002, *GOT_IT)
            return
        az, d = abs(rel_azimuth(t)), flat_distance(t)
        if st["reach"] or d <= REACH_M:
            if not st["reach"]:
                st["reach"] = True
                cue(t, "tone_on")
            return
        if not st["locked"] and az <= FACING_DEG:
            st.update(locked=True, locked_at=t, last_beep=t)
            cue(t, "ding")
        elif st["locked"] and az > UNLOCK_DEG:
            st["locked"] = False
        if not st["near"] and d <= NEAR_M:
            st.update(near=True, quiet_until=t + QUIET_AFTER_SPEECH_S)
            say(t, *WITHIN_REACH)
        if t >= st["quiet_until"] and t - st["last_beep"] >= beep_gap(d) - 1e-9:
            st["last_beep"] = t
            cue(t, "beep", muffled=az > BEHIND_DEG)

    def stream(t, kind):                                                # the 10/s messages
        if kind == "pose":
            put(t, dict(type="pose", session_id=session_id, map_id=map_id, t_device=round(t0_device + t, 3),
                        camera_transform=[round(v, 6) for v in G.flat_colmajor(camera_transform(t))],
                        head_yaw_deg=round(G.wrap180(head_yaw(t)), 1), head_source="fusion"))
        elif kind == "guidance" and st["active"]:
            put(t, dict(type="guidance", session_id=session_id, item_id=item_id, phase=phase(t),
                        rel_azimuth_deg=round(rel_azimuth(t), 1), distance_m=round(flat_distance(t), 2)))
        elif kind == "field":
            beacon = dict(**heard(t), muffled=phase(t) == "behind") if st["active"] else None
            voice = dict(**heard(t), anchor="item") if any(a <= t < b for a, b in lines) else None
            if beacon or voice or st["audible"]:                        # and once more, both null, when it goes quiet
                st["audible"] = bool(beacon or voice)
                put(t, dict(type="sound_field", session_id=session_id, t_device=round(t0_device + t, 3),
                            head_yaw_deg=round(G.wrap180(head_yaw(t)), 1), beacon=beacon, voice=voice))

    ticks = [(round(n * AUDIO_DT + AUDIO_DT / 2, 3), "audio") for n in range(int(round(END_S / AUDIO_DT)))]
    for k in range(int(round(END_S * 10)) + 1):                        # staggered, so no two messages share a time
        ticks += [(round(k / 10, 3), "pose"), (round(k / 10 + 0.002, 3), "guidance"), (round(k / 10 + 0.004, 3), "field")]
    for t, kind in sorted(ticks):
        audio(t) if kind == "audio" else stream(t, kind)
    out.sort(key=lambda p: p[0])
    return out


def phone_url(server):
    s = server.rstrip("/")
    return s.replace("https://", "wss://", 1).replace("http://", "ws://", 1) + "/v1/phone"


def parse_headers(items):
    return {k.strip(): v.strip() for k, v in (h.split(":", 1) for h in items)}


def describe(t, m):
    line = (f"[SIMULATED] {t:6.2f} s  {m['cue']:<8}  az {m['az_deg']:+6.1f}  el {m['el_deg']:+5.1f}  "
            f"{m['distance_m']:.2f} m")
    if m.get("muffled"):
        line += "  muffled"
    if m.get("text"):
        line += f'  "{m["text"]}" ({m["duration_s"]} s)'
    return line


async def send(ws, messages, speed=1.0, out=print):
    """Send (t, message) pairs at their times from now, divided by speed. Prints each cue."""
    start = time.monotonic()
    for t, m in messages:
        wait = start + t / speed - time.monotonic()
        if wait > 0:
            await asyncio.sleep(wait)
        await ws.send(json.dumps(m))
        if m["type"] == "sound":
            out(describe(t, m))


async def _listen(ws, errors, out):
    """Read what the server sends back (answers, touches, errors), so its outbox to us never fills."""
    try:
        async for raw in ws:
            m = json.loads(raw)
            if m.get("type") == "error":
                errors.append(m)
                out(f"[SIMULATED] server error for {m.get('for_type')}: {m.get('detail')}")
    except websockets.ConnectionClosed:
        pass


async def run(server, headers=None, runs=1, item_id="fake-keys", speed=1.0, out=print, connect=None):
    """Play the scenario `runs` times (None: until stopped) on one fresh session, t_device carrying on between runs."""
    url, session = phone_url(server), "sim-" + uuid.uuid4().hex[:12]
    connect = connect or websockets.connect
    errors, sent, n = [], 0, 0
    t0 = round(time.monotonic(), 3)                                    # a device clock: seconds since some boot
    out(f"[SIMULATED] fake phone, no iPhone: scripted 'find the keys' ({END_S:.0f} s) to {url} as session {session}")
    async with connect(url, additional_headers=headers or {}) as ws:
        listener = asyncio.ensure_future(_listen(ws, errors, out))
        try:
            while runs is None or n < runs:
                msgs = scenario(session, t0_device=t0 + n * (END_S + 1.0), item_id=item_id)
                out(f"[SIMULATED] run {n + 1}: {len(msgs)} messages")
                await send(ws, msgs, speed, out)
                sent += len(msgs)
                n += 1
            await asyncio.sleep(0.3)                                    # the server's reply to the last messages
        finally:
            listener.cancel()
    out(f"[SIMULATED] done: {n} run(s), {sent} messages, {len(errors)} server error(s)")
    return dict(session_id=session, runs=n, sent=sent, errors=errors)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="SIMULATED phone: a scripted 'find the keys' run for the dashboard")
    ap.add_argument("--server", default="http://127.0.0.1:8000")
    ap.add_argument("--header", action="append", default=[], help="'Name: value' (only for calls on the box itself)")
    ap.add_argument("--loop", action="store_true", help="play it again and again until Ctrl-C")
    ap.add_argument("--item-id", default="fake-keys", help="the guided item's id (the stub seeds its keys as fake-keys)")
    a = ap.parse_args()
    try:
        rep = asyncio.run(run(a.server, parse_headers(a.header), runs=None if a.loop else 1, item_id=a.item_id))
    except KeyboardInterrupt:
        print("[SIMULATED] stopped")
        sys.exit(0)
    except (OSError, websockets.WebSocketException) as e:
        print(f"can't reach {a.server}: {e} (on the tailnet? allowed login?)")
        sys.exit(1)
    sys.exit(1 if rep["errors"] else 0)
