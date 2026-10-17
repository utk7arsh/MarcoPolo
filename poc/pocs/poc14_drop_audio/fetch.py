"""Fetch a small labelled set of public Freesound *preview* clips (read-only, local testing only).
Each clip is saved in its own new directory under data/downloads/freesound/<label>_<id>/."""
import html
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DL = ROOT / "data" / "downloads" / "freesound"
QUERIES = {
    "drop": ["keys drop floor", "keys dropped on table", "dropping keys", "coin drop floor", "phone drop floor", "drop object wooden floor"],
    "other": ["footsteps indoor", "people talking room", "door close", "dishes kitchen", "television living room", "typing keyboard"],
}
PER_QUERY = 3
UA = {"User-Agent": "Mozilla/5.0"}


def search(q):
    url = "https://freesound.org/search/?" + urllib.parse.urlencode({"q": q})
    t = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read().decode("utf-8", "replace")
    out = []
    for m in re.finditer(r'data-mp3="(https://cdn\.freesound\.org/previews/[^"]+-lq\.mp3)"', t):
        mp3 = m.group(1)
        sid = re.search(r"/(\d+)_\d+-lq\.mp3", mp3).group(1)
        tm = re.search(r'href="/people/[^/]+/sounds/' + sid + r'/"[^>]*>([^<]+)<', t)
        title = html.unescape(tm.group(1)).strip() if tm else ""
        if sid not in [o["id"] for o in out]:
            out.append({"id": sid, "mp3": mp3, "title": title, "query": q})
    return out


if __name__ == "__main__":
    meta = []
    for label, qs in QUERIES.items():
        for q in qs:
            for r in search(q)[:PER_QUERY]:
                d = DL / f"{label}_{r['id']}"
                d.mkdir(parents=True, exist_ok=True)
                f = d / "clip.mp3"
                if not f.exists():
                    f.write_bytes(urllib.request.urlopen(urllib.request.Request(r["mp3"], headers=UA), timeout=60).read())
                r.update(label=label, path=str(f))
                meta.append(r)
                time.sleep(0.5)
    (DL / "index.json").write_text(json.dumps(meta, indent=2))
    for m in meta:
        print(m["label"], m["id"], "|", m["query"], "|", m["title"][:60])
