"""Read-only Brave Search HTML helper: prints title, url, snippet."""
import html, re, sys, time, urllib.parse, urllib.request
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
def clean(s):
    s = re.sub(r"<!--.*?-->", "", s or "", flags=re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s))).strip()
def search(q):
    url = "https://search.brave.com/search?" + urllib.parse.urlencode({"q": q, "source": "web"})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    t = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    out = []
    parts = re.split(r'<div class="snippet[^"]*"[^>]*data-type="web"', t)[1:]
    for p in parts:
        a = re.search(r'<a href="(https?://[^"]+)"', p)
        ti = re.search(r'<div class="title[^"]*"[^>]*title="([^"]*)"', p) or re.search(r'<div class="title[^"]*"[^>]*>(.*?)</div>', p, flags=re.S)
        c = re.search(r'<div class="content[^"]*"[^>]*>(.*?)</div>', p, flags=re.S)
        if a:
            out.append((clean(ti.group(1)) if ti else "", html.unescape(a.group(1)), clean(c.group(1)) if c else ""))
    return out
for i, q in enumerate(sys.argv[1:]):
    if i:
        time.sleep(3)
    print("### " + q)
    try:
        for t, l, s in search(q)[:10]:
            print("- " + t + "\n  " + l + "\n  " + s[:400])
    except Exception as e:
        print("ERROR", e)
    print()
