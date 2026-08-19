#!/usr/bin/env python3
"""latex_project.py — scaffold and check a minimal LaTeX research project.

Usage:
  python3 latex_project.py init --dir <dir> [--title ...] [--author ...] \
      [--chapters ...] [--lang zh|en]
  python3 latex_project.py check --dir <dir>

The script is pure standard library and runs from any cwd.
Templates are read from ../assets relative to this file.
"""

import argparse
import re
import sys
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
ASSETS = SKILL_ROOT / "assets"

# Cite commands: \cite, \citet, \citep, \citeyear, \citeauthor, \citealp,
# \citealt, \citenum, \citetext; allow up to two optional arguments before the key list.
CITE_RE = re.compile(
    r"\\(?:cite|citet|citep|citealp|citealt|citeauthor|citeyear|citenum|citetext)"
    r"(?:\[[^\]]*\]){0,2}\{([^}]+)\}"
)
BIB_ENTRY_RE = re.compile(r"@(\w+)\s*[\(\{]\s*([^,\s]+)\s*,")
INCLUDE_RE = re.compile(r"\\(?:include|input)\{([^}]+)\}")
DOC_CLASS_RE = re.compile(r"\\documentclass(?:\[[^\]]*\])?\s*\{([^}]+)\}")
CHAPTER_RE = re.compile(r"\\chapter\s*\{")
MARKDOWN_HEADING_RE = re.compile(r"^\s*#{1,6}\s")
MARKDOWN_BOLD_ITALIC_RE = re.compile(r"(?<!\\)(\*\*|__)")
MARKDOWN_TASK_RE = re.compile(r"^\s*[-*]\s*\[[ xX]\]")
CJK_RE = re.compile(r"[\u3400-\u9fff\u3000-\u303f\uff00-\uffef]")
CHINESE_SUPPORT_RE = re.compile(
    r"\\usepackage(?:\[[^\]]*\])?\s*\{(?:ctex|xeCJK|CJK)\}"
    r"|\\documentclass(?:\[[^\]]*\])?\s*\{(?:ctexart|ctexrep|ctexbook)\}"
)

DEFAULT_CHAPTERS = ["introduction", "methods", "results", "discussion", "conclusion"]


def eprint(msg: str) -> None:
    print(msg, file=sys.stderr)


def strip_tex_comments(text: str) -> str:
    """Remove TeX comments from text (line-wise, ignoring escaped percent)."""
    out_lines = []
    for line in text.splitlines():
        cut = None
        for i, ch in enumerate(line):
            if ch == "%" and (i == 0 or line[i - 1] != "\\"):
                cut = i
                break
        out_lines.append(line if cut is None else line[:cut])
    return "\n".join(out_lines)


def rel_to_project(project_dir: Path, path: Path) -> str:
    try:
        return str(path.relative_to(project_dir))
    except ValueError:
        return str(path)


def slug_to_title(slug: str) -> str:
    return slug.replace("-", " ").replace("_", " ").strip().title()


def chapter_filename(index: int, slug: str) -> str:
    return f"ch{index:02d}-{slug}.tex"


def build_includes(chapters):
    lines = []
    for i, slug in enumerate(chapters, 1):
        lines.append(f"\\include{{chapters/{chapter_filename(i, slug)}}}")
    return "\n".join(lines)


def cmd_init(args) -> int:
    project_dir = Path(args.dir).resolve()
    if project_dir.exists() and any(project_dir.iterdir()):
        if not args.force:
            eprint(f"[latex-project] ERROR init: directory not empty: {project_dir}")
            eprint("[latex-project] use --force to overwrite template files in place")
            return 1
    project_dir.mkdir(parents=True, exist_ok=True)
    chapters_dir = project_dir / "chapters"
    chapters_dir.mkdir(exist_ok=True)

    slugs = [s.strip() for s in args.chapters.split(",") if s.strip()]
    if not slugs:
        eprint("[latex-project] ERROR init: --chapters must contain at least one slug")
        return 1
    seen = set()
    for slug in slugs:
        if slug in seen:
            eprint(f"[latex-project] ERROR init: duplicate chapter slug: {slug}")
            return 1
        seen.add(slug)

    if args.lang == "zh":
        lang_packages = "\\usepackage{ctex}"
    else:
        lang_packages = "\\usepackage[T1]{fontenc}\n\\usepackage[utf8]{inputenc}"

    main_template = (ASSETS / "main.tex").read_text(encoding="utf-8")
    main_text = (
        main_template
        .replace("__LANG_PACKAGES__", lang_packages)
        .replace("__TITLE__", args.title)
        .replace("__AUTHOR__", args.author)
        .replace("__DATE__", args.date)
        .replace("__INCLUDES__", build_includes(slugs))
    )
    (project_dir / "main.tex").write_text(main_text, encoding="utf-8")
    print(f"[latex-project] language: {args.lang} "
          f"({'ctex + xelatex' if args.lang == 'zh' else 'fontenc + pdflatex'})")

    chapter_template = (ASSETS / "chapter.tex").read_text(encoding="utf-8")
    for i, slug in enumerate(slugs, 1):
        chapter_path = chapters_dir / chapter_filename(i, slug)
        chapter_text = chapter_template.replace("__CHAPTER_TITLE__", slug_to_title(slug))
        chapter_path.write_text(chapter_text, encoding="utf-8")

    refs_template = (ASSETS / "refs.bib").read_text(encoding="utf-8")
    (project_dir / "refs.bib").write_text(refs_template, encoding="utf-8")

    print(f"[latex-project] initialized: {project_dir}")
    print(f"[latex-project] chapters: {len(slugs)}")
    for i, slug in enumerate(slugs, 1):
        print(f"  chapters/{chapter_filename(i, slug)}")
    print("[latex-project] next: python3 scripts/latex_project.py check --dir "
          f"{project_dir}")
    return 0


def collect_tex_files(project_dir: Path):
    return sorted(project_dir.rglob("*.tex"))


def resolve_includes(project_dir: Path, start: Path) -> tuple:
    r"""Resolve \include/\input recursively.

    Returns (missing, reachable_tex_files). Paths are relative to project_dir.
    """
    missing = []
    reachable = []
    visited = set()

    def visit(file: Path):
        if file in visited:
            return
        visited.add(file)
        rel_file = rel_to_project(project_dir, file)
        try:
            text = strip_tex_comments(file.read_text(encoding="utf-8"))
        except OSError as exc:
            missing.append(f"{rel_file}: cannot read ({exc})")
            return
        reachable.append(file)
        for raw in INCLUDE_RE.finditer(text):
            target = raw.group(1).strip()
            if not target:
                missing.append(f"{rel_file}: empty \\include/\\input")
                continue
            base = file.parent
            candidate = base / target
            if candidate.suffix != ".tex":
                candidate = base / f"{target}.tex"
            if not candidate.exists():
                # Also try project root (main.tex convention may be root-relative).
                alt = project_dir / target
                if alt.suffix != ".tex":
                    alt = project_dir / f"{target}.tex"
                if alt.exists():
                    candidate = alt
                else:
                    missing.append(f"{rel_file}: "
                                   f"\\include/\\input target not found: {target}")
                    continue
            visit(candidate.resolve())

    visit(start.resolve())
    return missing, [p.resolve() for p in reachable]


def cmd_check(args) -> int:
    project_dir = Path(args.dir).resolve()
    if not project_dir.exists():
        eprint(f"[latex-project] ERROR check: directory not found: {project_dir}")
        return 1

    errors = []
    warnings = []

    main_tex = project_dir / "main.tex"
    refs_bib = project_dir / "refs.bib"
    if not main_tex.exists():
        eprint("[latex-project] ERROR check: main.tex not found")
        return 1
    if not refs_bib.exists():
        eprint("[latex-project] ERROR check: refs.bib not found")
        return 1

    try:
        main_text = strip_tex_comments(main_tex.read_text(encoding="utf-8"))
    except OSError as exc:
        eprint(f"[latex-project] ERROR check: cannot read main.tex ({exc})")
        return 1

    # Documentclass and chapter splitting.
    doc_match = DOC_CLASS_RE.search(main_text)
    doc_class = doc_match.group(1).strip() if doc_match else ""
    if not doc_class:
        warnings.append("main.tex: no \\documentclass found")
    else:
        print(f"[latex-project] documentclass: {doc_class}")

    # Resolve includes recursively from main.tex.
    missing, reachable = resolve_includes(project_dir, main_tex)
    for item in missing:
        errors.append(item)
    reachable_rel = []
    for p in reachable:
        if p == main_tex.resolve():
            continue
        try:
            reachable_rel.append(p.relative_to(project_dir))
        except ValueError:
            warnings.append(f"{p}: \\include/\\input target outside project directory")
    if len(reachable_rel) < 2:
        errors.append("main.tex: expected at least 2 \\include'd chapter files in chapters/")

    # Gather all tex files for citation and markdown checks.
    all_tex = collect_tex_files(project_dir)

    # Citation keys in all .tex files.
    cite_keys = set()
    for tex in all_tex:
        try:
            text = strip_tex_comments(tex.read_text(encoding="utf-8"))
        except OSError:
            continue
        for raw in CITE_RE.finditer(text):
            for key in raw.group(1).split(","):
                key = key.strip()
                if key:
                    cite_keys.add(key)

    # BibTeX keys in refs.bib.
    try:
        bib_text = refs_bib.read_text(encoding="utf-8")
    except OSError as exc:
        eprint(f"[latex-project] ERROR check: cannot read refs.bib ({exc})")
        return 1
    bib_keys = {}
    for raw in BIB_ENTRY_RE.finditer(bib_text):
        if raw.group(1).strip().lower() == "comment":
            continue
        key = raw.group(2).strip()
        bib_keys.setdefault(key, 0)
        bib_keys[key] += 1

    for key, count in bib_keys.items():
        if count > 1:
            errors.append(f"refs.bib: duplicate BibTeX key: {key} (x{count})")

    for key in sorted(cite_keys):
        if key not in bib_keys:
            errors.append(f"citation with no BibTeX entry: {key}")

    for key in sorted(bib_keys):
        if key not in cite_keys:
            warnings.append(f"refs.bib: BibTeX entry not cited in .tex: {key}")

    # Markdown leakage and chapter checks.
    has_cjk = False
    for tex in all_tex:
        rel = tex.relative_to(project_dir)
        try:
            stripped = strip_tex_comments(tex.read_text(encoding="utf-8"))
        except OSError:
            continue
        lines = stripped.splitlines()
        if CJK_RE.search(stripped):
            has_cjk = True
        in_chapters_dir = rel.parts[0] == "chapters"
        for lineno, line in enumerate(lines, 1):
            if MARKDOWN_HEADING_RE.match(line):
                errors.append(f"{rel}:{lineno}: Markdown heading in .tex: {line.strip()}")
            if MARKDOWN_BOLD_ITALIC_RE.search(line):
                warnings.append(f"{rel}:{lineno}: possible Markdown bold/italic marker: "
                                f"{line.strip()}")
            if MARKDOWN_TASK_RE.match(line):
                warnings.append(f"{rel}:{lineno}: possible Markdown task list: "
                                f"{line.strip()}")
        if in_chapters_dir and doc_class in {"report", "book", "ctexrep", "ctexbook"}:
            if not CHAPTER_RE.search("\n".join(lines)):
                warnings.append(f"{rel}: report/book chapter file without \\chapter{{}}")

    # Chinese text requires a Chinese-capable package/documentclass.
    if has_cjk and not CHINESE_SUPPORT_RE.search(main_text):
        errors.append("main.tex: CJK text found but no Chinese support package "
                      "(use \\usepackage{ctex} or xelatex + xeCJK, or --lang zh with init)")

    # Every non-main .tex file should be reachable from main.tex.
    all_rel = {p.relative_to(project_dir) for p in all_tex}
    reachable_set = {p.relative_to(project_dir) for p in reachable}
    for rel in sorted(all_rel - reachable_set):
        if rel.parts[0] not in {"main.tex"}:
            warnings.append(f"{rel}: .tex file not \\include/\\input-reachable from main.tex")

    # Report.
    print(f"[latex-project] checked: {project_dir}")
    print(f"[latex-project] tex files: {len(all_tex)}; cite keys: {len(cite_keys)}; "
          f"bib entries: {len(bib_keys)}; reachable includes: {len(reachable_rel)}")

    for warning in warnings:
        print(f"  WARNING: {warning}")
    for error in errors:
        eprint(f"  ERROR: {error}")

    if errors:
        eprint("[latex-project] CHECK RESULT: FAIL")
        return 1
    print("[latex-project] CHECK RESULT: PASS")
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        prog="latex_project.py",
        description="Scaffold and check a minimal chapter-split LaTeX research project.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_init = sub.add_parser("init", help="create a new LaTeX project skeleton")
    p_init.add_argument("--dir", required=True, help="project directory to create")
    p_init.add_argument("--title", default="Research Report")
    p_init.add_argument("--author", default="")
    p_init.add_argument("--date", default="\\today")
    p_init.add_argument("--chapters", default=",".join(DEFAULT_CHAPTERS),
                        help="comma-separated chapter slugs (default: introduction,methods,"
                             "results,discussion,conclusion)")
    p_init.add_argument("--lang", choices=["zh", "en"], default="zh",
                        help="document language: zh loads ctex and compiles with xelatex; "
                             "en loads fontenc/inputenc and compiles with pdflatex "
                             "(default: zh)")
    p_init.add_argument("--force", action="store_true",
                        help="overwrite template files if the directory is not empty")
    p_init.set_defaults(func=cmd_init)

    p_check = sub.add_parser("check", help="validate an existing LaTeX project")
    p_check.add_argument("--dir", required=True, help="project directory to check")
    p_check.set_defaults(func=cmd_check)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
