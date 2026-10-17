"""Read-only Bing HTML search helper."""
import html, re, sys, urllib.parse, urllib.request
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
def search(q):
    url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": q, "setlang": "en-US", "cc": "US"})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    t = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    out = []
    for m in re.finditer(r'<li class="b_algo"(.*?)</li>', t, flags=re.S):
        blk = m.group(1)
        a = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', blk, flags=re.S)
        if not a:
            continue
        p = re.search(r'<p[^>]*>(.*?)</p>', blk, flags=re.S) or re.search(r'class="b_caption"[^>]*>(.*?)</div>', blk, flags=re.S)
        clean = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()
        link = html.unescape(a.group(1))
        mu = re.search(r"[?&]u=a1([^&]+)", link)
        if mu:
            import base64
            b = mu.group(1); b += "=" * (-len(b) % 4)
            try:
                link = base64.urlsafe_b64decode(b).decode("utf-8", "replace")
            except Exception:
                pass
        out.append((clean(a.group(2)), link, clean(p.group(1) if p else "")))
    return out
for q in sys.argv[1:]:
    print("### " + q)
    try:
        for t, l, s in search(q)[:10]:
            print("- " + t + "\n  " + l + "\n  " + s[:300])
    except Exception as e:
        print("ERROR", e)
    print()
