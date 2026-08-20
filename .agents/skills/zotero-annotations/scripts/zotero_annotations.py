#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
zotero_annotations.py — 读取 Zotero 文献 PDF 批注（高亮/下划线/笔记），按颜色分组输出。
增量模式：批注缓存到 ~/.cache/zotero-annotations/，第二次起只打印新增/更新的批注。

纯标准库，直接访问 Zotero 本地 API (http://127.0.0.1:23119)，只读、免 key，不写库。
严格范围：只读批注元数据；绝不取全文(fulltext)、不取附件 file-url、不下载/解析 PDF、
不调用插件 zotero.py。放行钩子白名单匹配的就是本脚本，保持工作流单一才无审批弹窗。

用法：
  python3 zotero_annotations.py --query "示例标题" [--collection "示例合集"]
  python3 zotero_annotations.py --key ASDFGHJK
  python3 zotero_annotations.py --key ASDFGHJK --full     # 忽略缓存，全量输出
  python3 zotero_annotations.py --query "..." --json

参数：
  --query TEXT      标题子串（大小写不敏感；Unicode 破折号已归一化）
  --collection TEXT 集合名（精确、大小写不敏感）；缺省搜索全库
  --key KEY         Zotero item key，直接定位，最快最精确
  --full            忽略缓存，全量输出
  --json            输出原始 JSON（含 delta 信息）
  --no-color        不按颜色分组
  --cache-dir PATH  显式指定缓存目录

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
import json
import os
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


def all_collections():
    """分页抓取库中全部 collection（默认只取前 100 条会漏掉后面的）。"""
    cols = []
    start = 0
    while True:
        batch = api(
            "/api/users/0/collections",
            {"format": "json", "limit": 100, "start": start},
        )
        if not batch:
            break
        cols.extend(batch)
        if len(batch) < 100:
            break
        start += len(batch)
    return cols


def top_items():
    """分页抓取库中全部顶层条目（默认只取前 100 条会漏掉后面的）。"""
    items = []
    start = 0
    while True:
        batch = api(
            "/api/users/0/items/top",
            {"format": "json", "limit": 100, "start": start},
        )
        if not batch:
            break
        items.extend(batch)
        if len(batch) < 100:
            break
        start += len(batch)
    return items


def find_collection(name):
    cols = all_collections()
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
    """返回某条目的 PDF 附件（须是 attachment 且 contentType=application/pdf，
    避免把网页快照 HTML 等误当 PDF）。"""
    try:
        kids = api(f"/api/users/0/items/{item_key}/children", {"format": "json"})
    except Exception:  # noqa: BLE001
        return []
    return [
        k["data"]
        for k in kids
        if k.get("data", {}).get("itemType") == "attachment"
        and k.get("data", {}).get("contentType") == "application/pdf"
    ]


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
            candidates = find_item_by_title(top_items(), args.query)
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
             f"条目 {item['key']} 没有 PDF 附件，无法读取批注")

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
