# Agent 上课回复 JSON 规范 — 小小学习科学家

delta 记录原则：仅当本次交互观察到新的学习行为模式或能力变化时，才生成 delta。无变化时 model_update_delta 为空数组 []。

## JSON 结构定义

```json
{
  "student_input_analysis": {
    "summary": "对孩子本轮表现的一句话概括",
    "current_week": "Week 1-12",
    "current_ability": "学习能力维度",
    "current_level": "当前观察到的水平描述",
    "evidence_type": "guess | explanation | question | self_correction | error_analysis | transfer_attempt | reflection | experiment_result | other",
    "scaffolding_level_used": 0,
    "learning_behavior_observed": "具体的可观察学习行为描述",
    "emo_state_hint": "curious | confused | confident | frustrated | engaged | neutral"
  },
  "model_update_delta": [
    {
      "week": 1,
      "ability_dimension": "independence | retrieval | error_analysis | problem_decomposition | explanation | transfer | metacognition | persistence | strategy | attention",
      "sub_skill": "例如：retrieval_practice_habit（主动回忆习惯）",
      "previous_level": "之前水平描述",
      "new_level": "新水平描述",
      "delta_reason": "孩子在本次实验中主动尝试闭卷回忆，且能准确描述回忆困难在哪里",
      "timestamp": "2026-08-09T14:25:30Z"
    }
  ],
  "teaching_plan": {
    "next_action": "challenge | experiment | discover | transfer | reflect | mission | scaffold",
    "target_week": 1,
    "target_ability": "retrieval",
    "reason": "一句话",
    "proposed_activity": "简短描述",
    "scaffolding_level": 1,
    "priority": 1
  }
}
```

## 能力维度速查

| 维度 | 观察什么 | 子技能示例 |
|------|---------|-----------|
| independence | 是否越来越少需要提示 | self_start / hint_frequency / self_check |
| retrieval | 是否主动尝试回忆 | active_recall / self_testing / retrieval_habit |
| error_analysis | 是否能解释为什么错 | error_classify / pattern_find / fix_plan |
| problem_decomposition | 是否能把大问题拆小 | break_down / step_by_step / chunking |
| explanation | 能否用自己的话解释 | feynman / teach_others / example_generate |
| transfer | 能否把方法用到新任务 | cross_subject / real_world_apply / pattern_recognize |
| metacognition | 是否知道自己哪里不会 | know_what_dont_know / strategy_aware / self_assess |
| persistence | 遇到困难是否继续尝试 | try_again / help_seek / frustration_tolerance |
| attention | 专注力表现 | single_task / distraction_manage / focus_duration |
