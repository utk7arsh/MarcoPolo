"""Read-only Bing HTML search; decodes result URLs. Usage: python -I bingsearch.py "q1" ["q2" ...]"""
import base64, html, re, sys, urllib.parse, urllib.request

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"

def dec(u):
    m = re.search(r"[?&]u=a1([^&]+)", u)
    if not m:
        return u
    s = m.group(1)
    s += "=" * (-len(s) % 4)
    try:
        return base64.urlsafe_b64decode(s).decode("utf-8", "replace")
    except Exception:
        return u

def search(q, n=10):
    url = "https://www.bing.com/search?" + urllib.parse.urlencode({"q": q, "count": "20"})
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9"})
    t = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    out = []
    for blk in re.findall(r'<li class="b_algo"(.*?)</li>', t, flags=re.S):
        m = re.search(r'<h2[^>]*>\s*<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', blk, flags=re.S)
        if not m:
            continue
        link = dec(html.unescape(m.group(1)))
        title = html.unescape(re.sub(r"<[^>]+>", "", m.group(2))).strip()
        sm = re.search(r'<p[^>]*>(.*?)</p>', blk, flags=re.S)
        snip = html.unescape(re.sub(r"<[^>]+>", "", sm.group(1))).strip() if sm else ""
        out.append((title, link, snip))
    return out[:n]

if __name__ == "__main__":
    for q in sys.argv[1:]:
        print(f"### {q}")
        try:
            for title, link, snip in search(q):
                print(f"- {title}\n  {link}\n  {snip[:300]}")
        except Exception as e:
            print("ERROR", e)
        print()
