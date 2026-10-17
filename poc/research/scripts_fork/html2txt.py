import sys,re,html
t=sys.stdin.read()
t=re.sub(r'(?is)<(script|style|noscript)[^>]*>.*?</\1>',' ',t)
t=re.sub(r'(?i)<br\s*/?>|</p>|</li>|</h[1-6]>|</tr>|</div>','\n',t)
t=html.unescape(re.sub(r'<[^>]+>',' ',t))
t=re.sub(r'[ \t]+',' ',t)
t=re.sub(r'\n\s*\n+','\n',t)
print(t)
