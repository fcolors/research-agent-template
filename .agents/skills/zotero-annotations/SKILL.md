---
name: zotero-annotations
description: 读取本地 Zotero 文献 PDF 里的批注（高亮/下划线/笔记），按颜色和页码展示，增量输出省 token；可列出/拉取 Zotero PDF 附件，也可按批注精确位置（annotationPosition）从 PDF 提取高亮处前后句上下文，并导出全文 txt / PDF 副本。当用户问"某篇文献/集合里我标了什么、批注原文上下文是什么、前后几句怎么解释"、需要定位阅读进度、或把 Zotero 附件 PDF 拉到本地做深度分析时使用。
whenToUse: 科研取证阶段需要回顾 Zotero 批注、核对阅读进度、把用户标过的段落纳入证据链、读批注原文上下文、或拉取 Zotero PDF 附件做全文提取/深度分析时。默认只读元数据；--save-pdf 才复制 PDF；上下文模式需 PyMuPDF。
---

# Zotero 批注读取 + 上下文精确定位 + 附件拉取（DSH 版）

访问 Zotero 桌面版本地 API（`127.0.0.1:23119`）。**不写 Zotero 库、不改 PDF**。
- 批注/附件元数据：纯标准库。
- 上下文模式（精确定位/全文导出/PDF 副本）：需要 PyMuPDF，依赖清单见 `.agents/requirements/zotero-annotations.txt`。
- `--save-pdf DIR` 会把 PDF 附件复制到本地目录（用于深度分析），不修改 Zotero 里的 PDF。

## 前置条件（需用户在 Zotero 开启本地服务）

Zotero → 设置 → 高级(Advanced) → 服务器(Server) → 勾选
**"Allow other applications on this system to communicate with Zotero"** → 重启 Zotero。
验证：`curl http://127.0.0.1:23119/api/schema` 返回 JSON 即正常。

## 依赖（仅上下文模式）

```bash
python3 -m pip install -r .agents/requirements/zotero-annotations.txt
```

不进入上下文模式时无需安装；脚本会自动检测，缺依赖会报 `ERROR 500 DEPENDENCY_MISSING`。

## 脚本位置（相对本 skill 根）

```bash
python3 scripts/zotero_annotations.py <args>
```

**禁止**：直接 curl/WebFetch 访问 Zotero API、调用插件 zotero.py、修改 Zotero PDF 本体或写库。

## 命令参数

定位（必选其一）：

- `--key KEY` Zotero item key，直接定位，最快最精确
- `--query TEXT` 标题子串（大小写不敏感，Unicode 破折号已归一化）
- `--collection TEXT` 集合名（精确、大小写不敏感）；与 `--query` 连用

批注元数据模式（默认）：

- `--full` 忽略缓存，全量输出
- `--json` 原始 JSON（含 delta/reading/cache_path）
- `--no-color` 不按颜色分组
- `--cache-dir PATH` 显式指定缓存目录

附件能力：

- `--list-attachments` 只读列出该条目的 PDF 附件元数据（key/title/contentType/file URL），不下载
- `--save-pdf [DIR]` 把该条目的 PDF 附件复制到 DIR（缺省 `.zotero-pdf`）；不输出批注
- `--force` 与 `--save-pdf` 连用，覆盖已存在文件

上下文模式（任给其一即进入；需 PyMuPDF）：

> 定位策略：优先用 `annotationPosition` 的 rects 在 `page.get_text("dict")` 的行 bbox 上直接锁定命中行，再取同 block 前后行；只有 rects 缺失/坐标异常时才回退到整页文本字符串查找。

- `--color NAME|HEX` 只处理指定颜色批注（可多次：red / #ff6666）
- `--ann-key KEY` 只处理指定批注 key（可多次）
- `--before N / --after N` 高亮处前/后句数，默认 2/2（共 5 句）
- `--fulltext` 导出全文 txt 到缓存目录
- `--export-pdf` 复制 PDF 副本到缓存目录
- `--json` 上下文结果 JSON

## 增量与缓存（省 token，必须告知用户）

- **增量**：第一次读取全量建缓存；之后只打印"新增/更新/删除"的批注，已看过的不重复输出。
- **缓存目录优先级**：`--cache-dir`（显式）> 当前工作目录 `.zotero-annotations/` > 系统 temp。
- **必须向用户提示缓存路径**：STATUS 行有 `cache=路径`；落到 temp 时要明确说明"本次缓存放到了临时目录"。不要默默缓存。
- 想看全量：`--full`。

## 输出与汇报（按原样呈现，不润色）

- **成败汇报**：成功 stdout 有 `STATUS: OK | mode=first|incremental|full|list-attachments|save-pdf|context | ...`；
  失败 stderr 有 `[zotero-annotations] ERROR <码> <LABEL>: 文字`。进程退出码仅 0/1，具体原因**以文字为准**。
- **批注块（可 grep）**：每条固定 4 行
  ```text
  <<<ANN key=XXXX color=red hex=#ff6666 page=1782 type=highlight
  TEXT: 高亮文字
  COMMENT: 批注
  >>>ANN
  ```
- **上下文块（可 grep）**：
  ```text
  <<<CTX key=XXXX color=red page=3
  PHRASE: 高亮短语
  COMMENT: 批注
    [S-2] 前第2句
  >>> [S0] 所在句（含高亮）
    [S+1] 后第1句
  >>>CTX
  ```
  定位：`grep '^<<<ANN'` 全部 / `grep '^<<<CTX'` 上下文 / `grep 'color=red'` 按颜色 / `grep 'page=N'` 按页。

## 阅读定位（推测用户读到哪，不拉全文）

元数据模式自动输出 `### 阅读定位` 块：
- **方法2 最远标记**：批注页码最大的一条 = 读到的最后位置（有旧缓存时带"上次"对比）。
- **方法1 新增分布**：本次新增/更新批注的页码分布与范围 = 最近在读的区间。
- STATUS 行含 `reading=pageN`。

## 工作流

1. 只回顾批注：运行脚本**一次**（用 `--key` 或 `--query [--collection]`）。
2. 按输出原样呈现（增量在前，注明条数与缓存路径）。
3. 用户要"批注原文/前后几句"：用上下文模式，例如
   `python3 scripts/zotero_annotations.py --key XXXX --color red --before 2 --after 2`
4. 用户要"导出全文/PDF 副本"：`--fulltext --export-pdf`（产物在缓存目录，STATUS 行给出路径）。
5. 用户要把附件 PDF 拉到本地做深度分析：
   - 先 `--list-attachments` 确认附件；
   - 再 `--save-pdf .refs/zotero-pdf` 复制到本地；
   - 建议目标目录放 `.refs/` 或 `temp/`，不要放进 `.agents/`。

## 阻塞处理（以 stderr 文字里的 HTTP 风格码为准）

| 文本码 | 含义 | 处理 |
|---|---|---|
| 503 SERVICE_UNAVAILABLE | 端口/本地 API 未开 | 让用户按"前置条件"开启本地服务并重启 Zotero；**不要**用 zotero.py |
| 404 NOT_FOUND | 集合或条目未找到 | 转告脚本文字；集合不存在会列出可用集合名 |
| 300 MULTIPLE_CHOICES | 标题歧义 | 脚本列出候选 key，请用户用 `--key` 指定 |
| 422 UNPROCESSABLE_ENTITY | 条目无 PDF 附件 | 如实说明，可能只有网页快照 |
| 404 PDF_FILE_UNREACHABLE | Zotero 附件文件路径在本机不可达 | 确认 Zotero storage 与本脚本同机；远程/跨设备时不要伪装已拉取 |
| 500 DEPENDENCY_MISSING | 未安装 PyMuPDF | 执行 `python3 -m pip install -r .agents/requirements/zotero-annotations.txt` |

## 呈现给用户

- 原样引用高亮文字与批注，不自行润色。
- 遇到**半词高亮**（如 `e`、`prob`）：说明是 Zotero 存储的片段，建议用户在 Zotero 里核对，不要自己去读 PDF。
- 颜色语义：红 `#ff6666` 多为内容批注，黄/蓝多为生词标注；不擅自解读，除非用户确认。

## 局限与后续

- 上下文模式依赖 PyMuPDF；元数据/附件列表/附件复制只用标准库。
- 依赖 Zotero 桌面版本地 API 开启；附件文件路径需与脚本同机可达（Linux 服务器上需 Zotero 与本脚本同机，或把 storage 目录挂载到同机）。
- 上下文定位优先按 rect 锁定行，跨栏/双栏场景比整页字符串查找更稳；分句仍是规则方法，对图片型 PDF 可能失败，失败时输出"无法在页文本中定位该短语"。
- 机制通用：这套"定位→提取→格式化 + STATUS/ERROR 协议 + 增量缓存 + 附件拉取"可套用到其它数据源做新 skill。
