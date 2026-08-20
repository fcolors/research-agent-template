# .agents — 可迁移科研调研技能包（模板版）

本目录是**字段无关、可整体迁移**的科研调研 agent 技能与记忆层。换项目 = 复制本目录 + 在 `memory/` 里按新领域填配置，机制层无需改动。

## 参考调研工作流

web_search -> key words for Read-Black for OA get -> OA get (MUST! and MUST parallel for out of time ) -> analysis paper and Red-Black -> write 1 latex chapter -> analysis paper and Red-Black -> make v1 article -> Red-Black with peer-reviewer -> ESL IMRaD up up -> make full article for user -> tell user how to use it in chinese.

特别注意！以上仅用于参考，而飞轮、门禁规则等在全流程下进行,必须避免由于框架造成的打卡模式(只按流程办事，没有真正给出有效产出，飞轮门禁的正确使用则是其保证）

## 结构

```text
.agents/
├── README.md                        # 本文件
├── docs/                            # 通用设计与规范（随技能包迁移）
│   ├── README.md                    #   文档索引
│   ├── research-skill-arsenal.md    #   武器库设计（字段无关，领域作配置）
│   ├── dsh-plugin-spec.md           #   DSH skill 形态规范
│   ├── dsh-research-flywheel-reference.md  #  科研飞轮运行参考
│   └── dsh-research-gates-reference.md     #  科研门禁运行参考
├── memory/                          # 技能私有记忆（配置/学习卡/私有武器），不含 PDF/索引/缓存
│   ├── open-article-get/            #   只放 how to search（领域检索配置卡）
│   │   ├── README.md
│   │   ├── INDEX.md                 #   配置卡导航
│   │   └── example-topic.md         #   通用配置卡模板（复制并改写为你的领域）
│   └── red-black-review/            #   红黑队私有记忆（学习卡 + L1/L2 武器）
│       ├── README.md
│       ├── learned/                 #   学习卡（项目私有，换项目清空）
│       └── weapons/                 #   L1/L2 私有武器（项目私有）
├── requirements/                    # 技能第三方依赖清单（按需 pip install -r）
│   ├── README.md
│   └── zotero-annotations.txt       #   PyMuPDF（仅 zotero 上下文模式需要）
└── skills/
    ├── open-article-get/            # 检索并获取合法 OA 文章（含脚本）
    ├── peer-reviewer/               # 同行评审（审稿人角色）
    ├── red-black-review/            # 红黑对抗打磨（含 L0 武器）
    ├── review-quality-analyzer/     # 综述质量提示词工程
    ├── latex-research-writing/      # 极简 LaTeX 交付（main.tex + 拆章 + BibTeX，含脚本）
    └── zotero-annotations/          # Zotero 批注读取 + 附件拉取（含脚本）
```

## 通用 vs 私有（迁移边界）

| 层级                                                        | 内容                                                 | 迁移时                          |
| ----------------------------------------------------------- | ---------------------------------------------------- | ------------------------------- |
| `.agents/docs/`                                           | 技能包**设计与规范**（字段无关、可跨学科复用） | ✅ 随技能包一起走               |
| `.agents/skills/` + `.agents/requirements/`             | 技能机制 + 依赖清单                                  | ✅ 随技能包一起走               |
| `.agents/memory/open-article-get/`、`red-black-review/` | 检索配置卡、学习卡、私有武器                         | 换项目时按需替换/清空           |
| 项目专属实测/审计记录                                       | ——                                                 | ❌ 不放本模板；留在各自项目仓库 |

## 迁移约定

1. **技能脚本以 skill 根目录为基准执行**，例如：
   ```bash
   cd .agents/skills/zotero-annotations
   python3 scripts/zotero_annotations.py --key XXX
   ```
2. **PDF、索引、缓存不放 `.agents/`**：
   - OA 文献资产放 `.refs/oa-article/`
   - Zotero 附件复制放 `.refs/zotero-pdf/` 或 `temp/`
   - 批注缓存放 `.zotero-annotations/`（工作目录或 temp）
3. **`memory/` 只放配置、学习卡与私有武器**，不放检索历史、已下载 PDF、摘要缓存。
4. **依赖**：有第三方依赖的 skill 在 `requirements/` 建对应 `*.txt` 并登记；纯标准库 skill 不建文件。
5. 新增 skill 时保持单层 `<name>/SKILL.md`；脚本放 `<name>/scripts/`。
6. **LaTeX 交付物**：`latex-research-writing` 生成的项目（`main.tex`、`chapters/`、`refs.bib`）放在项目根目录（如 `latex-project/`）或用户指定目录，不放 `.agents/`。
