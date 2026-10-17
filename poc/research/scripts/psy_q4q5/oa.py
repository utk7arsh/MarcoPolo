"""OpenAlex search helper (read-only). Usage: python -I oa.py "query" [n]"""
import json, sys, urllib.parse, urllib.request

def main():
    q = sys.argv[1]
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 6
    url = "https://api.openalex.org/works?" + urllib.parse.urlencode({"search": q, "per-page": n})
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 research-readonly"})
    d = json.load(urllib.request.urlopen(req, timeout=30))
    for w in d.get("results", []):
        oa = w.get("open_access", {}) or {}
        locs = w.get("locations", []) or []
        pdfs = [l.get("pdf_url") for l in locs if l.get("pdf_url")]
        lps = [l.get("landing_page_url") for l in locs if l.get("landing_page_url")]
        print(f"- {w.get('display_name')} ({w.get('publication_year')}) doi={w.get('doi')} oa={oa.get('oa_status')}")
        if oa.get("oa_url"): print(f"    oa_url: {oa.get('oa_url')}")
        for p in pdfs[:4]: print(f"    pdf: {p}")
        for p in lps[:3]: print(f"    landing: {p}")

if __name__ == "__main__":
    main()
