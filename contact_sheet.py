#!/usr/bin/env python3
"""contact_sheet.py PAGES_DIR OUT.png [cols] - quick preview grid of page-*.png"""
import sys, pathlib
from PIL import Image
d = pathlib.Path(sys.argv[1]); out = sys.argv[2]; cols = int(sys.argv[3]) if len(sys.argv) > 3 else 4
ps = sorted(d.glob("page-*.png")); w, h, g = 432, 576, 12
rows = (len(ps) + cols - 1) // cols
sheet = Image.new("RGB", (cols * (w + g) + g, rows * (h + g) + g), (150, 150, 150))
for i, p in enumerate(ps):
    im = Image.open(p).convert("RGB").resize((w, h), Image.LANCZOS)
    sheet.paste(im, (g + (i % cols) * (w + g), g + (i // cols) * (h + g)))
sheet.save(out); print(out)
