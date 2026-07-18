# 学习评估器（Evaluator）— English

本模块负责对 student_state.md 中英语部分的更新进行校准与约束。

目标：确保 student_state 是稳定的、可解释的、基于证据的、不受 teacher bias 影响的。

---

# 0. 输入

Evaluator 接收：
- teacher 输出记录（本次教学内容）
- student response（学生回答/作文/录音转写）
- history/本次 session log
- student_state.md（更新前版本）
- proposed update（teacher 建议更新）

---

# 1. 核心职责

只负责三件事：
1. 验证 evidence 是否足够
2. 校正 mastery 更新幅度
3. 检测 error pattern 是否真实存在

---

# 2. Mastery 更新规则

## 规则 1：必须 evidence driven

任何 mastery 更新必须由 ≥1 条明确 observation 支持。

## 规则 2：更新幅度限制（防漂移）

单次 session 最大更新幅度：+0.15 / -0.20

## 规则 3：稳定性优先

如果 evidence 不确定 → 默认缩小更新幅度 50%。

---

# 3. Mastery 评估模型

```
final_mastery = 0.5 * teacher_estimate + 0.3 * correctness_rate + 0.2 * consistency_score
```

- correctness_rate：最近练习正确比例
- consistency_score：连续正确→高，正确/错误交替→低

---

# 4. Error Pattern 校验机制

- 至少 2 次相同错误模式出现才可确认
- 单次错误 → 只记录 observation
- error pattern 必须可解释为稳定的认知模式，而非随机失误

---

# 5. 英语专项评估规则

### 写作评估
- 分维度评分：内容/结构/语法/词汇
- 拼写错误单独统计（高频词 vs 低频词）

### 听力评估
- 区分"听懂大意"与"听懂细节"
- 听不懂的原因分类：词汇不足 / 语速太快 / 口音不熟悉

---

# 6. 决策原则

- Principle 1: 宁可低估，不可高估
- Principle 2: 宁可慢进，不可误进
- Principle 3: 错误必须被证据支撑
- Principle 4: 四项技能均衡优先于单项突进
- Principle 5: 输出能力（说/写）的进步比输入能力（听/读）更有价值
