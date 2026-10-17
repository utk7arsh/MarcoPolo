"""Pull only the needed frames out of ORBIT's 4 GB validation_224.zip with HTTP range requests.

figshare redirects to a signed S3 URL that expires after ~10 s, so every read re-resolves the
redirect. Reads are cached in 1 MB blocks (frames of one video sit next to each other in the zip).
Untrusted data: we only parse the zip structure and save JPEG bytes; nothing is executed.
"""
import io
import json
import random
import time
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
URL = "https://ndownloader.figshare.com/files/28368351"  # validation_224.zip
OUT = ROOT / "data" / "downloads" / "orbit_frames"
ANN = ROOT / "data" / "downloads" / "orbit_annotations" / "orbit_extra_annotations.zip"
BLOCK = 1 << 20

OBJECTS = [("P189", "keys"), ("P194", "door-keys"), ("P778", "keys"), ("P867", "front-door-keys"),
           ("P235", "apple-tv-remote"), ("P867", "remote-control"), ("P235", "wallet"), ("P778", "wallet"),
           ("P194", "sunglasses"), ("P778", "sunglasses"), ("P194", "apple-mobile-phone"), ("P778", "iphone-6"),
           ("P194", "wrist-watch"), ("P778", "apple-watch"), ("P235", "bose-wireless-headphones"),
           ("P867", "headphones"), ("P778", "cane"), ("P194", "ladies-purse")]


class RangeFile(io.RawIOBase):
    def __init__(self, url):
        self.url, self.pos, self.cache = url, 0, {}
        self.size = int(self._head())

    def _signed(self):
        req = urllib.request.Request(self.url, method="HEAD")
        opener = urllib.request.build_opener(NoRedirect())
        try:
            opener.open(req, timeout=30)
        except urllib.error.HTTPError as e:
            if e.code in (301, 302, 303, 307):
                return e.headers["Location"]
            raise
        raise RuntimeError("no redirect")

    def _head(self):
        r = urllib.request.urlopen(urllib.request.Request(self._signed(), headers={"Range": "bytes=0-0"}), timeout=60)
        return r.headers["Content-Range"].split("/")[-1]

    def _block(self, i):
        if i not in self.cache:
            for attempt in range(5):
                try:
                    lo, hi = i * BLOCK, min(self.size, (i + 1) * BLOCK) - 1
                    r = urllib.request.urlopen(urllib.request.Request(self._signed(), headers={"Range": f"bytes={lo}-{hi}"}), timeout=120)
                    self.cache[i] = r.read()
                    break
                except Exception:
                    time.sleep(1 + attempt)
        return self.cache[i]

    def readable(self): return True
    def seekable(self): return True
    def tell(self): return self.pos

    def seek(self, off, whence=0):
        self.pos = off if whence == 0 else (self.pos + off if whence == 1 else self.size + off)
        return self.pos

    def readinto(self, b):
        n = min(len(b), self.size - self.pos)
        if n <= 0:
            return 0
        out, p = bytearray(), self.pos
        while len(out) < n:
            blk = self._block(p // BLOCK)
            s = p % BLOCK
            take = blk[s:s + (n - len(out))]
            out += take
            p += len(take)
        b[:n] = out
        self.pos += n
        return n


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *a, **k):
        return None


def main(n_reg=6, n_test=10, seed=0):
    rng = random.Random(seed)
    ann = zipfile.ZipFile(ANN)
    z = zipfile.ZipFile(io.BufferedReader(RangeFile(URL), buffer_size=BLOCK))
    names = z.namelist()
    print(len(names), "members; e.g.", names[:3])
    index = []
    for user, obj in OBJECTS:
        if (OUT / f"{user}--{obj}" / "test.json").exists():
            index.append({"user": user, "object": obj, "dir": str(OUT / f"{user}--{obj}")}); continue
        folder = obj.replace("-", " ")  # the zip uses spaces where the annotation files use hyphens
        clean = sorted({n.rsplit("/", 1)[0] for n in names if f"/{user}/" in n and (f"/{obj}/clean/" in n or f"/{folder}/clean/" in n) and n.endswith(".jpg")})
        clutter_ann = [a for a in ann.namelist() if a.startswith("validation/") and a.split("/")[-1].startswith(f"{user}--{obj}--clutter--")]
        if not clean or not clutter_ann:
            print("skip", user, obj, len(clean), len(clutter_ann)); continue
        # registration: frames spread over the clean videos
        reg_frames = []
        for v in clean[:3]:
            fr = sorted(n for n in names if n.startswith(v + "/") and n.endswith(".jpg"))
            reg_frames += [fr[int(i)] for i in (len(fr) * (0.2 + 0.6 * k / max(1, n_reg // 3 - 1)) for k in range(n_reg // 3))]
        # test: clutter frames with the object present and a box
        a = json.loads(ann.read(clutter_ann[0]))
        good = [(k, v["object_bounding_box"]) for k, v in a.items() if v.get("object_bounding_box") and not v.get("object_not_present_issue")]
        rng.shuffle(good)
        tests = []
        for fname, box in good:
            cand = [n for n in names if n.endswith("/" + fname)]
            if cand:
                tests.append((cand[0], box))
            if len(tests) >= n_test:
                break
        d = OUT / f"{user}--{obj}"
        (d / "register").mkdir(parents=True, exist_ok=True)
        (d / "test").mkdir(parents=True, exist_ok=True)
        for i, n in enumerate(reg_frames):
            (d / "register" / f"{i:02d}.jpg").write_bytes(z.read(n))
        tl = []
        for i, (n, box) in enumerate(tests):
            (d / "test" / f"{i:02d}.jpg").write_bytes(z.read(n))
            tl.append({"file": f"test/{i:02d}.jpg", "box_xywh": [box["x"], box["y"], box["w"], box["h"]]})
        (d / "test.json").write_text(json.dumps(tl, indent=1))
        index.append({"user": user, "object": obj, "dir": str(d), "n_register": len(reg_frames), "n_test": len(tl)})
        print(f"{user} {obj}: {len(reg_frames)} registration frames, {len(tl)} clutter frames with boxes")
    (OUT / "index.json").write_text(json.dumps(index, indent=1))


if __name__ == "__main__":
    main()
