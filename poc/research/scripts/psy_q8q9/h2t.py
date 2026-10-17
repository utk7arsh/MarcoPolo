"""Convert an HTML file to plain text (read-only, stdlib only). Usage: h2t.py in.html out.txt"""
import html, re, sys
src = open(sys.argv[1], encoding="utf-8", errors="replace").read()
src = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", src)
src = re.sub(r"(?i)<br\s*/?>", "\n", src)
src = re.sub(r"(?i)</(p|div|h\d|li|tr|table|section|caption|figcaption|dd|dt)>", "\n", src)
src = re.sub(r"(?i)</t[dh]>", " | ", src)
txt = html.unescape(re.sub(r"<[^>]+>", " ", src))
txt = re.sub(r"[ \t\r\f\v]+", " ", txt)
txt = re.sub(r"\n\s*\n+", "\n\n", txt)
open(sys.argv[2], "w", encoding="utf-8").write(txt)
print(len(txt), "chars")
