---
name: paper-red-black-review
description: 面向论文阅读、文献综述与研究调研的红黑对抗打磨技能。以固定 L0 武器为底线，在需要提高交付质量时，对论断真实性、证据权威性、引文支撑关系和“只述原著”进行独立审查、守正修订与复审。若运行环境支持 subagent，则按本技能声明调用 red-reviewer 与 black-reviewer；否则由当前 agent 严格分角色顺序执行。
whenToUse: 阅读论文并形成客观陈述；撰写或打磨综述/调研；交付前核验关键 claim、数字、引文与证据等级；用户要求“再审一遍、挑错、深核、只述原著、核对引用、提高严谨性”时。
metadata:
  disable-model-invocation: false
---

# Paper Red–Black Review

> 目标：把论文阅读/综述从“写得像对”提升到“每个关键论断都能回到原文、证据等级与措辞匹配、没有把推断写成事实”。

本技能只保留固定 **L0 标准武器**。  
不做自动学习，不写 `learned/`，不维护 L1/L2，不允许 subagent 自行扩充长期规则。


---

## 0. 文件约定

同目录下：

- `L0-WEAPONS.md`：固定基础武器，所有审查必须遵守。
- `RED-SUBAGENT.md`：红方独立审查提示词。
- `BLACK-SUBAGENT.md`：黑方守正修订提示词。
- `REREVIEW.md`：复审与“只述原著”抽检协议。

如果运行环境支持 subagent：
1. 主 agent 负责与用户交流、准备材料、决定是否需要打磨。
2. 需要打磨时，优先调用独立 Red subagent。
3. Red 返回后，再调用独立 Black subagent。
4. 主 agent 按 `REREVIEW.md` 做最终逐条对账后再交付用户。

如果运行环境不支持 subagent：
- 当前 agent 仍按 **Red → Black → Re-review** 三个阶段顺序执行；
- 各阶段不得提前替下一角色辩护；
- Red 阶段必须先形成独立问题清单，再进入 Black。

Weapons 打磨
- 私有化存储路径为 `.agents/memory/red-black-review/`。
- L1/L2 武器以 `.md` 形式由主 agent 写入 `.agents/memory/red-black-review/weapons/` 对应的 `L1-weapons/`、`L2-weapons/` 中。


---

## 1. 什么时候启动“打磨”

正常论文阅读不必每次都启动红黑流程。

出现以下任一情况时启动：

- 用户明确要求：审稿、挑错、核验、深挖、打磨、复审、提高严谨性。
- 需要把某篇论文写成可引用的客观陈述。
- 综述/调研准备交付，存在关键数字、机制性结论、比较性结论或强因果措辞。
- 一个关键 claim 依赖单篇来源、预印本、技术报告、二手来源或不确定出处。
- 当前正文含有“首次、证明、显著、导致、优于、实现了、表明”等高承诺词。
- agent 对某个数字、架构属性、实验条件、证据等级或引文支撑关系没有把握。

只是普通摘要、低风险笔记、用户明确不要深审时，不应为了流程而强行启动。

---

## 2. L0 两条第一性原则

所有检查最终必须收敛到：

### A. 真实性 Truthfulness

每条论断必须：
- 可追溯；
- 可核验；
- 不杜撰；
- 不漂移；
- 不把推断升级为事实；
- 不丢失原文限定词；
- 数字、方向、单位、对象和条件与来源一致。

### B. 权威性 Authority

每个支撑必须：
- 来源真实、可识别；
- 引用真正支撑对应 claim，而非仅主题相关；
- 证据等级与正文措辞匹配；
- 不用孤例冒充普遍结论；
- 对预印本、技术报告、会议论文、同行评审论文等来源类型保持诚实；
- 关键断言优先使用原始来源，而不是二手转述。

具体检查项见 `L0-WEAPONS.md`。

---

## 3. 主 agent 的输入准备

启动 Red 前，尽量整理以下材料：

- `task_goal`：用户最终要得到什么。
- `target_text`：待审段落/章节/综述。
- `source_materials`：论文全文、PDF、网页、补充材料或证据表。
- `claims`：若已有，列出关键 claim。
- `citation_map`：若已有，正文 claim → 来源。
- `constraints`：篇幅、语气、是否只允许原始来源等。

若原文不可访问：
- 必须显式标注核验边界；
- 不得假装已经“回原文验证”。

---

## 4. Red 阶段

调用 `RED-SUBAGENT.md`。

Red 的任务不是改稿，而是：
1. 找出最可能使当前表述失真的地方；
2. 找出引用“相关但不支撑”的地方；
3. 找出证据等级与措辞不匹配的地方；
4. 检查数字、限定词、对象、范围、因果方向；
5. 区分真正错误与可选增强。

Red 必须输出可操作 finding，不得只给“建议更严谨”之类泛评。

---

## 5. Black 阶段

将以下信息交给 `BLACK-SUBAGENT.md`：

- 原目标；
- 原正文；
- Red findings；
- 可访问的原始来源；
- L0 武器。

Black 必须逐条判定：

- `ACCEPT`：成立，修改。
- `PARTIAL`：部分成立，只改成立部分。
- `REJECT`：不成立，用原文/证据反驳。
- `DEFER`：证据不足，不能装作已解决。

Black 的核心纪律：

> 修真正错误，但不得为了迎合 Red 制造新内容。

涉及论文原文时，新增事实必须遵循“只述原著”。

---

## 6. Re-review

Black 完成后，由主 agent 使用 `REREVIEW.md`：

1. Red 每条 finding 是否有处置；
2. 认账是否真的改了；
3. 反驳是否有明确依据；
4. 新增内容是否仍能回到原文；
5. 随机抽检 2–3 个高风险句；
6. 给出：
   - ✅ resolved
   - ⚠️ partial
   - MISS

存在 MATERIAL/BLOCKER 级 MISS 时不得声称“已收敛”。

---

## 7. “只述原著”模式

当用户要求：
- 总结单篇论文；
- 写某文献的客观陈述；
- 给综述正文生成可引用描述；

必须启用 source-bounded 模式：

只写论文实际报告：
- 做了什么系统/方法；
- 在什么条件下；
- 测了什么；
- 报告了什么结果；
- 作者如何表述结论。

禁止自动加入：
- 论文没有说的机制解释；
- agent 自己的合理化；
- 因果延伸；
- 价值判断；
- “因此可推广到……”；
- 把作者推测写成事实。

数字就地说明性质：
- measured / measured experimentally
- calculated
- configured
- estimated
- reported
- upper bound

宁可少写，也不要补齐论文没有提供的信息。

---

## 8. 停止条件

满足以下条件即可停止，不为“跑流程”而继续制造问题：

- Red 无 MATERIAL/BLOCKER finding；
- Black 已处理所有有效 finding；
- Re-review 无 MISS；
- 抽检句都能回到来源；
- 剩余内容仅为 OPTIONAL enhancement。

允许输出：

`CONVERGED — MINIMAL/NO FURTHER REVISION NEEDED`

---

## 9. 不变量

1. 真实性 + 权威性不可降级。
2. Red 必须独立，不提前替正文辩护。
3. Black 必须守正，不为迎合 Red 过度修订。
4. 论文客观陈述只述原著。
5. 无原文时不得伪装成已核验。
6. 不自动学习，不自动扩充武器库。
7. 有 subagent 能力时优先按模板调用；无则严格分阶段模拟。
