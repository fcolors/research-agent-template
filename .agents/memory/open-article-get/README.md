# open-article-get memory

本目录只保存 **how to search**，不保存检索历史、已查论文、PDF、摘要缓存或阅读状态。

## 结构

- `INDEX.md`：检索配置导航。
- 其它 `.md`：按主题/项目组织的检索配置卡，可包含：
  - 主题关键词与 synonyms
  - include / exclude terms
  - 作者、机构、venue、年份限制
  - preferred sources（OpenAlex/arXiv/Crossref/Unpaywall/publisher OA page）
  - query expansion 提示
  - ranking / filtering 偏好
  - 可复用的领域检索脚本片段

## 与 skill 的分工

- 通用检索/下载/索引逻辑：`.agents/skills/open-article-get/scripts/oa_article.py`。
- 领域特定“怎么搜”：本目录。
- 长期文献资产（索引 + PDF）：`.refs/oa-article/`。
