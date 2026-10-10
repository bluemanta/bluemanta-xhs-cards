#!/usr/bin/env python3
"""Download images from a saved notion-get-file-download-urls result.
Usage: download_images.py URLS_JSON OUT_DIR/images   (signed URLs expire in ~5 min)"""
import json, re, sys, pathlib, urllib.request
d = json.loads(pathlib.Path(sys.argv[1]).read_text())
out = pathlib.Path(sys.argv[2]); out.mkdir(parents=True, exist_ok=True)
for f in d["files"]:
    name = re.search(r"[?&]name=([^&]+)", f["reference"]).group(1)
    urllib.request.urlretrieve(f["url"], out / name)
    print("ok", name)
for u in d.get("unresolved", []):
    print("UNRESOLVED", u)
