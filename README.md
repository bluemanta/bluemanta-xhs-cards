# 小红书长文切图 (xhs_cards)

Turns the final 「小红书终稿」 (older cards: 「小红书版」) of a ContentHub topic card into 3:4 swipeable card PNGs (1728×2304),
white cards in the 深蓝夜航 style: header (round logo avatar `assets/logo.png`, name, verified tick, ···), 34px body,
line height 1.85, page number on each card. Colours come from the logo: navy #082541, gold #EFC173 (secondary:
footer bar, heading bar, cover accents), cream #F6F3EB. Page 1 is a text cover on logo navy with the logo
bottom-right (2026-10-09 Chris: use it instead of the Muse cover for now).

Look and feel modelled on fxyadela/write-then-publish (same 864×1152 logical canvas ×2, 34px/1.85 body,
42–56px side padding, header ~150px). No code from that repo is used (its license is personal non-commercial).

## Files
- `extract.py` — saved notion-fetch result → `note.md` (title + body), `hashtags.txt`, `image_refs.json`,
  `cover.json`, `daodu.txt` and `post.txt` (see 「导读」 below).
  Looks for the top-level `## 小红书终稿` heading first (card layout since 2026-10-09: 状态条 → 待 Chris 拍板 →
  小红书终稿 → 切图 → 子页面), then falls back to the old `## 小红书版…` heading (first match wins; archived
  versions inside `<details>` are ignored). Override with `--section-prefix '## …'`. The section ends at the
  next `#`–`###` heading, so keep the 终稿 section flat (no sub-headings inside it). Takes `**标题…**：…` as
  title, everything after `**正文**` until `**话题**` / `**封面…**`.
  Images whose alt text contains 「封面」 are skipped (text cover is generated instead); images whose alt text
  contains 「旧版」 (e.g. undeletable 「墨绿旧版」 blocks) are dropped entirely and listed as `skipped (旧版)`.
- `download_images.py` — saved notion-get-file-download-urls result → `images/` (URLs expire in ~5 min).
- `render.py` + `template.html` — note dir → `pages/page-NN.png` + `manifest.json`.
- `contact_sheet.py` — preview grid of all pages.
- `.venv/` — Python venv with playwright; uses system `/usr/bin/google-chrome` (no browser download needed).

## Setup
Python 3 (`#!/usr/bin/env python3`). `extract.py` and `download_images.py` use the standard library only (`json`, `re`, `pathlib`, `urllib`). Third-party packages, from the imports in the other scripts (`requirements.txt`):

- **Playwright** (`from playwright.sync_api import sync_playwright` in `render.py`) — headless Chrome. `render.py` launches the first binary that exists among `/usr/bin/google-chrome`, `/usr/bin/chromium`, and `/usr/bin/chromium-browser`. If none of those paths exist, Playwright uses the Chromium installed by `playwright install chromium`.
- **Pillow** (`from PIL import Image` in `contact_sheet.py`) — preview contact sheet.

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
# skip when a system Chrome/Chromium is already at one of the paths above
.venv/bin/playwright install chromium
```

## Run for any card (agent steps)
1. `notion-fetch` the card id → save the JSON/text result to `<NOTE_DIR>/fetch.json`.
2. `.venv/bin/python extract.py <NOTE_DIR>/fetch.json <NOTE_DIR>` → check `note.md`.
3. For the refs in `image_refs.json` (non-cover), call `notion-get-file-download-urls`, save the result to
   `<NOTE_DIR>/urls.json`, then `.venv/bin/python download_images.py <NOTE_DIR>/urls.json <NOTE_DIR>/images`
   right away. (If a note has no images, skip.)
4. Render:
   ```
   cd /path/to/this/repo
   .venv/bin/python render.py <NOTE_DIR>        # cover fields come from the card's 「封面」 block (see below)
   python3 contact_sheet.py <NOTE_DIR>/pages <NOTE_DIR>/contact.png 6   # look at it
   ```
   Options (override the 封面 block): `--title-lines "行1|行2"`, `--cover-tag`, `--cover-sub`, `--accent "词1、词2"`; `--no-cover`,
   `--name`, `--handle`, `--out`.
5. Upload to Notion: per PNG, `notion-create-file-upload {filename}` → `curl -X POST <upload_url>
   -H "authorization: <header from response>" -F "file=@page-NN.png;type=image/png"` → collect
   `file-upload://…` ids → `notion-create-pages` under the card with `<image src="file-upload://…"></image>`
   lines in order (with a line like 「共 N 张｜按章节切｜藏蓝版｜MM-DD」), then a `## 小红书正文（发布时粘贴）`
   section with the contents of `post.txt` (导读 + hashtags, i.e. what Chris pastes into Xiaohongshu), not the
   card body. Update the main card's 切图 line to the new count. Never touch the card's 状态 or other content.
   Old image blocks can't be deleted or moved by the API: relabel them under a 「旧版…（可删）」 heading.
   Each re-cut creates a fresh 「小红书切图」 subpage under the card and moves the old 切图 page under 「历史版本」
   (notion-move-pages, rename it 「旧版切图 MM-DD …」); then point the card's 切图 line at the new page.

## Markdown the renderer understands (note.md)
- `# 标题` first line; paragraphs separated by blank lines; `<br>` = line break inside a paragraph.
- `**…**` inline bold (navy). A paragraph that is entirely `**…**` → highlighted punch line box.
- First `<br>` piece that is entirely bold (e.g. `**1️⃣ 导购给会员发消息**`) → section heading, kept with next block.
- Pieces starting with ❌ ✅ 👉 📮 → hanging-indent emoji bullets; `· ` → dot list item.
- A piece ending in `：` is kept on the same page as what follows; so is a short (≤40 chars) question ending in
  `？` that opens a multi-line paragraph (e.g. `为什么 AI 能跟进得准…？<br>因为…`).
- `![alt](images/x.png)` → full-width rounded image; shrunk (≥70% of natural height) to use leftover space.

## Pagination modes (`--mode auto|section|flow`, default auto)
render.py prints `mode: …` and a per-page outline (also saved in `pages/manifest.json`).
- **auto**: section mode if the body has ≥2 section titles, otherwise flow. A section title is the bold first
  line of a multi-line paragraph (e.g. `**1️⃣ 导购给会员发消息**<br>…`), or a line starting with 1️⃣…/`1.`/`1、`.
- **section** (approved by Chris on 10-09):
  - Groups: 导语 (everything before the first section) → one group per section → 总结 + 钩子. A middle section
    runs to the next title; the last section keeps its paragraph plus the image / ❌✅👉 / · paragraphs right after it,
    and the first plain paragraph after that starts 总结 + 钩子 (a short 📮 hook stays on the summary page if it fits).
  - Every group starts on a new page and is laid out on as few pages as possible: settings are tried from loose to
    tight (images 100% → 90/80/70%, then line height 1.78 on that group's pages with images 70/62/55%) and the
    loosest one that reaches the smallest page count wins. Only if it still doesn't fit does it split (sentence-safe;
    images may also shrink to 60% to use leftover space). No 「（续）」 continuation labels (removed 10-09 per Chris).
    Font size never changes.
  - One large image per page (10-09): if the fewest-pages layout of a multi-page group puts 2+ images on one page and
    they can't reach 80% width there, the group is re-laid out with at most one extra page and no in-flow squeezing
    of a second image onto a page; that layout is kept if no page is crowded and nothing overflows.
  - Outro pull-up (10-09): the outro's first paragraph (e.g. 「四个动作，一个共同点：…」) moves onto the last section's
    last page if it fits there with that page's images still ≥80% wide AND the rest of the outro then needs fewer
    pages; otherwise it is undone. The outline shows that page as 「[N️⃣ … + 总结]」.
  - Tail balancing: if a group's last page is under 50% full, or holds only an image, whole blocks move over from
    the previous page (never stranding a heading), so there is no lone-line or lone-image page.
  - Image grow (10-09): after pagination every section-mode page's images are enlarged uniformly to the largest
    width (≤100% of the content width) that does not overflow; the outline's `img N%` is that final scale (no `img`
    = 100%). Then a group's last page under 60% full is centred vertically. Font size never changes; the tighter-spacing retry is flow-only.
- **flow**: the original continuous layout (output is byte-identical to the pre-section renderer).

## Pagination rules
Measured in headless Chrome, block by block (never by character count). A block that does not fit moves
to the next page; a long text piece is split only at sentence ends (。！？；). If the last page is under 30%
full, slightly tighter spacing (line height 1.78/1.72, smaller gaps) is tried and kept only if it saves a page.
Font size is never reduced. Warnings (overflow, block taller than a page) go to stdout and manifest.json.

## Cover (「封面」 block on the card, optional)
Put this under `## 小红书终稿`, after the 标题 line and before `**正文**` (bold line + bullets):
```
**封面**
- 主标题：改AI匹配业务？｜还是改业务适应AI？      ← ≤2 lines, split with ｜
- 副标题：连锁门店老板会关注的4个动作
- 栏目：AI进化论 01                              ← 栏目标签 + 期数
- 强调词：改业务                                 ← optional, shown in gold; several: 词1、词2
```
`extract.py` writes these to `cover.json` (plus the card's 内容支柱 as `pillar`). Priority per field:
CLI flag > 封面 block > fallback. Fallbacks: title = the note title split after the first ，？：;
tag = 内容支柱 (no issue number); subtitle and accent = none. render.py prints where each field came from.

## 导读 (「导读」 block on the card = the post caption, optional)
Put it under `## 小红书终稿`, after the 封面 block and before `**正文**`:
```
**导读**
AI工具买了，员工也培训了，业绩没动？
…（any number of lines）
#连锁门店 #门店管理 …        ← optional trailing hashtag line
**正文**
```
Everything from `**导读**` to `**正文**` is excluded from the rendered cards (like the 封面 block) and written to
`daodu.txt`. Trailing pure-hashtag lines are not part of `daodu.txt`; they are used as the tags only if the card
has no `**话题**：` line (otherwise `**话题**` wins, so tags never appear twice). `post.txt` =
「小红书正文（发布时粘贴）」 label + 导读 + blank line + hashtags; with no 导读 block it holds just the hashtags.
Test sample: /workspace/xhs_cards/daodu-test/sample.md.

License: private and proprietary to the repository owner. All rights reserved.
