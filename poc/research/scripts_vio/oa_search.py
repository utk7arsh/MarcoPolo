"""OpenAlex search helper (read-only). Usage: python -I oa_search.py "query" ["query2" ...]"""
import json
import sys
import urllib.parse
import urllib.request

for q in sys.argv[1:]:
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode({"search": q, "per-page": "8", "select": "id,title,publication_year,doi,open_access,cited_by_count"})
    try:
        d = json.load(urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "research-script"}), timeout=30))
    except Exception as e:
        print("ERROR", q, e)
        continue
    print("###", q)
    for r in d.get("results", []):
        print("-", r.get("publication_year"), r.get("title"), "|", r.get("doi"), "| oa:", (r.get("open_access") or {}).get("oa_url"), "| cites:", r.get("cited_by_count"))
    print()
