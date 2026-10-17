"""Query OpenAlex for titles; print OA/PDF locations (read-only)."""
import json, sys, urllib.parse, urllib.request, time

def q(title, n=3):
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode({"search": title, "per-page": n})
    req = urllib.request.Request(url, headers={"User-Agent": "mailto:research@example.com"})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    for w in d["results"]:
        print(f"* {w['display_name']} ({w['publication_year']}) {w.get('doi')} cites={w.get('cited_by_count')}")
        oa = w.get("open_access", {})
        print(f"    OA={oa.get('is_oa')} oa_url={oa.get('oa_url')}")
        seen = set()
        for loc in w.get("locations", []):
            for k in ("pdf_url", "landing_page_url"):
                u = loc.get(k)
                if u and u not in seen:
                    seen.add(u); print(f"    {k}: {u}")

if __name__ == "__main__":
    for t in sys.argv[1:]:
        print(f"### {t}")
        try:
            q(t)
        except Exception as e:
            print("ERROR", e)
        time.sleep(0.3)
