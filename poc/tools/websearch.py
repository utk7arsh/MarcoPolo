"""Minimal web search via DuckDuckGo's HTML endpoint (read-only)."""
import html
import re
import sys
import urllib.parse
import urllib.request


def search(q, n=10):
    url = "https://html.duckduckgo.com/html/?" + urllib.parse.urlencode({"q": q})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Safari/605.1.15"})
    t = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "replace")
    results = re.findall(r'<a rel="nofollow" class="result__a" href="([^"]+)">(.*?)</a>.*?<a class="result__snippet"[^>]*>(.*?)</a>', t, flags=re.S)
    out = []
    for href, title, snip in results[:n]:
        m = re.search(r"uddg=([^&]+)", href)
        link = urllib.parse.unquote(m.group(1)) if m else href
        clean = lambda s: html.unescape(re.sub(r"<[^>]+>", "", s)).strip()
        out.append((clean(title), link, clean(snip)))
    return out


if __name__ == "__main__":
    for q in sys.argv[1:]:
        print(f"### {q}")
        try:
            for title, link, snip in search(q):
                print(f"- {title}\n  {link}\n  {snip[:300]}")
        except Exception as e:
            print("ERROR", e)
        print()
