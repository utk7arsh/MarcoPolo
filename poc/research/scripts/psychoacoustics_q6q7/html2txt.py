"""Convert an HTML file to plain text (stdlib only). Usage: python -I html2txt.py in.html out.txt"""
import sys
from html.parser import HTMLParser

class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.out = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        if tag in ("p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "tr", "table", "section"):
            self.out.append("\n")
        if tag in ("td", "th"):
            self.out.append(" | ")
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1
    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)

src, dst = sys.argv[1], sys.argv[2]
with open(src, encoding="utf-8", errors="replace") as f:
    h = f.read()
p = P()
p.feed(h)
import re
t = "".join(p.out)
t = re.sub(r"[ \t]+", " ", t)
t = re.sub(r"\n\s*\n+", "\n\n", t)
with open(dst, "w", encoding="utf-8") as f:
    f.write(t)
print(len(t))
