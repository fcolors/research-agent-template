---
name: latex-research-writing
description: 把研究/调研/综述的最终成果写成极简、可移植、可编译的 LaTeX 项目：main.tex 总入口、chapters/ 按章拆分、refs.bib 统一维护 BibTeX 数据库，正文只用 \cite/\citep/\citet 做学术引用。当研究模式结束进入交付阶段、用户要求输出 LaTeX/可移植排版/学术引用/按章拆稿，或需要把 Markdown 研究笔记转成 LaTeX 时使用。
whenToUse: 交付论文、综述、调研报告时；用户并未明确以Markdown交付；需要投稿、版本化或生成可编译 PDF；把既有 Markdown 草稿迁移为 LaTeX 时。
---

# LaTeX 研究写作（Latex Research Writing）

> 目标：研究模式的最终交付物**不是 Markdown 笔记**，而是一个**最小、可移植、可编译、按章拆分、引用可对账**的 LaTeX 项目。
> 本 skill 只定义最终写作形态与机器检查，不替代证据纪律、审稿、红黑打磨。先完成证据抽取与审稿，再进入本 skill 写作。

## 0. 不变量（MUST）

1. 最终交付物必须是 LaTeX 项目，**不得**是单个 Markdown/PDF 草稿或一长段 Markdown 文本。
2. 必须包含 `main.tex`（唯一主编译入口）。
3. 正文必须**按章拆分**到 `chapters/`，每章一个 `.tex` 文件；`main.tex` 只保留 preamble、目录、`\include` 和参考文献入口。
4. 所有引用必须使用 `\cite` / `\citep` / `\citet` 等 LaTeX 引用命令；**禁止**手写参考文献格式（如 `(Smith et al., 2021)`）。
5. 所有被引文献必须进入 `refs.bib`（BibTeX 数据库），正文中的每个 cite key 都必须能在 `refs.bib` 中找到。
6. 交付前必须通过 `latex_project.py check` 和一次完整编译；编译失败不得交付。
7. `.tex` 文件内**禁止**出现 Markdown 语法（`#` 标题、`**`、`__`、`- [ ]` 等）。
8. 正文文本保持**极简**：只用 report/book + 必需包；不堆砌自定义宏、颜色、目录树、花哨模板。

## 1. 项目结构

```text
latex-project/
├── main.tex                       # 唯一主编译入口：documentclass + 必需包 + \include + 参考文献
├── refs.bib                       # BibTeX 数据库：所有被引文献集中在这里
└── chapters/
    ├── ch01-introduction.tex      # 每章一个文件
    ├── ch02-methods.tex
    ├── ch03-results.tex
    ├── ch04-discussion.tex
    └── ch05-conclusion.tex
```

- 章节文件命名：`chNN-slug.tex`，`NN` 从 `01` 开始两位编号；slug 用英文小写连字符。
- 可以按需增删章节，但**至少 2 章**，且不得把所有正文塞进 `main.tex` 来绕过拆章。
- 草稿期允许保留 Markdown 工作笔记，但必须放在 `notes/` 或项目外；`chapters/`、`main.tex`、`refs.bib` 内不得出现 Markdown 笔记。

## 2. main.tex 最小模板

中文项目（默认，`init --lang zh`）用 `ctex`，编译走 `xelatex`：

```latex
\documentclass[11pt]{report}
\usepackage{ctex}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage[numbers,sort&compress]{natbib}
\usepackage[hidelinks]{hyperref}

\title{<中文标题>}
\author{<作者>}
\date{\today}

\begin{document}
\maketitle
\tableofcontents

\include{chapters/ch01-introduction}
\include{chapters/ch02-methods}
\include{chapters/ch03-results}
\include{chapters/ch04-discussion}
\include{chapters/ch05-conclusion}

\bibliographystyle{plainnat}
\bibliography{refs}
\end{document}
```

英文项目（`init --lang en`）用 `fontenc + inputenc`，编译走 `pdflatex`：

```latex
\documentclass[11pt]{report}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage{amsmath,amssymb}
\usepackage{graphicx}
\usepackage[numbers,sort&compress]{natbib}
\usepackage[hidelinks]{hyperref}
...
```

约束：
- **中文正文必须加载 `\usepackage{ctex}`**（或 `xeCJK`）；`latex_project.py check` 检测到 CJK 文本但 main.tex 无中文支持包时直接 FAIL。
- 文献管理统一用 `natbib` + BibTeX；`\bibliographystyle{plainnat}`、`\bibliography{refs}` 放在 `\end{document}` 前。
- `\include` 只放 `chapters/` 下的章节文件；除非有明确需要，不得在 main.tex 中直接写正文段落。
- 图片使用 `\includegraphics` 且放在 `figures/`；表格用 `table` 环境；这两者不是拆章或引用的替代。

## 3. 章节文件模板

```latex
\chapter{Introduction}

Introductory paragraph. ... \citep{Smith2021Quantum}.
```

- 每章以 `\chapter{...}` 开头（documentclass 为 report/book 时）；章内用 `\section`、`\subsection` 组织。
- 段落保持**最小格式化**：只保留正文、章节命令、数学、表格、图和引用命令；不贴整段 Markdown 转换残留（如 `###`、`- ` 列表符号改用手动 `itemize`/`enumerate`，或直接写成句子）。
- 章节文件内不得出现 `\bibliography`、`\bibliographystyle`（这些只在 main.tex）。
- 章节文件内不得出现 `\bibitem`（手写 thebibliography 环境）。

## 4. 引用与 BibTeX 规则

### 4.1 引用命令

- 括号引用：`\citep{Smith2021Quantum}`。
- 文本引用：`\citet{Smith2021Quantum}` 或 `\citet[p.~5]{Smith2021Quantum}`。
- 多篇：`\citep{Smith2021Quantum,Doe2022Nature}`。
- 年份/作者单独出现时用 `\citeyear` / `\citeauthor`，不得手打年份或作者名来伪造引用。

### 4.2 BibTeX key 规范

- key 形如 `FirstAuthorLastNameYearFirstDistinctWord`，例如 `Smith2021Quantum`。
- 同作者同年用 `Smith2021a`、`Smith2021b`，并在 `refs.bib` 中按字母区分。
- key 只允许字母、数字、连字符、下划线；不得有空格、逗号、引号。

### 4.3 refs.bib 条目规范

- 每条必须含：author/editor、title、year、booktitle/journal、publisher/school/institution 中适用的字段，以及 `doi` 或 `url` 至少其一。
- 期刊论文用 `@article`；会议论文用 `@inproceedings`；预印本用 `@misc` 并写 `eprint` 或 `url`；书籍/学位论文/技术报告按标准类型。
- **禁止**出现字段值为空、`TODO`、`placeholder` 的条目。
- **禁止**在正文里用注释或文字代替 BibTeX 条目（如 `% TODO: add Smith 2021` 不作为引用）。
- 每条 key 在 `refs.bib` 中唯一；`latex_project.py check` 会查重。

### 4.4 维护方式

- 新增引用时：先在 `refs.bib` 加条目，再在正文用 `\citep` / `\citet` 引用。
- 删除正文引用时：先删除正文 cite 命令，再决定是否从 `refs.bib` 移除（未被引用的条目是允许的，但会在 check 中产生 WARNING）。
- 每轮写作结束前运行：
  ```bash
  python3 scripts/latex_project.py check --dir <latex-project>
  ```

## 5. 写作流程

1. **确认章节划分**：按研究目标列 `chapters/` 清单（2–8 章为宜；超过 8 章先考虑是否该合并或改 report 为 book）。
2. **初始化或手工创建**：
   ```bash
   cd .agents/skills/latex-research-writing
   # 中文项目（默认 --lang zh）
   python3 scripts/latex_project.py init --dir ../../../latex-project \
     --title "中文标题" --author "作者" \
     --chapters introduction,methods,results,discussion,conclusion
   # 英文项目
   python3 scripts/latex_project.py init --dir ../../../latex-project \
     --lang en --title "Title" --author "Author" \
     --chapters introduction,methods,results,discussion,conclusion
   ```
   或由 agent 用 `str_replace_editor` 按模板手工创建 `main.tex`、`chapters/`、`refs.bib`。
3. **逐章写作**：每次只写一章；写完一章立刻把其中每个 cite key 与 `refs.bib` 对账。
4. **全量检查**：
   ```bash
   python3 scripts/latex_project.py check --dir <latex-project>
   ```
   必须 `PASS`。
5. **编译**：
   ```bash
   cd <latex-project>
   # 中文项目：xelatex + ctex
   latexmk -xelatex -interaction=nonstopmode main.tex
   # 英文项目：pdflatex
   latexmk -pdf -interaction=nonstopmode main.tex
   ```
   或手动：
   ```bash
   # 中文
   xelatex main.tex && bibtex main && xelatex main.tex && xelatex main.tex
   # 英文
   pdflatex main.tex && bibtex main && pdflatex main.tex && pdflatex main.tex
   ```
   编译失败时：读 `.log` 错误 → 修 `.tex`/`.bib` → 重新 check → 重新编译，直到干净。
6. **交付**：交付 `main.tex`、`chapters/*.tex`、`refs.bib`，以及可选 PDF；不得只交付 Markdown 转贴的文本。

## 6. 机器检查（封闭规则）

`scripts/latex_project.py check` 强制验证以下项：

| 检查 | 失败后果 |
|---|---|
| `main.tex` 存在，且为唯一主编译入口 | FAIL |
| `\include` / `\input` 的文件都存在（递归） | FAIL |
| 所有 `.tex` 中 cite key 在 `refs.bib` 中均有条目 | FAIL |
| `refs.bib` 中 key 无重复 | FAIL |
| `.tex` 中无 Markdown 标题（`#` 到 `######`） | FAIL |
| 检测到 CJK 文本时，`main.tex` 必须加载 `ctex`/`xeCJK`/`CJK` 或使用 `ctexart`/`ctexrep`/`ctexbook` | FAIL |
| 章节按 `chapters/` 拆分（存在至少 2 个 `\include` 的章节文件） | FAIL |
| report/book 类时每章以 `\chapter{` 开头 | WARNING |
| `.tex` 中出现 `**` / `__` / `- [ ]` 等 Markdown 残留 | WARNING |
| `refs.bib` 中有条目未被正文引用 | WARNING |

- FAIL = 交付阻断；WARNING = 必须肉眼确认，能清则清。
- 机器检查不得被 agent 临场关闭或降低标准。

## 7. 与红黑审稿的关系

- 先经 `paper-red-black-review` 审稿通过，再按本 skill 写成 LaTeX；写作过程中新增的 claim 仍需可追溯。
- 成稿后可用 `peer-reviewer` 对 LaTeX 正文做格式与写作质量审读；该审读不改变本 skill 的硬规则。

## 8. 禁止事项

- 禁止把 Markdown 原样贴进 `.tex`，仅把标题符号换成 LaTeX 命令但保留 Markdown 列表/粗体/代码块。
- 禁止在章节文件里使用 `\bibliography`、`\bibliographystyle`、`thebibliography`。
- 禁止用 `\href` 手写参考文献列表代替 BibTeX。
- 禁止把全部正文写在 `main.tex` 的 `\begin{document}` 内来绕过拆章。
- 禁止交付未通过 `check` 或未编译通过的项目。
- 禁止在 `.tex` 中留下 `TODO`、`FIXME`、空章节而不标注 `\chapter{}`（空章直接不创建）。
