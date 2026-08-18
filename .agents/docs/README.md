# .agents/docs — 通用设计与规范

> 本目录只保留**字段无关、可跨项目复用**的设计/规范文档，随 `.agents/` 一起迁移。
> 项目专属的实测报告、基线测量、专属流程等记录**不放这里**，留在各自项目仓库。

## 文档索引

| 文件 | 作用 |
|---|---|
| `research-skill-arsenal.md` | 科研调研武器库设计：封闭规则 / 开放组合 / 字段无关 / 飞轮学习 |
| `dsh-plugin-spec.md` | DSH skill 形态规范（SKILL.md、frontmatter、scripts/、notes） |
| `dsh-research-flywheel-reference.md` | 科研飞轮运行参考（任务级控制机制、COMPLETE/PARTIAL/BLOCKED 终止协议） |
| `dsh-research-gates-reference.md` | 科研门禁运行参考（防装读/防杜撰/claim 可追溯/证据链机器可消费结构） |

## 迁移注意事项

1. `.agents/skills/` 内的脚本都以 skill 根目录为基准执行，不依赖仓库绝对路径。
2. `.agents/memory/` 只放检索/评审配置、学习卡与私有武器；PDF、索引、缓存放 `.refs/`、`temp/`。
3. 本目录文档若引用 `scripts/`、`review/`、`temp/` 等路径，那是示例仓库路径；迁移后按新项目对应位置理解。
