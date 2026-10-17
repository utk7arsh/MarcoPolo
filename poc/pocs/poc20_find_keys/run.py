"""POC 20: Can a model actually find "my keys" in a camera frame, and from how far?

Open-vocabulary detector YOLO-World v2 (text prompt "keys"; exportable to Core ML / runnable through
Zetic Melange on iPhone) on real photos of keys (Wikimedia Commons). Each photo is shrunk step by step
to simulate the keys being farther away, and we record whether the keys are still found.

Key size in pixels -> distance from the chest camera (ARKit 1920x1440, fx = 1600, keys ~8 cm):
  distance = 0.08 m * 1600 / pixels_in_full_frame
A detector that sees the full 1920 px frame squeezed to 640 px loses 3x resolution; running it on
3x3 tiles of the frame keeps full resolution (9 runs per frame).
"""
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
IMGS = sorted((ROOT / "data" / "downloads" / "commons_keys").glob("*/image.jpg"))
OUT = ROOT / "data" / "tmp" / "poc20"
OUT.mkdir(parents=True, exist_ok=True)
PROMPTS = ["keys", "car key", "keychain"]


def main():
    from ultralytics import YOLOWorld
    model = YOLOWorld("yolov8s-worldv2.pt")
    model.set_classes(PROMPTS)
    rows = []
    for p in IMGS:
        im = Image.open(p).convert("RGB")
        full = model.predict(np.array(im), imgsz=640, conf=0.05, verbose=False)[0]
        if len(full.boxes) == 0:
            rows.append(dict(image=p.parent.name, found_full=False))
            print(f"{p.parent.name:52} no keys found at full size")
            continue
        b = full.boxes
        k = int(np.argmax(b.conf.cpu().numpy()))
        x0, y0, x1, y1 = b.xyxy[k].cpu().numpy()
        conf = float(b.conf[k])
        # size of the keys as the detector saw them (detector input is 640 px on the long side)
        scale_in = 640 / max(im.size)
        key_px_in = max(x1 - x0, y1 - y0) * scale_in
        d = ImageDraw.Draw(im); d.rectangle([x0, y0, x1, y1], outline=(255, 40, 120), width=6)
        im.save(OUT / f"{p.parent.name}.jpg", quality=85)
        # shrink until lost
        sizes = []
        for s in (1.0, 0.7, 0.5, 0.35, 0.25, 0.18, 0.12, 0.08):
            small = Image.open(p).convert("RGB")
            w, h = small.size
            small = small.resize((max(16, int(w * s)), max(16, int(h * s))))
            canvas = Image.new("RGB", (w, h), (128, 128, 128)) if s < 1 else None
            # keep the detector input size fixed: paste the shrunken photo into a grey frame of the
            # original size, so the keys really are fewer pixels in the 640 px detector input
            if canvas is not None:
                canvas.paste(small, ((w - small.size[0]) // 2, (h - small.size[1]) // 2)); small = canvas
            r = model.predict(np.array(small), imgsz=640, conf=0.05, verbose=False)[0]
            ok = len(r.boxes) > 0 and float(r.boxes.conf.max()) >= 0.15
            sizes.append((round(float(key_px_in) * s, 1), bool(ok), round(float(r.boxes.conf.max()), 2) if len(r.boxes) else 0.0))
        smallest_found = min([px for px, ok, _ in sizes if ok], default=None)
        rows.append(dict(image=p.parent.name, found_full=True, conf_full=round(conf, 2), key_px_in_detector=round(float(key_px_in), 1),
                         ladder=sizes, smallest_px_found=smallest_found))
        print(f"{p.parent.name:52} conf {conf:.2f} keys {key_px_in:5.1f} px in 640 input -> still found down to {smallest_found} px; ladder {sizes}")
    (ROOT / "reports" / "poc20_find_keys.json").write_text(json.dumps(rows, indent=2))
    found = [r for r in rows if r.get("found_full")]
    mins = [r["smallest_px_found"] for r in found if r["smallest_px_found"]]
    if mins:
        px = float(np.median(mins))
        print(f"\nfound at full size in {len(found)}/{len(rows)} photos; median smallest size still found: {px:.0f} px (in the detector input)")
        for label, factor in (("full frame squeezed to 640 px", 640 / 1920), ("3x3 tiles (full resolution)", 1.0)):
            dist = 0.08 * 1600 * factor / px
            print(f"  {label}: keys found out to ~{dist:.1f} m from the chest camera")


if __name__ == "__main__":
    main()
