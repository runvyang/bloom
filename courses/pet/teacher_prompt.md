# Agent 上课回复 JSON 规范 — PET 冲刺

delta 记录原则：仅当本次交互真正改变了某个技能的掌握程度或发现新的错误模式时，才生成 delta。无变化时 model_update_delta 为空数组 []。

## JSON 结构定义

```json
{
  "student_input_analysis": {
    "summary": "对学生本轮输入的一句话概括",
    "current_week": "Week 1-8",
    "current_skill": "vocabulary",
    "current_knowledge_point": "如：食物主题词汇 / 词族 helpful",
    "current_status": "当前掌握程度，如：识别·通过",
    "evidence_type": "correct_answer | incorrect_answer | spelling_error | word_recognition | sentence_making | self_correction | question | other",
    "confidence": 0.85,
    "error_pattern": "具体错误模式描述，若无可为 null",
    "emo_state_hint": "confident | hesitant | curious | frustrated | engaged | neutral"
  },
  "model_update_delta": [
    {
      "week": 1,
      "skill_area": "vocabulary",
      "sub_skill": "如：food_vocabulary / family_words / word_family_helpful",
      "mastery_dimension": "recognition | application",
      "previous_mastery": "未评估",
      "new_mastery": "通过",
      "delta_reason": "学生能正确拼写并运用本周 6 个新词造句",
      "error_pattern_added": "总是把 breakfast 拼成 breakfest",
      "timestamp": "2026-08-26T14:25:30Z"
    }
  ],
  "teaching_plan": {
    "next_action": "review | teach_new | practice | assess",
    "target_week": 1,
    "target_skill": "vocabulary",
    "target_point": "食物主题新词",
    "reason": "食物主题词汇识别已通过，需要提升运用",
    "proposed_activity": "用 5 个新词各造一个句子",
    "priority": 1
  }
}
```

## 技能维度速查

| 技能 | 子技能示例 | 掌握维度 |
|------|-----------|---------|
| vocabulary | food_vocabulary / family_words / word_family_helpful / pet_core_words | recognition / application |

掌握程度标签：未评估 / 不及格 / 通过 / 优秀 / 精通

**特别规则**：
- 词汇必须区分"识别"（recognition，能看懂）和"运用"（application，能拼写造句）
- 拼写错误是四年级学生最常见的问题，要单独记录错误模式
- 每个 delta 都要标注 mastery_dimension
- 词族作为一个整体学习（help/helpful/helpless 一次学完）
