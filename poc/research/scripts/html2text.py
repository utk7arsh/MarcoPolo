"""Extract visible text from an HTML file (stdlib only). Usage: html2text.py in.html [out.txt]"""
import html, re, sys
from html.parser import HTMLParser

class P(HTMLParser):
    def __init__(self):
        super().__init__()
        self.out = []
        self.skip = 0
    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        if tag in ("p", "br", "li", "h1", "h2", "h3", "h4", "div", "section", "tr"):
            self.out.append("\n")
    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript") and self.skip:
            self.skip -= 1
    def handle_data(self, data):
        if not self.skip:
            self.out.append(data)

src = open(sys.argv[1], encoding="utf-8", errors="replace").read()
p = P()
p.feed(src)
txt = "".join(p.out)
txt = re.sub(r"[ \t]+", " ", txt)
txt = re.sub(r"\n\s*\n+", "\n", txt)
if len(sys.argv) > 2:
    open(sys.argv[2], "w").write(txt)
else:
    print(txt)
