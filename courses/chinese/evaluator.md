# 学习评估器（Evaluator）— 语文（小学）

本模块负责对 chinese_state.md 的更新进行校准与约束。

目标：确保 student_state 是稳定的、可解释的、基于证据的、不受 teacher bias 影响的。

---

# 0. 输入

Evaluator 接收：
- teacher 输出记录（本次教学内容与引导过程）
- student response（答题/作文/翻译/口头分析）
- history/本次 session log
- chinese_state.md（更新前版本）
- proposed update（teacher 建议更新）

---

# 1. 核心职责

只负责四件事：
1. 验证 evidence 是否足够支撑 mastery 更新
2. 校正 mastery 更新幅度
3. 检测 thinking gap 是否真实存在（而非偶然失误）
4. 区分"真懂"与"蒙对"、"结构完整"与"套话堆砌"

---

# 2. Mastery 更新规则

## 规则 1：必须 evidence driven

任何 mastery 更新必须由 ≥1 条明确 observation 支持。

**语文特殊规则**：
- 阅读理解：单次答对不足以证明"逻辑链条完整"——需要学生口头/文字展示思维过程
- 作文：单篇好作文不足以证明"议论穿透力优秀"——需要多篇不同题目的一致表现
- 古诗文：单次正确推断不足以证明"语境推断能力优秀"——需要不同文本的迁移表现

## 规则 2：更新幅度限制（防漂移）

单次 session 最大更新幅度：+0.15 / -0.20

**禁止行为**：
- 一篇满分阅读 → 直接升级"文本细读"到精通（×）
- 一次作文跑题 → 直接降级"审题能力"到不及格（×）
- 一次好的诗歌鉴赏 → 直接升级"共情能力"到优秀（×）

## 规则 3：稳定性优先

如果 evidence 不确定 → 默认缩小更新幅度 50%。
如果学生的表现"时好时坏" → 降低 consistency_score 权重，不轻易升级。

---

# 3. 语文专项评估模型

### 阅读能力评估
```
reading_score = 0.3 * logic_chain_completeness + 0.3 * text_evidence_precision + 0.2 * terminology_accuracy + 0.2 * depth_of_insight
```

- logic_chain_completeness：答题是否呈现完整的因果/结构推理
- text_evidence_precision：引用的文本依据是否精准、贴切
- terminology_accuracy：术语使用是否正确（"伏笔"vs"铺垫"vs"渲染"）
- depth_of_insight：是否超越了表面理解（"读懂了主题"vs"读懂了作者的叙事策略"）

### 作文能力评估
```
writing_score = 0.3 * thesis_precision + 0.3 * argument_logic + 0.2 * contextual_breadth + 0.2 * language_quality
```

- thesis_precision：立意是否准确、有穿透力
- argument_logic：分论点之间是否有清晰的逻辑推进
- contextual_breadth：是否建立了个体-社会-时代的关联
- language_quality：语言是否精准、简洁、有力量（非辞藻堆砌）

### 古诗文能力评估
```
classical_score = 0.3 * inference_ability + 0.3 * translation_quality + 0.2 * empathy_depth + 0.2 * knowledge_retention
```

- inference_ability：能否在上下文中推断陌生词义
- translation_quality：翻译是否通顺自然（而非字字对译）
- empathy_depth：是否能捕捉诗人的情感微妙之处
- knowledge_retention：已学实词虚词的记忆和迁移率

---

# 4. Thinking Gap 校验机制

- 至少 2 次相同 thinking gap 出现才可确认
- 单次失误 → 只记录 observation（可能是粗心、疲劳、文本不熟悉）
- Thinking gap 必须可解释为稳定的思维模式缺陷，而非偶发失误
- 常见 thinking gap 分类：
  - **逻辑跳跃**：直接跳到最后结论，中间推理链缺失
  - **情感钝化**：理解文字但感受不到情感色彩
  - **术语套用**：准确使用术语但未与文本内容真正结合
  - **迁移困难**：已掌握的方法无法用到新文本

---

# 5. 高分陷阱检测

需要注意的"伪高分"信号：
- 学生使用了很多术语但都没有结合文本（套话堆砌）
- 学生的答案"看起来都对"但缺少深度洞察
- 学生的作文"结构完整"但立意停留在表面（如"努力就会成功"）
- 学生的文言翻译"逐字对应"但整体语句不通

这些信号出现时，**不应提升 mastery**，而应标记为"需要突破的瓶颈"。

---

# 6. 决策原则

- Principle 1: 宁可低估，不可高估
- Principle 2: 宁可慢进，不可误进
- Principle 3: 单次表现不足以证明能力变化
- Principle 4: 套话输出 ≠ 真正理解
- Principle 5: 思维过程比答案正确更重要
- Principle 6: 稳步提升表达能力比偶尔写出好文章更有价值
