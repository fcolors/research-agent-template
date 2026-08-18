# DSH 插件生态规范速览（科研工作流交付物形态手册）

> 目的：把“面向 DSH 生态的交付物”落到**具体的插件形态**上，形成可复用、可向 GitHub 推送的规范。任何后续构建（研究预设、技能、门禁、调度、记忆）都对应下面某一类 DSH 构件。
>
> 依据：本机 `@deepseek-ai/dsh@0.1.0-rc.6` 的 preset 与包文档、GitHub `deepseek-ai/deepseek-harness` 仓库（`config/agent-presets/`、`.agents/`、`docs/cordis-primer.md`、`packages/AGENTS.md`、`examples/`）。
>
> 状态：速览版。深层机制以 DSH 仓库的 `docs/` 与各包 README 为准。

---

## 0. 一句话模型

DSH 是一个 **Cordis 插件化 agent harness**：**一切皆插件**。运行单元是 **profile**，profile 由若干 **组合包（bundle）** 的 patch 层叠加而成，最上面叠用户的 `cordis.patch.yml` 与 `--patch` 覆盖。agent 本身是**每个会话一个的组合**（agent preset），它看到的工具/技能/目标/规划由 preset 的 `cordis.yml` 装配。**持久状态在会话日志**，不在插件里。

配置叠加顺序（从空根开始）：

```
空根
 → dsh.profile.bundles 中各 bundle 的 patch
 → profile 自身 cordis.patch.yml
 → $DSH_HOME/cordis.patch.yml（home 级）
 → --patch 指定的覆盖层
```

用 `dsh --dump-config` / `--dump-default-config` 可无启动查看组合结果。

---

## 1. Profile（运行单元）

| 项 | 说明 |
|---|---|
| 位置 | `$DSH_HOME/profiles/<name>/` |
| 元数据 | `dsh.profile`（manifest，含按顺序排列的 `bundles`） |
| 用户覆盖 | `cordis.patch.yml`（顶层 YAML 数组：id-targeted 覆盖 / disable / insert） |
| 依赖 | `package.json`（树外插件依赖，pnpm 安装到 profile 的 node_modules） |
| 入口 | `dsh --profile <name> ...`；`web` 与 `headless` 首次使用自动初始化 |

**科研用法**：做一个 `research` profile，bundles = DSH 标准工具 + 你的研究叠加；`cordis.patch.yml` 挂研究技能根、门禁、调度 overlay。

---

## 2. 组合包 Bundle

- 一个可安装的 patch 层（`cordis.yml` / `cordis.patch.yml`），可整体塞进某个 profile 的 `bundles` 列表。
- 内置组合包：`@deepseek-ai/dsh-base`、`@deepseek-ai/dsh-web-app`、`@deepseek-ai/dsh-headless`。
- 约定：一个可独立复用的功能单位（如“研究证据纪律”或“arXiv 每日流水线”）做成 bundle，多个 profile 共用。

---

## 3. 插件 Plugin（Cordis）

- 形态：一个 Cordis 插件包（`cordis.yml` 或代码注册），向各 registry 贡献能力。
- **注册即副作用**：一律经 `ctx.effect()` / `ctx.on()`；registry 的 `register()` 返回 disposer。
- **realm（域）**：agent-plane 的插件行必须放在带 `isolate` 域的 group 里，否则发布到根域会与别的 preset 冲突（`dsh-agent-presets` 在 mount 时拒绝）。
- 主机平面（host plane）vs 代理平面（agent plane）：registry/沙箱/审批/持久化/模型路由在主机平面；preset 只装配“每个 agent 看到什么”。
- 模型可见 ⟺ 已记日志：凡进入模型请求的东西都必须能从会话日志重建。

**科研用法**：需要给 agent 加新能力（如“读 PDF 页码区间”的工具、自定义验证器）时，写一个小 Cordis 插件，注册进 preset。

---

## 4. Agent preset（每会话的 agent 组合）

位置：`<dsh>/config/agent-presets/<name>/`，含：

- `preset.yml`：名称 / 描述 / 顺序。
- `agent.cordis.yml`：该 agent 的工具、prompt 段落、能力装配。内置三档：
  - `minimal`：双工具（持久 bash + str_replace_editor），固定 persona。
  - `standard`：完整编码 agent（shell / fs / jobs / skills / goals / planning / compaction / subagents / workflows / ask-user / todo / web）。
  - `code`（PTC 模式）：standard 全部能力 + Code Mode SDK（一个 TS 程序组合多步操作）。

标准 preset 的关键行（可复制后改）：
```
persona / agent-instructions     # 身份 + 指令文件（AGENTS.md 路由入口）
tool-bash / tool-pwsh            # shell
tool-fs / tool-fs-search         # 文件系统
tool-jobs                        # 后台任务
skill-filesystem / tool-skill    # 技能注册表 + 加载器
tool-goal                        # 目标工具
plan-mode                        # 计划模式（会话日志里的软状态）
compaction / tool-result-pruner  # 上下文裁剪
tool-subagent(-fork) / tool-workflow / tool-ralph  # 委派与编排
tool-ask-user / tool-todo / tool-web
```

**科研用法**：复制 `standard` 生成 `research-agent` preset，替换 persona、挂研究 skills、可按需 disable 不需要的工具。

---

## 5. Skill（可复用动作，按需加载）

发现根（rank 顺序）：`<项目>/.dsh/skills` → `<项目>/.agents/skills` → 自定义目录 → `~/.dsh/skills` → `~/.agents/skills`。

两种文件形态：`<name>/SKILL.md`（目录包，可带 `references/`、`scripts/`、`assets/`）或扁平 `<name>.md`。**不支持嵌套 `**/SKILL.md`**。

frontmatter（kebab-case 名）：
```yaml
---
name: zotero-pdf-export
description: 把 Zotero 选中的 PDF 只读导出并复制进项目 tmp/zotero-pdf/。在需要读取论文原文时使用。
whenToUse: 进入取证阶段的必读前提
metadata: { ... }               # 可选
disable-model-invocation: false  # true 则模型侧不可见
user-invocable: true             # false 则人侧不可见
---
```

约定：
- 只装“局部流程 + 工具用法 + 检查项”，不枚举全部知识、不试图替代思维。
- `skill()` 每次重读当前文件：**改了体就生效**，无需缓存失效。
- 模型侧/人侧调用策略各自独立（`modelInvocable` / `userInvocable`）。

**科研用法**：`zotero-pdf-export`、`pdf-evidence-reading`、`cite-verify`、`term-disambiguation`、`search-expansion`、`contradiction-tracking`、`template-compliance`、`morning-brief-write` 等，全部 SKILL.md 形态放进 `<repo>/.agents/skills/`。

---

## 6. Agent Note（决策记录，记忆的载体）

路径：`.agents/notes/{lifecycle}/{class}/yyyy-mm-dd-主题.md`。

- lifecycle：`proposed / implemented / rejected / archived`
- class：`feature / bug-fix / simplification / architecture / process / testing`
- 三行头 + 骨架（`verify-agent-note-format` 门禁强制）：
```markdown
# Agent Note: <标题>

Status: <proposed | implemented | rejected — 一行原因>

## Problem
…（独立于解决方案的动机）
## Decision          （implemented；present tense，与真实状态同步）
…bespoke…
## Alternatives considered   （强制：每个备选为何落选）
## Consequences      （implemented）
## Acceptance criteria / ## Risks   （proposed）
```
- `archived` 永久冻结、不再作权威；归档只允许加一行 `Archived: YYYY-MM-DD`。
- **非平凡改动必须在同一提交里带 Note**（或更新既有 Note）。
- 别加中心 `INDEX.md`（有专门 Note 论证不要索引）；用相对 markdown 链接互指。

**科研用法**：记录范围收缩、为何排除某类证据、采用的术语定义、被证伪的假设、go/no-go 依据。lifecycle 让“已失效的上下文”从活动规则中移走。

---

## 7. 工具 Tool（agent 能力的最小单位）

- 注册进 `tools` registry；schema 是 JSON Schema 子集（只用 type/properties/required/additionalProperties/items/enum/const/oneOf）。
- 渲染意图（render intent）是设计的一部分：`generic / terminal / diff / locations`，presentation 是 args 的纯函数。
- 工具描述/卡片属于请求前缀，注意 KV cache 稳定性。

**科研用法**：`pdf_extract --info/--pages` 这类确定性工具适合做成工具；偏“流程”的（导出→拷贝→标注）适合做成 skill。

---

## 8. 门禁与 CI（验证信号，机械层）

- 本地钩子要窄：pre-commit 廉价检查，pre-push 只跑增量 typecheck；穷举交 CI。
- 聚合门禁：`scripts/run-gates.ts`（带依赖图 + 有界并发）组织 `verify-*` 集合。
- DSH 门禁示例：`verify-agent-note-format`、`verify-archived-agent-notes`、`verify-md-links`、`verify-doc-refs`、`verify-doc-budgets`、`verify-cordis-config`。
- 原则：**机器只验证可判定的性质**（链接可解析、字段完整、类型通过）；审美与价值由人。

**科研用法**：L1 门禁脚本（DOI/引用解析、claim↔evidence 完整性、模板 section 齐全）做成 `scripts/verify-*.py`，挂 Gitea Actions 或本地 pre-commit。可直接复用你 `auto-research/scripts/verification/` 里已写好的幻觉核查、引用可追溯、元数据交叉核验脚本。

---

## 9. AGENTS.md（就近路由与硬约束）

- 根 `AGENTS.md`：全局目标、仓库布局、命令、硬约束、门禁策略（短，几屏）。
- 子树 `AGENTS.md`：只补该区域需要的知识。
- `CLAUDE.md` 是 `AGENTS.md` 的软链。
- 每条规则自足 + 链接高层文档；能压缩就压缩（`verify-doc-budgets` 顶预算）。
- 规则从失败长出：只影响一个方向的放局部，影响多方向的才升根。


---

## 11. 科研交付物 → DSH 形态映射（速查表）

| 你要交付的东西 | DSH 形态 | 放哪 |
|---|---|---|
| 科研 agent 本体（工具/技能/纪律装配） | agent preset（复制 standard 改） | 你的 profile 的 patch 层 |
| 证据纪律 | 根 `AGENTS.md` + 研究方向子树 | 仓库 |
| 可复用动作 | skill（SKILL.md 目录包） | `<repo>/.agents/skills/` |
| 研究决策/教训（含“Trap”类知识） | Agent Note（lifecycle 治理） | `.agents/notes/` |
| L1 验证 | verify-* 脚本 + Gitea Actions / pre-commit | `scripts/` |
| 自我升级 | web-cordis 模式（改自己的 profile/skills） | profile |

---

## 附：要深挖时的权威入口

- 本机已装：`@deepseek-ai/dsh@0.1.0-rc.6`（`node_modules/@deepseek-ai/` 下每包自带 README，机制文档最全）。
- 源码仓库：`deepseek-ai/deepseek-harness` —— `docs/cordis-primer.md`（loader/patch 语义）、`docs/architecture.md`（agent-loop 与扩展点）、`packages/AGENTS.md`（包级规范）、`docs/cookbook/`（加工具/加包/加 LLM 适配器实操）、`examples/`（可运行的 leaf）。
- 本地参考克隆：本仓库 `.refs/dsh-src`（GitHub 公开源码的 .agents + AGENTS.md + 部分 docs，gitignored）。
