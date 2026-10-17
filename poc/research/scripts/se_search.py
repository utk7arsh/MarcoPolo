"""StackExchange read-only search. Usage: se_search.py TAG "query" [more queries]"""
import json, sys, time, urllib.parse, urllib.request, gzip, html
tag = sys.argv[1]
for q in sys.argv[2:]:
    url = "https://api.stackexchange.com/2.3/search/advanced?" + urllib.parse.urlencode(
        {"order": "desc", "sort": "relevance", "q": q, "tagged": tag, "site": "stackoverflow", "pagesize": 15})
    raw = urllib.request.urlopen(url, timeout=30).read()
    try:
        raw = gzip.decompress(raw)
    except Exception:
        pass
    d = json.loads(raw)
    print(f"### [{tag}] {q}  (quota {d.get('quota_remaining')})")
    for it in d.get("items", []):
        print(f"- {it['question_id']} s={it.get('score')} a={it.get('answer_count')} {html.unescape(it['title'])[:110]}\n  {it['link']}")
    time.sleep(1)
