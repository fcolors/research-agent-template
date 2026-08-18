#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
oa_article.py — open-article-get skill 的通用检索/下载/索引助手。

职责：把 SKILL.md 中稳定的重复动作固化为脚本，减少 agent 临场写码：
  lookup   核验 DOI / arXiv ID / 题名，输出标准化文献卡片（OpenAlex + Crossref + Unpaywall + arXiv）
  fetch    只下载合法 OA PDF（Unpaywall / OpenAlex / arXiv），不绕过付费墙
  index    维护 .refs/oa-article/index.tsv（查找/增改/去重）

纯标准库，无需安装依赖。所有命令输出机器可读状态行：
  STATUS: OK | ...
  STATUS: NO_OA | ...
  STATUS: NOT_FOUND | ...
失败时 stderr 输出：
  [oa-article] ERROR <码> <LABEL>: 文字
退出码：0 表示命令完成（含“未找到合法 OA”这类有效结果）；1 表示网络/参数等致命错误。

用法示例：
  python3 oa_article.py lookup --doi "10.48550/arXiv.1706.03762"
  python3 oa_article.py lookup --arxiv "1706.03762"
  python3 oa_article.py lookup --title "Attention Is All You Need"
  python3 oa_article.py fetch --doi "10.48550/arXiv.1706.03762" --out .refs/oa-article/pdf
  python3 oa_article.py fetch --arxiv "1706.03762" --out .refs/oa-article/pdf
  python3 oa_article.py index --tsv .refs/oa-article/index.tsv --find "1706.03762"
  python3 oa_article.py index --tsv .refs/oa-article/index.tsv --upsert --doi "..." --title "..." --year 2017
"""

import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

BASE_OPENALEX = "https://api.openalex.org"
BASE_CROSSREF = "https://api.crossref.org"
BASE_UNPAYWALL = "https://api.unpaywall.org/v2"
BASE_ARXIV_API = "http://export.arxiv.org/api/query"

DEFAULT_EMAIL = os.environ.get("OA_EMAIL", "agent@research.local")
USER_AGENT = "article-research open-article-get/0.1 (mailto:%s)" % DEFAULT_EMAIL

INDEX_HEADER = [
    "key", "title", "authors", "year", "doi", "published_doi",
    "arxiv_id", "venue", "result_level", "oa_url", "pdf_path",
    "openalex_id", "note",
]

# ---------------------------------------------------------------------------
# 基础工具
# ---------------------------------------------------------------------------

def eprint(*args):
    print(*args, file=sys.stderr)


def fail(code, label, text):
    print(f"[oa-article] ERROR {code} {label}: {text}", file=sys.stderr)
    sys.exit(1)


def http_json(url, timeout=30, nonfatal_http=(404,), retries=2):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_exc = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if exc.code in nonfatal_http:
                return None
            if exc.code in (429, 503) and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            fail(exc.code, "UPSTREAM_HTTP", f"{url} -> HTTP {exc.code}")
        except Exception as exc:  # noqa: BLE001
            fail(503, "SERVICE_UNAVAILABLE", f"{url} -> {exc}")


def http_bytes(url, timeout=60, retries=2, nonfatal_http=None):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    last_exc = None
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                final_url = resp.geturl()
                ctype = resp.headers.get("content-type", "")
                body = resp.read()
                return body, ctype, final_url
        except urllib.error.HTTPError as exc:
            last_exc = exc
            if nonfatal_http and exc.code in nonfatal_http:
                return None, "", url
            if exc.code in (429, 503) and attempt < retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            fail(exc.code, "DOWNLOAD_HTTP", f"{url} -> HTTP {exc.code}")
        except Exception as exc:  # noqa: BLE001
            fail(503, "DOWNLOAD_UNAVAILABLE", f"{url} -> {exc}")


def normalize_doi(text):
    if not text:
        return ""
    s = text.strip()
    s = re.sub(r"^https?://(dx\.)?doi\.org/", "", s, flags=re.I)
    s = re.sub(r"^doi:\s*", "", s, flags=re.I)
    return s.strip().lower()


def arxiv_from_text(text):
    if not text:
        return ""
    m = re.search(r"(\d{4}\.\d{4,5})", text)
    if m:
        return m.group(1)
    m = re.search(r"arxiv\s*[:/]?\s*(\d{4}\.\d{4,5})", text, flags=re.I)
    if m:
        return m.group(1)
    return ""


def arxiv_doi(arxiv_id):
    return "10.48550/arXiv." + arxiv_id


def safe_filename(text):
    s = re.sub(r"[^A-Za-z0-9._-]+", "_", text or "")
    s = s.strip("_")
    return s[:120] or "document"


def title_key(title):
    h = hashlib.sha1((title or "").strip().lower().encode("utf-8")).hexdigest()[:12]
    return "title-" + h


def print_status(label, **fields):
    rest = " | ".join(f"{k}={v}" for k, v in fields.items())
    print(f"STATUS: {label}" + (f" | {rest}" if rest else ""))


def openalex_work_by_doi(doi):
    """OpenAlex 用 DOI landing URL 直查，失败时用 filter=doi 兜底。

    OpenAlex 429/404 都返回 None，由上层决定是否回退 Crossref；网络其它错误仍 fail。
    """
    url = BASE_OPENALEX + "/works/https://doi.org/" + urllib.parse.quote(doi, safe="/")
    data = http_json(url, nonfatal_http=(404, 429))
    if data:
        return data
    url = BASE_OPENALEX + "/works?filter=doi:" + urllib.parse.quote(doi, safe="")
    data = http_json(url, nonfatal_http=(404, 429))
    results = (data or {}).get("results", [])
    return results[0] if results else None


def openalex_work_by_title(title):
    url = (BASE_OPENALEX + "/works?filter=title.search:"
           + urllib.parse.quote(title) + "&sort=relevance_score:desc&per-page=3")
    data = http_json(url, nonfatal_http=(404, 429))
    results = (data or {}).get("results", [])
    return results[0] if results else None


def crossref_work_by_title(title):
    """Crossref 题名检索兜底；把命中结果转成与 OpenAlex work 相近的结构。"""
    url = (BASE_CROSSREF + "/works?query.title="
           + urllib.parse.quote(title) + "&rows=3")
    data = http_json(url)
    items = (data or {}).get("message", {}).get("items", [])
    if not items:
        return None
    item = items[0]
    authors = []
    for a in item.get("author") or []:
        name = ((a.get("given") or "") + " " + (a.get("family") or "")).strip()
        if name:
            authors.append(name)
    return {
        "doi": normalize_doi(item.get("DOI") or ""),
        "title": (item.get("title") or [""])[0],
        "authors": authors,
        "publication_year": (item.get("issued") or {}).get("date-parts", [[""]])[0][0],
        "primary_location": {},
        "open_access": {},
        "id": "",
        "venue": (item.get("container-title") or [""])[0],
    }


def crossref_work_by_doi(doi):
    url = BASE_CROSSREF + "/works/" + urllib.parse.quote(doi, safe="")
    data = http_json(url)
    return (data or {}).get("message")


def unpaywall_for(doi):
    url = (BASE_UNPAYWALL + "/" + urllib.parse.quote(doi, safe="/")
           + "?email=" + urllib.parse.quote(DEFAULT_EMAIL))
    data = http_json(url, nonfatal_http=(404, 403, 422))
    return data


def arxiv_api_work(arxiv_id):
    url = BASE_ARXIV_API + "?id_list=" + urllib.parse.quote(arxiv_id) + "&max_results=1"
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            xml_text = resp.read().decode("utf-8")
    except Exception as exc:  # noqa: BLE001
        fail(503, "ARXIV_UNAVAILABLE", f"{url} -> {exc}")
    ns = {"a": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(xml_text)
    entry = root.find("a:entry", ns)
    if entry is None:
        return None
    title = entry.findtext("a:title", default="", namespaces=ns).strip().replace("\n", " ")
    summary = entry.findtext("a:summary", default="", namespaces=ns).strip()
    published = entry.findtext("a:published", default="", namespaces=ns)
    authors = []
    for author in entry.findall("a:author", ns):
        name = author.findtext("a:name", default="", namespaces=ns)
        if name:
            authors.append(name)
    return {
        "title": title,
        "authors": authors,
        "year": published[:4] if published else "",
        "venue": "arXiv",
        "doi": arxiv_doi(arxiv_id),
        "arxiv_id": arxiv_id,
        "result_level": "preprint",
        "oa": True,
        "oa_url": "https://arxiv.org/abs/" + arxiv_id,
        "pdf_url": "https://arxiv.org/pdf/" + arxiv_id,
        "openalex_id": "",
        "published_doi": "",
        "summary": summary,
    }


def find_published_doi_by_title(record):
    """仅对 arXiv/preprint 记录尝试用 Crossref 按题名找正式出版 DOI。

    宁缺毋滥：只接受题名归一化后高度一致的 journal-article/proceedings-article；
    找不到就留空，绝不强行合并。
    """
    title = (record.get("title") or "").strip()
    if len(title) < 12:
        return ""
    try:
        url = (BASE_CROSSREF + "/works?query.title="
               + urllib.parse.quote(title) + "&rows=3")
        data = http_json(url)
    except SystemExit:
        return ""
    items = (data or {}).get("message", {}).get("items", [])
    norm_title = re.sub(r"[^a-z0-9]+", "", title.lower())
    for item in items:
        item_title = (item.get("title") or [""])[0]
        if re.sub(r"[^a-z0-9]+", "", item_title.lower()) == norm_title:
            doi = normalize_doi(item.get("DOI") or "")
            if doi and doi != record.get("doi"):
                return doi
    return ""


# ---------------------------------------------------------------------------
# 文献卡片（record）构建
# ---------------------------------------------------------------------------

def build_record(oa_work, arxiv_id="", unpaywall=None):
    """把 OpenAlex/arXiv/Unpaywall 汇聚成 skill 约定的标准字段。"""
    doi = normalize_doi(oa_work.get("doi") or (unpaywall or {}).get("doi") or "")
    title = oa_work.get("display_name") or oa_work.get("title") or ""
    authors = []
    for a in oa_work.get("authorships") or []:
        name = (a.get("author") or {}).get("display_name") or ""
        if name:
            authors.append(name)
    if not authors:
        authors = oa_work.get("authors") or []
    venue = ""
    if oa_work.get("primary_location") and oa_work.get("primary_location", {}).get("source"):
        venue = oa_work["primary_location"]["source"].get("display_name") or ""
    if not venue:
        venue = oa_work.get("venue") or ""
    year = oa_work.get("publication_year") or oa_work.get("year") or ""
    openalex_id = (oa_work.get("id") or "").split("/")[-1]

    # OA 状态：OpenAlex 与 Unpaywall 交叉，Unpaywall 更专门
    up_oa = (unpaywall or {}).get("is_oa")
    up_locations = (unpaywall or {}).get("oa_locations") or []
    oa_oa = (oa_work.get("open_access") or {}).get("is_oa")
    is_oa = bool(up_oa if up_oa is not None else oa_oa)

    oa_url = ""
    pdf_url = ""
    result_level = "abstract"
    best_location = (unpaywall or {}).get("best_oa_location") or {}
    if not best_location and is_oa:
        best_location = oa_work.get("best_oa_location") or {}
    if best_location:
        oa_url = best_location.get("url") or best_location.get("url_for_pdf") or ""
        pdf_url = best_location.get("url_for_pdf") or ""
        version = best_location.get("version") or ""
        if version == "publishedVersion":
            result_level = "published"
        elif version in ("acceptedVersion", "submittedVersion"):
            result_level = "preprint"
        else:
            result_level = "published" if pdf_url else "abstract"
    if not oa_url and is_oa:
        oa_url = (oa_work.get("open_access") or {}).get("oa_url") or ""
    if not pdf_url and is_oa:
        for loc in up_locations:
            if loc.get("url_for_pdf"):
                pdf_url = loc["url_for_pdf"]
                version = loc.get("version") or ""
                result_level = "published" if version == "publishedVersion" else "preprint"
                break
    # arXiv 专属：合法 preprint PDF 与 landing
    if arxiv_id:
        if not oa_url:
            oa_url = "https://arxiv.org/abs/" + arxiv_id
        if not pdf_url:
            pdf_url = "https://arxiv.org/pdf/" + arxiv_id
        if result_level == "abstract":
            result_level = "preprint"
    # DOI 为 arXiv DOI 时也标 preprint（除非已找到 publishedVersion）
    if doi and doi.startswith("10.48550/arxiv") and result_level != "published":
        result_level = "preprint"

    record = {
        "key": doi or ("arxiv:" + arxiv_id if arxiv_id else title_key(title)),
        "title": title,
        "authors": "; ".join(authors) if isinstance(authors, list) else str(authors),
        "year": str(year),
        "doi": doi,
        "published_doi": "",
        "arxiv_id": arxiv_id,
        "venue": venue,
        "result_level": result_level,
        "oa": is_oa,
        "oa_url": oa_url,
        "pdf_url": pdf_url,
        "openalex_id": openalex_id,
        "note": "",
    }

    # published_doi 规则：正式 DOI 与 arXiv DOI 不同才填
    if doi and not doi.startswith("10.48550/arxiv"):
        record["published_doi"] = doi
    elif arxiv_id:
        record["published_doi"] = find_published_doi_by_title(record)

    return record


def lookup_record(doi=None, arxiv=None, title=None):
    """统一入口：按优先级 DOI > arXiv > title 生成标准 record。"""
    if doi:
        doi = normalize_doi(doi)
        if not doi:
            fail(400, "BAD_DOI", "DOI 为空或格式无法识别")
        oa_work = openalex_work_by_doi(doi)
        if oa_work is None:
            # Crossref 兜底，保证至少能确认 reference
            cross = crossref_work_by_doi(doi)
            if not cross:
                return {"key": doi, "doi": doi, "title": "", "authors": "", "year": "",
                        "venue": "", "result_level": "abstract", "oa": False,
                        "oa_url": "", "pdf_url": "", "arxiv_id": "", "openalex_id": "",
                        "published_doi": doi, "note": "not_found"}
            oa_work = {
                "doi": doi,
                "title": (cross.get("title") or [""])[0],
                "authorships": [],
                "publication_year": (cross.get("issued") or {}).get("date-parts", [[""]])[0][0],
                "primary_location": {},
                "open_access": {},
                "id": "",
            }
            for fam, giv in zip(cross.get("author", []), cross.get("author", [])):
                pass
            # Crossref author 结构不同，单独处理
            oa_work["authors"] = []
            for a in cross.get("author") or []:
                oa_work["authors"].append(
                    ((a.get("given") or "") + " " + (a.get("family") or "")).strip())
            oa_work["venue"] = (cross.get("container-title") or [""])[0]
        unpaywall = unpaywall_for(doi)
        arxiv_id = ""
        if doi.startswith("10.48550/arxiv"):
            arxiv_id = doi.split("arxiv.", 1)[-1]
        return build_record(oa_work, arxiv_id=arxiv_id, unpaywall=unpaywall)

    if arxiv:
        arxiv_id = arxiv_from_text("arxiv:" + arxiv) or arxiv.strip()
        if not re.fullmatch(r"\d{4}\.\d{4,5}", arxiv_id):
            fail(400, "BAD_ARXIV", f"arXiv ID 格式无法识别: {arxiv}")
        oa_work = openalex_work_by_doi(arxiv_doi(arxiv_id))
        if oa_work is None:
            rec = arxiv_api_work(arxiv_id)
            if rec is None:
                return {"key": "arxiv:" + arxiv_id, "doi": arxiv_doi(arxiv_id),
                        "title": "", "authors": "", "year": "", "venue": "",
                        "result_level": "abstract", "oa": False, "oa_url": "",
                        "pdf_url": "", "arxiv_id": arxiv_id, "openalex_id": "",
                        "published_doi": "", "note": "not_found"}
            rec["published_doi"] = find_published_doi_by_title(rec)
            return rec
        unpaywall = unpaywall_for(arxiv_doi(arxiv_id))
        return build_record(oa_work, arxiv_id=arxiv_id, unpaywall=unpaywall)

    if title:
        oa_work = openalex_work_by_title(title)
        if oa_work is None:
            # OpenAlex 不可用（404/429）时用 Crossref 题名检索兜底
            oa_work = crossref_work_by_title(title)
        if oa_work is None:
            return {"key": title_key(title), "doi": "", "title": title,
                    "authors": "", "year": "", "venue": "", "result_level": "abstract",
                    "oa": False, "oa_url": "", "pdf_url": "", "arxiv_id": "",
                    "openalex_id": "", "published_doi": "", "note": "not_found"}
        doi = normalize_doi(oa_work.get("doi") or "")
        arxiv_id = ""
        if doi.startswith("10.48550/arxiv"):
            arxiv_id = doi.split("arxiv.", 1)[-1]
        unpaywall = unpaywall_for(doi) if doi else None
        rec = build_record(oa_work, arxiv_id=arxiv_id, unpaywall=unpaywall)
        # 题名查询时只高置信接受；给 agent 留 title 原样便于判断
        rec["query_title"] = title
        return rec

    fail(400, "BAD_QUERY", "请提供 --doi / --arxiv / --title 中至少一个标识符")


def print_record(record):
    print(json.dumps(record, ensure_ascii=False, indent=2))


# ---------------------------------------------------------------------------
# lookup 子命令
# ---------------------------------------------------------------------------

def cmd_lookup(args):
    rec = lookup_record(doi=args.doi, arxiv=args.arxiv, title=args.title)
    if rec.get("note") == "not_found" or (not rec.get("title") and not rec.get("authors")):
        print_record(rec)
        print_status("NOT_FOUND", key=rec.get("key"), doi=rec.get("doi") or "none")
        return
    print_record(rec)
    print_status(
        "OK",
        found="yes",
        key=rec.get("key"),
        doi=rec.get("doi") or "none",
        published_doi=rec.get("published_doi") or "none",
        result_level=rec.get("result_level"),
        oa="yes" if rec.get("oa") else "no",
    )


# ---------------------------------------------------------------------------
# fetch 子命令
# ---------------------------------------------------------------------------

def looks_like_pdf(body, ctype):
    return (body[:5] == b"%PDF-") or ("application/pdf" in (ctype or ""))


def cmd_fetch(args):
    rec = lookup_record(doi=args.doi, arxiv=args.arxiv, title=args.title)
    if rec.get("note") == "not_found":
        print_status("NOT_FOUND", key=rec.get("key"))
        return
    if not rec.get("oa"):
        print_status("NO_OA", key=rec.get("key"), result_level=rec.get("result_level"),
                     reason="no_legal_oa_metadata")
        return

    out_dir = args.out or ".refs/oa-article/pdf"
    os.makedirs(out_dir, exist_ok=True)

    candidates = []
    if rec.get("pdf_url"):
        candidates.append(("best_oa_pdf", rec["pdf_url"]))
    if rec.get("arxiv_id"):
        candidates.append(("arxiv_pdf", "https://arxiv.org/pdf/" + rec["arxiv_id"] + ".pdf"))
    if rec.get("oa_url"):
        candidates.append(("oa_landing", rec["oa_url"]))
    seen = set()
    for label, url in candidates:
        if not url or url in seen:
            continue
        seen.add(url)
        try:
            body, ctype, final_url = http_bytes(
                url,
                nonfatal_http=(400, 401, 403, 404, 405, 406, 409, 410, 415, 422, 429, 451, 500, 502, 503),
            )
        except SystemExit:
            continue
        if body is None:
            continue
        if not looks_like_pdf(body, ctype):
            # 有些 landing page 会 200 返回 HTML，不当作 PDF
            continue
        base = rec.get("doi") or rec.get("key").replace(":", "_")
        fname = safe_filename(base) + ".pdf"
        dest = os.path.join(out_dir, fname)
        if os.path.exists(dest) and not args.force:
            print_status("EXISTS", key=rec.get("key"), pdf_path=dest,
                         bytes=os.path.getsize(dest), source=label)
            return
        with open(dest, "wb") as f:
            f.write(body)
        print_status("OK", mode="fetch", key=rec.get("key"),
                     result_level=rec.get("result_level"), pdf_path=dest,
                     bytes=len(body), source=label)
        return
    print_status("NO_OA", key=rec.get("key"), result_level=rec.get("result_level"),
                 reason="oa_metadata_yes_but_download_failed")


# ---------------------------------------------------------------------------
# index 子命令
# ---------------------------------------------------------------------------

def read_index(tsv):
    if not os.path.exists(tsv):
        return []
    rows = []
    with open(tsv, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            rows.append(row)
    return rows


def write_index(tsv, rows):
    with open(tsv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=INDEX_HEADER, delimiter="\t",
                                extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            clean = {k: row.get(k, "") for k in INDEX_HEADER}
            writer.writerow(clean)


def cmd_index(args):
    tsv = args.tsv or ".refs/oa-article/index.tsv"
    if args.find:
        q = args.find.strip().lower()
        rows = read_index(tsv)
        hits = []
        for r in rows:
            hay = " ".join(str(r.get(k, "")) for k in INDEX_HEADER).lower()
            if q in hay:
                hits.append(r)
        if not hits:
            print_status("NOT_FOUND", tsv=tsv, query=args.find)
            return
        for r in hits:
            print("\t".join(r.get(k, "") for k in INDEX_HEADER))
        print_status("OK", mode="index-find", matches=len(hits), tsv=tsv)
        return

    if args.upsert:
        rec = None
        if args.doi or args.arxiv or args.title:
            rec = lookup_record(doi=args.doi, arxiv=args.arxiv, title=args.title)
        key = args.key or (rec or {}).get("key") or ""
        if not key:
            fail(400, "BAD_KEY", "upsert 需要 --key，或能由 --doi/--arxiv/--title 推导出 key")
        row = {
            "key": key,
            "title": args.title or (rec or {}).get("title", ""),
            "authors": args.authors or (rec or {}).get("authors", ""),
            "year": args.year or (rec or {}).get("year", ""),
            "doi": normalize_doi(args.doi or "") or (rec or {}).get("doi", ""),
            "published_doi": args.published_doi or (rec or {}).get("published_doi", ""),
            "arxiv_id": args.arxiv or (rec or {}).get("arxiv_id", ""),
            "venue": args.venue or (rec or {}).get("venue", ""),
            "result_level": args.result_level or (rec or {}).get("result_level", "abstract"),
            "oa_url": args.oa_url or (rec or {}).get("oa_url", ""),
            "pdf_path": args.pdf_path or (rec or {}).get("pdf_path", ""),
            "openalex_id": args.openalex_id or (rec or {}).get("openalex_id", ""),
            "note": args.note or "",
        }
        rows = read_index(tsv)
        for i, r in enumerate(rows):
            if (r.get("key") or "").strip().lower() == key.lower():
                rows[i] = row
                write_index(tsv, rows)
                print_status("OK", mode="index-update", key=key, tsv=tsv)
                return
        rows.append(row)
        os.makedirs(os.path.dirname(tsv) if os.path.dirname(tsv) else ".", exist_ok=True)
        write_index(tsv, rows)
        print_status("OK", mode="index-add", key=key, tsv=tsv)
        return

    # 默认：显示前若干行，方便快速检查
    rows = read_index(tsv)
    if not rows:
        print_status("EMPTY", tsv=tsv)
        return
    for r in rows[:20]:
        print("\t".join(r.get(k, "") for k in INDEX_HEADER))
    print_status("OK", mode="index-show", rows=len(rows), shown=min(len(rows), 20), tsv=tsv)


# ---------------------------------------------------------------------------
# 参数与入口
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="command", required=True)

    p_lookup = sub.add_parser("lookup", help="核验 DOI / arXiv ID / 题名，输出标准文献卡片")
    p_lookup.add_argument("--doi")
    p_lookup.add_argument("--arxiv")
    p_lookup.add_argument("--title")
    p_lookup.set_defaults(func=cmd_lookup)

    p_fetch = sub.add_parser("fetch", help="只下载合法 OA PDF")
    p_fetch.add_argument("--doi")
    p_fetch.add_argument("--arxiv")
    p_fetch.add_argument("--title")
    p_fetch.add_argument("--out", help="输出目录（默认 .refs/oa-article/pdf）")
    p_fetch.add_argument("--force", action="store_true", help="已存在时覆盖")
    p_fetch.set_defaults(func=cmd_fetch)

    p_index = sub.add_parser("index", help="维护 .refs/oa-article/index.tsv")
    p_index.add_argument("--tsv", help="TSV 路径（默认 .refs/oa-article/index.tsv）")
    p_index.add_argument("--find", help="按子串查找（DOI/题名/作者/年份等）")
    p_index.add_argument("--upsert", action="store_true", help="按 key 更新或新增一行")
    p_index.add_argument("--key")
    p_index.add_argument("--doi")
    p_index.add_argument("--arxiv")
    p_index.add_argument("--title")
    p_index.add_argument("--authors")
    p_index.add_argument("--year")
    p_index.add_argument("--published-doi")
    p_index.add_argument("--venue")
    p_index.add_argument("--result-level")
    p_index.add_argument("--oa-url")
    p_index.add_argument("--pdf-path")
    p_index.add_argument("--openalex-id")
    p_index.add_argument("--note")
    p_index.set_defaults(func=cmd_index)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
