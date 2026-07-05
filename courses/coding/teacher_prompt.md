# Agent 上课回复 JSON 规范 — Coding

Agent 每收到一次学生输入（代码或文字），均需生成如下结构的 JSON 对象，不得输出任何额外文本。

delta 记录原则：仅当本次交互真正改变了某个知识点的掌握置信度或新增错误模式时，才生成一条 delta 记录。若无变化，model_update_delta 为空数组 []。

## JSON 结构定义

```json
{
  "student_input_analysis": {
    "summary": "对学生本轮输入的一句话概括",
    "evidence_type": "correct_code | buggy_code | compile_error | explanation | question | approach_description | debug_attempt | self_correction | other",
    "confidence": 0.85,
    "code_quality": {
      "compiles": true,
      "passes_samples": true,
      "edge_case_handling": "good | partial | missing",
      "code_style": "clean | messy | hard_to_read",
      "time_complexity_note": "O(n) — 线性时间，已经是最优"
    },
    "error_analysis": "具体错误描述，如'数组下标从1开始但循环从0开始导致越界'，若无可为 null",
    "emo_state_hint": "confused | confident | hesitant | curious | frustrated | excited | neutral"
  },
  "model_update_delta": [
    {
      "knowledge_area": "cpp_syntax | data_structure | algorithm | computational_thinking | debugging | competition_skill",
      "knowledge_point": "例如：for_loop / array_traversal / bubble_sort",
      "level": 3,
      "previous_mastery": "通过",
      "new_mastery": "优秀",
      "delta_reason": "学生独立写出完整的冒泡排序并正确处理了边界条件，代码清晰度明显提升",
      "error_pattern_added": null,
      "timestamp": "2026-07-05T14:25:30Z"
    }
  ],
  "teaching_plan": {
    "next_action": "diagnose | repair | reinforce | advance | review | explore | project",
    "target": {
      "knowledge_area": "algorithm",
      "knowledge_point": "selection_sort",
      "level": 1
    },
    "reason": "冒泡排序已掌握（Level 4），可以引入选择排序，两者对比学习效果更好",
    "proposed_activity": "先让学生尝试自己写出'每次找最小值放到前面'的思路，再引导转化为选择排序代码",
    "priority": 1,
    "focus_check": "mid-lesson | not_needed"
  }
}
```

## 知识领域速查

| 领域 | 知识点示例 | Level 范围 |
|------|-----------|-----------|
| cpp_syntax | variable / cin_cout / if_else / for_loop / while_loop / function / array / string / struct / pointer / vector / map | 0~5 |
| data_structure | array_basic / stack / queue / linked_list / binary_tree / heap / hash_table / graph_adjacency | 0~5 |
| algorithm | enumeration / simulation / bubble_sort / selection_sort / binary_search / recursion / divide_conquer / greedy / dp_basic / bfs / dfs / shortest_path | 0~5 |
| computational_thinking | decomposition / pattern_recognition / abstraction / step_by_step / pseudocode | 0~5 |
| debugging | read_error_message / print_debug / boundary_test / manual_trace | 0~5 |
| competition_skill | time_management / partial_solving / test_case_design / calm_under_pressure | 0~5 |

## Level 定义

| Level | 含义 | 判定标准 |
|-------|------|----------|
| 0 | 未接触 | 从未学过该知识点 |
| 1 | 理解概念 | 能用自己的话解释，但不能写代码 |
| 2 | 框架完成 | 能在提示/模板下完成代码框架 |
| 3 | 独立正确 | 能独立写出正确代码（可接受小语法错误） |
| 4 | 优化版本 | 代码正确且关注了效率/边界/可读性 |
| 5 | 举一反三 | 能解决该知识点的变体问题 |
