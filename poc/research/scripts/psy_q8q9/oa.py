"""Read-only OpenAlex search: prints year, title, doi, OA urls."""
import json, sys, urllib.parse, urllib.request

def search(q, n=6):
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode({"search": q, "per-page": n})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (research-readonly)"})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    for w in d.get("results", []):
        oa = w.get("open_access", {}) or {}
        print(f"- {w.get('publication_year')} | {w.get('display_name')} | {w.get('doi')} | cited={w.get('cited_by_count')} | oa={oa.get('oa_url')}")
        seen = set()
        for loc in (w.get("locations") or [])[:8]:
            for k in ("pdf_url", "landing_page_url"):
                u = loc.get(k)
                if u and u not in seen and "doi.org" not in u:
                    seen.add(u)
                    print(f"    {k}: {u}")

if __name__ == "__main__":
    for q in sys.argv[1:]:
        print(f"### {q}")
        try:
            search(q)
        except Exception as e:
            print("ERROR", e)
        print()
