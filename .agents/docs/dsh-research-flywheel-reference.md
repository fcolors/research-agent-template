---
name: research-flywheel-reference
kind: dsh-runtime-reference
version: 0.3
status: draft
scope: generic-research
machine_oriented: true
language: zh-CN
note: 建议全文挂载
---

# DSH 科研飞轮运行参考

## 0. 用途

本文件供 DSH Agent 在运行科研/调研任务时直接参考。

本文件只定义任务级控制机制：

- 固定最大努力执行；
- 时间预算控制；
- 在 `T/3` 强制进行方向审核；
- 内容增量检查；
- 用户负反馈或连续无增量时升级；
- 学习写回；
- `COMPLETE / PARTIAL / BLOCKED` 终止协议。

本文件 **不得** 写入具体领域知识。
本文件 **不得** 替代 Zotero、Web 搜索、证据抽取、审稿、写作等能力型 Skill。
本文件不是面向人的方法论文章；运行时应优先把其中的 `MUST / MUST NOT / FAIL` 视为机器约束。

---

## 1. 必需输入

任务启动时，Runtime 必须解析：

```yaml
goal:
  id: <stable-goal-id>
  objective: <research objective>
  expected_output: <artifact or answer type>

time_budget:
  total: <duration>
  unit: minutes | hours
```

如果缺少 `time_budget.total`，Runtime 必须在 `create_goal` 或实质性调研开始前询问时间预算。

可选配置：

```yaml
flywheel_config:
  direction_review_fraction: 0.333
  max_no_increment_rounds: 2
  require_expansion_before_scope_narrowing: true
  learning_writeback: true
  red_black_enabled: true
  reverse_reproducibility_enabled: true
```

默认值：

```yaml
direction_review_fraction: 0.333
max_no_increment_rounds: 2
require_expansion_before_scope_narrowing: true
learning_writeback: true
```

---

## 2. 不可协商的不变量

Runtime 必须执行以下全部不变量。

```text
F01. 始终使用最大科研纪律运行。
F02. 时间预算只控制 scope 与覆盖度，不得降低真实性标准。
F03. Gate PASS 是必要条件，但绝不是“有进展”的充分条件。
F04. 每一轮都必须检查是否存在真实内容增量。
F05. 到达 T/3 时必须执行方向审核。
F06. 配置要求先扩后缩时，未完成 evidence expansion 前不得收紧 scope。
F07. 用户明确不满意或负面反馈，必须视为 escalation signal。
F08. 连续 N 轮无真实增量，必须触发 escalation。
F09. Escalation 必须改变至少一个控制变量。
F10. Runtime 不得修改当前活动 Skill 的硬规则。
F11. 无法核验的信息必须保持 unknown / blocked，不得补猜。
F12. 发现可复用失败模式或启发时，应写出 learning record。
```

任何 `MUST` 级不变量被违反，都属于运行失败，不是软警告。

---

## 3. 最大努力策略

DSH 不得因为“看起来任务简单”而自动选择较低研究质量模式。

禁止：

```text
简单任务 -> 浅层纪律
复杂任务 -> 严格纪律
```

要求：

```text
所有任务 -> 同一套真实性/证据纪律
时间预算 -> 决定 scope / coverage / round count
```

时间预算可以改变：

- source 数量；
- 阅读论文数量；
- 搜索覆盖范围；
- 对抗轮数；
- 输出长度；
- 全文阅读深度；
- 在输出 `PARTIAL` 前可容忍的 unresolved 分支数量。

时间预算不得改变：

- 禁止杜撰；
- 证据可追溯要求；
- 阅读状态真实性；
- source identity 检查；
- 适用时的 forward evidence 要求。

---

## 4. Runtime 状态

Runtime 应维护与下列语义等价的机器状态：

```yaml
flywheel_state:
  goal:
    id: <id>
    objective: <text>

  budget:
    total_minutes: <number>
    elapsed_minutes: <number>
    direction_review_at_minutes: <number>
    direction_review_done: false

  round:
    index: <integer>
    no_increment_streak: <integer>

  scope:
    current: <text-or-structured-scope>
    expansion_since_last_narrowing: false
    narrowing_requested: false

  progress:
    claims_count: <integer>
    evidence_count: <integer>
    sources_count: <integer>
    resolved_issues_count: <integer>
    learning_cards_count: <integer>

  review:
    unresolved_red_issues: <integer>

  status:
    RUNNING | DIRECTION_REVIEW | REPAIR | STALLED | ESCALATING | COMPLETE | PARTIAL | BLOCKED
```

Runtime 可以存更多字段，但不得破坏上述状态语义。

---

## 5. 单轮协议

每轮科研必须遵循以下逻辑顺序：

```text
ROUND_START
  -> READ_CURRENT_STATE
  -> SELECT_HIGHEST_VALUE_ACTION
  -> EXECUTE_RESEARCH_ACTION
  -> RECORD_DELTA
  -> RUN_REQUIRED_GATES
  -> CHECK_INCREMENT
  -> CHECK_DIRECTION_REVIEW_TRIGGER
  -> RUN_ADVERSARIAL_REVIEW_IF_CONFIGURED
  -> UPDATE_UNRESOLVED_ISSUES
  -> WRITE_LEARNING_IF_NEEDED
  -> DECIDE_NEXT_STATE
ROUND_END
```

解释：

```text
READ_CURRENT_STATE
  读取当前 goal、budget、scope、证据状态与 unresolved issues。

SELECT_HIGHEST_VALUE_ACTION
  选择当前最能降低关键不确定性、补证据或解决阻塞的动作。

EXECUTE_RESEARCH_ACTION
  调用能力型 Skill 或工具执行实际调研。

RECORD_DELTA
  记录这一轮相对于上一轮新增了什么。

RUN_REQUIRED_GATES
  检查当前内容是否满足研究下限。

CHECK_INCREMENT
  检查这一轮是否真的推进了研究，而不是只完成流程动作。

CHECK_DIRECTION_REVIEW_TRIGGER
  判断是否已到 T/3 强制方向审核点。

RUN_ADVERSARIAL_REVIEW_IF_CONFIGURED
  如果启用红黑队/审稿机制，则执行对抗检查。

WRITE_LEARNING_IF_NEEDED
  从本轮失败、修正、反例中提炼可复用学习。
```

Runtime 不得把 Gate 的执行本身算成研究增量。

进入 `STALLED` 后，不得原样重复相同 Round；除非下一轮至少改变一个实质控制变量。

---

## 6. T/3 方向审核

触发条件：

```text
elapsed_time >= total_time * direction_review_fraction
AND direction_review_done == false
```

默认：

```text
direction_review_fraction = 1/3
```

触发后，Runtime 必须暂停正常推进，并检查：

```yaml
direction_review:
  question_alignment:
    still_answers_original_goal: true | false

  scope:
    prematurely_narrowed: true | false
    adjacent_relevant_areas_missing: true | false

  evidence_base:
    expanding: true | false
    source_concentration_risk: true | false

  counter_evidence:
    counterexamples_contacted: true | false
    competing_explanations_contacted: true | false

  progress:
    real_increment_observed: true | false
```

允许的决策只有：

```text
CONTINUE
REDIRECT
EXPAND
BLOCKED
```

语义：

```text
CONTINUE
  当前方向成立，可以继续。

REDIRECT
  当前方向存在问题，必须在继续消耗主要预算前改向。

EXPAND
  当前证据面过窄，必须先扩大覆盖，再考虑收敛。

BLOCKED
  必需信息、工具、权限或 source 无法获得。
```

完成审核后设置：

```yaml
direction_review_done: true
```

不得因为 Gate 全绿就自动选择 `CONTINUE`。

---

## 7. 增量协议

只有产生至少一种 **可核验的语义增量**，本轮才算真实前进。

可计入的增量类型：

```yaml
increment_types:
  - new_claim
  - new_evidence
  - new_source
  - new_counterexample
  - new_term_or_concept
  - deeper_supported_analysis
  - newly_resolved_issue
  - new_learning_card
```

一个 delta 必须同时满足：

```text
semantic_delta == true
AND
verifiable_support == true
```

以下活动不得计作研究增量：

```text
- 重新跑相同 Gate；
- 生成语义等价的总结；
- 只改写旧文本，没有新含义；
- 重复相同搜索但没有得到新 evidence；
- 重新登记没有变化的 source；
- 新增无证据意见；
- 只增加过程日志。
```

如果没有合格 delta：

```yaml
increment:
  status: FAIL
  reason: CLOCK_IN
```

否则：

```yaml
increment:
  status: PASS
```

`CLOCK_IN` 表示 Agent 在执行流程，但研究内容没有前进。

---

## 8. 连续无增量计数

每轮结束后：

```text
if increment == PASS:
    no_increment_streak = 0
else:
    no_increment_streak += 1
```

升级条件：

```text
no_increment_streak >= max_no_increment_rounds
```

默认：

```yaml
max_no_increment_rounds: 2
```

Gate 变绿不得重置 `no_increment_streak`。

---

## 9. Scope 收紧规则

如果：

```yaml
require_expansion_before_scope_narrowing: true
```

则任何 scope narrowing 前，都必须至少执行一次新的 expansion 行为。

有效 expansion 包括：

```text
- 搜索反例；
- 搜索 competing hypotheses；
- 搜索不同研究群体 / 学派；
- 搜索不同方法类别；
- 检查近期 review；
- 搜索 negative / null results；
- 下钻更高权威或 primary source；
- 扩展术语、同义词和检索表达。
```

未扩先缩：

```yaml
scope_check:
  status: FAIL
  reason: NARROW_BEFORE_EXPAND
```

Runtime 必须先转入扩覆盖动作。

---

## 10. Escalation 协议

触发条件：

```text
E01. 用户明确负反馈。
E02. no_increment_streak 达到阈值。
E03. T/3 方向审核返回 REDIRECT 或 EXPAND。
E04. 同一个高价值 adversarial issue 多轮未解决。
E05. 审稿攻击面重复，出现 reviewer/checklist overfitting。
```

Escalation 必须改变至少一个变量：

```yaml
allowed_escalation_changes:
  - direction
  - scope
  - source_diversity
  - search_vocabulary
  - evidence_class
  - review_intensity
  - reviewer_perspective
  - claim_decomposition
  - research_decomposition
```

禁止：

```text
相同输入 + 相同搜索空间 + 相同动作 -> 再执行一次
```

升级结果应记录：

```yaml
escalation:
  trigger: <E01-E05>
  changed_variables: [...]
  rationale: <short machine-consumable text>
```

---

## 11. 对抗审查 Hook

如果启用 adversarial review，飞轮可以调用独立 review Skill。

期望接口：

```yaml
input:
  artifact: <current research artifact>
  evidence_state: <current evidence state>
  review_config: <config>

output:
  issues:
    - id: <issue-id>
      status: open | resolved
      severity: <level>
      type: <attack-surface>
```

飞轮本身不得塞入具体领域审稿规则。

如果 reviewer 连续：

```text
- 找不到新的有效错误；
- 只重复旧错误；
- 机械复读 checklist；
```

Runtime 应触发元审查/T4：

```text
回到：
  truthfulness
  authority
  goal alignment
```

并要求结果至少是：

```text
找到新的 attack surface
OR
显式记录本轮未找到新的有效 attack surface
```

不得把“红方没挑出错”自动等价为“结果正确”。

---

## 12. Learning 写回

每轮结束时，Runtime 应检查是否出现可复用学习。

参考结构：

```yaml
learning:
  id: <stable-id>
  trigger: <failure-or-observation>
  failure_pattern: <what happened>
  root_cause: <why existing controls missed it>
  new_heuristic: <future detection/correction rule>
  scope: session | domain | general
  action:
    no_change | update_config | update_memory | propose_skill_change
  evidence: <reference to actual case>
```

如果系统能力允许，Runtime 可以写入 session/domain memory。

Runtime 不得直接修改当前正在执行 Skill 的硬规则。

如果认为应该修改 Skill，必须输出：

```yaml
action: propose_skill_change
```

交由后续审核/版本化处理。

---

## 13. 终止协议

只允许三个终止状态：

```text
COMPLETE
PARTIAL
BLOCKED
```

### COMPLETE

要求所有适用条件满足：

```text
- 核心目标已经回答；
- 关键 claim 具备要求的 evidence；
- 必要 gates 通过；
- 主要反例 / competing explanations 已接触；
- 高优先级 adversarial issues 已解决或有明确 disposition；
- 最终 artifact 内部一致。
```

### PARTIAL

适用：

```text
- 预算已经或即将耗尽；
- 已经存在有证据支撑的可用阶段结果；
- 仍有 unresolved issues；
- 能明确指出下一步。
```

`PARTIAL` 输出必须包含：

```yaml
unresolved:
  - <issue>

next_actions:
  - <action>
```

### BLOCKED

适用：

```text
关键进展依赖当前无法取得的输入、工具、权限或 source。
```

不得用想象内容把 `BLOCKED` 伪装为完成。

---

## 14. 能力边界

`research-flywheel` 是机制层参考。

它应该做编排，不应吞并能力型逻辑。

可调用的外部能力例如：

```text
research-gate
reading-register
evidence-builder
source-verifier
red-black-review
reverse-reproducibility
latex-research-writing
zotero-annotations
web-search
pdf-reader
```

Skill 之间允许开放组合。

写作交付格式由 `latex-research-writing` skill 封闭定义（`main.tex` + `chapters/` + `refs.bib`）；飞轮只负责在终止前调用该 skill 并满足其 `check` 门禁，不得把最终成果退回 Markdown 正文交付。

被调用 Skill 内部的硬规则保持封闭，Runtime 不得临场重写。

---

## 15. 最小机器检查

DSH 实现应提供与以下语义等价的机器检查：

```text
check_increment
check_direction_review
check_scope_narrowing
check_terminal_state
validate_flywheel_state
```

建议 failure code：

```text
FW_MISSING_BUDGET
FW_DIRECTION_REVIEW_OVERDUE
FW_CLOCK_IN
FW_NO_INCREMENT_LIMIT
FW_NARROW_BEFORE_EXPAND
FW_ESCALATION_NO_CHANGE
FW_INVALID_TERMINAL_STATE
FW_RUNTIME_RULE_MUTATION
```

解释：

```text
FW_MISSING_BUDGET
  未设置时间预算。

FW_DIRECTION_REVIEW_OVERDUE
  已经过 T/3，但未执行方向审核。

FW_CLOCK_IN
  本轮只有流程活动，没有真实内容增量。

FW_NO_INCREMENT_LIMIT
  连续无增量达到阈值。

FW_NARROW_BEFORE_EXPAND
  scope 收紧前未完成要求的扩覆盖。

FW_ESCALATION_NO_CHANGE
  声称升级，但没有改变任何实质控制变量。

FW_INVALID_TERMINAL_STATE
  结束状态与实际条件不一致。

FW_RUNTIME_RULE_MUTATION
  Runtime 试图修改活动 Skill 的硬规则。
```

---

## 16. 参考执行状态机

```text
INIT
  -> 解析 goal
  -> 解析 time budget
  -> 加载本任务 Skill composition
  -> RUNNING

RUNNING
  -> 执行 research round
  -> gates
  -> increment check
  -> 必要时 direction review
  -> 必要时 adversarial review
  -> 必要时 learning writeback
  -> decision

如果 gate FAIL:
  -> REPAIR
  -> RUNNING

如果 direction review == REDIRECT / EXPAND:
  -> ESCALATING
  -> 改变控制变量
  -> RUNNING

如果 no_increment_streak 达到阈值:
  -> STALLED
  -> ESCALATING
  -> 改变控制变量
  -> RUNNING

如果 goal 已满足:
  -> COMPLETE

如果预算耗尽但已有可用、有证据结果:
  -> PARTIAL

如果关键依赖不可获得:
  -> BLOCKED
```

---

## 17. 禁止事项

Runtime 必须禁止：

```text
- 运行中临时发明或修改硬规则；
- 因时间短而降低 evidence / truthfulness 标准；
- 把流程活动当作内容进展；
- 在要求先扩后缩时直接缩 scope；
- 静默忽略用户负反馈；
- STALLED 后原样重复完全相同动作；
- 把 reviewer 沉默当作正确性的证明；
- 没有正文访问证据却声称 fulltext；
- 把 unknown 改写成确定事实；
- 结束时隐藏 unresolved issues。
```
