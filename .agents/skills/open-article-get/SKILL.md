---
name: open-article-get
description: 检索并获取合法开放获取（OA）的学术论文/期刊文章，优先确认 DOI 与正式发表版本；维护轻量本地元数据索引，避免重复检索与重复阅读。检索策略由 .agents/memory/open-article-get 提供，PDF 与长期文献记录存放在 .refs/oa-article/。
whenToUse: 需要根据关键词/题名/作者/DOI/arXiv ID 找到论文、核验正式发表信息、判断可合法获取到 abstract/preprint/published 哪一层、或下载合法 OA PDF 时。
---
# open-article-get

用于 open scholarly article retrieval。目标不是构建复杂文献管理系统，而是稳定回答：

1. 文献是否找到了？
2. 是否有可确认的 bibliographic reference？
3. 是否有 DOI / published DOI？
4. 当前合法可获取层级：abstract / preprint / published？

优先合法 OA，不绕过付费墙。

> 特别注意：优先选择后台运行模式，避免思维链阻塞。在不降低审查质量的情况下，也尽量减少使用subagent实现的方法。

## Boundary

本 skill 负责：

- 检索论文并核验元数据（OpenAlex、arXiv、Crossref、Unpaywall、publisher OA page）。
- 判断 preprint 与 published article 的关系。
- 优先定位正式发表 DOI 与合法 OA full text。
- 将长期有价值的元数据写入 `.refs/oa-article/index.tsv`。
- 将 OA PDF 放入 `.refs/oa-article/pdf/`。
- 检索前先查本地索引，避免重复检索和重复阅读。

本 skill 不负责：

- 在 `.agents/memory/` 记录检索历史；memory 只放 **how to search** 配置。
- 把 PDF、摘要、检索结果缓存进 `.agents/`。
- 系统性阅读全文、写 literature review 或长期笔记。
- 管理 Zotero collection/tag/citation key（那是 zotero-annotations / 库卫生门卫的职责）。
- 绕过 paywall、登录、验证码。

## Scripts

通用脚本在本 skill 的 `scripts/` 下，以 skill 根目录为基准执行：

```bash
python3 scripts/oa_article.py lookup --doi "10.xxxx/yyyy"      # 核验 DOI/题名/arXiv
python3 scripts/oa_article.py lookup --arxiv "1706.03762"
python3 scripts/oa_article.py lookup --title "Attention Is All You Need"
python3 scripts/oa_article.py fetch --arxiv "1706.03762" --out .refs/oa-article/pdf
python3 scripts/oa_article.py fetch --doi "10.xxxx/yyyy" --out .refs/oa-article/pdf
python3 scripts/oa_article.py index --tsv .refs/oa-article/index.tsv --find "10.xxxx"
python3 scripts/oa_article.py index --tsv .refs/oa-article/index.tsv --upsert --doi "..." --title "..."
```

脚本约定：

- `lookup` / `fetch` / `index` 均输出 `STATUS: OK | ...`、`STATUS: NO_OA | ...`、`STATUS: NOT_FOUND | ...`；致命错误在 stderr 输出 `[oa-article] ERROR <码> <LABEL>: 文字`。
- 退出码 0 表示命令完成（包括“未找到合法 OA”这类有效结果），1 表示网络/参数等致命错误。
- 脚本只是把稳定重复动作固化；领域检索策略不要写进脚本，放 `.agents/memory/open-article-get/`。

## Storage

```text
project/
├── .agents/
│   ├── skills/open-article-get/          # 本 skill + 通用脚本
│   └── memory/open-article-get/          # 只放 how to search，不放检索历史
└── .refs/
    └── oa-article/
        ├── index.tsv                     # 长期文献元数据索引
        └── pdf/                          # 合法 OA PDF
```

不要把下载文件放入 `.agents`。

### index.tsv

字段：`key title authors year doi published_doi arxiv_id venue result_level oa_url pdf_path openalex_id note`

- `key`: 优先 DOI，否则 arXiv ID，否则 title hash。
- `doi`: 当前记录关联 DOI；未知留空。
- `published_doi`: 正式发表 DOI；若 `doi` 本身即 version of record，可相同。
- `result_level`: `abstract | preprint | published`。
- `pdf_path`: 相对 `.refs/oa-article/` 的路径。

本地优先：

```bash
grep -iF '10.1234/example' .refs/oa-article/index.tsv
grep -iF 'partial title' .refs/oa-article/index.tsv
# 或
python3 scripts/oa_article.py index --tsv .refs/oa-article/index.tsv --find 'partial'
```

## Memory

`.agents/memory/open-article-get/` 只保存 how to search：

- 主题关键词与 synonyms、include/exclude terms。
- 作者、机构、venue、年份限制、preferred sources。
- query expansion 提示、ranking/filtering 偏好、可复用领域检索脚本。

不放：已下载 PDF、已查过哪些论文、阅读状态、摘要缓存、citation notes、搜索日志。

`README.md` 解释结构，`INDEX.md` 做配置导航。

## Retrieval flow

1. **Local first**：有 DOI/arXiv ID/明确题名时，先查 `.refs/oa-article/index.tsv`。命中且记录足够回答，则不重复检索；只有需要升级层级时再查网络。
2. **Search**：用 `oa_article.py lookup` 走 OpenAlex/Crossref/Unpaywall/arXiv；不要求固定顺序，按 identifier 走最短路径。
3. **Resolve identity**：优先 published DOI → DOI → arXiv ID → OpenAlex ID → normalized title+authors+year。arXiv 页面/OpenAlex/Crossref/publisher metadata 明确正式版本时写 `published_doi`；不要仅凭相似题名强行合并。
4. **Acquire legal OA**：只获取明确合法开放的内容。`result_level` 三档：`abstract` / `preprint` / `published`。同时存在 preprint 与 published OA 时优先 published。用 `oa_article.py fetch` 下载；文件名由 DOI/arXiv ID 生成，写入 `.refs/oa-article/pdf/`。
5. **Update index**：每个 canonical work 在 `index.tsv` 尽量保持一行，新信息更新旧行。可用 `index --upsert` 或手动编辑。

## Output contract

对单篇文献，输出尽量短，并明确：

```text
search_status: found | not_found
reference_status: confirmed | unconfirmed
doi: <doi | none>
published_doi: <doi | none>
result_level: abstract | preprint | published | none
oa: yes | no
local_record: yes | no
```

然后给最少必要信息：

```text
title:
authors:
year:
venue:
oa_url:
pdf_path:
```

未找到时说明卡在哪一层；不要为输出完整而编造空缺 metadata。

## Reading policy

默认目标是 retrieve, identify, index，不是阅读全文。除非用户明确要求理解正文，否则优先依据 metadata/abstract/identifier 完成任务；能通过索引回答的问题不重新打开全文。

## Quality rules

- DOI 统一去除 `https://doi.org/` 前缀后比较，case-insensitive。
- 区分 `doi` 与 `published_doi`；区分 `preprint` 与 `published`。
- publisher metadata / Crossref 可用于确认正式发表；arXiv 不能单独证明正式发表状态。
- OA URL 必须来自明确开放来源；找不到合法 OA 时返回 metadata/abstract 状态，不绕过访问控制。
- 本地已有记录优先复用；memory 只配置检索，不记录历史。
- `.refs/oa-article/` 才是长期文献资产目录。
