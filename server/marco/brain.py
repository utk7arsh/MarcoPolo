"""The real brain: frames -> detections -> 3D world positions -> world model events; hand stream -> touches;
queries -> answers; Photon labels -> new items. Same methods as StubBrain, so app.py can use either.
"""
import base64
import io
import os
import time
import uuid

import numpy as np
from PIL import Image, ImageOps

from . import geometry as G
from .touch import TouchDetector
from .world.memory import World, now_wall
from .world.roommap import RoomMap

TRANSPOSE = [None, Image.Transpose.ROTATE_270, Image.Transpose.ROTATE_180, Image.Transpose.ROTATE_90]
MAX_PHOTO_PX = 2048
MAX_RANGE_M = float(os.environ.get("MAX_RANGE_M", "4.0"))   # LiDAR placement isn't reliable further away
RECENT_TOUCH_S = 3.0


def crop_around(up, fr, k, scale, uv, z, half_m=0.12):
    """Square crop of an upright frame around sensor pixel uv at depth z, about 2 * half_m across in the world (the
    size comes from LiDAR, so a near and a far item give the same physical crop)."""
    u, v = uv
    s = fr.K[0, 0] * half_m / max(float(z), 0.1)
    jw, jh = (up.height, up.width) if k % 2 else (up.width, up.height)
    b = G.rotate_box([(u - s) * scale, (v - s) * scale, (u + s) * scale, (v + s) * scale], k, jw, jh)
    b = [max(0, b[0]), max(0, b[1]), min(up.width, b[2]), min(up.height, b[3])]
    if b[2] - b[0] < 16 or b[3] - b[1] < 16:
        w, h = up.size
        b = [w // 4, h // 4, 3 * w // 4, 3 * h // 4]
    return up.crop(tuple(int(x) for x in b))


class RealBrain:
    def __init__(self, detector, data_dir=None):
        self.detector = detector
        self.world = World()
        self.roommap = RoomMap()
        self.touch = TouchDetector()
        self.touches = {}              # touch_id -> dict(touch_id, crop_jpeg, position, item_id, t)
        self.audio = {}                # audio_id -> (bytes, ext)
        self.last_frame = None         # (upright image, meta, Frame, k, jpeg_scale)
        self.guidance_target = None
        self.last_touch = None         # (touch_id, item_id, t)
        self._last_world = 0.0
        self.frames_seen = 0

    # ---------------------------------------------------------------- views used by app.py
    @property
    def events(self):
        return self.world.events

    def items_public(self):
        return [it.public() for it in self.world.items.values()]

    def snapshot(self):
        return self.world.snapshot()

    # ---------------------------------------------------------------- frames
    def on_frame(self, meta, jpeg: bytes, depth, conf):
        T, K = G.mat4(meta["camera_transform"]), G.mat3(meta["intrinsics"])
        res = tuple(meta["image_resolution"])
        fr = G.Frame(T, K, res, depth, conf)
        self.world.observe_camera(T)
        self.touch.set_camera(K, res)
        t = float(meta["t_device"])
        k = G.upright_turns(T)
        im = Image.open(io.BytesIO(jpeg)).convert("RGB")
        jw, jh = im.size
        scale = float(meta.get("jpeg_scale", jw / fr.W))
        up = im.transpose(TRANSPOSE[k]) if k else im
        self.last_frame = (up, meta, fr, k, scale)
        dets = self.detector.detect(up, fr=fr, k=k, jpeg_scale=scale)
        events, detected, boxes = [], set(), []
        for d in dets:
            boxes.append(dict(item_id=d["item_id"], name=d["name"], box=d["box"], score=d.get("score"), present=d["present"]))
            if not d["present"] or d["item_id"] not in self.world.items:
                continue
            sbox = G.detector_box_to_sensor(d["box"], k, jw, jh, scale)
            pos = self.place(sbox, fr)
            if pos is None:
                continue
            z = float(-((pos - T[:3, 3]) @ T[:3, :3])[2])
            size_m = max(sbox[2] - sbox[0], sbox[3] - sbox[1]) * max(z, 0.1) / K[0, 0]
            events += self.world.sighting(d["item_id"], pos, t, size_m=size_m, confidence=d.get("score") or 0.5)
            detected.add(d["item_id"])
        events += self.world.check_absence(fr, detected, t)
        self.frames_seen += 1
        if self.frames_seen % 5 == 1:
            self.world.set_floor(self.roommap.floor_y())
        buf = io.BytesIO()
        up.save(buf, "JPEG", quality=70)
        out = [("dashboard", dict(type="frame", frame_id=meta["frame_id"], t_wall=meta.get("t_wall"), upright_turns=k,
                                  jpeg_b64=base64.b64encode(buf.getvalue()).decode(), boxes=boxes))]
        new = self.roommap.add(fr, np.asarray(im), scale)
        if new:
            out.append(("dashboard", dict(type="map_points", points=new)))
        for e in events:
            out += [("phone", e), ("dashboard", dict(type="timeline", events=[e]))]
        out.append(("dashboard", self.world.snapshot()))
        return out

    def place(self, sbox, fr):
        """3D footprint of a detection box (sensor px), or None: no depth there, or beyond MAX_RANGE_M (a far
        false alarm would otherwise move the item)."""
        pos = G.locate_footprint(sbox, fr)
        if pos is None:
            return None
        z = float(-((pos - fr.T[:3, 3]) @ fr.T[:3, :3])[2])
        return pos if 0.1 < z <= MAX_RANGE_M else None

    # ---------------------------------------------------------------- phone stream
    def on_phone(self, msg):
        kind = msg.get("type")
        t = float(msg.get("t_device") or 0.0)
        if kind == "pose":
            T = G.mat4(msg["camera_transform"])
            out = [("phone", e) for e in self.world.user_pose(T, t)]
            out += [("dashboard", dict(type="timeline", events=[e[1] for e in out]))] if out else []
            if time.time() - self._last_world >= 0.5:
                self._last_world = time.time()
                out.append(("dashboard", self.world.snapshot()))
            return out
        if kind == "hand":
            shapes = {iid: (it.position, it.size_m) for iid, it in self.world.items.items()
                      if it.position is not None and it.state in ("present", "stale")}
            msgs, began = self.touch.update(msg, shapes, t, self.guidance_target)
            for m in msgs:
                if m["type"] == "touch":
                    it = self.world.items.get(m["item_id"])
                    m["name"] = it.name if it else None
                    self.world.touched(m["item_id"], t)
                    self.last_touch = (m["touch_id"], m["item_id"], t)
            return [("phone", m) for m in msgs]
        if kind == "guidance":
            phase = msg.get("phase")
            self.guidance_target = msg.get("item_id") if phase not in (None, "off", "touched") else None
            it = self.world.items.get(msg.get("item_id"))
            return [("dashboard", {**msg, "target_position": it.public()["position"] if it else None, "user": self.world.user_public()})]
        if kind == "map":
            if msg.get("event") == "new_map":
                self.world.new_map(msg.get("map_id"))
            elif msg.get("event") == "relocalized":
                self.world.relocalized(msg.get("map_id"))
            return [("dashboard", self.world.snapshot())]
        if kind == "query":
            return self._query(msg, t)
        raise ValueError(f"unknown message type {kind!r}")

    def _query(self, msg, t):
        qid, qk = msg.get("query_id"), msg.get("kind")
        if qk == "find":
            return [("phone", self.world.answer_find(qid, msg.get("name")))]
        if qk == "set_place" and (msg.get("name") or "").lower() == "door":
            if self.world.user_T is None:
                raise ValueError("no pose yet: send pose messages before set_place")
            self.world.set_door(self.world.user_T[:3, 3])
            return [("phone", dict(type="answer", query_id=qid, kind="set_place", name="door", ok=True))]
        if qk == "what_is_this":
            if self.last_touch and t - self.last_touch[2] <= RECENT_TOUCH_S and self.last_touch[1] in self.world.items:
                it = self.world.items[self.last_touch[1]]
                return [("phone", dict(type="answer", query_id=qid, kind="what_is_this", status="known", item_id=it.item_id,
                                       name=it.name, label_text=it.label_text, label_audio_url=it.label_audio_url,
                                       touch_id=self.last_touch[0]))]
            tip = self.touch.tip if self.touch.tip_t is not None and t - self.touch.tip_t <= RECENT_TOUCH_S else None
            if tip is None or self.last_frame is None:
                return [("phone", dict(type="answer", query_id=qid, kind="what_is_this", status="no_touch"))]
            crop = self._crop_around(tip)
            tid = uuid.uuid4().hex[:12]
            buf = io.BytesIO()
            crop.save(buf, "JPEG", quality=85)
            self.touches[tid] = dict(touch_id=tid, crop_jpeg=buf.getvalue(), position=[round(float(v), 3) for v in tip], item_id=None, t=t)
            return [("phone", dict(type="answer", query_id=qid, kind="what_is_this", status="unknown", touch_id=tid)),
                    ("photon", dict(type="label_request", touch_id=tid, crop_url=f"/v1/touch/{tid}/crop.jpg", question="What is this?"))]
        raise ValueError(f"unknown query kind {qk!r}")

    def _crop_around(self, p, half_m=0.12):
        """Square crop of the latest upright frame around world point p (about 24 cm across)."""
        up, meta, fr, k, scale = self.last_frame
        uv, z = fr.project(np.asarray(p)[None])
        return crop_around(up, fr, k, scale, uv[0], float(z[0]), half_m)

    # ---------------------------------------------------------------- stub-only hooks (no fake sequences here)
    def guidance_sequence(self, item_id):
        return []

    def guidance_done(self, item_id):
        pass

    # ---------------------------------------------------------------- registration and labels
    def register(self, name, photo: bytes):
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(photo))).convert("RGB")
        im.thumbnail((MAX_PHOTO_PX, MAX_PHOTO_PX))          # phone photos are 12-48 MP; OWLv2 looks at 960 px anyway
        it = self.world.add_item(name)
        res = self.detector.register(it.item_id, name, im)
        if res["quality"] != "ok":
            del self.world.items[it.item_id]
            return dict(item_id=None, **res), []
        return dict(item_id=it.item_id, **res), [("dashboard", self.world.snapshot())]

    def label(self, touch_id, item_id, name, text, audio: bytes | None, audio_ext: str):
        audio_url = None
        if audio:
            aid = uuid.uuid4().hex[:12]
            self.audio[aid] = (audio, audio_ext or "m4a")
            audio_url = f"/v1/audio/{aid}"
        tc = self.touches.get(touch_id) if touch_id else None
        if touch_id and tc is None:
            raise KeyError(f"unknown touch_id {touch_id}")
        if item_id and item_id not in self.world.items:
            raise KeyError(f"unknown item_id {item_id}")
        if item_id is None:
            it = self.world.add_item(name)
            crop = Image.open(io.BytesIO(tc["crop_jpeg"])).convert("RGB")
            self.detector.register(it.item_id, name, crop, gate=False)     # a person already said what it is
            if tc.get("position"):
                it.position, it.state = np.asarray(tc["position"], float), "present"
                it.surface, it.last_seen_wall = self.world.surface_for(it.position[1]), now_wall()
            item_id = it.item_id
        it = self.world.items[item_id]
        it.name = name or it.name
        it.label_text = text or name or it.label_text
        it.label_audio_url = audio_url or it.label_audio_url
        if tc is not None:
            tc["item_id"] = item_id
        ev = self.world._event("label_added", it)
        return [("phone", dict(type="label_ready", item_id=item_id, name=it.name, label_text=it.label_text,
                               label_audio_url=it.label_audio_url)),
                ("dashboard", dict(type="timeline", events=[ev])), ("dashboard", self.world.snapshot())]
