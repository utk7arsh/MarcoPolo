"""Read-only literature search helper (OpenAlex, Semantic Scholar, arXiv, DBLP).

Usage:
  python3 -I litsearch.py [--src oa|s2|arxiv|dblp] [--n 10] [--abs 400] [--from 2016] "query one" "query two"
Prints title, year, venue, link and the start of the abstract (when the source has one).
Only performs HTTP GET requests against public, unauthenticated search APIs.
"""
import json
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

UA = "Mozilla/5.0 (lit-search helper; read-only)"


def get(url, tries=3):
    for i in range(tries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA})
            return urllib.request.urlopen(req, timeout=40).read().decode("utf-8", "replace")
        except Exception as e:  # noqa: BLE001
            if i == tries - 1:
                raise
            time.sleep(3 * (i + 1))


def oa_abstract(inv):
    if not inv:
        return ""
    pos = []
    for word, idxs in inv.items():
        for i in idxs:
            pos.append((i, word))
    pos.sort()
    return " ".join(w for _, w in pos)


def openalex(q, n, from_year, ta=False):
    params = {"per-page": str(n)}
    filt = []
    if ta:
        filt.append("title_and_abstract.search:" + q)
    else:
        params["search"] = q
    if from_year:
        filt.append(f"from_publication_date:{from_year}-01-01")
    if filt:
        params["filter"] = ",".join(filt)
    data = json.loads(get("https://api.openalex.org/works?" + urllib.parse.urlencode(params)))
    out = []
    for w in data.get("results", []):
        loc = (w.get("primary_location") or {})
        src = (loc.get("source") or {}).get("display_name") or ""
        link = w.get("doi") or loc.get("landing_page_url") or w.get("id")
        out.append((w.get("display_name"), w.get("publication_year"), src, link,
                    oa_abstract(w.get("abstract_inverted_index")), w.get("cited_by_count")))
    return out


def s2(q, n, from_year):
    params = {"query": q, "limit": str(n), "fields": "title,year,venue,abstract,url,externalIds,citationCount"}
    if from_year:
        params["year"] = f"{from_year}-"
    data = json.loads(get("https://api.semanticscholar.org/graph/v1/paper/search?" + urllib.parse.urlencode(params)))
    out = []
    for p in data.get("data", []):
        ext = p.get("externalIds") or {}
        link = ("https://doi.org/" + ext["DOI"]) if ext.get("DOI") else (
            ("https://arxiv.org/abs/" + ext["ArXiv"]) if ext.get("ArXiv") else p.get("url"))
        out.append((p.get("title"), p.get("year"), p.get("venue"), link, p.get("abstract") or "",
                    p.get("citationCount")))
    return out


def arxiv(q, n, from_year):
    params = {"search_query": "all:" + q, "max_results": str(n), "sortBy": "relevance"}
    t = get("http://export.arxiv.org/api/query?" + urllib.parse.urlencode(params))
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(t)
    out = []
    for e in root.findall("a:entry", ns):
        title = re.sub(r"\s+", " ", e.findtext("a:title", "", ns)).strip()
        year = e.findtext("a:published", "", ns)[:4]
        link = e.findtext("a:id", "", ns)
        summ = re.sub(r"\s+", " ", e.findtext("a:summary", "", ns)).strip()
        out.append((title, year, "arXiv", link, summ, None))
    return out


def dblp(q, n, from_year):
    params = {"q": q, "format": "json", "h": str(n)}
    data = json.loads(get("https://dblp.org/search/publ/api?" + urllib.parse.urlencode(params)))
    hits = ((data.get("result") or {}).get("hits") or {}).get("hit") or []
    out = []
    for h in hits:
        i = h.get("info", {})
        out.append((i.get("title"), i.get("year"), i.get("venue"), i.get("ee") or i.get("url"), "", None))
    return out


SRC = {"oa": openalex, "s2": s2, "arxiv": arxiv, "dblp": dblp,
       "ta": lambda q, n, fy: openalex(q, n, fy, ta=True)}


def full_abstracts(dois):
    """Print the full OpenAlex abstract (and S2 abstract as fallback) for each DOI."""
    for d in dois:
        d = d.replace("https://doi.org/", "")
        print(f"### DOI {d}")
        try:
            w = json.loads(get("https://api.openalex.org/works/doi:" + urllib.parse.quote(d)))
            loc = (w.get("primary_location") or {})
            src = (loc.get("source") or {}).get("display_name") or ""
            auth = ", ".join(a["author"]["display_name"] for a in w.get("authorships", [])[:8])
            print(f"TITLE: {w.get('display_name')}\nYEAR: {w.get('publication_year')}  VENUE: {src}\nAUTHORS: {auth}")
            ab = oa_abstract(w.get("abstract_inverted_index"))
            if not ab:
                p = json.loads(get("https://api.semanticscholar.org/graph/v1/paper/DOI:" + d + "?fields=abstract,venue,year"))
                ab = "[S2] " + (p.get("abstract") or "")
            print("ABSTRACT: " + ab)
        except Exception as e:  # noqa: BLE001
            print("ERROR", type(e).__name__, e)
        print()
        time.sleep(1.0)


if __name__ == "__main__":
    args = sys.argv[1:]
    if args and args[0] == "abs":
        full_abstracts(args[1:])
        sys.exit(0)
    src, n, abs_chars, from_year = "oa", 10, 400, 2016
    qs = []
    while args:
        a = args.pop(0)
        if a == "--src":
            src = args.pop(0)
        elif a == "--n":
            n = int(args.pop(0))
        elif a == "--abs":
            abs_chars = int(args.pop(0))
        elif a == "--from":
            v = args.pop(0)
            from_year = int(v) if v != "none" else None
        else:
            qs.append(a)
    for q in qs:
        print(f"### [{src}] {q}")
        try:
            for title, year, venue, link, ab, cites in SRC[src](q, n, from_year):
                c = f" cites={cites}" if cites is not None else ""
                print(f"- {title} ({year}; {venue}{c})\n  {link}")
                if ab and abs_chars:
                    print("  ABS: " + ab[:abs_chars])
        except Exception as e:  # noqa: BLE001
            print("ERROR", type(e).__name__, e)
        print()
        time.sleep(1.2)
