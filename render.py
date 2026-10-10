#!/usr/bin/env python3
"""Render a 小红书 note (note.md from extract.py) into 3:4 swipeable card PNGs (1728x2304).

Usage:
  render.py NOTE_DIR [--out NOTE_DIR/pages] [--cover-tag "AI进化论 01"] [--cover-sub "…"] [--accent "词1、词2"]
            [--title-lines "第一行|第二行"] [--no-cover] [--name 深蓝夜航] [--handle "@深蓝夜航 NightSail"]
--mode auto|section|flow (default auto: section mode when >=2 section titles; see README).
Cover fields: CLI flag > NOTE_DIR/cover.json (from the card's 「封面」 block via extract.py) > fallback
(title split after first ，？：; tag = 内容支柱; no subtitle). Avatar + cover logo: assets/logo.png.
NOTE_DIR must contain note.md (first line "# 标题") and images/ for any ![](images/x.png) lines.
Pagination is done by measuring real rendered height in headless Chrome, block by block;
paragraph pieces split by <br> are kept whole, a too-long piece is split only at sentence ends,
headings / lead-in lines ending in "：" (and short lead-in questions ending in "？" that open a
multi-line paragraph) are kept with the following block.
"""
import argparse, html, json, pathlib, re, sys
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
CHROME_CANDIDATES = ["/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"]
PARA_GAP, SEG_GAP, IMG_GAP = 34, 10, 34

def inline(md):
    t = html.escape(md, quote=False)
    return re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", t)

def sentences(md):
    parts = re.split(r"(?<=[。！？；])", md)
    return [inline(p) for p in parts if p]

def parse(note_dir):
    text = (note_dir / "note.md").read_text(encoding="utf-8").strip()
    lines = text.split("\n")
    assert lines[0].startswith("# "), "note.md must start with '# 标题'"
    title = lines[0][2:].strip()
    paras = [p.strip() for p in "\n".join(lines[1:]).split("\n\n") if p.strip()]
    blocks = []
    for pi, p in enumerate(paras):
        m = re.match(r"^!\[(.*?)\]\((.+?)\)$", p)
        if m:
            src = (note_dir / m.group(2)).resolve()
            if not src.exists():
                print("WARN missing image", src, file=sys.stderr); continue
            blocks.append({"cls": "img", "src": src.as_uri(), "html": f'<img src="{src.as_uri()}">', "gap": IMG_GAP,
                           "para": pi, "first": True})
            continue
        segs = [s.strip() for s in re.split(r"<br\s*/?>|\n", p) if s.strip()]
        if len(segs) == 1 and re.fullmatch(r"\*\*[^*]+\*\*", segs[0]):
            blocks.append({"cls": "punch", "html": inline(segs[0][2:-2]), "gap": PARA_GAP + 6, "para": pi, "first": True}); continue
        # section title: bold first line of a multi-line paragraph, or a line starting with 1️⃣ / "1." / "**1、"
        plain0 = re.sub(r"^\*\*|\*\*$", "", segs[0]).strip()
        is_sec = ((len(segs) > 1 and re.fullmatch(r"\*\*[^*]+\*\*", segs[0]) is not None)
                  or re.match(r"^(\*\*)?(\d\ufe0f?\u20e3|\d{1,2}[.、．]\s*\S)", segs[0]) is not None)
        for j, s in enumerate(segs):
            b = {"gap": PARA_GAP if j == 0 else SEG_GAP, "para": pi, "first": j == 0}
            if j == 0 and is_sec:
                b.update(sec=True, secTitle=html.escape(plain0))
            if j == 0 and len(segs) > 1 and re.fullmatch(r"\*\*[^*]+\*\*", s):
                b.update(cls="h", html=inline(s[2:-2]), kwn=True, gap=PARA_GAP + 10)
            elif s.startswith(("· ", "•")):
                body = s.lstrip("·• ").strip()
                b.update(cls="dot", html=inline(body), units=sentences(body))
            elif s[:1] in "❌✅👉📮⚠💡🔹▶" :
                b.update(cls="li", html=inline(s), units=sentences(s))
            else:
                b.update(cls="", html=inline(s), units=sentences(s))
            if s.endswith(("：", ":")) and b.get("cls") != "h":
                b["kwn"] = True
            # a short lead-in question opening a multi-line paragraph (e.g. 「为什么 AI 能…？」) stays with its answer
            if j == 0 and len(segs) > 1 and s.endswith(("？", "?")) and len(s) <= 40 and b.get("cls") != "h":
                b["kwn"] = True
            blocks.append(b)
    return title, blocks

def sections(blocks):
    """Split blocks into intro / one group per section / outro (summary + hook).
    A middle section runs until the next section title. The last section keeps its own paragraph plus
    following paragraphs that are images or ❌✅👉/· items; the first plain paragraph after it starts the outro."""
    starts = [i for i, b in enumerate(blocks) if b.get("sec")]
    if len(starts) < 1:
        return None, 0
    groups = []
    if starts[0] > 0:
        groups.append({"kind": "intro", "name": "导语", "label": "", "blocks": blocks[:starts[0]]})
    for k, s in enumerate(starts):
        if k + 1 < len(starts):
            end = starts[k + 1]
        else:
            end = len(blocks)
            for j in range(s + 1, len(blocks)):
                b = blocks[j]
                if b["para"] != blocks[s]["para"] and b.get("first") and b.get("cls", "") not in ("img", "li", "dot"):
                    end = j; break
        t = blocks[s]["secTitle"]
        groups.append({"kind": "section", "name": t, "label": "", "blocks": blocks[s:end]})  # no 「（续）」 labels (Chris 10-09)
        if k + 1 == len(starts) and end < len(blocks):
            groups.append({"kind": "outro", "name": "总结 + 钩子", "label": "", "blocks": blocks[end:]})
    return groups, len(starts)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("note_dir")
    ap.add_argument("--out")
    ap.add_argument("--cover-tag", default="")
    ap.add_argument("--cover-sub", default="")
    ap.add_argument("--title-lines", default="")
    ap.add_argument("--accent", default="", help="words in the cover title shown in gold, separated by 、")
    ap.add_argument("--mode", choices=["auto", "section", "flow"], default="auto",
                    help="section: each section on its own page(s); flow: continuous; auto: section if >=2 sections")
    ap.add_argument("--no-cover", action="store_true")
    ap.add_argument("--name", default="深蓝夜航")
    ap.add_argument("--handle", default="@深蓝夜航 NightSail")
    a = ap.parse_args()
    nd = pathlib.Path(a.note_dir).resolve()
    out = pathlib.Path(a.out).resolve() if a.out else nd / "pages"
    out.mkdir(parents=True, exist_ok=True)
    title, blocks = parse(nd)
    # cover fields: CLI flag > 「封面」 block on the card (cover.json from extract.py) > fallback
    cj = nd / "cover.json"
    cv = json.loads(cj.read_text(encoding="utf-8")) if cj.exists() else {}
    src = {}
    if a.title_lines:
        tl, src["title"] = a.title_lines.split("|"), "--title-lines"
    elif cv.get("title"):
        tl, src["title"] = [x.strip() for x in re.split(r"\s*[|｜]\s*|\s+/\s+", cv["title"]) if x.strip()], "封面 block"
    else:  # fallback: card title, break after the first comma / question / colon mark
        m = re.match(r"^(.+?[，,？?：:])(.+)$", title)
        tl, src["title"] = ([m.group(1), m.group(2)] if m else [title]), "note title (fallback)"
    tag = a.cover_tag or cv.get("tag") or cv.get("pillar", "")
    src["tag"] = "--cover-tag" if a.cover_tag else "封面 block" if cv.get("tag") else "内容支柱 property (fallback)" if tag else "none"
    sub = a.cover_sub or cv.get("sub", "")
    src["sub"] = "--cover-sub" if a.cover_sub else "封面 block" if cv.get("sub") else "none"
    accents = [w for w in re.split(r"[、,，|｜]\s*", a.accent or cv.get("accent", "")) if w.strip()]
    def mark(line):
        t = html.escape(line)
        for w in accents:
            t = t.replace(html.escape(w.strip()), f"<em>{html.escape(w.strip())}</em>", 1)
        return t
    groups, nsec = sections(blocks)
    mode = a.mode if a.mode != "auto" else ("section" if nsec >= 2 else "flow")
    if mode == "section" and nsec == 0:
        print("WARN --mode section but no sections found; using flow"); mode = "flow"
    print(f"mode: {mode} ({nsec} sections detected{', --mode ' + a.mode if a.mode != 'auto' else ', auto'})")
    print("cover:", {"title": tl, "tag": tag, "sub": sub, "accent": accents}, "| from:", src)
    logo = HERE / "assets" / "logo.png"
    data = {"titleLines": [mark(x) for x in tl], "blocks": blocks, "groups": groups if mode == "section" else None,
            "opts": {"cover": not a.no_cover, "coverTag": html.escape(tag), "coverSub": html.escape(sub),
                     "name": a.name, "handle": a.handle, "logo": logo.as_uri() if logo.exists() else "",
                     "noOrphan": mode == "section"}}
    exe = next((c for c in CHROME_CANDIDATES if pathlib.Path(c).exists()), None)
    # try the default typography first; if the last page is nearly empty, try slightly tighter
    # spacing and keep it only if it saves a page (never shrinks the font).
    variants = [{}, {"lh": 1.78, "gapScale": 0.8}, {"lh": 1.72, "gapScale": 0.65}] if mode == "flow" else [{}]
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path=exe, args=["--allow-file-access-from-files"])
        pg = br.new_page(viewport={"width": 1900, "height": 1300}, device_scale_factor=2)
        best = None
        for v in variants:
            d = json.loads(json.dumps(data)); d["opts"].update(v)
            pg.goto((HERE / "template.html").as_uri())
            pg.evaluate("document.fonts.ready")
            res = pg.evaluate("d => build(d)", d)
            res["variant"] = v
            if best is None or res["pages"] < best["pages"]:
                best = res
            if best is res and v and res["pages"] < first_pages:
                break
            if not v:
                first_pages = res["pages"]
                if res["lastFill"] >= 0.3 or res["pages"] <= 2:
                    break
        if best["variant"] != res["variant"]:  # re-render the chosen variant
            d = json.loads(json.dumps(data)); d["opts"].update(best["variant"])
            pg.goto((HERE / "template.html").as_uri()); pg.evaluate("document.fonts.ready")
            res = pg.evaluate("d => build(d)", d); res["variant"] = best["variant"]
        for old in out.glob("page-*.png"):
            old.unlink()
        paths = []
        for i, el in enumerate(pg.query_selector_all(".page"), 1):
            p = out / f"page-{i:02d}.png"
            el.screenshot(path=str(p))
            paths.append(str(p))
        br.close()
    print("variant:", res["variant"] or "default", f"last page fill {res['lastFill']:.0%}")
    (out / "manifest.json").write_text(json.dumps({"title": title, "mode": mode, "pages": paths, "outline": res.get("outline", []),
                                                   "warnings": res["warnings"]}, ensure_ascii=False, indent=1))
    for i, ol in enumerate(res.get("outline", []), 1):
        print(f"  p{i:02d} {ol}")
    print(f"title: {title}\npages: {res['pages']}")
    for w in res["warnings"]:
        print("WARN", w)
    print("\n".join(paths))

if __name__ == "__main__":
    main()
