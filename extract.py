#!/usr/bin/env python3
"""Extract the final 小红书版 body from a saved notion-fetch result.

Usage: extract.py FETCH_TEXT_OR_JSON OUT_DIR [--section-prefix '## 小红书终稿']
Writes OUT_DIR/note.md (title + body, images as notion-file-block refs),
OUT_DIR/hashtags.txt, OUT_DIR/image_refs.json, OUT_DIR/cover.json,
OUT_DIR/daodu.txt (the 「**导读**」 block, never rendered) and OUT_DIR/post.txt
(导读 + hashtags = the 「小红书正文（发布时粘贴）」 text for the 切图 page).
Default: looks for '## 小红书终稿' (card layout from 2026-10-09: 状态条 / 待拍板 / 终稿 /
切图 / 子页面), and falls back to the older '## 小红书版…' heading. Picks the FIRST top-level
heading that matches, ignoring anything inside <details> (archived versions).
"""
import json, re, sys, pathlib

def load(path):
    raw = pathlib.Path(path).read_text(encoding="utf-8")
    try:
        d = json.loads(raw)
        if isinstance(d, dict) and "text" in d:
            return d["text"]
    except Exception:
        pass
    return raw

COVER_KEYS = {"主标题": "title", "封面主标题": "title", "副标题": "sub", "栏目": "tag", "栏目标签": "tag",
              "栏目标签+期数": "tag", "强调词": "accent", "强调": "accent"}

def main():
    src, out = sys.argv[1], pathlib.Path(sys.argv[2])
    prefixes = ["## 小红书终稿", "## 小红书版"]
    if "--section-prefix" in sys.argv:
        prefixes = [sys.argv[sys.argv.index("--section-prefix") + 1]]
    out.mkdir(parents=True, exist_ok=True)
    lines = load(src).splitlines()
    start = None
    for prefix in prefixes:
        for i, l in enumerate(lines):
            if l.startswith(prefix):  # top-level only (archived versions are tab-indented inside <details>)
                start = i
                break
        if start is not None:
            break
    if start is None:
        sys.exit(f"no section starting with any of {prefixes!r}")
    print(f"section: {lines[start].strip()}")
    sec = []
    for l in lines[start + 1:]:
        if re.match(r"^#{1,3} ", l) or l.startswith("<details") or l.strip() == "---":
            break
        sec.append(l)
    title, body, tags, refs = None, [], "", []
    stop_markers = ("**封面", "**配图", "封面 16:9")
    in_body = in_cover = in_daodu = False
    daodu = []
    cover = {}
    skipped = []
    for l in sec:
        s = l.strip()
        if not s:
            continue
        # optional cover block (before **正文**):  **封面**  then  "- 字段：值"  bullets
        if not in_body and re.fullmatch(r"\*\*封面\*\*[:：]?|\*\*封面[:：]\*\*", s):
            in_cover = True
            continue
        if in_cover:
            cm = re.match(r"^[-*]\s*(?:\*\*)?([^：:*]+?)(?:\*\*)?\s*[:：]\s*(.*)$", s)
            if cm:
                key = COVER_KEYS.get(cm.group(1).strip())
                if key:
                    cover[key] = cm.group(2).strip()
                continue
            in_cover = False
        m = re.match(r"^\*\*标题[^*]*\*\*[:：]\s*(.+)$", s)
        if m and title is None:
            title = m.group(1).strip()
            continue
        if s in ("**正文**", "**正文：**", "**正文**：", "**正文**:"):
            in_body = True
            in_daodu = False
            continue
        # optional 导读 block (after 封面, before 正文): the post caption, excluded from the cards
        if not in_body and re.fullmatch(r"\*\*导读\*\*[:：]?|\*\*导读[:：]\*\*", s):
            in_daodu = True
            continue
        if in_daodu:
            if s.startswith("**话题**"):
                in_daodu = False  # fall through to the 话题 handler
            else:
                daodu.append(s)
                continue
        if s.startswith("**话题**"):
            tags = re.sub(r"^\*\*话题\*\*[:：]\s*", "", s)
            continue
        if s.startswith(stop_markers):
            break
        im = re.match(r"^!\[(.*?)\]\((notion-file-block://[^)]+)\)$", s)
        if im:
            alt, ref = im.groups()
            name = re.search(r"[?&]name=([^&]+)", ref)
            name = name.group(1) if name else f"img{len(refs)}.png"
            is_cover = "封面" in alt
            if "旧版" in alt:  # superseded image blocks the API can't delete (e.g. 「墨绿旧版」): skip entirely
                skipped.append(alt)
                continue
            refs.append({"alt": alt, "ref": ref, "name": name, "cover": is_cover})
            if in_body and not is_cover:
                body.append(f"![{alt}](images/{name})")
            continue
        if in_body:
            body.append(s)
    if not title:
        sys.exit("title line (**标题…**：…) not found")
    full = load(src)
    pm = re.search(r'"内容支柱"\s*:\s*"([^"]+)"', full)  # card property, used only as a tag fallback
    if pm:
        cover.setdefault("pillar", pm.group(1))
    (out / "cover.json").write_text(json.dumps(cover, ensure_ascii=False, indent=1), encoding="utf-8")
    # trailing pure-hashtag lines in 导读 are not caption prose; use them as tags if **话题** is missing
    dtags = []
    while daodu and re.fullmatch(r"(#\S+\s*)+", daodu[-1]):
        dtags.insert(0, daodu.pop())
    if not tags and dtags:
        tags = " ".join(dtags)
    daodu_txt = "\n".join(daodu)
    (out / "daodu.txt").write_text(daodu_txt + ("\n" if daodu_txt else ""), encoding="utf-8")
    post = "\n\n".join(x for x in (daodu_txt, tags) if x)
    (out / "post.txt").write_text("小红书正文（发布时粘贴）\n\n" + post + "\n", encoding="utf-8")
    (out / "note.md").write_text(f"# {title}\n\n" + "\n\n".join(body) + "\n", encoding="utf-8")
    (out / "hashtags.txt").write_text(tags + "\n", encoding="utf-8")
    (out / "image_refs.json").write_text(json.dumps(refs, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"title: {title}\nparagraphs/images: {len(body)}\nimage refs: {len(refs)}\ncover block: {cover or '-'}\n导读: {len(daodu)} lines" + (" (none: post.txt = hashtags only)" if not daodu else ""))
    for alt in skipped:
        print("skipped (旧版):", alt)

if __name__ == "__main__":
    main()
