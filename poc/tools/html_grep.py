"""Strip HTML to text and print snippets around a regex. Usage: html_grep.py PATTERN FILE..."""
import html
import re
import sys

pat = re.compile(sys.argv[1], re.I)
for f in sys.argv[2:]:
    t = open(f, errors="ignore").read()
    t = re.sub(r"<script.*?</script>|<style.*?</style>", "", t, flags=re.S)
    t = re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", t)))
    print("==", f)
    for m in list(pat.finditer(t))[:10]:
        print(" -", t[max(0, m.start() - 150): m.end() + 150])
