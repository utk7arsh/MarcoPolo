"""Read-only web search fallback: tries Bing, then Mojeek, then Brave HTML. Usage: search2.py "q1" "q2" ..."""
import html, re, sys, time, urllib.parse, urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"
clean = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s)).strip()

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    return urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")

def bing(q):
    t = get("https://www.bing.com/search?" + urllib.parse.urlencode({"q": q, "count": "15", "setlang": "en"}))
    out = []
    for blk in re.findall(r'<li class="b_algo"(.*?)</li>', t, flags=re.S):
        m = re.search(r'<h2[^>]*>\s*<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', blk, flags=re.S)
        if not m:
            continue
        s = re.search(r'<p[^>]*>(.*?)</p>', blk, flags=re.S)
        link = html.unescape(m.group(1))
        mm = re.search(r"[?&]u=a1([^&]+)", link)
        if "bing.com/ck/a" in link and mm:
            import base64
            try:
                b = mm.group(1); b += "=" * (-len(b) % 4)
                link = base64.urlsafe_b64decode(b).decode("utf-8", "replace")
            except Exception:
                pass
        out.append((clean(m.group(2)), link, clean(s.group(1)) if s else ""))
    return out

def mojeek(q):
    t = get("https://www.mojeek.com/search?" + urllib.parse.urlencode({"q": q}))
    out = []
    for m in re.finditer(r'<a class="title" href="([^"]+)"[^>]*>(.*?)</a>.*?<p class="s">(.*?)</p>', t, flags=re.S):
        out.append((clean(m.group(2)), html.unescape(m.group(1)), clean(m.group(3))))
    return out

def brave(q):
    t = get("https://search.brave.com/search?" + urllib.parse.urlencode({"q": q, "source": "web"}))
    out = []
    for m in re.finditer(r'<a href="(https?://[^"]+)"[^>]*class="[^"]*\bl1\b[^"]*"[^>]*>.*?<div class="title[^"]*"[^>]*>(.*?)</div>', t, flags=re.S):
        out.append((clean(m.group(2)), html.unescape(m.group(1)), ""))
    return out

if __name__ == "__main__":
    for q in sys.argv[1:]:
        print(f"### {q}")
        res = []
        for name, fn in (("bing", bing), ("mojeek", mojeek), ("brave", brave)):
            try:
                res = fn(q)
            except Exception as e:
                print(f"  [{name} error {e}]")
                res = []
            if res:
                print(f"  [via {name}]")
                break
        for title, link, snip in res[:10]:
            print(f"- {title}\n  {link}\n  {snip[:300]}")
        print()
        time.sleep(1.5)
