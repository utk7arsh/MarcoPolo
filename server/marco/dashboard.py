"""The dashboard adapter: the browser's API (frontend/docs/backend-integration-plan.md and fastapi-handoff.md; the
payload is frontend/src/lib/schema.ts, exported as frontend/docs/dashboard.snapshot.schema.json).

It runs no perception. It watches what the core already publishes (the dashboard feed: frame, world, timeline,
map_points; label_request to Photon; label_ready to the phone), the phone's own messages (pose, guidance, map,
command_ack) and the phone socket's lifecycle, and keeps a small read model. From it, app.py serves:
  GET  /dashboard/snapshot   one complete `dashboard.snapshot` envelope
  WS   /events               a snapshot at once, then after each change (at most 5/s) and at least once a second
  POST /dashboard/commands   Find and Stop for the phone (dashboard_commands.py)
  GET  /media/...            the recent upright frames, item photos, label audio and touch crops
all behind the same auth gate as /v1, and also under /api/... (the browser's default base path).
Everything here runs on the event loop thread; the core's state is only read, never changed.
"""
import asyncio
import base64
import io
import os
import re
import time
import uuid
from collections import OrderedDict

from . import geometry as G
from .dashboard_commands import CommandRelay, iso

PHONE_FRESH_S = 5.0          # silent this long: the phone counts as disconnected (frontend contract)
POSE_FRESH_S = 2.0           # connected but no pose this long: tracking limited
HEADPHONE_FRESH_S = 3.0      # head yaw from AirPods motion this recently: AirPods connected
GUIDANCE_FRESH_S = 3.0       # older guidance telemetry: navigation idle
FRAMES_KEPT = 30             # upright frames kept for /media (30 s at 1 frame/s; the browser needs 10)
EVENTS_KEPT = 50
REGISTRATIONS_KEPT = 20
MAP_PAD_M = 0.5
MIN_PUSH_S = 0.2
ISO_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?Z$")
SAFE_ID = re.compile(r"^[A-Za-z0-9_.-]{1,96}$")
PHASES = {"behind": "guiding", "turning": "guiding", "facing": "guiding", "approach": "guiding",
          "reach": "within_reach", "touched": "found"}
PATTERNS = {"guiding": "beacon", "within_reach": "steady", "found": "confirmation"}
MEMORY_KINDS = {"seen": "seen", "moved": "moved", "put_down": "moved", "label_added": "label_saved"}


def wall_or(value, fallback):
    return value if isinstance(value, str) and ISO_RE.match(value) else fallback


def audio_alias(url):
    """/v1/audio/<id> (the phone's path) -> /media/audio/<id> (the browser rewrites /media/ to its API base)."""
    if not url:
        return None
    m = re.match(r"^/v1/audio/([A-Za-z0-9_.-]+)$", url)
    return f"/media/audio/{m.group(1)}" if m else None


class Dashboard:
    def __init__(self, brain, command_timeout_s=None, room_id=None, room_name=None):
        self.brain = brain
        self.stream_id = "marco-" + uuid.uuid4().hex[:12]
        self.started = time.time()
        self.sequence = 0
        self.room_id = room_id or os.environ.get("MARCO_ROOM_ID", "room")
        self.room_name = room_name or os.environ.get("MARCO_ROOM_NAME", "Room")
        self.relay = CommandRelay(float(command_timeout_s or os.environ.get("DASHBOARD_COMMAND_TIMEOUT_S", "10")))
        self.phone_ws = None          # the socket bound to the current phone session
        self.session_id = None
        self.map_id = None
        self.last_phone = None        # (wall, monotonic) of the last phone message, any type
        self.pose = None              # dict(T, t_device, head_yaw, head_source, wall, mono, map_id)
        self.fusion = None            # (wall, monotonic) of the last AirPods-fused pose
        self.guidance = None          # (message, wall, monotonic)
        # The core already restored its registry. Show saved items before any phone/world event arrives.
        self.items = list(brain.items_public())
        self.frames: OrderedDict[str, dict] = OrderedDict()
        self.frame_meta = None
        self.frame_counter = 0
        self.bounds = None            # [min_x, max_x, min_z, max_z] of map points in the current map
        self.memory = []              # recentMemory entries, newest first
        self.memory_keys = set()
        self.memory_counter = 0
        self.registrations: OrderedDict[str, dict] = OrderedDict()
        self._changed = asyncio.Event()

    # ---------------------------------------------------------------- observations
    def _bump(self):
        self._changed.set()
        self._changed = asyncio.Event()

    async def wait_change(self, timeout=1.0):
        ev = self._changed
        try:
            await asyncio.wait_for(ev.wait(), timeout)
        except asyncio.TimeoutError:
            pass

    def _set_map(self, map_id, reset=False):
        if map_id and (reset or map_id != self.map_id):
            if self.map_id is not None or reset:
                self.bounds = None                       # a new coordinate frame: old extents don't apply
                self.pose = None
                self.guidance = None
            self.map_id = map_id

    def _bind(self, ws, session_id):
        if session_id and session_id != self.session_id:
            if self.session_id is not None:
                self.relay.session_replaced()
                self.pose, self.guidance, self.fusion = None, None, None
            self.session_id = session_id
        if ws is not None and session_id:
            self.phone_ws = ws

    def observe_frame_meta(self, meta):
        """A frame upload's meta, just before the core processes it (POST /v1/frames)."""
        self._bind(None, meta.get("session_id"))
        self._set_map(meta.get("map_id"))
        self.frame_meta = meta
        self.last_phone = (time.time(), time.monotonic())

    def observe_phone(self, ws, msg):
        """A message the phone sent on /v1/phone."""
        now, mono = time.time(), time.monotonic()
        self._bind(ws, msg.get("session_id"))
        self.last_phone = (now, mono)
        kind = msg.get("type")
        if kind == "map":
            self._set_map(msg.get("map_id"), reset=msg.get("event") == "new_map")
        elif msg.get("map_id"):
            self._set_map(msg["map_id"])
        if kind == "pose":
            try:
                T = G.mat4(msg["camera_transform"])
            except (KeyError, ValueError, TypeError):
                return
            t = float(msg.get("t_device") or 0.0)
            if self.pose is not None and t < self.pose["t_device"]:
                return                                   # out of order within the session
            self.pose = dict(T=T, t_device=t, head_yaw=msg.get("head_yaw_deg"), head_source=msg.get("head_source"),
                             wall=now, mono=mono, map_id=msg.get("map_id") or self.map_id)
            if msg.get("head_source") == "fusion":
                self.fusion = (now, mono)
        elif kind == "guidance":
            self.guidance = (msg, now, mono)
        elif kind == "command_ack":
            self.relay.ack(msg)
        self._bump()

    def phone_closed(self, ws):
        if ws is self.phone_ws:
            self.phone_ws = None
            self._bump()

    def observe(self, channel, msg):
        """Everything the core dispatches (app.dispatch)."""
        kind = msg.get("type")
        if channel == "dashboard":
            if kind == "world":
                self.items = list(msg.get("items") or [])
            elif kind == "frame":
                self._frame(msg)
            elif kind == "map_points":
                xs = [p[0] for p in msg.get("points") or []]
                zs = [p[2] for p in msg.get("points") or []]
                if xs:
                    b = self.bounds or [min(xs), max(xs), min(zs), max(zs)]
                    self.bounds = [min(b[0], min(xs)), max(b[1], max(xs)), min(b[2], min(zs)), max(b[3], max(zs))]
            elif kind == "timeline":
                for e in msg.get("events") or []:
                    self._memory(e)
        elif channel == "photon" and kind == "label_request" and SAFE_ID.match(str(msg.get("touch_id", ""))):
            tid = msg["touch_id"]
            self.registrations[tid] = dict(id=tid, status="waiting_for_label", photoUrl=f"/media/touch/{tid}.jpg",
                                           recipientName=None, itemId=None, label=None, updatedAt=iso(time.time()),
                                           message=msg.get("question"))
        elif channel == "phone" and kind == "label_ready":
            self._label_saved(msg)
        while len(self.registrations) > REGISTRATIONS_KEPT:
            self.registrations.popitem(last=False)
        self._bump()

    def observe_registration(self, name, result, source):
        """The reply of POST /v1/items: a saved item, or a retake."""
        rid = result.get("item_id") or f"retake-{uuid.uuid4().hex[:8]}"
        ok = result.get("quality") == "ok"
        self.registrations[rid] = dict(id=rid, status="saved" if ok else "retake",
                                       photoUrl=f"/media/items/{rid}.jpg" if ok else None, recipientName=None,
                                       itemId=result.get("item_id") if ok else None, label=None,
                                       updatedAt=iso(time.time()),
                                       message=None if ok else (result.get("reason") or f"Retake the photo of the {name}."))
        while len(self.registrations) > REGISTRATIONS_KEPT:
            self.registrations.popitem(last=False)
        self._bump()

    def _label_saved(self, msg):
        item_id = msg.get("item_id")
        touch = next((tid for tid, tc in list(getattr(self.brain, "touches", {}).items()) if tc.get("item_id") == item_id), None)
        key = touch if touch in self.registrations else (touch or item_id)
        if not key:
            return
        now = iso(time.time())
        reg = self.registrations.get(key) or dict(id=key, photoUrl=None, recipientName=None, message=None)
        reg.update(status="saved", itemId=item_id, updatedAt=now,
                   label=dict(audioUrl=audio_alias(msg.get("label_audio_url")), transcript=msg.get("label_text"),
                              authorName=None, durationSeconds=None, createdAt=now))
        self.registrations[key] = reg

    def _frame(self, msg):
        try:
            from PIL import Image
            jpeg = base64.b64decode(msg["jpeg_b64"])
            w, h = Image.open(io.BytesIO(jpeg)).size
        except (KeyError, ValueError, OSError):
            return
        self.frame_counter += 1
        token = f"{self.frame_counter}-{int(msg.get('frame_id') or 0)}"
        boxes = []
        for b in msg.get("boxes") or []:
            if not b.get("present") or not b.get("item_id"):
                continue
            x0, y0, x1, y1 = (min(max(float(v), 0.0), lim) for v, lim in zip(b["box"], (w, h, w, h)))
            if x1 > x0 and y1 > y0:
                boxes.append(dict(itemId=b["item_id"], boxPx=[round(x0, 1), round(y0, 1), round(x1, 1), round(y1, 1)]))
        meta = self.frame_meta or {}
        captured = wall_or(meta.get("t_wall") if meta.get("frame_id") == msg.get("frame_id") else None,
                           wall_or(msg.get("t_wall"), iso(time.time())))
        self.frames[token] = dict(jpeg=jpeg, w=w, h=h, frame_id=int(msg.get("frame_id") or 0), captured=captured,
                                  boxes=boxes)
        while len(self.frames) > FRAMES_KEPT:
            self.frames.popitem(last=False)

    def _memory(self, e):
        kind = MEMORY_KINDS.get(e.get("kind"))
        if kind is None or not e.get("item_id"):
            return
        key = (e.get("kind"), e["item_id"], e.get("t_wall"))
        if key in self.memory_keys:
            return
        self.memory_keys.add(key)
        self.memory_counter += 1
        self.memory.insert(0, dict(id=f"m-{self.memory_counter}", itemId=e["item_id"], kind=kind,
                                   at=wall_or(e.get("t_wall"), iso(time.time())), surface=e.get("surface")))
        del self.memory[EVENTS_KEPT:]

    # ---------------------------------------------------------------- reads
    def frame(self, token):
        return self.frames.get(token)

    def item(self, item_id):
        return next((it for it in self.items if it.get("item_id") == item_id), None)

    def phone_connected(self):
        return (self.phone_ws is not None and self.last_phone is not None
                and time.monotonic() - self.last_phone[1] <= PHONE_FRESH_S)

    def device_id(self):
        return self.session_id or ""

    # ---------------------------------------------------------------- the snapshot
    def snapshot(self):
        self.relay.expire()
        self.sequence += 1
        return dict(type="dashboard.snapshot", schemaVersion=1, streamId=self.stream_id, sequence=self.sequence,
                    sentAt=iso(time.time()), data=self._data())

    def _data(self):
        mono = time.monotonic()
        connected = self.phone_connected()
        map_id = self.map_id
        wearer = None
        if self.pose is not None and map_id and self.pose["map_id"] == map_id:
            p = self.pose["T"][:3, 3]
            hy = self.pose["head_yaw"]
            wearer = dict(at=iso(self.pose["wall"]), worldMapId=map_id,
                          position=dict(x=round(float(p[0]), 3), y=round(float(p[1]), 3), z=round(float(p[2]), 3)),
                          bodyYawDeg=round(G.heading_deg(self.pose["T"]), 1),
                          headYawDeg=round(float(hy), 1) if isinstance(hy, (int, float)) else None)
        if not connected:
            tracking = "unavailable"
        elif self.pose is None or mono - self.pose["mono"] > POSE_FRESH_S:
            tracking = "limited"
        else:
            tracking = "normal"
        fusion_fresh = self.fusion is not None and mono - self.fusion[1] <= HEADPHONE_FRESH_S
        items = [self._item(it, map_id) for it in self.items if it.get("item_id")]
        return dict(
            session=dict(id=self.session_id or "", deviceId=self.device_id(), roomId=self.room_id, roomName=self.room_name,
                         worldMapId=map_id),
            devices=dict(phone=dict(state="connected" if connected else "disconnected",
                                    lastMessageAt=iso(self.last_phone[0]) if self.last_phone else None, tracking=tracking),
                         airpods=dict(state="connected" if (connected and fusion_fresh) else "unknown",
                                      lastMessageAt=iso(self.fusion[0]) if self.fusion else None)),
            map=self._map(map_id, items, wearer),
            wearer=wearer,
            items=items,
            camera=self._camera(),
            navigation=self._navigation(connected, mono),
            registrations=list(reversed(self.registrations.values())),
            recentMemory=list(self.memory),
            lastCommand=self.relay.last(),
        )

    def _item(self, it, map_id):
        iid = it["item_id"]
        rec = getattr(getattr(self.brain, "registry", None), "records", {}).get(iid)     # saved: it has a photo on disk
        photo = f"/media/items/{iid}.jpg" if rec is not None and SAFE_ID.match(iid) else None
        voice = None
        if it.get("label_text") or it.get("label_audio_url"):
            voice = dict(audioUrl=audio_alias(it.get("label_audio_url")), transcript=it.get("label_text"), authorName=None,
                         durationSeconds=None,
                         createdAt=wall_or((rec or {}).get("updated_wall"), wall_or(it.get("last_seen_wall"), iso(self.started))))
        last = None
        if it.get("last_seen_wall") and ISO_RE.match(it["last_seen_wall"]):
            pos = it.get("position")
            usable = pos is not None and it.get("state") not in ("stale",) and map_id is not None
            last = dict(at=it["last_seen_wall"], roomId=self.room_id, roomName=self.room_name, surface=it.get("surface"),
                        worldMapId=map_id if usable else None,
                        position=dict(x=float(pos[0]), y=float(pos[1]), z=float(pos[2])) if usable else None)
        return dict(id=iid, name=it.get("name") or "item", photoUrl=photo, voiceLabel=voice, lastSeen=last)

    def _map(self, map_id, items, wearer):
        if not map_id:
            return None
        xs, zs = [], []
        if self.bounds:
            xs += self.bounds[:2]
            zs += self.bounds[2:]
        for it in items:
            p = (it.get("lastSeen") or {}).get("position")
            if p:
                xs.append(p["x"])
                zs.append(p["z"])
        if wearer:
            xs.append(wearer["position"]["x"])
            zs.append(wearer["position"]["z"])
        if not xs:
            return None
        min_x, max_x, min_z, max_z = min(xs) - MAP_PAD_M, max(xs) + MAP_PAD_M, min(zs) - MAP_PAD_M, max(zs) + MAP_PAD_M
        return dict(worldMapId=map_id, bounds=dict(minX=round(min_x, 3), maxX=round(max_x, 3), minZ=round(min_z, 3),
                                                   maxZ=round(max_z, 3)), walls=None)

    def _camera(self):
        if not self.frames:
            return None
        token, f = next(reversed(self.frames.items()))
        return dict(frameId=f["frame_id"], capturedAt=f["captured"], widthPx=f["w"], heightPx=f["h"],
                    imageUrl=f"/media/frames/{token}.jpg", boxes=f["boxes"])

    def _navigation(self, connected, mono):
        msg, wall, seen = self.guidance if self.guidance else (None, None, None)
        fresh = msg is not None and connected and mono - seen <= GUIDANCE_FRESH_S
        state = PHASES.get(msg.get("phase"), "idle") if fresh else ("idle" if connected else "unavailable")
        active = state in ("guiding", "within_reach", "found")
        dist = msg.get("distance_m") if fresh and active else None
        bearing = msg.get("rel_azimuth_deg") if fresh and active else None
        return dict(state=state, targetItemId=msg.get("item_id") if fresh and active else None,
                    distanceM=max(0.0, float(dist)) if isinstance(dist, (int, float)) else None,
                    bearingDeg=float(bearing) if isinstance(bearing, (int, float)) else None,
                    bearingReference="head" if isinstance(bearing, (int, float)) else None,
                    audioPattern=PATTERNS.get(state, "off"), spokenInstruction=None,
                    updatedAt=iso(wall) if wall else iso(self.started))
