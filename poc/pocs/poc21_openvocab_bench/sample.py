"""Sample small instances of everyday items from Open Images validation (human-drawn boxes)."""
import csv
import json
import random
import time
import urllib.request
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSVS = [(ROOT / "data/downloads/openimages_val_bbox/validation-annotations-bbox.csv", "validation"), (ROOT / "data/downloads/openimages_test_bbox/test-annotations-bbox.csv", "test")]
DL = ROOT / "data/downloads/openimages_val_imgs"
CLASSES = {"/m/0qjjc": "remote control", "/m/0jyfg": "glasses", "/m/017ftj": "sunglasses", "/m/050k8": "mobile phone",
           "/m/0gjkl": "wristwatch", "/m/02jvh9": "mug", "/m/04dr76w": "bottle", "/m/01b7fy": "headphones"}
PER_CLASS = 12

boxes = defaultdict(list)
split_of = {}
for path, split in CSVS:
    with open(path) as f:
        for r in csv.DictReader(f):
            if r["LabelName"] in CLASSES and r["IsDepiction"] != "1" and r["IsGroupOf"] != "1":
                b = [float(r["XMin"]), float(r["YMin"]), float(r["XMax"]), float(r["YMax"])]
                boxes[(r["ImageID"], r["LabelName"])].append(b)
                split_of[r["ImageID"]] = split
rng = random.Random(0)
items = []
for lab, name in CLASSES.items():
    cands = [(k, v) for k, v in boxes.items() if k[1] == lab and len(v) <= 3 and all(0.002 <= (b[2] - b[0]) * (b[3] - b[1]) <= 0.06 for b in v)]
    rng.shuffle(cands)
    items += [{"image_id": k[0], "class": name, "boxes": v, "split": split_of[k[0]]} for k, v in cands[:PER_CLASS]]
for it in items:
    d = DL / it["image_id"]; d.mkdir(parents=True, exist_ok=True)
    f = d / "image.jpg"
    if not f.exists():
        f.write_bytes(urllib.request.urlopen(f"https://s3.amazonaws.com/open-images-dataset/{it['split']}/{it['image_id']}.jpg", timeout=60).read())
        time.sleep(0.1)
    it["path"] = str(f.relative_to(ROOT))  # relative to poc/, so the file has no machine-specific paths
(ROOT / "pocs/poc21_openvocab_bench/items.json").write_text(json.dumps(items, indent=1))
print(len(items), "items;", {n: sum(1 for i in items if i["class"] == n) for n in CLASSES.values()})
