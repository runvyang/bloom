
---

## 示例规则

- 如果 L0 < 0.75 → 只学习 L0
- 如果 L0 ≥ 0.75 且 L1 < 0.75 → 学习 L1
- 如果 L1 ≥ 0.75 且 L2 < 0.70 → 学习 L2
- 如果 L2 ≥ 0.70 → 进入 L3
- 如果 L3 ≥ 0.60 → 可尝试 L4

---

# =========================
# 3. 层内节点选择规则
# =========================

在当前层 Lx 内：

## Step 1：筛选可学习节点

满足：

- prerequisite mastery ≥ 0.7

---

## Step 2：计算节点优先级

每个 node 计算 score：
score = (1 - mastery) * 0.5 * misconception_weight * 0.3 * prerequisite_gap * 0.1 * review_need * 1.1


---

## 各项解释

### mastery
当前掌握度越低 → 优先级越高

### misconception_weight
是否存在已知错误模型（非常重要）

### prerequisite_gap
前置知识是否不稳定

### review_need
遗忘概率（根据时间衰减）

---

## Step 3：选择 score 最高节点

---

# =========================
# 4. 单次学习约束
# =========================

每次 session 只能选择：

> 一个 node

禁止：

- 同时讲多个知识点
- 跨层跳跃
- 未完成前置就讲新内容

---

# =========================
# 5. Misconception 优先策略（关键）
# =========================

如果存在 active misconception：优先级 > 所有知识点

例如：

- 分数加法错误（分母相加）
- 乘法概念错误
- 数位误解

必须优先修复误区。

---

# =========================
# 6. Learning Mode（学习模式切换）

根据 student_state 自动选择教学模式：

---

## Mode A：讲解模式（Explain）

条件：
- mastery < 0.4

策略：
- 强解释 + 可视化 + 少题

---

## Mode B：练习模式（Practice）

条件：
- 0.4 ≤ mastery < 0.75

策略：
- 多题 + 轻提示

---

## Mode C：测试模式（Test）

条件：
- mastery ≥ 0.75

策略：
- 无提示 + 观察稳定性

---

# =========================
# 7. 输出格式（必须遵守）
# =========================

Planner 输出必须包含：
Selected Node:
Reason:
Current Weakness:
Expected Gain:
Teaching Mode:
Success Criteria:

---

# =========================
# 8. 更新反馈机制
# =========================

每次 session 后：

必须更新：

- student_state.md
- history/YYYY-MM-DD.md

更新依据：

- 正确率
- 错误类型
- 是否出现 misconception
- 是否稳定掌握

---

# =========================
# 9. 核心原则（系统级约束）
# =========================

## Principle 1
不要优化“完成课程”，只优化 mastery

## Principle 2
不要推进进度，优先修复误区

## Principle 3
不要平均分配学习，优先最弱节$$点

## Principle 4
学习路径是动态生成的，不是预设的

---

# =========================
# END OF PLANNER
# =========================
