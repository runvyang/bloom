# Agent 上课回复 JSON 规范 — 点招冲刺

delta 记录原则：仅当本次交互真正改变了某个题型的掌握程度或发现新的错误模式时，才生成 delta。无变化时 model_update_delta 为空数组 []。

## JSON 结构定义

```json
{
  "student_input_analysis": {
    "summary": "对学生本轮解题的一句话概括",
    "current_week": "第1-12周",
    "current_problem_type": "M1 | M2 | M3 | M4 | M5 | T1 | T2 | I1",
    "current_model": "当前训练的标准模型，如：沙漏模型面积比",
    "current_status": "当前掌握程度",
    "evidence_type": "correct_answer | incorrect_answer | partial_correct | explanation | question | stuck | time_out | self_correction | other",
    "error_category": "计算错误 | 模型不会 | 看错条件 | 时间不够 | 无",
    "time_used": "本道题用时（分钟），限时题必填",
    "emo_state_hint": "confident | anxious | focused | frustrated | engaged | neutral"
  },
  "model_update_delta": [
    {
      "week": 1,
      "problem_type": "M1",
      "sub_skill": "如：sandglass_area_ratio（沙漏面积比）",
      "previous_mastery": "未评估",
      "new_mastery": "通过",
      "delta_reason": "学生能独立识别沙漏模型并正确应用面积比公式解题",
      "error_pattern_added": "有时忘记对应边平方关系，误用一次比",
      "timestamp": "2026-08-25T14:25:30Z"
    }
  ],
  "teaching_plan": {
    "next_action": "teach_model | practice | mixed_review | timed_test | error_review | mock_exam",
    "target_week": 1,
    "target_type": "M1",
    "target_point": "蝴蝶模型比例转换",
    "reason": "沙漏模型已掌握，进阶到蝴蝶模型",
    "proposed_activity": "2 道蝴蝶模型比例转换题，先画图标注再计算",
    "time_limit": 15,
    "priority": 1
  }
}
```

## 题型速查

| 编号 | 考点 | 子技能示例 |
|------|------|-----------|
| M1 | 几何模型 | sandglass_area_ratio / butterfly_proportion / shadow_area |
| M2 | 行程综合 | catch_up / meet_twice / variable_speed / segment_analysis |
| M3 | 数论 | coprime_diagonal / divisibility / gcd_lcm |
| M4 | 最值优化 | min_perimeter / tiered_pricing / optimal_choice |
| M5 | 计数组合 | addition_multiplication / star_and_bar / at_least_at_most |
| T1 | 图形空间 | symmetry_rotation / cube_unfold / spatial_relation |
| T2 | 逻辑记忆 | ranking_logic / sequence_memory / word_recall |
| I1 | 信息学 | binary_decimal / graph_vertices / connectivity |

掌握程度标签：未评估 / 不及格 / 通过 / 优秀 / 精通

**特别规则**：
- 每题必须标注 error_category（错误原因分类）
- 限时题必须记录 time_used
- 第三阶段模考题要记录得分率
