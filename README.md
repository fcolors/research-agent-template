# Research Agent Template

<p align="center">
  <img src="docs/banner.png" alt="banner" width="100%">
</p>

一个**可迁移的科研调研 agent 技能包**模板。把论文检索、批注取证、红黑对抗审稿、综述质量提示词工程等能力，封装成字段无关、可组合的 DSH skill，整体复制到任意研究项目即可使用。

## 这是什么

- `.agents/` 是一组**与学科解耦**的科研调研技能（skills）+ 通用设计文档 + 依赖清单 + 私有记忆结构。
- 研究模式最终交付默认走 `latex-research-writing`：输出**极简 LaTeX 项目**（`main.tex` + `chapters/` + `refs.bib`），不再以 Markdown 作为最终正文格式。
- 换项目 = 复制 `.agents/` + 在 `memory/` 里按新领域填配置，机制层无需改动。
- 所有脚本以各自 skill 根目录为基准执行，不依赖仓库绝对路径。

## 目录结构

```text
research-agent-template/
├── README.md                          # 本文件
├── .gitignore                         # 忽略运行时产物（.refs/、temp/、缓存）
├── LICENSE                            # GPL-3.0
└── .agents/                           # 可迁移技能包
    ├── README.md                      # 技能包说明（结构 + 迁移边界 + 约定）
    ├── docs/                          # 通用设计/规范
    ├── memory/                        # 私有记忆结构（配置卡/学习卡/武器，模板占位）
    ├── requirements/                  # 第三方依赖清单
    └── skills/                        # 6 个内置技能
```

## 内置技能

| skill | 作用 | 依赖 |
|---|---|---|
| `open-article-get` | 检索并获取合法 OA 文章，维护本地元数据索引 | 标准库 |
| `peer-reviewer` | 以同行评审标准审视手稿/章节/段落 | 无 |
| `red-black-review` | 红黑对抗打磨：真实性/权威性审查 + 守正修订 + 复审 | 无 |
| `review-quality-analyzer` | 综述质量提示词工程（子代理 A 分析 + B 反思迭代） | 无 |
| `latex-research-writing` | 交付极简 LaTeX：main.tex + 按章拆分 + BibTeX 引用管理 + 机器检查；中文默认 `ctex`+`xelatex`，英文 `fontenc`+`pdflatex` | 标准库 |
| `zotero-annotations` | 读取 Zotero 批注 + 上下文精确定位 + 附件拉取 | PyMuPDF（仅上下文模式） |

## 快速开始

1. 把 `.agents/` 复制到你的项目根目录。
2. （可选）安装依赖：
   ```bash
   pip install -r .agents/requirements/zotero-annotations.txt
   ```
3. 在 `.agents/memory/open-article-get/` 放你的领域检索配置卡（复制 `example-topic.md` 改写）。
4. 研究模式交付 LaTeX 初稿（默认 `--lang zh`，加载 `ctex`；英文项目用 `--lang en`）：
   ```bash
   cd .agents/skills/latex-research-writing
   python3 scripts/latex_project.py init --dir ../../../latex-project \
     --title "中文标题" --author "作者" \
     --chapters introduction,methods,results,discussion,conclusion
   python3 scripts/latex_project.py check --dir ../../../latex-project
   cd ../../../latex-project
   latexmk -xelatex -interaction=nonstopmode main.tex   # 英文项目改用 -pdf
   ```
5. 按需调用各 skill（详见各 `SKILL.md`）。

## 运行产物去哪（不放 `.agents/`）

- OA 文献资产 → `.refs/oa-article/`
- Zotero 附件副本 → `.refs/zotero-pdf/` 或 `temp/`
- 批注缓存 → `.zotero-annotations/`（工作目录或 temp）

## License

GPL-3.0（详见 `LICENSE`）。其中 `zotero-annotations` 的上下文提取模块参考了开源项目（MIT License）实现。
