"""Records every message the server receives, byte for byte, so any walk becomes a replayable session.

Layout: <root>/<session_id>/
  frames.jsonl                 one line per frame: the meta JSON + received_wall
  frames/<frame_id>.jpg        the JPEG as sent
  frames/<frame_id>.depth      zlib(float16) as sent
  frames/<frame_id>.conf       zlib(uint8) as sent
  phone.jsonl                  every WebSocket message from the phone (pose, hand, guidance, query, map)
  out.jsonl                    every message the server sent back to the phone
"""
import json
import threading
import time
from pathlib import Path


class Recorder:
    def __init__(self, root):
        self.root = Path(root)
        self.lock = threading.Lock()

    def _dir(self, session_id):
        safe = "".join(ch for ch in str(session_id) if ch.isalnum() or ch in "-_")[:64] or "unknown"
        d = self.root / safe
        (d / "frames").mkdir(parents=True, exist_ok=True)
        return d

    def frame(self, meta: dict, image: bytes, depth: bytes, conf: bytes):
        d = self._dir(meta.get("session_id"))
        fid = int(meta["frame_id"])
        with self.lock:
            (d / "frames" / f"{fid:06d}.jpg").write_bytes(image)
            (d / "frames" / f"{fid:06d}.depth").write_bytes(depth)
            (d / "frames" / f"{fid:06d}.conf").write_bytes(conf)
            with open(d / "frames.jsonl", "a") as f:
                f.write(json.dumps({**meta, "received_wall": time.time()}) + "\n")

    def message(self, session_id, stream: str, msg: dict):
        d = self._dir(session_id)
        with self.lock, open(d / f"{stream}.jsonl", "a") as f:
            f.write(json.dumps({**msg, "received_wall": time.time()}) + "\n")
