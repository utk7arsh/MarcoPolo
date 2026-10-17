"""Fetch Apple developer documentation JSON and print the readable text.

Usage: python appledoc.py avfaudio/avaudioenvironmentnode/islistenerheadtrackingenabled
"""
import json
import sys
import urllib.request

BASE = "https://developer.apple.com/tutorials/data/documentation/{}.json"


def inline_text(items, refs):
    out = []
    for it in items or []:
        t = it.get("type")
        if t == "text":
            out.append(it.get("text", ""))
        elif t == "codeVoice":
            out.append("`" + it.get("code", "") + "`")
        elif t in ("emphasis", "strong"):
            out.append(inline_text(it.get("inlineContent"), refs))
        elif t == "reference":
            r = refs.get(it.get("identifier"), {})
            out.append("`" + (r.get("title") or it.get("identifier", "").split("/")[-1]) + "`")
        elif t == "link":
            out.append(it.get("title", "") + " <" + it.get("destination", "") + ">")
        else:
            out.append(inline_text(it.get("inlineContent"), refs))
    return "".join(out)


def blocks_text(blocks, refs, depth=0):
    lines = []
    for b in blocks or []:
        t = b.get("type")
        if t == "heading":
            lines.append("## " + b.get("text", ""))
        elif t == "paragraph":
            lines.append(inline_text(b.get("inlineContent"), refs))
        elif t == "aside":
            lines.append("> [" + b.get("style", "note") + "] " + " ".join(blocks_text(b.get("content"), refs, depth + 1)))
        elif t in ("unorderedList", "orderedList"):
            for item in b.get("items", []):
                lines.append("  - " + " ".join(blocks_text(item.get("content"), refs, depth + 1)))
        elif t == "codeListing":
            lines.append("```\n" + "\n".join(b.get("code", [])) + "\n```")
        elif t == "termList":
            for item in b.get("items", []):
                lines.append("  * " + inline_text(item.get("term", {}).get("inlineContent"), refs) + ": " + " ".join(blocks_text(item.get("definition", {}).get("content"), refs)))
        elif t == "table":
            for row in b.get("rows", []):
                lines.append(" | ".join(" ".join(blocks_text(cell, refs)) for cell in row))
        else:
            if "content" in b:
                lines.extend(blocks_text(b.get("content"), refs, depth + 1))
    return lines


def main(path):
    with urllib.request.urlopen(BASE.format(path.lower()), timeout=30) as r:
        d = json.load(r)
    refs = d.get("references", {})
    md = d.get("metadata", {})
    print("# " + md.get("title", path))
    plats = md.get("platforms", [])
    if plats:
        print("Availability: " + ", ".join(f"{p.get('name')} {p.get('introducedAt','?')}" + (" (deprecated " + p.get('deprecatedAt') + ")" if p.get('deprecatedAt') else "") + (" beta" if p.get('beta') else "") for p in plats))
    for sec in d.get("primaryContentSections", []):
        if sec.get("kind") == "declarations":
            for dec in sec.get("declarations", []):
                print("Declaration: " + "".join(tok.get("text", "") for tok in dec.get("tokens", [])))
    print("Abstract: " + inline_text(d.get("abstract"), refs))
    for sec in d.get("primaryContentSections", []):
        if sec.get("kind") == "content":
            print("\n".join(blocks_text(sec.get("content"), refs)))
        if sec.get("kind") == "properties":
            print("Properties section present")
    for ts in d.get("topicSections", []):
        print("Topic: " + ts.get("title", "") + " -> " + ", ".join(refs.get(i, {}).get("title", i.split("/")[-1]) for i in ts.get("identifiers", [])))


if __name__ == "__main__":
    for p in sys.argv[1:]:
        try:
            main(p)
        except Exception as e:
            print(f"ERROR {p}: {e}")
        print("\n" + "=" * 80 + "\n")
