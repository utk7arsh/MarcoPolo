"""The stub brain: speaks the full INTERFACES.md protocol with fake perception, so the phone app and the dashboard
can be built before the real pipeline exists. The geometry is already real: frames are turned upright from gravity,
fake items are projected into each frame as boxes, and the room map is built from the actual LiDAR depth.

Fake behaviour:
  items       keys (2 m behind where the user first stood, table height), mug (1.5 m to the right, counter),
              bottle (1 m ahead, floor), plus anything registered through /v1/items or Photon
  find        answers from those items
  guidance    when the phone starts guiding, hand_proximity counts down 1.0 -> 0 m over ~8 s, then touch + touch_end
  door        "this is the door" (query set_place) remembers where the user stands
  what is it  unknown the first time: a label_request (crop of the latest frame) goes to Photon; once Photon posts
              the label, the item becomes known and label_ready goes to the phone
Every method returns a list of (channel, message) for the app to send.
"""
import base64
import io
import os
import time
import uuid
from pathlib import Path

import numpy as np
from PIL import Image, ImageOps

from . import codec, geometry as G
from .registry import Registry

SPEEDUP = float(os.environ.get("STUB_SPEEDUP", "1"))
VOXEL = 0.05


def now_wall():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{int(time.time() * 1000) % 1000:03d}Z"


class StubBrain:
    def __init__(self, data_dir):
        self.data_dir = data_dir
        self.items = {}            # item_id -> dict(name, position, surface, last_seen_wall, state, label_text, label_audio_url)
        self.pose = {}             # session_id -> latest pose message (+ parsed T)
        self.trajectory = []       # (x, z, t)
        self.voxels = set()
        self.last_frame = None     # (upright PIL image, meta)
        self.touches = {}          # touch_id -> dict(crop_jpeg, position, item_id)
        self.audio = {}            # audio_id -> (bytes, ext)
        self.events = []
        self.guiding = set()       # item_ids with a running fake guidance sequence
        self._last_world = 0.0
        self.seeded = False
        self.door = None           # set by the "this is the door" query
        self.registry = Registry(Path(data_dir) / "registry" if data_dir else None)
        for rec in self.registry.items():                  # registrations and labels saved before a restart
            aid = rec.get("audio_id")
            self.items[rec["item_id"]] = dict(item_id=rec["item_id"], name=rec["name"], position=None, surface=None,
                                              last_seen_wall=None, state="registered", label_text=rec.get("label_text"),
                                              label_audio_url=f"/v1/audio/{aid}" if aid else None,
                                              source=rec.get("source", "app"))
        self.audio.update(self.registry.audio())

    # ---------------------------------------------------------------- helpers
    def _seed(self, T):
        """Place the fake items around where the user first stood."""
        if self.seeded:
            return
        p = T[:3, 3]
        h = np.radians(G.heading_deg(T))
        fwd, right = np.array([np.sin(h), 0, -np.cos(h)]), np.array([np.cos(h), 0, np.sin(h)])
        for name, off, y in (("keys", -2.0 * fwd, 0.75), ("mug", 1.5 * right, 0.92), ("bottle", 1.0 * fwd, 0.0)):
            pos = p + off
            pos[1] = y
            iid = "fake-" + name
            self.items[iid] = dict(item_id=iid, name=name, position=[round(float(v), 3) for v in pos],
                                   surface=G.surface_name(y), last_seen_wall=now_wall(), state="present",
                                   label_text=None, label_audio_url=None, source="seed")
        self.seeded = True

    def _event(self, kind, item, **extra):
        e = dict(type="event", kind=kind, item_id=item["item_id"], name=item["name"], position=item.get("position"),
                 surface=item.get("surface"), t_wall=now_wall(), **extra)
        self.events.append(e)
        return e

    def world(self):
        latest = next(iter(self.pose.values()), None)
        user = None
        if latest is not None:
            T = latest["T"]
            user = dict(position=[round(float(v), 3) for v in T[:3, 3]], heading_deg=round(G.heading_deg(T), 1))
        return dict(type="world", items=list(self.items.values()), user=user, trajectory=self.trajectory[-3000:])

    def snapshot(self):
        return self.world()

    def items_public(self):
        return list(self.items.values())

    def find_item(self, name):
        n = (name or "").strip().lower().rstrip("s")
        for it in self.items.values():
            if it["name"].lower().rstrip("s") == n or n in it["name"].lower():
                return it
        return None

    # ---------------------------------------------------------------- frames
    def on_frame(self, meta, jpeg: bytes, depth, conf):
        T = G.mat4(meta["camera_transform"])
        K = G.mat3(meta["intrinsics"])
        self._seed(T)
        fr = G.Frame(T, K, tuple(meta["image_resolution"]), depth, conf)
        k = G.upright_turns(T)
        im = Image.open(io.BytesIO(jpeg)).convert("RGB")
        jw, jh = im.size
        scale = float(meta.get("jpeg_scale", jw / fr.W))
        up = im.transpose([None, Image.Transpose.ROTATE_270, Image.Transpose.ROTATE_180, Image.Transpose.ROTATE_90][k]) if k else im  # k clockwise quarter turns
        self.last_frame = (up, meta)
        boxes = []
        for it in self.items.values():
            if it.get("position") is None:
                continue
            uv, z = fr.project(np.array([it["position"]]))
            if z[0] <= 0.1:
                continue
            u, v = uv[0]
            s = K[0, 0] * 0.10 / z[0]                               # a 10 cm object at that depth
            b = [(u - s / 2) * scale, (v - s / 2) * scale, (u + s / 2) * scale, (v + s / 2) * scale]
            if b[2] < 0 or b[3] < 0 or b[0] > jw or b[1] > jh:
                continue
            boxes.append(dict(item_id=it["item_id"], name=it["name"], box=[round(x, 1) for x in G.rotate_box(b, k, jw, jh)],
                              score=0.9, present=True))
        buf = io.BytesIO()
        up.save(buf, "JPEG", quality=70)
        out = [("dashboard", dict(type="frame", frame_id=meta["frame_id"], t_wall=meta.get("t_wall"), upright_turns=k,
                                  jpeg_b64=base64.b64encode(buf.getvalue()).decode(), boxes=boxes))]
        pts, uvs = fr.point_cloud(step=4)
        keys = np.floor(pts / VOXEL).astype(np.int64)
        new = []
        arr = np.asarray(im)
        for key, p, (u, v) in zip(map(tuple, keys), pts, uvs):
            if key in self.voxels:
                continue
            self.voxels.add(key)
            iu, iv = min(int(u * scale), jw - 1), min(int(v * scale), jh - 1)
            r, g, b = arr[iv, iu]
            new.append([round(float(p[0]), 3), round(float(p[1]), 3), round(float(p[2]), 3), int(r), int(g), int(b)])
        if new:
            out.append(("dashboard", dict(type="map_points", points=new)))
        out.append(("dashboard", self.world()))
        return out

    # ---------------------------------------------------------------- phone messages
    def on_phone(self, msg):
        t = msg.get("type")
        if t == "pose":
            T = G.mat4(msg["camera_transform"])
            self.pose[msg.get("session_id", "default")] = {**msg, "T": T}
            self._seed(T)
            self.trajectory.append([round(float(T[0, 3]), 3), round(float(T[2, 3]), 3), msg.get("t_device")])
            if time.time() - self._last_world >= 0.5:
                self._last_world = time.time()
                return [("dashboard", self.world())]
            return []
        if t == "hand":
            codec.decode_patches(msg["depth_patches_f16_b64"], "f16", size=int(msg.get("patch", 9)))
            codec.decode_patches(msg["conf_patches_u8_b64"], "u8", size=int(msg.get("patch", 9)))
            if len(msg.get("joints", [])) != codec.N_JOINTS:
                raise ValueError(f"hand message needs {codec.N_JOINTS} joints, got {len(msg.get('joints', []))}")
            return []
        if t == "guidance":
            return [("dashboard", {**msg, "type": "guidance"})]
        if t == "map":
            return [("dashboard", dict(type="timeline", events=self.events[-50:]))]
        if t == "query":
            return self._query(msg)
        raise ValueError(f"unknown message type {t!r}")

    def _query(self, msg):
        qid = msg.get("query_id")
        if msg.get("kind") == "find":
            it = self.find_item(msg.get("name"))
            if it is None or it.get("position") is None:
                return [("phone", dict(type="answer", query_id=qid, kind="find", found=False,
                                       reason="never_seen" if it is None else "not_where_last_seen"))]
            return [("phone", dict(type="answer", query_id=qid, kind="find", found=True, item_id=it["item_id"], name=it["name"],
                                   position=it["position"], surface=it["surface"], seen_ago_s=600, confidence=0.8))]
        if msg.get("kind") == "set_place":
            latest = next(iter(self.pose.values()), None)
            if (msg.get("name") or "").lower() != "door":
                raise ValueError("set_place supports name 'door' only")
            if latest is None:
                raise ValueError("no pose yet: send pose messages before set_place")
            self.door = [round(float(v), 3) for v in latest["T"][:3, 3]]
            return [("phone", dict(type="answer", query_id=qid, kind="set_place", name="door", ok=True))]
        if msg.get("kind") == "what_is_this":
            labelled = [tc for tc in self.touches.values() if tc.get("item_id")]
            if labelled:
                it = self.items[labelled[-1]["item_id"]]
                return [("phone", dict(type="answer", query_id=qid, kind="what_is_this", status="known", item_id=it["item_id"],
                                       name=it["name"], label_text=it.get("label_text"), label_audio_url=it.get("label_audio_url"),
                                       touch_id=labelled[-1]["touch_id"]))]
            if self.last_frame is None:
                return [("phone", dict(type="answer", query_id=qid, kind="what_is_this", status="no_touch"))]
            up, _ = self.last_frame
            w, h = up.size
            crop = up.crop((w // 4, h // 4, 3 * w // 4, 3 * h // 4))
            buf = io.BytesIO()
            crop.save(buf, "JPEG", quality=85)
            tid = uuid.uuid4().hex[:12]
            latest = next(iter(self.pose.values()), None)
            pos = None
            if latest is not None:
                T = latest["T"]
                pos = (T[:3, 3] - 0.5 * T[:3, 2]).round(3).tolist()   # half a metre in front of the chest
            self.touches[tid] = dict(touch_id=tid, crop_jpeg=buf.getvalue(), position=pos, item_id=None)
            return [("phone", dict(type="answer", query_id=qid, kind="what_is_this", status="unknown", touch_id=tid)),
                    ("photon", dict(type="label_request", touch_id=tid, crop_url=f"/v1/touch/{tid}/crop.jpg", question="What is this?"))]
        raise ValueError(f"unknown query kind {msg.get('kind')!r}")

    def guidance_sequence(self, item_id):
        """Fake touch for the guided item: (delay_s, channel, message) steps; the app plays them out."""
        it = self.items.get(item_id)
        if it is None or item_id in self.guiding:
            return []
        self.guiding.add(item_id)
        steps, dt = [], 1 / 15 / SPEEDUP
        n = int(8 * 15)
        for i in range(n + 1):
            steps.append((dt, "phone", dict(type="hand_proximity", item_id=item_id, distance_m=round(1.0 * (1 - i / n), 3))))
        tid = uuid.uuid4().hex[:12]
        steps.append((0.0, "phone", dict(type="touch", touch_id=tid, item_id=item_id, name=it["name"], position=it["position"],
                                         t_device=None)))
        steps.append((1.0 / SPEEDUP, "phone", dict(type="touch_end", touch_id=tid)))
        return steps

    def guidance_done(self, item_id):
        self.guiding.discard(item_id)

    # ---------------------------------------------------------------- registration and labels
    def register(self, name, photo: bytes, source="app"):
        im = ImageOps.exif_transpose(Image.open(io.BytesIO(photo))).convert("RGB")
        if min(im.size) < 64:
            return dict(item_id=None, quality="retake", reason=f"can't see the {name} clearly (photo too small)"), []
        iid = uuid.uuid4().hex[:12]
        self.items[iid] = dict(item_id=iid, name=name, position=None, surface=None, last_seen_wall=None, state="registered",
                               label_text=None, label_audio_url=None, source=source)
        buf = io.BytesIO()
        im.save(buf, "JPEG", quality=90)
        self.registry.save(iid, name=name, source=source, photo=buf.getvalue())
        return dict(item_id=iid, quality="ok", reason=""), [("dashboard", self.world())]

    def label(self, touch_id, item_id, name, text, audio: bytes | None, audio_ext: str, source="photon"):
        audio_url = aid = None
        ext = audio_ext or "m4a"
        if audio:
            aid = uuid.uuid4().hex[:12]
            self.audio[aid] = (audio, ext)
            audio_url = f"/v1/audio/{aid}"
        tc = self.touches.get(touch_id) if touch_id else None
        if touch_id and tc is None:
            raise KeyError(f"unknown touch_id {touch_id}")
        if item_id is None and tc is not None:
            item_id = tc.get("item_id")       # a lost HTTP response may retry the original touch
        if item_id and item_id not in self.items:
            raise KeyError(f"unknown item_id {item_id}")
        new_photo = None
        if item_id is None:
            item_id = uuid.uuid4().hex[:12]
            pos = tc["position"] if tc else None
            new_photo = tc["crop_jpeg"] if tc else None
            self.items[item_id] = dict(item_id=item_id, name=name, position=pos,
                                       surface=G.surface_name(pos[1]) if pos else None, last_seen_wall=now_wall(),
                                       state="present" if pos else "registered", label_text=None, label_audio_url=None,
                                       source=source)
        it = self.items[item_id]
        if audio_url and it.get("label_audio_url"):
            self.audio.pop(it["label_audio_url"].rsplit("/", 1)[-1], None)   # a new voice label replaces the old one
        it.update(name=name or it["name"], label_text=text or name, label_audio_url=audio_url or it.get("label_audio_url"))
        if tc is not None:
            tc["item_id"] = item_id
        if it.get("source") != "seed":
            self.registry.save(item_id, name=it["name"], source=it.get("source", "app"), label_text=it["label_text"],
                               photo=new_photo, audio_id=aid, audio=audio, audio_ext=ext)
        ev = self._event("label_added", it)
        return [("phone", dict(type="label_ready", item_id=item_id, name=it["name"], label_text=it["label_text"],
                               label_audio_url=it["label_audio_url"])),
                ("dashboard", dict(type="timeline", events=[ev])), ("dashboard", self.world())]

    def remove(self, source):
        """DELETE /v1/items?source=...: forget every item from that source. Returns ([{item_id, name}], messages)."""
        gone = [it for it in self.items.values() if it.get("source", "app") == source]
        ids = {it["item_id"] for it in gone}
        for it in gone:
            del self.items[it["item_id"]]
            if it.get("label_audio_url"):
                self.audio.pop(it["label_audio_url"].rsplit("/", 1)[-1], None)
        for tc in self.touches.values():
            if tc.get("item_id") in ids:
                tc["item_id"] = None
        self.guiding -= ids
        self.registry.remove(ids)
        return [dict(item_id=it["item_id"], name=it["name"]) for it in gone], [("dashboard", self.world())]
