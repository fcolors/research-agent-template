# Re-review Protocol — 最终对账与客观陈述抽检

> 本文件由主 agent 使用。  
> 它不是第三个 subagent，只是一份最终门禁协议。

---

## 1. Finding 对账

建立：

`Red finding → Black verdict → 实际修改/保留 → 证据`

逐条标记：

- ✅ `RESOLVED`
- ⚠️ `PARTIAL`
- `MISS`

判定规则：

### ✅ RESOLVED
- ACCEPT 后确实完成修正；
- PARTIAL 后成立部分已修正；
- REJECT 有明确、足够依据。

### ⚠️ PARTIAL
- 已处理但仍有残余不确定性；
- 证据存在但不足以支持原强度；
- 修改后仍需降级或补核。

### MISS
- Red 提了 MATERIAL/BLOCKER，Black 没处理；
- “认账”但正文没改；
- “反驳”但没有依据；
- 新增修订又产生新的真实性/权威性问题。

---

## 2. 高风险句抽检

至少抽查 2–3 句，优先选择：

- 带数字；
- 强因果；
- 比较性结论；
- “首次/证明/显著/优于”等强措辞；
- 依赖单一来源；
- 来源为预印本/技术报告；
- Black 本轮新增的句子。

对每句问：

1. 来源在哪里？
2. 原文实际报告什么？
3. 当前句是否比原文更强？
4. 是否丢失限定条件？
5. 引用是否直接支撑整句？
6. 数字性质是否准确？

---

## 3. Objective Statement Test

如果输出包含对单篇论文的客观陈述，每句必须通过：

### Test A — Source test
能否指出原文依据？

### Test B — Scope test
是否只说该文实际研究的对象和条件？

### Test C — Modality test
是否保留作者的不确定性和限定词？

### Test D — Interpretation test
是否混入了 reviewer 自己的解释？

### Test E — Number test
数字的值、单位、对象、条件、性质是否一致？

任一失败：
- 修改；
- 降级措辞；
- 或删除。

---

## 4. Citation-support Test

随机选若干正文引用，做反向检查：

> “如果把正文这句话单独交给该来源，它真的能支持吗？”

特别防止：

- 来源只提到主题，但未报告正文结论；
- 一篇论文只支持复合句的一半；
- 引用用于背景，却被正文当作实证；
- 二手来源替代已有可获得的原始来源。

---

## 5. Convergence

只有满足以下条件才能判定收敛：

- 无未处理 BLOCKER；
- 无未处理 MATERIAL；
- 所有 REJECT 均有依据；
- 抽检句无真实性漂移；
- 客观陈述通过 source-bounded test；
- 剩余问题仅为 MINOR 或 OPTIONAL。

输出：

`CONVERGED`

或：

`NOT CONVERGED`

若 `NOT CONVERGED`，只列真正阻塞交付的问题，不开启无限扩展式审稿。

---

## 6. 最终用户交付原则

向用户交付时：

- 不暴露内部角色表演；
- 直接给修订结果与必要的核验说明；
- 对尚未核验处明确标注；
- 不把内部 confidence 包装成外部事实；
- 用户若只要客观陈述，就只给客观陈述，不附加额外解释。
