"""Read a recorded session (recorder.py layout) back as one time-ordered stream, for replay and offline runs."""
import json
from pathlib import Path


class Session:
    def __init__(self, path):
        self.dir = Path(path)
        if not (self.dir / "frames.jsonl").exists():
            raise FileNotFoundError(f"{self.dir} has no frames.jsonl: not a recorded session")
        self.frames = [json.loads(line) for line in (self.dir / "frames.jsonl").read_text().splitlines() if line.strip()]
        p = self.dir / "phone.jsonl"
        self.phone = [json.loads(line) for line in p.read_text().splitlines() if line.strip()] if p.exists() else []
        t = self.dir / "truth.json"
        self.truth = json.loads(t.read_text()) if t.exists() else None

    def frame_bytes(self, meta):
        base = self.dir / "frames" / f"{int(meta['frame_id']):06d}"
        return (base.with_suffix(".jpg").read_bytes(), base.with_suffix(".depth").read_bytes(),
                base.with_suffix(".conf").read_bytes())

    def stream(self):
        """('frame', meta) and ('phone', msg) in device-time order (frames first on ties)."""
        items = [(float(m["t_device"]), 0, "frame", m) for m in self.frames]
        items += [(float(m.get("t_device", 0.0) or 0.0), 1, "phone", m) for m in self.phone]
        for _, _, kind, m in sorted(items, key=lambda x: (x[0], x[1])):
            yield kind, m
