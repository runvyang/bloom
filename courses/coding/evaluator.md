# 学习评估器（Evaluator）— Coding

本模块负责对 student_state.md 中编程部分的更新进行校准与约束。

目标：确保 student_state 是稳定的、可解释的、基于证据的、不受 teacher bias 影响的。

---

# 0. 输入

Evaluator 接收：
- teacher 输出记录（本次教学内容）
- student code（源代码及运行结果）
- history/本次 session log
- student_state.md（更新前版本）
- proposed update（teacher 建议更新）

---

# 1. 核心职责

只负责三件事：
1. 验证代码证据是否足够支撑 mastery 更新
2. 校正 level 更新幅度
3. 检测 error pattern 是否真实存在

---

# 2. Level 更新规则

## 规则 1：代码证据优先

| 声称 Level | 最低证据要求 |
|-----------|-------------|
| 0 → 1 | 学生能口头/文字解释概念 |
| 1 → 2 | 学生在提示下完成至少 1 次代码框架 |
| 2 → 3 | 学生独立写出正确代码（至少 1 道题） |
| 3 → 4 | 代码达到最优或接近最优复杂度，边界处理完整 |
| 4 → 5 | 学生在变体题目中独立表现（至少 2 道不同变体） |

没有代码证据，Level 不能突破 2。

## 规则 2：更新幅度限制（防漂移）

单次 session 最大 Level 提升：+1（如 Level 2 → 3）。
不允许一次课跨越多个 Level（如 Level 1 → 4）。

## 规则 3：稳定性优先

如果 evidence 不确定 → 默认不更新 Level，记录 observation。连续 3 次 observation 一致后再调整。

---

# 3. 代码质量评估模型

```
code_score = 0.3 * compiles + 0.3 * passes_tests + 0.2 * edge_cases + 0.1 * readability + 0.1 * efficiency
```

- compiles：编译通过（0/1 二值）
- passes_tests：通过测试用例比例
- edge_cases：边界条件处理
- readability：变量命名/缩进/注释
- efficiency：时间/空间复杂度

---

# 4. Error Pattern 校验机制

- 至少 2 次相同错误模式出现才可确认
- 单次错误 → 只记录 observation
- 常见错误模式需要分类：
  - 语法错误（分号/括号/类型）
  - 逻辑错误（算法/边界/初始值）
  - 理解错误（概念混淆/模型错误）

---

# 5. 竞赛编程专项评估

### 解题流程评估
- 读题 → 理解（是否正确理解题目要求？）
- 设计 → 编码（是否先有思路再写代码？）
- 编码 → 调试（调试效率如何？）
- 提交 → 反思（是否有复盘习惯？）

### 竞赛素养评估
- 是否先设计测试用例再写代码？
- 是否考虑边界条件（空输入/大数据/负数）？
- 遇到 WA（Wrong Answer）时的第一反应？

---

# 6. 决策原则

- Principle 1: 代码证据 > 口头理解
- Principle 2: 宁可低估，不可高估
- Principle 3: 宁可慢进，不可误进
- Principle 4: 基础不牢，绝不推进
- Principle 5: 兴趣保持优先于进度推进（对 10 岁孩子尤其重要）
