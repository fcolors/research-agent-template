---
name: zotero-annotations
description: 读取本地 Zotero 文献 PDF 里的批注（高亮/下划线/笔记），按颜色和页码展示；也可从 Zotero 中获取 PDF（经 zotero-pdf-bridge 只读），按批注精确位置读原文上下文（前后 N 句），导出全文 / PDF 副本。当用户问"某篇文献/某个集合里我标了什么、有哪些批注/标注/高亮"、"这条/这个颜色批注的原文上下文/前后几句/解释一下"、或要获取 Zotero 中的 PDF 时使用。增量输出，只打印新增/变化的批注，避免浪费 token。
---

# Zotero 批注读取（元数据 + 上下文 + 获取 PDF）

本 skill 与 `zotero-annotations-cli` **功能一致**（元数据 / 上下文 / 全文 / 导出 PDF 副本），
区别仅在于本 skill 直接运行 `.py`，而 CLI 打包成独立可执行文件。单一命令自动判定模式：
只给基础参数 → 元数据模式；给了上下文参数任一只 → 上下文模式（读 PDF 原文）。

```bash
python3 <skill目录>/scripts/zotero_annotations.py <args>
```

**只允许执行这条命令**，其余一律禁用（curl、插件 zotero.py、直接读取 PDF）。

## 依赖（元数据零第三方依赖；仅上下文模式需 PyMuPDF）

- **元数据模式 = 纯标准库**：只用 Python 标准库（argparse/base64/json/os/re/sys/tempfile/urllib），
  任何装了 Python 3 的机器直接跑即可，无需安装任何东西。
- **上下文模式（读 PDF 原文）需要 PyMuPDF + zotero-pdf-bridge 插件**：
  - 插件：Zotero → Plugins / Add-ons → Install Add-on From File → `zotero-pdf-bridge.xpi`
    （GitHub Releases 下载，详见 `zotero-pdf-bridge/README.md`）。
  - PyMuPDF：脚本先 `import pymupdf`，失败回退 `import fitz`，都没有则 `fitz=None`；
    此时元数据模式照常可用，只有上下文模式报 `ERROR 500 DEPENDENCY_MISSING`，提示安装：
    ```bash
    python3 -m pip install -r <skill目录>/requirements.txt
    ```

## 元数据模式（默认，不读 PDF）

脚本内部完成：**端口检查**（查 `/api/schema`）→ **只读** Zotero 本地 API 取批注元数据。

参数：
- 定位：`--query` 标题（模糊，Unicode 破折号已归一化）；`--collection` 集合名；`--key` item key（最快最精确）
- `--full` 忽略缓存全量输出；`--json` 原始 JSON；`--no-color` 不按颜色分组；`--cache-dir PATH` 显式缓存目录

## 上下文模式（给了上下文参数任一只即进入；读 PDF 原文）

经 `zotero-pdf-bridge` 的 `/pdf-bridge/<itemKey>` **只读**获取 PDF（base64），
不访问 Windows 文件系统（无 `/mnt`、无 `C:`、无 `~/Zotero/storage`）。

- `--color NAME|HEX` 只处理指定颜色（可多次：red / #ff6666）
- `--ann-key KEY` 只处理指定批注 key（可多次）
- `--before N / --after N` 上下文前/后句数，默认 2/2（共 5 句）
- `--fulltext` 导出全文 txt 到 `<cache>/<key>.txt`
- `--export-pdf` 导出 PDF 副本到 `<cache>/<key>.pdf`（可对接 PDF 阅读插件）
- 原理：用批注的 `annotationPosition`（精确矩形坐标）定位高亮处，输出所在句及前后 N 句。

## 增量与缓存

- **增量**：第一次读取全量；之后只打印"新增/更新/删除"的部分，已看过的内容不重复输出，省 token。
- **缓存目录优先级**：`--cache-dir`（显式指定）> 当前工作目录下 `.zotero-annotations/`（默认，跟随项目）> 系统 temp。
- **必须向用户提示缓存位置**：脚本 STATUS 行有 `cache=路径`、增量行也有"缓存:"；每次运行都要把缓存路径告诉用户，若落到 temp 要明确说明"本次缓存放到了临时目录"。不要默默缓存。
- 想看全量：`--full`。

## 输出与汇报（agent 据此向用户说明）

- **成败汇报**：成功时 stdout 有 `STATUS: OK | mode=annotate|context | ...`；失败时 stderr 有 `[zotero-annotations] ERROR <HTTP码> <LABEL>: 文字`。
- **批注块（元数据模式，可 grep）**：每条批注固定 4 行：
  ```text
  <<<ANN key=XXXX color=red hex=#ff6666 page=1782 type=highlight
  TEXT: 高亮文字
  COMMENT: 批注
  >>>ANN
  ```
  定位技巧：`grep '^<<<ANN'` 全部；`grep '^<<<ANN' | grep 'color=red'` 按颜色；`grep 'page=3'` 按页；`grep 'key=XXX'` 按条目。
- **上下文块（上下文模式，可 grep `<<<CTX`）**：
  ```text
  <<<CTX key=XXXX color=red page=1
  PHRASE: 高亮短语
  COMMENT: 批注
    [S-2] 前第2句
  >>> [S0] 所在句（含高亮）
    [S+1] 后第1句
  >>>CTX
  ```
- **阅读定位（元数据模式自动输出 `### 阅读定位`）**：方法2 最远标记（批注页码最大的一条）+
  方法1 新增分布（本次新增批注的页码范围），推测用户读到哪，不拉全文。STATUS 行含 `reading=pageN`。

## 工作流

1. 运行脚本**一次**（用 `--key` 或 `--query [--collection]`）。
2. 按输出原样呈现（增量在前，注明条数）；`--json` 时说明缓存路径。
3. 用户要"批注原文/前后几句/解释"：用上下文模式
   `python3 ...zotero_annotations.py --key XXXX --color red --before 2 --after 2`。
4. 用户要"导出全文 / PDF 副本"：`--fulltext --export-pdf`（产物在缓存目录，STATUS 行给出路径）。

## 阻塞处理（以 stderr 文字里的 HTTP 风格码为准）

| 文本码 | 含义 | 处理 |
|---|---|---|
| 503 SERVICE_UNAVAILABLE | 端口/本地 API 未开 | 让用户在 Zotero 里开启本地服务并重启（Settings→Advanced→Server→Allow...）。**不要**用 zotero.py |
| 404 NOT_FOUND | 集合或条目未找到 | 转告脚本给出的文字；集合不存在会列出可用集合名 |
| 300 MULTIPLE_CHOICES | 标题歧义 | 脚本列出候选 key，请用户用 `--key` 指定 |
| 422 UNPROCESSABLE_ENTITY | 条目无 PDF 附件 | 如实说明，可能只有网页快照 |
| 404 PDF_NOT_FOUND | PDF Bridge 取不到 PDF（未装插件/未同步/网页快照） | 让用户装 `zotero-pdf-bridge.xpi`（GitHub Releases → Zotero → Plugins → Install Add-on From File）后重试 |
| 500 INVALID_PDF | PDF Bridge 返回的数据不是有效 PDF（不以 `%PDF-` 开头） | 报告脚本输出，按 PDF Bridge 状态排查 |
| 500 DEPENDENCY_MISSING | 未安装 PyMuPDF | 执行 `python3 -m pip install -r <skill目录>/requirements.txt` |

## 呈现给用户

- 原样引用高亮文字与批注；不自行润色。
- 遇到**半词高亮**（如 `e`、`prob`、`ombining...`）：说明是 Zotero 存储的片段，建议用户在 Zotero 里核对，**不要**自己去读 PDF。
- 颜色语义：红色 `#ff6666` 多为内容批注，黄/蓝多为生词标注；不擅自解读，除非用户确认。
