"""What people taught the server survives a restart: items registered through POST /v1/items and labels from
POST /v1/labels (docs/INTERFACES.md §3.3, §5).

Both brains keep items in memory for speed and write them here whenever a registration or a label changes. On
start they reload them, and the real brain registers each saved photo with the detector again, so detection works
straight away. Positions are not saved: the 1 frame/s pipeline places an item again as soon as the camera sees it.

Layout under MARCO_DATA/registry/:
  items.json               [{item_id, name, source, photo_kind, label_text, audio_id, audio_ext, created_wall, updated_wall}]
  photos/<item_id>.jpg     the photo (or touch crop) the item was registered from
  templates/<item_id>.png  lossless pixels used by the real detector; independent of the display photo
  audio/<audio_id>.<ext>   the item's voice label, as uploaded
Every write is atomic (temp file + rename), so a crash mid-write leaves the previous state.
"""
import json
import os
import re
import tempfile
import time
from pathlib import Path

SAFE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SAFE_EXT = re.compile(r"^[A-Za-z0-9]{1,8}$")


def _now_wall():
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _atomic_write(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


class Registry:
    """A no-op when root is None (tests and tools that build a brain without a data folder)."""

    def __init__(self, root):
        self.root = Path(root) if root else None
        self.records: dict[str, dict] = {}
        if self.root is None:
            return
        (self.root / "photos").mkdir(parents=True, exist_ok=True)
        (self.root / "templates").mkdir(parents=True, exist_ok=True)
        (self.root / "audio").mkdir(parents=True, exist_ok=True)
        index = self.root / "items.json"
        if index.exists():
            self.records = {r["item_id"]: r for r in json.loads(index.read_text())}

    @property
    def enabled(self):
        return self.root is not None

    def items(self) -> list[dict]:
        return list(self.records.values())

    def photo(self, item_id) -> bytes | None:
        if self.root is None:
            return None
        p = self.root / "photos" / f"{item_id}.jpg"
        return p.read_bytes() if p.exists() else None

    def audio(self) -> dict[str, tuple[bytes, str]]:
        """Every saved voice label, as the brains keep them: audio_id -> (bytes, ext)."""
        out = {}
        for r in self.records.values():
            aid, ext = r.get("audio_id"), r.get("audio_ext")
            if aid and ext and self.root is not None:
                p = self.root / "audio" / f"{aid}.{ext}"
                if p.exists():
                    out[aid] = (p.read_bytes(), ext)
        return out

    def template(self, item_id) -> bytes | None:
        if self.root is None:
            return None
        p = self.root / "templates" / f"{item_id}.png"
        return p.read_bytes() if p.exists() else None

    def save(self, item_id, *, name, source, label_text=None, photo: bytes | None = None,
             audio_id=None, audio: bytes | None = None, audio_ext=None,
             template: bytes | None = None, photo_kind=None):
        """Creates or updates one item. A new voice label replaces (and deletes) the item's previous one."""
        if self.root is None:
            return
        if not SAFE.match(item_id):
            raise ValueError(f"unsafe item_id {item_id!r}")
        if photo_kind not in (None, "full", "crop"):
            raise ValueError(f"unknown photo_kind {photo_kind!r}")
        rec = self.records.get(item_id) or dict(item_id=item_id, created_wall=_now_wall(), audio_id=None, audio_ext=None)
        rec.update(name=name, source=source, label_text=label_text, updated_wall=_now_wall())
        if photo is not None:
            _atomic_write(self.root / "photos" / f"{item_id}.jpg", photo)
            if template is None:
                # A replacement reference must not keep the previous photo's detector pixels or inferred kind.
                (self.root / "templates" / f"{item_id}.png").unlink(missing_ok=True)
                if photo_kind is None:
                    rec.pop("photo_kind", None)
        if template is not None:
            _atomic_write(self.root / "templates" / f"{item_id}.png", template)
        if photo_kind is not None:
            rec["photo_kind"] = photo_kind
        if audio is not None and audio_id:
            if not (SAFE.match(audio_id) and SAFE_EXT.match(audio_ext or "")):
                raise ValueError(f"unsafe audio id or extension {audio_id!r}.{audio_ext!r}")
            _atomic_write(self.root / "audio" / f"{audio_id}.{audio_ext}", audio)
            self._drop_audio(rec)
            rec.update(audio_id=audio_id, audio_ext=audio_ext)
        self.records[item_id] = rec
        self._write_index()

    def remove(self, item_ids):
        if self.root is None:
            return
        for iid in item_ids:
            rec = self.records.pop(iid, None)
            if rec is None:
                continue
            (self.root / "photos" / f"{iid}.jpg").unlink(missing_ok=True)
            (self.root / "templates" / f"{iid}.png").unlink(missing_ok=True)
            self._drop_audio(rec)
        self._write_index()

    def _drop_audio(self, rec):
        if rec.get("audio_id") and rec.get("audio_ext"):
            (self.root / "audio" / f"{rec['audio_id']}.{rec['audio_ext']}").unlink(missing_ok=True)

    def _write_index(self):
        _atomic_write(self.root / "items.json", json.dumps(list(self.records.values()), indent=1).encode())
