#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zotero_annotations.py — 读取 Zotero 文献 PDF 批注（高亮/下划线/笔记），按颜色分组输出。
增量模式：批注缓存到 ~/.cache/zotero-annotations/，第二次起只打印新增/更新的批注。

纯标准库，直接访问 Zotero 本地 API (http://127.0.0.1:23119)，只读、免 key，不写库。
显式拉取附件：--save-pdf DIR 会把 PDF 附件复制到本地目录（用于后续全文提取/深度分析），
--list-attachments 只读列出附件元数据。
用法：
  python3 zotero_annotations.py --query "示例标题" [--collection "示例合集"]
  python3 zotero_annotations.py --key ASDFGHJK
  python3 zotero_annotations.py --key ASDFGHJK --full     # 忽略缓存，全量输出
  python3 zotero_annotations.py --query "..." --json
  python3 zotero_annotations.py --key ASDFGHJK --list-attachments
  python3 zotero_annotations.py --key ASDFGHJK --save-pdf .refs/zotero-pdf

参数：
  --query TEXT      标题子串（大小写不敏感；Unicode 破折号已归一化）
  --collection TEXT 集合名（精确、大小写不敏感）；缺省搜索全库
  --key KEY         Zotero item key，直接定位，最快最精确
  --full            忽略缓存，全量输出
  --json            输出原始 JSON（含 delta 信息）
  --no-color        不按颜色分组
  --cache-dir PATH  显式指定缓存目录
  --list-attachments  只读列出 PDF 附件元数据
  --save-pdf DIR    下载 PDF 附件到 DIR（默认 .zotero-pdf），不输出批注
  --force           --save-pdf 时覆盖已存在文件
  --color NAME|HEX  上下文模式：只处理指定颜色（可多次）
  --ann-key KEY     上下文模式：只处理指定批注 key（可多次）
  --before N        上下文前句数（默认 2）
  --after N         上下文后句数（默认 2）
  --fulltext        上下文模式：导出全文 txt 到缓存目录
  --export-pdf      上下文模式：复制 PDF 副本到缓存目录

缓存目录优先级：--cache-dir > 当前工作目录下 .zotero-annotations/ > 系统 temp。
无论落在哪，脚本都会在输出里给出 cache= 路径；请把缓存位置告知用户。

退出码：0 成功，1 失败。具体错误类型见 stderr 的 `ERROR <HTTP码> <LABEL>: 文字`，
HTTP 风格码如 503 SERVICE_UNAVAILABLE / 404 NOT_FOUND / 300 MULTIPLE_CHOICES / 422 UNPROCESSABLE_ENTITY。

阅读定位（推测当前读到哪，方便 AGENT 快速定位，无需拉全文）：
  - 方法1 新增分布：本次新增/更新批注的页码分布与范围（用户最近在读的区间）。
  - 方法2 最远标记：全部批注里页码最大的一条（读到的最后位置）。
  输出在 "### 阅读定位" 块；STATUS 行含 reading=pageN；--json 含 reading/reading_prev；
  reading 也会写入缓存供下次对比。
"""

import argparse
import datetime
import glob
import json
import os
import re
import shutil
import sys
import tempfile
import urllib.request
import urllib.parse

BASE = "http://127.0.0.1:23119"

# Zotero 内置批注颜色（hex -> 友好名）。
COLOR_NAMES = {
    "#ff6666": "red",
    "#ffd400": "yellow",
    "#2ea8e5": "blue",
    "#ff7f2a": "orange",
    "#98fb98": "green",
    "#ff00ff": "magenta",
    "#000000": "black",
}

try:
    import pymupdf as fitz  # 新版包名；旧版 fitz 亦可用（仅上下文模式需要）
except ImportError:
    try:
        import fitz  # type: ignore
    except ImportError:
        fitz = None  # type: ignore

PLACEHOLDER = "\uE000"  # 私有区字符，用于分句时保护缩写点号


def api(path, params=None):
    url = BASE + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    with urllib.request.urlopen(url, timeout=15) as resp:
        return json.loads(resp.read().decode("utf-8"))


def fail(code, label, text):
    """统一错误输出：文字直接可读，并带 HTTP 风格错误码（如 404 NOT_FOUND）。
    进程退出码统一为 1（HTTP 码 >255 会被 shell 截断，故不放退出码里）。"""
    print(f"[zotero-annotations] ERROR {code} {label}: {text}", file=sys.stderr)
    sys.exit(1)


def check_status():
    """端口可访问返回 True，否则打印提示并返回 False（调用方 fail 503）。"""
    try:
        api("/api/schema")  # 真实 JSON 端点；根 /api/ 是纯文本
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"[zotero-annotations] 无法连接 Zotero 本地 API: {exc}", file=sys.stderr)
        fail(503, "SERVICE_UNAVAILABLE",
             "Zotero 本地 API 不可用。请在 Zotero 中开启本地服务："
             "Settings(Preferences) -> Advanced -> Server -> "
             "'Allow other applications on this system to communicate with Zotero'，然后重启 Zotero。")


def find_collection(name):
    cols = api("/api/users/0/collections", {"format": "json", "limit": 100})
    wanted = name.strip().lower()
    matches = [
        c["data"]
        for c in cols
        if c.get("data", {}).get("name", "").strip().lower() == wanted
    ]
    if not matches:
        available = sorted(c["data"]["name"] for c in cols)
        fail(404, "NOT_FOUND", f"集合 '{name}' 不存在。可用集合："
             + (", ".join(available) if available else "(无)"))
    if len(matches) > 1:
        print(
            f"[zotero-annotations] 存在多个同名集合 '{name}'，使用第一个。",
            file=sys.stderr,
        )
    return matches[0]


def items_in_collection(col_key):
    items = []
    start = 0
    while True:
        batch = api(
            f"/api/users/0/collections/{col_key}/items",
            {"format": "json", "limit": 100, "start": start},
        )
        if not batch:
            break
        items.extend(batch)
        if len(batch) < 100:
            break
        start += len(batch)
    return items


def all_annotations():
    """分页抓取库中全部 annotation 条目。"""
    out = []
    start = 0
    while True:
        batch = api(
            "/api/users/0/items",
            {"itemType": "annotation", "format": "json", "limit": 100, "start": start},
        )
        if not batch:
            break
        out.extend(batch)
        if len(batch) < 100:
            break
        start += len(batch)
    return out


def normalize(text):
    """标题归一化：小写、统一 Unicode 破折号/空白，使带连字符与不带连字符的标题可互配。"""
    if not text:
        return ""
    out = text.lower()
    for ch in "\u2010\u2011\u2012\u2013\u2014\u2015\u2212":
        out = out.replace(ch, "-")
    for ch in "\u00a0\u2009\u202f\u200b":
        out = out.replace(ch, " ")
    return " ".join(out.split())


def find_item_by_title(items, query):
    q = normalize(query)
    hits = [it["data"] for it in items if it.get("data", {}).get("itemType") != "attachment"]
    hits = [d for d in hits if q in normalize(d.get("title"))]
    return hits


def creator_string(d):
    return ", ".join(f"{c.get('firstName','')} {c.get('lastName','')}".strip() for c in d.get("creators", [])) or "?"


def page_key(d):
    label = d.get("annotationPageLabel") or ""
    num = int(label) if label.isdigit() else 10**9
    return (num, d.get("annotationSortIndex", ""))


def color_name(hexc):
    return COLOR_NAMES.get((hexc or "").lower(), hexc or "?")


def fetch_attachment_pdfs(item_key):
    """返回 PDF 附件列表；每个元素为 data 字段 + 私有 _links（含 enclosure 文件位置）。

    原 zotero-annotations 只读批注时不取 file-url；从“拉取文献附件”能力加入后，
    仍默认只把 _links 保留在内存中，不打印、不下载，除非用户显式 --save-pdf。
    """
    try:
        kids = api(f"/api/users/0/items/{item_key}/children", {"format": "json"})
    except Exception:  # noqa: BLE001
        return []
    out = []
    for k in kids:
        if k.get("data", {}).get("itemType") == "attachment":
            d = dict(k["data"])
            d["_links"] = k.get("links", {})
            out.append(d)
    return out


def attachment_enclosure(att):
    return (att.get("_links") or {}).get("enclosure") or {}


def safe_attachment_filename(att):
    raw = att.get("filename") or att.get("title") or att.get("key") or "attachment"
    name = re.sub(r"[^A-Za-z0-9._-]+", "_", raw)
    name = name.strip("_")
    return name[:150] or att.get("key", "attachment")


def read_attachment_bytes(att):
    """读取 Zotero 附件原始字节。优先 enclosure.file://（同机 storage），
    失败时尝试 Zotero 本地 API 的 /file 端点，由 HTTP 重定向到 file:// 时手动解析。
    只读取，不修改 Zotero。
    """
    enc = attachment_enclosure(att)
    href = enc.get("href") or ""
    # 1) 直接文件路径
    if href:
        parsed = urllib.parse.urlparse(href)
        if parsed.scheme == "file":
            src = urllib.request.url2pathname(parsed.path)
            candidates = [src]
            # file:///C:/... 这类盘符绝对路径在 POSIX 上 url2pathname 会给 /C:/...；补一个去首斜杠版本
            if re.match(r"^/[A-Za-z]:/", src):
                candidates.append(src[1:])
            for c in candidates:
                if os.path.isfile(c):
                    try:
                        with open(c, "rb") as f:
                            return f.read()
                    except OSError as exc:
                        fail(422, "PDF_FILE_UNREADABLE", f"无法读取附件文件 {c}: {exc}")
            fail(404, "PDF_FILE_UNREACHABLE",
                 f"Zotero 附件文件不可达：{src}。请确认 Zotero storage 与本脚本同机，"
                 "或用 --save-pdf 前先在 Zotero 中能正常打开该 PDF。")
        if parsed.scheme in ("http", "https"):
            try:
                req = urllib.request.Request(href, headers={"User-Agent": "zotero-annotations/1.0"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    return resp.read()
            except Exception as exc:  # noqa: BLE001
                fail(422, "PDF_DOWNLOAD_FAILED", f"Zotero 附件下载失败：{exc}")
    # 2) 本地 API 文件端点兜底（通常会 302 到 file://，urllib 会拒绝 file 重定向）
    api_url = f"{BASE}/api/users/0/items/{att.get('key')}/file"
    try:
        req = urllib.request.Request(api_url, headers={"User-Agent": "zotero-annotations/1.0"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return resp.read()
    except urllib.error.HTTPError as exc:
        if exc.code in (302, 303, 307, 308):
            loc = exc.headers.get("Location") or exc.headers.get("location") or ""
            if loc.startswith("file:"):
                parsed = urllib.parse.urlparse(loc)
                src = urllib.request.url2pathname(parsed.path)
                candidates = [src]
                if re.match(r"^/[A-Za-z]:/", src):
                    candidates.append(src[1:])
                for c in candidates:
                    if os.path.isfile(c):
                        with open(c, "rb") as f:
                            return f.read()
            fail(404, "PDF_FILE_UNREACHABLE", f"Zotero 附件文件不可达（302 -> {loc}）")
        fail(422, "PDF_DOWNLOAD_FAILED", f"Zotero 附件下载失败：HTTP {exc.code}")
    except Exception as exc:  # noqa: BLE001
        fail(422, "PDF_DOWNLOAD_FAILED", f"Zotero 附件下载失败：{exc}")


def save_attachment(att, dest_dir, force=False):
    """把单个 Zotero PDF 附件保存到 dest_dir；返回 (dest_path, size, action)。"""
    data = read_attachment_bytes(att)
    os.makedirs(dest_dir, exist_ok=True)
    fname = safe_attachment_filename(att)
    dest = os.path.join(dest_dir, fname)
    if os.path.exists(dest) and not force:
        return dest, os.path.getsize(dest), "exists"
    with open(dest, "wb") as f:
        f.write(data)
    return dest, len(data), "saved"


# ---------------------------------------------------------------------------
# 上下文提取（基于批注精确位置 annotationPosition；依赖 PyMuPDF）
# 该模块移植自开源 zotero-annotations 项目（MIT License）的 CLI 上下文模式
# ---------------------------------------------------------------------------

def zotero_data_dir_candidates():
    """收集可能的 Zotero 数据目录：prefs.js 里的 dataDir + 默认 ~/Zotero。"""
    out = []
    appdata = os.environ.get("APPDATA")
    if appdata:
        for prefs in (
            glob.glob(os.path.join(appdata, "Zotero", "Zotero", "prefs.js"))
            + glob.glob(os.path.join(appdata, "Zotero", "Zotero", "*", "prefs.js"))
        ):
            try:
                with open(prefs, encoding="utf-8", errors="ignore") as f:
                    for line in f:
                        # user_pref("extensions.zotero.dataDir", "C:/path/to/Zotero");
                        if "extensions.zotero.dataDir" not in line:
                            continue
                        parts = line.split('"')
                        if len(parts) >= 4:
                            try:
                                val = parts[3].encode().decode("unicode_escape")
                            except (UnicodeDecodeError, AttributeError):
                                val = parts[3]
                            out.append(val)
            except OSError:
                pass
    out.append(os.path.join(os.path.expanduser("~"), "Zotero"))
    return out


def locate_pdf_file(att):
    """在 Zotero 本地存储里定位 PDF 文件的绝对路径（只读）。找不到返回 None。"""
    link = att.get("linkMode") or ""
    path = att.get("path") or ""
    fname = att.get("filename") or ""
    key = att.get("key")
    if link == "linked_file" and path:
        p = path[len("attachments:") :] if path.startswith("attachments:") else path
        if os.path.exists(p):
            return p
    if path.startswith("storage:"):
        fname = path[len("storage:") :] or fname
    for data_dir in zotero_data_dir_candidates():
        p = os.path.join(data_dir, "storage", key, fname)
        if os.path.exists(p):
            return p
    for data_dir in zotero_data_dir_candidates():
        d = os.path.join(data_dir, "storage", key)
        if os.path.isdir(d):
            pdfs = glob.glob(os.path.join(d, "*.pdf"))
            if pdfs:
                return pdfs[0]
    return None


def conv_rect(page, r):
    """Zotero annotationPosition 的 rect 是 PDF 原生坐标（左下原点）；
    转成 PyMuPDF 的左上原点坐标系。"""
    H = page.rect.height
    x0, y0, x1, y1 = r
    return fitz.Rect(x0, H - y1, x1, H - y0)


def exact_phrase(page, rects):
    """按批注 rect 逐块取词并拼接，得到高亮的精确文本。"""
    frags = [page.get_textbox(conv_rect(page, r)).strip() for r in rects]
    return " ".join(f for f in frags if f)


def split_sentences(text):
    """粗略分句：句号/问号/叹号 + 空白 + 大写/数字 开头为新句。
    先保护常见缩写（e.g., Fig., et al., 数字点号）避免误切。"""
    def protect(m):
        return m.group(0).replace(".", PLACEHOLDER)

    t = re.sub(
        r"\b(?:e\.g|i\.e|et al|etc|vs|cf|approx|al|Fig|Figs|Figure|Ref|Refs|"
        r"Eq|Eqs|No|Nos|Dr|Prof|Mr|Mrs|Ms|St|Mt|Jan|Feb|Mar|Apr|Jun|Jul|Aug|"
        r"Sep|Oct|Nov|Dec|U\.S|U\.K|Ph\.D|Inc|Ltd|Corp|Co)\.",
        protect,
        text,
        flags=re.IGNORECASE,
    )
    parts = re.split(
        r"(?<=[.!?])\s*(?:\[[0-9][^\]\n]{0,15}\]\s*)*(?=[A-Z0-9\"'“])", t
    )
    return [p.replace(PLACEHOLDER, ".").strip() for p in parts if p.strip()]


def page_lines(page):
    """取页内所有文本行 (bbox, 归一化文本)，用于定位锚点行。"""
    out = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            txt = "".join(s["text"] for s in line["spans"])
            txt = re.sub(r"\s+", " ", txt).strip()
            if txt:
                out.append((fitz.Rect(line["bbox"]), txt))
    return out


def page_line_entries(page):
    """取页内所有文本行及其所属 block/行号；后续优先用 rect 锁定命中行。"""
    entries = []
    for bi, block in enumerate(page.get_text("dict")["blocks"]):
        if block.get("type") != 0:
            continue
        for li, line in enumerate(block["lines"]):
            txt = "".join(s["text"] for s in line["spans"])
            txt = re.sub(r"\s+", " ", txt).strip()
            if txt:
                entries.append({
                    "bbox": fitz.Rect(line["bbox"]),
                    "text": txt,
                    "block": bi,
                    "line": li,
                })
    return entries


def best_line_for_rects(page, rects):
    """直接按 annotationPosition 的 rects 锁定高亮所在文本行。

    这是与旧版的关键区别：不再先取词再回整页字符串 find，而是用 rect 与
    PyMuPDF dict 提取的每一行 bbox 算重叠面积，重叠最大的行就是高亮所在行。
    返回 entries 中的全局下标；找不到返回 None。
    """
    entries = page_line_entries(page)
    if not entries or not rects:
        return None
    rrects = [conv_rect(page, r) for r in rects]
    best_idx, best_area = None, -1.0
    for i, e in enumerate(entries):
        area = 0.0
        for r in rrects:
            ov = r & e["bbox"]
            if not ov.is_empty:
                area += (ov.x1 - ov.x0) * (ov.y1 - ov.y0)
        if area > best_area:
            best_area, best_idx = area, i
    return best_idx if best_idx is not None and best_area > 0 else None


def context_from_rect(page, rects, before, after, phrase):
    """基于 rect 的上下文提取（主路径）。

    流程：rects -> 命中行 -> 同 block 内取该行前后 N 行 -> 行文本拼接后分句。
    若分句后仍无法定位目标句，则退回行级上下文（命中行 + 前后行），
    不再回整页字符串 find，避免双栏/页眉页脚/公式造成的串行定位错误。
    """
    entries = page_line_entries(page)
    hit_idx = best_line_for_rects(page, rects)
    if hit_idx is None:
        return None
    hit = entries[hit_idx]

    # 窗口选择：优先同 block 内前后行；同 block 行数不够时，再向相邻 block 借行。
    block_idxs = [i for i, e in enumerate(entries) if e["block"] == hit["block"]]
    pos_in_block = block_idxs.index(hit_idx)
    start_in_block = max(0, pos_in_block - before)
    end_in_block = min(len(block_idxs) - 1, pos_in_block + after)
    if (pos_in_block - start_in_block >= before
            and end_in_block - pos_in_block >= after):
        win_entries = [entries[i] for i in block_idxs[start_in_block:end_in_block + 1]]
        hit_in_win = pos_in_block - start_in_block
    else:
        start = max(0, hit_idx - before)
        end = min(len(entries), hit_idx + after + 1)
        win_entries = entries[start:end]
        hit_in_win = hit_idx - start

    window_text = " ".join(e["text"] for e in win_entries)
    sents = split_sentences(window_text)
    target = None
    nphrase = re.sub(r"\s+", " ", phrase).strip().lower() if phrase else ""
    if nphrase:
        for i, sent in enumerate(sents):
            if nphrase in re.sub(r"\s+", " ", sent).strip().lower():
                target = i
                break
    if target is None:
        # 用命中行作为目标（行级上下文）
        return [e["text"] for e in win_entries], hit_in_win, (0, len(win_entries))
    return sents, target, (0, len(sents))


def anchor_line_text(page, rect):
    """旧 fallback：找与高亮 rect 垂直重叠面积最大的那一行，返回其文本（定位锚点）。"""
    best_txt, best_ov = None, -1
    for bbox, txt in page_lines(page):
        ov = rect & bbox
        if ov.is_empty:
            continue
        area = (ov.x1 - ov.x0) * (ov.y1 - ov.y0)
        if area > best_ov:
            best_ov, best_txt = area, txt
    return best_txt


def find_phrase_offset(ntext, nphrase, anchor=None):
    """在页文本里定位短语偏移。若有锚点行文本，优先找锚点附近的那次出现，
    解决"同一短语在标题/正文重复"时定位到错误出现的问题。"""
    if anchor:
        ai = ntext.find(anchor)
        if ai >= 0:
            lo, hi = max(0, ai - len(anchor)), min(len(ntext), ai + len(anchor) * 2)
            idx = ntext.lower().find(nphrase.lower(), lo, hi)
            if idx >= 0:
                return idx
    return ntext.lower().find(nphrase.lower())


def context_window(page_text, phrase, before, after, anchor=None):
    """在页文本里定位 phrase，返回 (句子列表, 命中句索引, (start,end))。"""
    ntext = re.sub(r"\s+", " ", page_text).strip()
    nphrase = re.sub(r"\s+", " ", phrase).strip()
    if not nphrase:
        return None
    idx = find_phrase_offset(ntext, nphrase, anchor)
    if idx < 0:
        return None
    sents = split_sentences(ntext)
    pos = 0
    offsets = []
    for sent in sents:
        st = ntext.find(sent, pos)
        if st < 0:
            st = pos
        offsets.append((st, st + len(sent)))
        pos = st + len(sent)
    target = None
    for i, (st, en) in enumerate(offsets):
        if st <= idx < en:
            target = i
            break
    if target is None:
        return None
    lo = max(0, target - before)
    hi = min(len(sents), target + after + 1)
    return sents, target, (lo, hi)


def extract_fulltext(doc):
    """整篇 PDF 文本，页间用分隔行。"""
    parts = []
    for i, page in enumerate(doc):
        parts.append(f"\n\n===== PAGE {i + 1} =====\n\n" + page.get_text("text"))
    return "".join(parts)


def print_ctx(r_, before, after):
    print(f"<<<CTX key={r_['key']} color={color_name(r_['color'])} page={r_['page']}")
    print(f"PHRASE: {r_['phrase']}")
    if r_.get("comment"):
        print(f"COMMENT: {r_['comment']}")
    if r_.get("sentences"):
        sents = r_["sentences"]
        tgt = r_["target_idx"]
        lo, hi = r_["window"]
        for i in range(lo, hi):
            mark = ">>>" if i == tgt else "   "
            rel = i - tgt
            label = "S0" if rel == 0 else f"S{'+' if rel > 0 else ''}{rel}"
            print(f"  {mark} [{label}] {sents[i]}")
    else:
        print("  (无法在页文本中定位该短语；可能是跨栏排版或文本为图片)")
    print(">>>CTX")


def open_pdf_doc(att):
    """打开 Zotero PDF 附件为 PyMuPDF 文档；优先本地路径，失败时读字节流。
    返回 (doc, pdf_path, data)。"""
    if fitz is None:
        fail(500, "DEPENDENCY_MISSING",
             "本机未安装 PyMuPDF，无法读取 PDF 原文。请先执行：pip install pymupdf")
    pdf_path = locate_pdf_file(att)
    if pdf_path and os.path.exists(pdf_path):
        return fitz.open(pdf_path), pdf_path, None
    data = read_attachment_bytes(att)
    return fitz.open(stream=data, filetype="pdf"), None, data


def is_context_requested(args):
    """是否进入上下文模式：给了上下文参数中的任一。"""
    return bool(args.color or args.ann_key or args.fulltext or args.export_pdf)


def cmd_context(item, pdfs, args):
    """上下文模式：按批注 annotationPosition 精确定位高亮处，输出前后 N 句；
    可选导出全文 txt 与 PDF 副本。"""
    att = pdfs[0]
    doc, pdf_path, pdf_data = open_pdf_doc(att)

    pdf_keys = {p["key"] for p in pdfs}
    raw = [a for a in all_annotations() if a["data"].get("parentItem") in pdf_keys]
    annos = [a["data"] for a in raw]

    def color_to_hex(c):
        c = c.lower().lstrip("#")
        for h, name in COLOR_NAMES.items():
            if name == c:
                return h.lstrip("#")
        return c
    wanted_colors = {color_to_hex(c) for c in args.color}

    def keep(a):
        if args.ann_key and a["key"] not in set(args.ann_key):
            return False
        if args.color:
            col = (a.get("annotationColor") or "").lstrip("#").lower()
            if col not in wanted_colors:
                return False
        return True
    annos = [a for a in annos if keep(a)]

    results = []
    for a in annos:
        pos = a.get("annotationPosition")
        page_label = a.get("annotationPageLabel")
        try:
            info = json.loads(pos) if pos else {}
            page_idx = int(info["pageIndex"])
            rects = info.get("rects", [])
        except (ValueError, KeyError, TypeError):
            info, page_idx, rects = {}, None, []
        if rects and page_idx is not None and page_idx < doc.page_count:
            page = doc[page_idx]
            phrase = exact_phrase(page, rects) or a.get("annotationText") or ""
            # 主路径：直接用 rect 锁定命中行，再取同 block 前后行，避免整页字符串 find 串行
            ctx = context_from_rect(page, rects, args.before, args.after, phrase)
            if ctx is None:
                # fallback：无 rect 命中行时，才退回旧的整页文本 find（如 annotationPosition 缺失或坐标异常）
                anchor = anchor_line_text(page, conv_rect(page, rects[0]))
                ctx = context_window(
                    page.get_text("text"), phrase, args.before, args.after, anchor
                )
            if ctx is None:
                sents, tgt, lo, hi = None, None, None, None
            else:
                sents, tgt, (lo, hi) = ctx
        else:
            phrase = a.get("annotationText") or ""
            sents, tgt, lo, hi = None, None, None, None
        results.append({
            "key": a["key"],
            "color": a.get("annotationColor"),
            "page": page_label,
            "text": a.get("annotationText"),
            "comment": a.get("annotationComment"),
            "phrase": phrase,
            "page_index": page_idx,
            "sentences": sents,
            "target_idx": tgt,
            "window": (lo, hi) if sents else None,
            "rects": rects,
        })

    cache_dir = resolve_cache_dir(args.cache_dir)
    os.makedirs(cache_dir, exist_ok=True)
    txt_path, pdf_out = None, None
    if args.fulltext:
        txt_path = os.path.join(cache_dir, item["key"] + ".txt")
        with open(txt_path, "w", encoding="utf-8") as f:
            f.write(extract_fulltext(doc))
    if args.export_pdf:
        pdf_out = os.path.join(cache_dir, item["key"] + ".pdf")
        if pdf_data is not None:
            with open(pdf_out, "wb") as f:
                f.write(pdf_data)
        else:
            shutil.copy2(pdf_path, pdf_out)

    if args.json:
        print(json.dumps({
            "item": {
                "key": item["key"],
                "title": item.get("title"),
                "creators": creator_string(item),
                "year": item.get("date", ""),
            },
            "pdf_source": pdf_path or (item["key"] + ".pdf"),
            "exports": {"fulltext_txt": txt_path, "pdf_copy": pdf_out},
            "contexts": results,
        }, ensure_ascii=False, indent=2))
        return

    print("=" * 72)
    print("Title :", item.get("title"))
    print("Author:", creator_string(item))
    print("PDF   :", pdf_path or f"stream({att.get('filename') or att['key']})")
    print(f"STATUS: OK | mode=context | item={item['key']} | contexts={len(results)} "
          f"| before={args.before} after={args.after} "
          f"| fulltext_txt={txt_path or 'none'} | pdf_copy={pdf_out or 'none'}")
    print("=" * 72)

    if not args.no_color:
        groups = {}
        for r_ in results:
            groups.setdefault(r_["color"], []).append(r_)
        ordered = sorted(groups.items(), key=lambda kv: (kv[0] != "#ff6666", kv[0] or ""))
        for color, rs in ordered:
            print(f"\n### 颜色 {color_name(color)} ({color}) — {len(rs)} 条")
            for r_ in rs:
                print_ctx(r_, args.before, args.after)
    else:
        for r_ in results:
            print_ctx(r_, args.before, args.after)


# ---------------------------------------------------------------------------
# 增量缓存
# ---------------------------------------------------------------------------

def resolve_cache_dir(explicit=None):
    """缓存目录优先级：--cache-dir > 当前工作目录 .zotero-annotations/ > 系统 temp。
    调用方需把最终 cache 路径提示给用户。"""
    if explicit:
        return explicit
    try:
        cwd = os.getcwd()
        if cwd and os.access(cwd, os.W_OK):
            return os.path.join(cwd, ".zotero-annotations")
    except Exception:  # noqa: BLE001
        pass
    return os.path.join(tempfile.gettempdir(), "zotero-annotations")


def load_cache(cache_dir, item_key):
    path = os.path.join(cache_dir, item_key + ".json")
    if not os.path.exists(path):
        return None, path
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), path
    except (OSError, json.JSONDecodeError):
        return None, path


def save_cache(cache_dir, path, item_key, annos, versions, reading=None):
    os.makedirs(cache_dir, exist_ok=True)
    payload = {
        "item_key": item_key,
        "saved_at": datetime.datetime.now().isoformat(timespec="seconds"),
        "reading": reading,
        "annotations": {
            a["key"]: {
                "version": versions.get(a["key"]),
                "type": a.get("annotationType"),
                "color": a.get("annotationColor"),
                "page": a.get("annotationPageLabel"),
                "text": a.get("annotationText"),
                "comment": a.get("annotationComment"),
            }
            for a in annos
        },
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


def print_ann_block(d):
    """每条批注用可 grep 的起止标记包裹。用 grep '^<<<ANN' 定位全部，
    grep 'color=red' 按颜色过滤，grep 'key=XXX' 按条目定位。"""
    page = d.get("annotationPageLabel") or "?"
    atype = d.get("annotationType", "?")
    color = d.get("annotationColor") or ""
    text = (d.get("annotationText") or "").replace("\n", " ")
    comment = (d.get("annotationComment") or "").replace("\n", " ") or "(无)"
    print(f"<<<ANN key={d.get('key')} color={color_name(color)} hex={color} page={page} type={atype}")
    print(f"TEXT: {text}")
    print(f"COMMENT: {comment}")
    print(">>>ANN")


def reading_position(annos, new_changed):
    """推测用户当前阅读位置（纯批注元数据推导，不读全文，不越界）。

    方法1 增量位置: 本次新增/更新批注的页码分布 -> 用户最近在读的区间。
    方法2 最远标记: 全部批注里页码最大的一条 -> 读到的最后位置。

    返回 dict 供 --json 与人类可读输出共用；无相应数据时为 None。
    """
    r = {"method2_farthest": None, "method1_delta": None}
    if annos:
        last = max(annos, key=page_key)
        r["method2_farthest"] = {
            "page": last.get("annotationPageLabel") or "?",
            "key": last.get("key"),
            "total": len(annos),
        }
    if new_changed:
        pages = []
        for a in new_changed:
            label = a.get("annotationPageLabel") or ""
            if label.isdigit():
                pages.append(int(label))
        if pages:
            pages.sort()
            r["method1_delta"] = {
                "count": len(pages),
                "pages": pages,
                "min": pages[0],
                "max": pages[-1],
            }
    return r


def render_reading(r, old_r=None):
    """输出阅读定位块（可 grep：grep '阅读定位' 定位整块）。
    old_r 为旧缓存的 reading，用于跨会话"对比"进度。"""
    print("\n### 阅读定位（推测当前读到哪，无需拉取全文）")
    f = r.get("method2_farthest")
    if f:
        prog = ""
        if old_r and old_r.get("method2_farthest"):
            old_p = old_r["method2_farthest"].get("page")
            if str(old_p) != str(f["page"]):
                prog = f"  [上次: 第 {old_p} 页]"
        print(f"最远标记: 第 {f['page']} 页 (key={f['key']}, 共 {f['total']} 条批注){prog}")
    else:
        print("最远标记: (无批注)")
    d = r.get("method1_delta")
    if d:
        print(f"新增分布: {d['count']} 条新增/更新，页码 {d['pages']}，"
              f"范围 {d['min']}–{d['max']} 页")
    else:
        print("新增分布: (本次无新增/更新)")


def render_rows(rows, no_color):
    if no_color:
        for d in rows:
            print_ann_block(d)
        return
    groups = {}
    for d in rows:
        groups.setdefault(d.get("annotationColor"), []).append(d)
    if not groups:
        return
    # 红色(内容标注)优先展示
    order = sorted(groups.items(), key=lambda kv: (kv[0] != "#ff6666", kv[0] or ""))
    for color, rs in order:
        print(f"\n### 颜色 {color_name(color)} ({color}) — {len(rs)} 条")
        for d in rs:
            print_ann_block(d)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--query")
    ap.add_argument("--collection")
    ap.add_argument("--key")
    ap.add_argument("--full", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--cache-dir")
    ap.add_argument("--list-attachments", action="store_true",
                    help="只列出 PDF 附件元数据（只读，不下载）")
    ap.add_argument("--save-pdf", nargs="?", const=".zotero-pdf", metavar="DIR",
                    help="下载 PDF 附件到 DIR（默认 .zotero-pdf），用于深度分析；不输出批注")
    ap.add_argument("--force", action="store_true", help="--save-pdf 时覆盖已存在文件")
    # 上下文模式（任给其一即进入；需 PyMuPDF）
    ap.add_argument("--color", action="append", default=[],
                    help="只处理指定颜色批注（可多次：red / #ff6666）")
    ap.add_argument("--ann-key", action="append", default=[],
                    help="只处理指定批注 key（可多次）")
    ap.add_argument("--before", type=int, default=2, help="上下文前句数，默认 2")
    ap.add_argument("--after", type=int, default=2, help="上下文后句数，默认 2")
    ap.add_argument("--fulltext", action="store_true",
                    help="导出全文 txt 到缓存目录")
    ap.add_argument("--export-pdf", action="store_true",
                    help="复制 PDF 副本到缓存目录")
    args = ap.parse_args()

    if not (args.key or args.query):
        ap.error("provide --key or --query")

    if not check_status():
        sys.exit(1)  # 防御性兜底；check_status 失败时已 fail(503)

    # 1) 定位文献
    if args.key:
        item = api(f"/api/users/0/items/{args.key}", {"format": "json"})["data"]
    else:
        if args.collection:
            col = find_collection(args.collection)
            if not col:
                sys.exit(1)  # find_collection 失败时已 fail(404)
            candidates = find_item_by_title(items_in_collection(col["key"]), args.query)
        else:
            candidates = find_item_by_title(
                api("/api/users/0/items/top", {"format": "json", "limit": 100}),
                args.query,
            )
        if not candidates:
            fail(404, "NOT_FOUND", f"没有匹配标题 '{args.query}' 的条目")
        if len(candidates) > 1:
            for c in candidates:
                print(f"  - {c['key']}  {c.get('title')}", file=sys.stderr)
            fail(300, "MULTIPLE_CHOICES",
                 f"标题 '{args.query}' 命中 {len(candidates)} 条，有歧义。"
                 "请用 --key 精确定位或细化 --query。")
        item = candidates[0]

    # 2) PDF 附件
    pdfs = fetch_attachment_pdfs(item["key"])
    if not pdfs:
        fail(422, "UNPROCESSABLE_ENTITY",
             f"条目 {item['key']} 没有 PDF 附件")

    # 2a) 上下文模式（精确定位 + 前后句 + 全文/PDF 导出；需 PyMuPDF）
    if is_context_requested(args):
        cmd_context(item, pdfs, args)
        return

    # 2b) 只列附件（只读，不下载、不读批注）
    if args.list_attachments:
        print("=" * 72)
        print("Title :", item.get("title"))
        print("PDF attachments:")
        for p in pdfs:
            enc = attachment_enclosure(p)
            href = enc.get("href") or ""
            print(f"  - key={p.get('key')}  title={p.get('title') or p.get('filename')}  "
                  f"contentType={p.get('contentType')}  file={href}")
        print(f"STATUS: OK | mode=list-attachments | attachments={len(pdfs)} | "
              f"item={item.get('key')}")
        return

    # 2c) 拉取 PDF 附件（显式写文件，用于后续全文提取/深度分析）
    if args.save_pdf is not None:
        dest_dir = args.save_pdf or ".zotero-pdf"
        saved = 0
        total = 0
        for p in pdfs:
            dest, size, action = save_attachment(p, dest_dir, force=args.force)
            print(f"[zotero-annotations] {action}: {dest} ({size} bytes)", file=sys.stderr)
            if action == "saved":
                saved += 1
            total += size
        print(f"STATUS: OK | mode=save-pdf | saved={saved} | attachments={len(pdfs)} "
              f"| bytes={total} | dir={dest_dir} | item={item.get('key')}")
        return

    # 3) 挂在附件上的批注
    pdf_keys = {p["key"] for p in pdfs}
    raw = [a for a in all_annotations() if a["data"].get("parentItem") in pdf_keys]
    versions = {a["data"]["key"]: a.get("version") for a in raw}
    annos = [a["data"] for a in raw]
    annos.sort(key=page_key)

    # 4) 增量计算 + 缓存
    cache_dir = resolve_cache_dir(args.cache_dir)
    old_cache, cache_path = load_cache(cache_dir, item["key"])
    old = (old_cache or {}).get("annotations", {})
    old_reading = (old_cache or {}).get("reading")
    had_cache = bool(old)
    current_keys = {a["key"] for a in annos}
    new_changed = [
        a for a in annos
        if a["key"] not in old or old[a["key"]].get("version") != versions.get(a["key"])
    ]
    removed = [k for k in old if k not in current_keys]
    reading = reading_position(annos, new_changed)
    save_cache(cache_dir, cache_path, item["key"], annos, versions, reading)

    if args.json:
        print(json.dumps(
            {
                "item": {
                    "key": item["key"],
                    "itemType": item.get("itemType"),
                    "title": item.get("title"),
                    "creators": creator_string(item),
                    "year": item.get("date", ""),
                    "publication": item.get("publicationTitle"),
                    "doi": item.get("DOI"),
                    "collections": item.get("collections", []),
                },
                "attachments": [{"key": p["key"], "title": p.get("title")} for p in pdfs],
                "annotations": annos,
                "delta": {
                    "new_or_changed": [a["key"] for a in new_changed],
                    "removed": removed,
                },
                "reading": reading,
                "reading_prev": old_reading,
                "cache_path": cache_path,
            },
            ensure_ascii=False,
            indent=2,
        ))
        return

    # 5) 人类可读输出
    print("=" * 72)
    print("Title :", item.get("title"))
    print("Author:", creator_string(item))
    print("Source:", item.get("publicationTitle") or "", item.get("date") or "")
    if item.get("DOI"):
        print("DOI   :", item["DOI"])
    print("PDF(s):", ", ".join(p.get("title") or p["key"] for p in pdfs))
    print(f"Annotations: {len(annos)}")
    # 机器可读的成败汇报，agent 应据此向用户说明结果。
    mode = "incremental" if (not args.full and had_cache) else ("full" if had_cache else "first")
    reading_txt = "none"
    if reading.get("method2_farthest"):
        reading_txt = f"page{reading['method2_farthest']['page']}"
    print(f"STATUS: OK | mode={mode} | annotations={len(annos)} "
          f"| new_updated={len(new_changed)} | removed={len(removed)} "
          f"| reading={reading_txt} | cache={cache_path}")
    print("=" * 72)

    # 阅读定位：两种方法推测当前读到哪，方便 AGENT 快速定位，无需拉取全文。
    render_reading(reading, old_reading)

    if not args.full and had_cache:
        print(f"增量：新增/更新 {len(new_changed)} 条，删除 {len(removed)} 条（缓存: {cache_path}）")
        if not new_changed and not removed:
            print("（无变化）")
        if new_changed:
            render_rows(new_changed, args.no_color)
        if removed:
            print("已删除:", ", ".join(removed))
    else:
        if had_cache:
            print(f"全量输出 {len(annos)} 条（--full）")
        else:
            print(f"首次读取，共 {len(annos)} 条")
        render_rows(annos, args.no_color)


if __name__ == "__main__":
    main()
