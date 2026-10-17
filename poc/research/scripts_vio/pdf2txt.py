"""Extract text from a PDF with pypdf. Usage: python -I pdf2txt.py in.pdf out.txt"""
import sys
from pypdf import PdfReader

r = PdfReader(sys.argv[1])
with open(sys.argv[2], "w") as f:
    for i, p in enumerate(r.pages):
        try:
            t = p.extract_text() or ""
        except Exception as e:
            t = f"[extract error {e}]"
        f.write(f"\n\n===== PAGE {i+1} =====\n")
        f.write(t)
print(len(r.pages), "pages")
