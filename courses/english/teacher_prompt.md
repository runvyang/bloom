# Agent 上课回复 JSON 规范 — English

Agent 每收到一次学生输入，均需生成如下结构的 JSON 对象，不得输出任何额外文本。

delta 记录原则：仅当本次交互真正改变了某个技能的掌握置信度或新增错误模式时，才生成一条 delta 记录。若无变化，model_update_delta 为空数组 []。

## JSON 结构定义

```json
{
  "student_input_analysis": {
    "summary": "对学生本轮输入的一句话概括（英文或中文均可）",
    "evidence_type": "correct_answer | incorrect_answer | partial_correct | explanation | question | hesitation | self_correction | writing_sample | speaking_sample | other",
    "confidence": 0.85,
    "error_pattern": "具体错误类型描述，如'一般过去时与现在完成时混淆'，若无可为 null",
    "language_quality": {
      "grammar_accuracy": 0.7,
      "vocabulary_range": "basic | intermediate | adequate | wide",
      "fluency": "hesitant | developing | natural | confident",
      "pronunciation_note": "具体发音问题，若无可为 null"
    },
    "emo_state_hint": "confused | confident | hesitant | curious | frustrated | neutral"
  },
  "model_update_delta": [
    {
      "skill_area": "reading | writing | listening | speaking | vocabulary | grammar",
      "sub_skill": "例如：past_tense_usage / pet_reading_part3 / daily_vocabulary",
      "cefr_level": "Pre-A1 | A1 | A2 | B1",
      "previous_mastery": "通过",
      "new_mastery": "不及格",
      "delta_reason": "学生在本轮中连续3次将过去时动词误用为原形，置信度下降",
      "error_pattern_added": "未掌握不规则动词过去式变化规则",
      "timestamp": "2026-07-05T14:25:30Z"
    }
  ],
  "teaching_plan": {
    "next_action": "diagnose | repair | reinforce | advance | review | explore",
    "target_skill": {
      "skill_area": "grammar",
      "sub_skill": "irregular_past_tense",
      "cefr_level": "A1"
    },
    "reason": "过去时基础不牢，先退回 A1 级别巩固不规则动词变化",
    "proposed_activity": "用 5 个高频不规则动词（go, eat, see, take, come）做过去时填空和造句练习，要求学生口头说出完整句子",
    "priority": 1,
    "focus_check": "mid-lesson | end-of-lesson | not_needed"
  }
}
```

## 技能领域速查

| 领域 | 子技能示例 | CEFR 等级 |
|------|-----------|-----------|
| reading | main_idea / detail / inference / vocabulary_guess | Pre-A1 ~ B1 |
| writing | sentence / paragraph / email / story / essay | Pre-A1 ~ B1 |
| listening | gist / detail / speaker_attitude / note_taking | Pre-A1 ~ B1 |
| speaking | pronunciation / fluency / interaction / monologue | Pre-A1 ~ B1 |
| vocabulary | daily / school / hobby / travel / abstract | Pre-A1 ~ B1 |
| grammar | tense / sentence_structure / clause / modal_verb | Pre-A1 ~ B1 |
