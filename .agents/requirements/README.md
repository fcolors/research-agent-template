# .agents/requirements — 技能依赖清单

> 目的：让 `.agents/` 迁移到新环境后可以按需重建依赖，不污染主仓库环境。
> 原则：只有真正需要第三方库的 skill 才建 requirements；其余 skill 用标准库。

## 安装

```bash
# 从项目根目录
python3 -m pip install -r .agents/requirements/zotero-annotations.txt
```

建议使用项目已有虚拟环境（`requirements.txt` / `pyproject.toml` 已声明核心依赖）。

## 文件索引

| 文件 | 对应 skill | 依赖 | 需要时机 |
|---|---|---|---|
| `zotero-annotations.txt` | `.agents/skills/zotero-annotations/` | `pymupdf==1.24.10` | 仅上下文模式（精确定位/前后句/全文导出/PDF 副本） |
| （无文件） | `open-article-get` | 标准库 | 无需安装 |

## 复现说明

1. 先确保 Zotero 本地服务已开启（`curl http://127.0.0.1:23119/api/schema` 返回 JSON）。
2. 纯批注/附件拉取：
   ```bash
   cd .agents/skills/zotero-annotations
   python3 scripts/zotero_annotations.py --key XXXXX --list-attachments
   python3 scripts/zotero_annotations.py --key XXXXX --save-pdf .refs/zotero-pdf
   ```
3. 上下文模式（精确定位）：
   ```bash
   cd .agents/skills/zotero-annotations
   python3 scripts/zotero_annotations.py --key XXXXX --color red --before 2 --after 2
   python3 scripts/zotero_annotations.py --key XXXXX --fulltext --export-pdf
   ```
   如果提示 `DEPENDENCY_MISSING`，执行：
   ```bash
   python3 -m pip install -r .agents/requirements/zotero-annotations.txt
   ```
4. `open-article-get` 无需第三方依赖；检索/下载脚本 `scripts/oa_article.py` 用标准库。

## 来源说明

- 上下文模式（`annotationPosition` 精确定位）移植自开源 `zotero-annotations` 项目的 CLI 模式（MIT License），依赖 PyMuPDF。
- 本仓库只保留 Python 运行形态，不打包 exe；如需免 Python 分发，可用 PyInstaller + PyMuPDF 自行打包。
