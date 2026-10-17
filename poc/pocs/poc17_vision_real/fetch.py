"""Download a small set of real photos from Wikimedia Commons (read-only; local testing)."""
import json
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DL = ROOT / "data" / "downloads" / "commons"
UA = {"User-Agent": "MarcoPoloPOC/0.1 (local research)"}
TITLES = [
    "File:Spice rack (6194773009).jpg", "File:Spice rack, 2014.jpg", "File:Spices on Spice Rack.JPG",
    "File:Spice rack ideas for the kitchen.jpg", "File:Spice rack with letter labels.jpg",
    "File:Kitchen Wall Spice Rack and Old Fire Extinguisher.jpg",
    "File:Nateglinide 60 mg bottle, Zydus, front view.jpg", "File:ClearRx prescription bottles - Flickr - bartsz.jpg",
    "File:Clonazepam Pills and Pill Bottle.jpg", "File:Canned food.jpg", "File:Tin cans.jpg",
    "File:GuLong canned food on the shelf.jpg",
]
SEARCH_HANDS = ["hand holding jar", "hand reaching shelf jar", "hands cooking kitchen spices", "hand holding pill bottle", "hand holding can"]


def api(params):
    url = "https://commons.wikimedia.org/w/api.php?" + urllib.parse.urlencode({**params, "format": "json"})
    return json.loads(urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=30).read())


def info(titles):
    d = api({"action": "query", "titles": "|".join(titles), "prop": "imageinfo", "iiprop": "url|mime", "iiurlwidth": 1600})
    return [(p["title"], p["imageinfo"][0]) for p in d["query"]["pages"].values() if p.get("imageinfo")]


if __name__ == "__main__":
    titles = list(TITLES)
    for q in SEARCH_HANDS:
        d = api({"action": "query", "list": "search", "srsearch": q, "srnamespace": 6, "srlimit": 4})
        titles += [r["title"] for r in d["query"]["search"] if re.search(r"\.(jpe?g|png)$", r["title"], re.I)]
    out = []
    for i in range(0, len(titles), 20):
        for title, ii in info(titles[i:i + 20]):
            slug = re.sub(r"[^A-Za-z0-9]+", "_", title[5:])[:60]
            d = DL / slug
            d.mkdir(parents=True, exist_ok=True)
            f = d / "image.jpg"
            if not f.exists():
                f.write_bytes(urllib.request.urlopen(urllib.request.Request(ii.get("thumburl") or ii["url"], headers=UA), timeout=60).read())
                time.sleep(0.3)
            out.append({"title": title, "path": str(f)})
    (DL / "index.json").write_text(json.dumps(out, indent=2))
    for o in out:
        print(o["title"][:90])
