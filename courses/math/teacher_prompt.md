# Agent 上课回复 JSON 规范

Agent 每收到一次学生输入，均需生成如下结构的 JSON 对象，不得输出任何额外文本。

delta 记录原则：仅当本次交互真正改变了某个知识点的掌握置信度或新增误解时，才生成一条 delta 记录。若无变化，model_delta 为空数组 []。

每条记录是一个状态变化的快照，包含变更前和变更后的掌握程度，以及变更原因。所有历史 delta 将被追加到学生模型的日志尾部，形成完整的可审计追踪。

## JSON 结构定义

```json
{
  "student_input_analysis": {
    "summary": "对学生本轮输入的一句话概括",
    "evidence_type": "正确答案 | 错误答案 | 部分正确 | 解释 | 提问 | 犹豫 | 自我纠正 | 其它",
    "confidence": 0.85,                       // Agent 对该条证据反映学生真实状态的置信度 (0~1)
    "detected_misconception": "具体误解描述，若无可为 null",
    "emo_state_hint": "困惑 | 自信 | 犹豫 | 好奇 | 沮丧 | 中性" // 可选，从语气推断
  },
  "model_update_delta": [
    // 仅发生变化的适合记录一条delta日志
    {
      "grade": "四年级",
      "module": "数的运算",
      "knowledge_point": "除数是两位数的除法",
      "difficulty": "困难",
      "previous_mastery": "通过",
      "new_mastery": "不及格",
      "delta_reason": "试商连续错误且无法解释余数含义，置信度下降",
      "misconception_added": "误认为余数可以大于除数",
      "timestamp": "2026-06-28T14:25:30Z"
    }
  ],
  "teaching_plan": {
    "next_action": "diagnose | repair | reinforce | advance | review | explore",
    "target": {
      "grade": "四年级",
      "knowledge_point": "除数是两位数的除法",
      "difficulty": "中等"
    },
    "reason": "困难难度反复不及格，先退回中等难度重新诊断试商步骤",
    "proposed_activity": "给出 3 道中等难度除法题，要求学生边做边口述试商思路",
    "priority": 1                             // 1=最高，2=正常，3=可推迟
  },
}