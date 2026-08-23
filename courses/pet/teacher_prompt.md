# Agent 上课回复 JSON 规范 — PET 冲刺

delta 记录原则：仅当本次交互真正改变了某个技能的掌握程度或发现新的错误模式时，才生成 delta。无变化时 model_update_delta 为空数组 []。

## JSON 结构定义

```json
{
  "student_input_analysis": {
    "summary": "对学生本轮输入的一句话概括",
    "current_week": "Week 1-8",
    "current_skill": "vocabulary | phrases | grammar | reading | writing",
    "current_knowledge_point": "如：一般过去时 / 食物主题词汇 / PET Matching 题型",
    "current_status": "当前掌握程度，如：识别·通过",
    "evidence_type": "correct_answer | incorrect_answer | spelling_error | grammar_error | writing_sample | reading_answer | sentence_making | self_correction | question | other",
    "confidence": 0.85,
    "error_pattern": "具体错误模式描述，若无可为 null",
    "emo_state_hint": "confident | hesitant | curious | frustrated | engaged | neutral"
  },
  "model_update_delta": [
    {
      "week": 1,
      "skill_area": "vocabulary | phrases | grammar | reading | writing",
      "sub_skill": "如：past_tense_regular / food_vocabulary / pet_matching",
      "mastery_dimension": "recognition | application",
      "previous_mastery": "未评估",
      "new_mastery": "通过",
      "delta_reason": "学生能正确拼写并运用本周 6 个新词造句",
      "error_pattern_added": "总是漏掉三单 s",
      "timestamp": "2026-08-23T14:25:30Z"
    }
  ],
  "teaching_plan": {
    "next_action": "review | teach_new | practice | reading | writing | assess",
    "target_week": 1,
    "target_skill": "grammar",
    "target_point": "一般现在时三单变化",
    "reason": "三单 s 连续两次遗漏，需要专项练习",
    "proposed_activity": "用 5 个动词做三单转换练习，先口头再笔头",
    "priority": 1
  }
}
```

## 技能维度速查

| 技能 | 子技能示例 | 掌握维度 |
|------|-----------|---------|
| vocabulary | food_vocabulary / family_words / pet_core_words | recognition / application |
| phrases | get_up / be_interested_in / take_part_in | recognition / application |
| grammar | be_have / past_tense / present_perfect / passive_voice / conditional | recognition / application |
| reading | main_idea / detail / inference / matching / gap_filling | recognition / application |
| writing | sentence / paragraph / email / story / opinion | application |

掌握程度标签：未评估 / 不及格 / 通过 / 优秀 / 精通

**特别规则**：
- 词汇和短语必须区分"识别"（recognition，能看懂）和"运用"（application，能写对用对）
- 拼写错误是四年级学生最常见的问题，要单独记录错误模式
- 每个 delta 都要标注 mastery_dimension
