# <你的主题> — 检索配置卡

> 这是"怎么搜"的配置示例；把命中文献的元数据写入 `.refs/oa-article/index.tsv`，不要把搜索历史写回这里。
> 使用：复制本文件为 `<主题>.md`，替换下方占位符为真实领域关键词，并在 `INDEX.md` 登记。

## 主题关键词
- <topic keyword 1>, <topic keyword 2>
- <method / technique keyword>
- <application / benchmark keyword>

## include / exclude terms
- include: "<核心词>", "<近义词>"
- exclude: "<无关词>"（除非做跨领域对比）

## 作者 / 机构 / venue / 年份
- 优先 <年份范围> 后的进展类文献；经典方法论文献只作历史锚点。
- venue 优先：<venue list>。
- 高相关课题组：<group names> 等。

## preferred sources
1. OpenAlex：discovery、DOI、OA 状态、引用关系。
2. arXiv：preprint PDF。
3. Crossref：DOI/正式发表核验。
4. Unpaywall：OA location。
5. publisher page：最终确认 version of record。

## query expansion 提示
- "<核心词>" → "<近义词 1>", "<近义词 2>"
- "<方法>" → "<别名>", "<缩写>"

## ranking / filtering 偏好
- 先近 5 年综述/进展，再按被引与 OA 可得性排序。
- 仅 arXiv 预印本可得的，标 `preprint`；有正式 DOI 但只能看摘要的标 `abstract`。
