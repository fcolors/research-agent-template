---
name: research-gates-reference
kind: dsh-runtime-reference
version: 0.3
status: draft
scope: generic-research
machine_oriented: true
language: zh-CN
note: 建议全文挂载
---
# DSH 科研门禁运行参考

## 0. 用途

本文件定义 DSH 科研工作流使用的通用 Gate 机制。

Gate 的目标：

```text
- 防止装读；
- 防止杜撰；
- 防止 claim 不可追溯；
- 防止 reverse reasoning 冒充 forward evidence；
- 保证 source 与 reading state 可审计；
- 把 review failure 输出为机器可消费结构；
- 保证 Gate 自身也可以被复现和反向审计。
```

本文件只定义通用机制。

领域术语、source 清单、近年优先窗口、authority 偏好、Zotero collection、审稿词表等必须通过配置提供，不得硬编码进通用 Gate 机制。

> 特别注意: 构建的Gate检查脚本应当有在后台运行的能力，避免干扰主agent。在不降低审查质量的情况下，也尽量减少使用subagent实现的方法。

---

## 1. Gate 栈

标准顺序：

```text
G0 -> L0 -> L1 -> L2 -> L3
```

语义：

```yaml
G0:
  name: workspace_hygiene
  purpose: 保证研究产物可发现、可导航、可复现

L0:
  name: source_library_hygiene
  purpose: 检查 source / library 的结构完整性与身份一致性

L1:
  name: reading_register
  purpose: 检查实际阅读层级与客观概述

L2:
  name: forward_evidence
  purpose: 检查 claim -> evidence 的方向与可追溯性

L3:
  name: adversarial_review
  purpose: 攻击论证、scope、对齐、authority 与措辞
```

所有 Gate 必须输出机器可读结果。

工作流可以通过显式配置关闭不适用 Gate。

任何已启用 Gate 不得被静默跳过。

---

## 2. 通用 Gate Contract

每个 Gate 必须实现与下列语义等价的输入输出。

输入：

```yaml
gate_input:
  gate_id: <G0|L0|L1|L2|L3>
  artifact_refs: [...]
  config: <gate-specific config>
  state_ref: <optional current research state>
```

输出：

```yaml
gate_result:
  gate_id: <G0|L0|L1|L2|L3>
  status: PASS | FAIL | WARN | BLOCKED
  failures:
    - code: <stable-code>
      subject: <machine-identifiable target>
      message: <short explanation>
      evidence_ref: <optional>
  warnings:
    - code: <stable-code>
      subject: <target>
      message: <short explanation>
  metrics: {}
```

状态语义：

```text
PASS
  所有硬检查已执行，且没有 hard failure。

FAIL
  存在至少一个硬规则违规。

WARN
  没有硬失败，但存在非阻塞风险。

BLOCKED
  因缺少必要输入、权限、source、工具或上游结果，Gate 无法完成。
```

如果必需检查没有执行，Gate 不得返回 `PASS`。

---

## 3. G0 — 工作空间卫生

### 3.1 目的

G0 检查第二个 Agent 在不知道隐藏路径的情况下，能否找到并复现当前调研产物。

### 3.2 必要检查

通用检查应包括：

```text
- protected root / output 位置没有时效性临时产物；
- 过程日志存在索引或确定性发现路径；
- source artifact 与 generated artifact 可区分；
- temp 目录内容不会被误认为正式产物；
- README / index / navigation chain 能到达任务结果；
- 不存在多个含义不清的“最终版”artifact。
```

具体目录规则必须来自 config。

示例：

```yaml
g0:
  authoritative_docs_dir: docs/
  logs_index: logs/INDEX.md
  temp_dirs:
    - temp/
  forbidden_root_extensions:
    - jsonl
    - zip
    - bak
  max_navigation_steps: 5
```

### 3.3 模糊导航测试

建议启用：

```text
给子 Agent 一个模糊需求，不告诉路径。
如果它不能在配置的 max_navigation_steps 内找到目标 artifact，
则按策略返回 FAIL 或 WARN。
```

### 3.4 Failure code

```text
G0_TRANSIENT_ARTIFACT
  时效性/临时文件进入正式位置。

G0_MISSING_INDEX
  缺少必要索引。

G0_BROKEN_NAVIGATION
  导航链断裂。

G0_AMBIGUOUS_OUTPUT
  存在多个难以区分的正式输出。

G0_UNTRACKED_LOG
  过程日志未被索引。

G0_TEMP_LEAK
  temp 内容泄漏到正式产物区。
```

---

## 4. L0 — Source / Library 卫生

### 4.1 目的

L0 检查计划使用的 source 是否可唯一识别、达到工作流要求的可访问层级，并且 library 结构没有明显损坏。

### 4.2 必要检查

L0 应检测：

```text
- 重复 DOI / stable identifier；
- 同一 work 的重复条目；
- orphan attachment；
- orphan metadata record；
- 在预期存在时缺 DOI / URL / stable identifier；
- 在要求 fulltext 时缺 PDF / 正文；
- title-author-year identity conflict；
- version conflict；
- attachment 与 source identity 不一致。
```

Gate 必须字段无关：依赖配置的 identity fields，不得绑定特定学科。

### 4.3 示例输出

```yaml
gate_result:
  gate_id: L0
  status: FAIL
  failures:
    - code: L0_DUPLICATE_SOURCE
      subject: doi:10.xxxx/abc
    - code: L0_MISSING_FULLTEXT
      subject: paper-key-17
  metrics:
    checked_sources: 42
    duplicate_groups: 1
    missing_fulltext: 1
```

### 4.4 `need_add`

研究需要但尚未进入配置 library 的 source，可以标记：

```yaml
source_status:
  source_id: <id>
  status: need_add
```

如果工作流规定“必须入库后才能引用”，则 `need_add` 必须成为 L0/L1 的 hard blocker。

---

## 5. L1 — Reading Register

### 5.1 目的

L1 防止系统声称自己读到了实际没有访问的层级。

### 5.2 阅读层级

标准值：

```text
metadata
abstract
fulltext
```

`fulltext` 必须意味着 Agent 本轮确实访问了正文主体，而且有可复核证据。

以下情况不得算 `fulltext`：

```text
- 模型先验知识；
- 搜索结果 snippet；
- 引用片段；
- 仅摘要；
- 二手综述中对该论文的描述。
```

### 5.3 Register 结构

每个被引用或研究关键 source 应具有：

```yaml
paper_id: <stable key / DOI / arXiv / other stable id>

reading_level:
  metadata | abstract | fulltext

objective_summary: >
  2-4 句客观概述，只写 source 实际报告内容。
  Agent 自己的评价、解释、推断必须另行标记，不能混入。

reading_evidence:
  source_ref: <pdf/html/text extraction ref>
  locations:
    - <page/section/offset>

evidence_links:
  - <claim-id>

status:
  in_library | need_add | unavailable
```

### 5.4 Fulltext 证明

`reading_level: fulltext` 至少必须存在以下一种证据：

```text
- 带 location metadata 的全文提取；
- 实际 PDF 正文读取 + 页码；
- HTML 正文读取 + section；
- 其他配置认可、带稳定 locator 的全文表示。
```

### 5.5 Failure code

```text
L1_MISSING_REGISTER
  被引用/关键 source 没有 reading register。

L1_INVALID_READING_LEVEL
  reading_level 值或状态不合法。

L1_FULLTEXT_UNPROVEN
  声称 fulltext，但没有正文访问证据。

L1_SUMMARY_NOT_OBJECTIVE
  objective_summary 混入明显评价/推断。

L1_CITED_SOURCE_NEED_ADD
  严格入库策略下，引用了 need_add source。

L1_SOURCE_UNAVAILABLE
  必需 source 无法获得。
```

---

## 6. L2 — Forward Evidence

### 6.1 目的

L2 检查事实性 claim 是否由可追踪证据支撑，并明确证据搜索方向。

### 6.2 Evidence Card 结构

```yaml
claim_id: <stable-id>

claim: <single auditable proposition>

direction:
  forward | reverse

evidence:
  - source_id: <stable source id>
    location: <page / section / paragraph / locator>
    source_level:
      primary | review | standard | authority | secondary | engineering_judgment
    evidence_type:
      established | interpretation | hypothesis | contested | unknown

quotes:
  - <short source fragment if allowed/needed>
```

### 6.3 Forward 规则

对每个需要证据的事实性 claim：

```text
count(forward evidence) >= configured minimum
```

默认：

```yaml
l2:
  min_forward_evidence_per_claim: 1
```

Gate 不得因为 source 与 claim “主题相关”就自动推断其支持 claim。

### 6.4 Reverse Evidence

`direction: reverse` 只能在策略明确允许时使用，典型位置：

```text
discussion
hypothesis generation
future work
exploratory reasoning
```

Reverse evidence 不得满足 forward evidence 的硬要求。

### 6.5 Evidence 对齐检查

L2 应检查：

```text
- source 确实包含被引用内容；
- locator 真实存在；
- evidence 支持的是当前 exact claim，而不仅是相邻话题；
- source identity 与 Reading Register 一致；
- evidence_type 与 claim 用词强度相容。
```

### 6.6 Failure code

```text
L2_MISSING_EVIDENCE
  claim 缺少要求的 evidence。

L2_REVERSE_USED_AS_FORWARD
  reverse evidence 被当作 forward evidence。

L2_INVALID_LOCATOR
  页码/章节/locator 无效。

L2_SOURCE_MISMATCH
  evidence 指向的 source identity 不一致。

L2_CLAIM_EVIDENCE_MISALIGNMENT
  evidence 与 exact claim 不对齐。

L2_EVIDENCE_TOO_WEAK_FOR_WORDING
  证据强度不足以支撑当前措辞。

L2_UNREGISTERED_SOURCE
  evidence 使用了未进入 Reading Register 的 source。
```

---

## 7. L3 — 对抗审查

### 7.1 目的

L3 在 source/evidence 基础完整后，主动攻击论证与写作质量。

L3 不能替代 L0-L2。

### 7.2 最小通用攻击面

L3 应检查：

```text
- 孤例证明 / 单一例子过度外推；
- 相关性被误写成支持或因果；
- claim-source 不对齐；
- scope 过宽或过窄；
- 超出 source 适用范围；
- wording 强于 evidence；
- 漏掉反例；
- 漏掉 competing explanation；
- authority / source quality 不足；
- 术语不一致；
- 概念偷换；
- 时间线不一致；
- 叙述流畅掩盖 evidence gap。
```

### 7.3 Issue 结构

```yaml
review_issue:
  id: <stable-id>
  attack_type: <type>
  severity: low | medium | high | critical
  target: <claim/paragraph/section/artifact>
  finding: <short issue description>
  required_action:
    add_evidence | weaken_claim | narrow_scope | expand_scope |
    add_counterexample | correct_term | restructure | verify_source | other
  status: open | resolved | rejected
```

### 7.4 Red-Black 闭环

如果 L3 使用 red-black review，则每个 issue 必须显式对账：

```yaml
red_issue:
  id: R-001

black_response:
  disposition: accepted | rejected | partially_accepted
  rationale: <text>
  action_taken: <text>
  evidence_ref: <optional>

recheck:
  status: resolved | unresolved
```

仅写“已修改”“已修复”等自由文本，不得算 resolved。

必须有 `recheck`。

### 7.5 Meta Review 触发

如果 L3 连续：

```text
- 找不到新的有效 issue；
- 反复重复同一 issue 类；
- 只机械复述 checklist；
```

Runtime 应触发元审查，重新从：

```text
truthfulness
authority
goal alignment
```

寻找遗漏 attack surface。

目的是发现 reviewer/checklist 自身过拟合。

### 7.6 Failure code

```text
L3_SINGLETON_PROOF
  孤例被用来证明一般结论。

L3_CORRELATION_AS_SUPPORT
  相关性被当成支持/因果。

L3_SCOPE_MISMATCH
  claim 或文章 scope 不恰当。

L3_OVERCLAIM
  wording 超过 evidence 能力。

L3_MISSING_COUNTEREVIDENCE
  关键反例或 competing explanation 未接触。

L3_AUTHORITY_WEAKNESS
  支撑强 claim 的 source authority 不足。

L3_TERMINOLOGY_ERROR
  领域术语使用不一致或错误。

L3_CONCEPT_SUBSTITUTION
  发生概念偷换。

L3_CHRONOLOGY_ERROR
  时间线或先后关系错误。

L3_UNRESOLVED_REVIEW_ISSUE
  高优先级 review issue 未闭环。
```

---

## 8. 跨 Gate 一致性

Gate 栈必须支持跨层对账。

要求：

```text
L0 source identity
    -> L1 paper_id

L1 reading register
    -> L2 source_id

L2 evidence cards
    -> final artifact claims/citations

L3 issue targets
    -> L2 claim IDs / artifact locations
```

source 或 claim 的 key 不得跨层静默改变。

推荐稳定 ID：

```text
source_id
claim_id
issue_id
artifact_id
```

---

## 9. Reverse Reproducibility

应使用独立 reverse-reproducibility 检查 Gate 自身是否可复现。

应检查：

```text
- source fingerprint 是否稳定；
- evidence-card key 是否一致；
- L0/L1/L2 source ID 是否一致；
- 被引用 locator 是否仍有效；
- quote 是否仍匹配 source；
- reading_level 是否有证明；
- gate config fingerprint 是否有记录；
- 相同 input/config 是否能得到语义等价的机器 verdict。
```

参考结构：

```yaml
reverse_reproducibility:
  source_fingerprint_ok: true | false
  key_consistency_ok: true | false
  locator_validation_ok: true | false
  quote_match_ok: true | false
  reading_proof_ok: true | false
  config_fingerprint_ok: true | false
  deterministic_verdict_ok: true | false
```

建议 failure code：

```text
RR_SOURCE_FINGERPRINT_MISMATCH
  source 内容或身份指纹发生不一致。

RR_KEY_MISMATCH
  跨层 stable key 不一致。

RR_LOCATOR_INVALID
  页码/section/locator 已失效。

RR_QUOTE_MISMATCH
  保存的 quote 与当前 source 不匹配。

RR_READING_PROOF_MISSING
  reading level 缺少证明。

RR_CONFIG_UNVERSIONED
  Gate 配置没有版本/指纹。

RR_NONREPRODUCIBLE_VERDICT
  同 input/config 无法得到语义等价 verdict。
```

---

## 10. Gate 执行顺序

默认：

```text
G0
 -> L0
 -> L1
 -> L2
 -> L3
 -> reverse-reproducibility
```

如果依赖关系不被破坏，DSH 可以并行执行彼此独立的检查。

硬依赖示例：

```text
L1 fulltext verification 依赖真实 source access。
L2 source linkage 依赖稳定 source identity。
L3 evidence alignment review 依赖 L2 claim/evidence mapping。
```

如果上游硬依赖是 `BLOCKED`，下游 Gate 不得伪造 `PASS`。

可以返回：

```yaml
status: BLOCKED
reason: UPSTREAM_DEPENDENCY_BLOCKED
```

---

## 11. FAIL / WARN 策略

典型 hard fail：

```text
- 声称 fulltext 但没有证明；
- 事实性 claim 缺少要求 evidence；
- reverse evidence 冒充 forward support；
- source / locator 对不上；
- critical review issue 未解决；
- 严格 library policy 下引用了未入库 source。
```

典型 WARN：

```text
- source authority 低于偏好；
- source 年份老于 preferred recency；
- source diversity 不足；
- 存在非 critical unresolved reviewer issue；
- 工作流偏好 fulltext，但当前只有 abstract 且未设为 hard requirement。
```

FAIL/WARN 边界可以配置，但必须版本化，不能运行中临时改变。

---

## 12. 领域配置

机制字段保持通用。

示例：

```yaml
domain:
  name: <domain-name>

  source_identity:
    primary_keys:
      - doi
      - arxiv
      - isbn
      - canonical_url

  recency:
    preferred_years: 5

  authority_hierarchy:
    - standard
    - primary
    - official_authority
    - peer_reviewed_review
    - secondary

  glossary:
    - <term>

  library:
    provider: zotero | filesystem | other
    collection: <optional>
```

换领域时应该优先换 config，而不是改 Gate 机制代码。

---

## 13. 推荐机器命令 / Checker

DSH 仓库可以提供与以下语义等价的命令：

```text
gate_workspace_hygiene
gate_source_library
gate_reading_register
verify_forward_evidence
run_peer_review
verify_reverse_reproducibility
run_gates
```

聚合结果建议：

```yaml
research_gates:
  G0: PASS
  L0: PASS
  L1: PASS
  L2: FAIL
  L3: BLOCKED
  reverse_reproducibility: BLOCKED

overall: FAIL
blocking_gate: L2
```

聚合规则：

```text
if any enabled gate == FAIL:
    overall = FAIL

else if any enabled gate == BLOCKED:
    overall = BLOCKED

else if any enabled gate == WARN:
    overall = WARN

else:
    overall = PASS
```

---

## 14. 与 Research Flywheel 的集成

Gate 系统负责研究下限。

Gate 不负责判断某一轮有没有进展。

必须严格区分：

```text
gate_result
  -> “当前研究状态是否合格、是否允许继续使用？”

increment_result
  -> “这一轮是否真的让研究前进？”
```

因此：

```text
gate PASS + increment FAIL
```

是完全合法的组合，表示：

```text
没有明显违规，但 Agent 在空转。
```

必须进入 stall / `CLOCK_IN` 处理。

同样：

```text
increment PASS + gate FAIL
```

表示：

```text
这一轮有新内容，但新内容当前不合格，必须先 REPAIR。
```

推荐状态转换：

```text
gate FAIL
  -> REPAIR

gate PASS + increment FAIL
  -> STALLED / escalation logic

gate PASS + increment PASS
  -> continue / review / complete
```

---

## 15. 禁止事项

Gate 实现必须禁止：

```text
- 用模型先验知识推断 fulltext 已读；
- 因 source 主题相近就推断支持 exact claim；
- 把 reverse search 包装成 forward evidence；
- 静默跳过已启用检查；
- 接受损坏或不一致的 source ID / locator；
- 用 L3 的文字审稿替代 L2 evidence verification；
- 必要输入不可用时仍返回 PASS；
- 隐藏 unresolved critical issue；
- 把领域专用规则写死进通用 Gate 机制；
- 把 Gate PASS 当成研究有进展的证明。
```
