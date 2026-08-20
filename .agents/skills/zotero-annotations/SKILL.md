---
name: zotero-annotations
description: 读取本地 Zotero 文献 PDF 里的批注（高亮/下划线/笔记），按颜色和页码展示。当用户问"某篇文献/某个集合里我标了什么、有哪些批注/标注/高亮"时使用。增量输出，只打印新增/变化的批注，避免浪费 token。本 skill 只读批注**元数据**；如需"看批注的原文上下文（前后几句）"，请用配套的 zotero-annotations-cli skill（读 PDF 原文需 zotero-pdf-bridge 插件）。
---

# Zotero 批注读取

## 两条命令（严格分工）

### 命令1：批注元数据（默认，只读，无审批）

```bash
python3 <skill目录>/scripts/zotero_annotations.py <args>
```

只允许执行这条命令取批注，其余一律禁用（curl、插件 zotero.py、fulltext、直接读取 PDF）。

**零依赖**：本脚本只用 Python 标准库（argparse/datetime/json/os/sys/tempfile/urllib），
任何装了 Python 3 的机器直接 `python3 .../zotero_annotations.py <args>` 即可，无需
安装任何第三方库、无需 PyMuPDF（本 skill 不读 PDF）。若报 `ModuleNotFoundError`，
说明运行环境缺失标准库（几乎不可能），按报错排查即可。

脚本内部完成：**端口检查**（查 `/api/schema`，不可用则 exit 2）→ **只读** Zotero 本地 API 取批注元数据。

参数：
- `--query` 标题（模糊，Unicode 破折号已归一化）；`--collection` 集合名；`--key` item key（最快最精确）
- `--full` 忽略缓存全量输出；`--json` 原始 JSON；`--no-color` 不按颜色分组

## 增量与缓存
- **增量**：第一次读取全量；之后只打印"新增/更新/删除"的部分，已看过的内容不重复输出，省 token。
- **缓存目录优先级**：`--cache-dir`（显式指定）> 当前工作目录下 `.zotero-annotations/`（默认，跟随项目）> 系统 temp。
- **必须向用户提示缓存位置**：脚本 STATUS 行有 `cache=路径`、增量行也有"缓存:"；每次运行都要把缓存路径告诉用户，若落到 temp 要明确说明"本次缓存放到了临时目录"。不要默默缓存。
- 想看全量：`--full`。

## 输出与汇报（agent 据此向用户说明）
- **成败汇报**：成功时 stdout 有 `STATUS: OK | mode=first|incremental|full | annotations=N | new_updated=N | removed=N | cache=路径`；失败时 stderr 有 `[zotero-annotations] ERROR ...`。
- **错误文字（HTTP 风格码，人人可懂）**：失败时 stderr 直接输出可读文字，形如 `ERROR 404 NOT_FOUND: 没有匹配标题 'xxx' 的条目`。进程退出码仅 `0` 成功 / `1` 失败，具体原因**以文字为准**，不要向用户解释数字。
- **批注块（可 grep 定位）**：每条批注固定 4 行：
  ```text
  <<<ANN key=XXXX color=red hex=#ff6666 page=1782 type=highlight
  TEXT: 高亮文字
  COMMENT: 批注
  >>>ANN
  ```
  定位技巧：`grep '^<<<ANN'` 全部；`grep '^<<<ANN' | grep 'color=red'` 按颜色；`grep 'page=3'` 按页；`grep 'key=XXX'` 按条目。
- 汇报时说明：读取成功/失败、模式（首次/增量/全量）、条数与缓存路径。

## 阅读定位（推测当前读到哪，AGENT 快速定位）
脚本**自动**输出 `### 阅读定位` 块，两种方法互补，**不拉取全文**（纯批注元数据推导）：

- **方法2 最远标记**：全部批注里页码最大的一条 = 用户读到的最后位置。
  如 `最远标记: 第 5 页 (key=ASDFGHK, 共 64 条批注)  [上次: 第 3 页]`（有旧缓存且进度变化时带"上次"对比）。
- **方法1 新增分布**：本次新增/更新批注的页码分布与范围 = 用户最近在读的区间。
  如 `新增分布: 3 条新增/更新，页码 [4, 4, 5]，范围 4–5 页`。无新增时显示"(本次无新增/更新)"。

**AGENT 用法**：
- 用 `grep '阅读定位'` 定位整块；STATUS 行含 `reading=pageN`；`--json` 含 `reading`（本次）与 `reading_prev`（上次缓存）。
- 组合两方法判断进度：`method1_delta` 告诉你最近新增标在哪几页，`method2_farthest` 告诉整体最远到哪；两者接近说明在顺序读，相差大说明回头补充或跳读。
- `reading` 会写入缓存（缓存 JSON 顶层），下次运行即可跨会话"对比"进度。
- 用户要读原文/找 PDF 段落：仍按下方工作流第 3 条处理，**不要**用阅读定位替代全文。

## 工作流
1. 运行脚本**一次**（用 `--key` 或 `--query [--collection]`）。
2. 按输出原样呈现（增量在前，注明条数）；`--json` 时说明缓存路径。
3. 用户要"原文/PDF 段落/上下文"：**只有**在用户明确要求看批注原文上下文（前后几句）时，
   改用配套 skill **`zotero-annotations-cli`** 的上下文模式（`--color` / `--ann-key` /
   `--before/--after` 等），并说明它需要读 PDF 原文（依赖 `zotero-pdf-bridge` 插件）。
   本 skill 的脚本**只读批注元数据，不提供** `zotero_context.py`（旧版已并入 CLI）。

### 需要"原文上下文"时 → 用 zotero-annotations-cli（读 PDF）

当用户说"看某条/某颜色批注的原文上下文/前后几句/解释一下"时，改用配套 skill：

```bash
zotero_annotations_cli --key <item_key> [--color red|blue|...] [--ann-key <ann_key>] [--before 2] [--after 2]
```

- CLI 通过 `zotero-pdf-bridge` 的 `/pdf-bridge/<itemKey>` **只读**获取 PDF（base64），
  不访问 Windows 文件系统（无 `/mnt`、无 `C:`、无 `~/Zotero/storage`）。
- 原理：用批注的 `annotationPosition`（精确矩形坐标）定位高亮处，输出所在句及前后 N 句（默认各 2 句，共 5 句）。
- 参数：`--color`（颜色名或 hex，可多次）、`--ann-key`（批注 key，可多次）、`--before/--after`（句数）、`--fulltext`（导出全文 txt 到 `<cache>/<key>.txt`）、`--export-pdf`（导出 PDF 副本到 `<cache>/<key>.pdf`）。
- 输出格式（可 grep `<<<CTX` 定位）：
  ```text
  <<<CTX key=XXXX color=red page=1
  PHRASE: 高亮短语
  COMMENT: 批注
    [S-2] 前第2句
    [S-1] 前第1句
  >>> [S0] 所在句（含高亮）
    [S+1] 后第1句
    [S+2] 后第2句
  >>>CTX
  ```
- 局限：分句与定位基于文本流，跨栏排版/图片型 PDF 可能定位失败（会如实标注"无法定位"）。同一短语在标题与正文重复出现时，用锚点行就近定位，通常取到正文出现处。
- **汇报**：说明读的是原文、条数、以及 `--fulltext/--export-pdf` 的导出路径（若有）。

## 阻塞处理（以 stderr 文字里的 HTTP 风格码为准）
| 文本码 | 含义 | 处理 |
|---|---|---|
| 503 SERVICE_UNAVAILABLE | 端口/本地 API 未开 | 让用户在 Zotero 里开启本地服务并重启（Settings→Advanced→Server→Allow...）。**不要**用 zotero.py |
| 503 SERVICE_UNAVAILABLE | 端口/本地 API 未开 | 让用户在 Zotero 里开启本地服务（编辑→设置→高级→设置编辑器→extensions.zotero.httpServer.enabled）设置为true。**不要**用 zotero.py |
| 404 NOT_FOUND | 集合或条目未找到 | 转告脚本给出的文字；集合不存在会列出可用集合名 |
| 300 MULTIPLE_CHOICES | 标题歧义 | 脚本列出候选 key，请用户用 `--key` 指定 |
| 422 UNPROCESSABLE_ENTITY | 条目无 PDF 附件 | 如实说明，可能只有网页快照 |

## 呈现给用户
- 原样引用高亮文字与批注；不自行润色。
- 遇到**半词高亮**（如 `e`、`prob`、`ombining...`）：说明是 Zotero 存储的片段，建议用户在 Zotero 里核对，**不要**自己去读 PDF。
- 颜色语义：红色 `#ff6666` 多为内容批注，黄/蓝多为生词标注；不擅自解读，除非用户确认。
