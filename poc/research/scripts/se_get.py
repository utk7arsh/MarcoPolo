"""Fetch StackOverflow questions + answers (read-only) as text. Usage: se_get.py id1 id2 ..."""
import json, sys, urllib.parse, urllib.request, gzip, html, re

def fetch(url):
    raw = urllib.request.urlopen(url, timeout=30).read()
    try:
        raw = gzip.decompress(raw)
    except Exception:
        pass
    return json.loads(raw)

def txt(b):
    b = re.sub(r"<pre[^>]*><code>(.*?)</code></pre>", lambda m: "\n```\n" + m.group(1) + "\n```\n", b, flags=re.S)
    b = re.sub(r"<br\s*/?>|</p>|</li>", "\n", b)
    b = re.sub(r"<a [^>]*href=\"([^\"]+)\"[^>]*>(.*?)</a>", r"\2 <\1>", b, flags=re.S)
    return html.unescape(re.sub(r"<[^>]+>", "", b)).strip()

ids = ";".join(sys.argv[1:])
q = fetch(f"https://api.stackexchange.com/2.3/questions/{ids}?site=stackoverflow&filter=withbody")
a = fetch(f"https://api.stackexchange.com/2.3/questions/{ids}/answers?site=stackoverflow&filter=withbody&sort=votes&pagesize=50")
ans = {}
for it in a.get("items", []):
    ans.setdefault(it["question_id"], []).append(it)
for it in q.get("items", []):
    print("=" * 100)
    print(f"Q {it['question_id']} [{it.get('creation_date')}] score={it.get('score')}: {html.unescape(it['title'])}\n{it['link']}")
    print(txt(it.get("body", ""))[:3000])
    for an in ans.get(it["question_id"], []):
        print("-" * 40, f"ANSWER score={an.get('score')} accepted={an.get('is_accepted')} by {an.get('owner',{}).get('display_name')}")
        print(txt(an.get("body", ""))[:4000])
print("quota", a.get("quota_remaining"))
