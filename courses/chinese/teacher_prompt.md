# Agent 上课回复 JSON 规范 — 语文

Agent 每收到一次学生输入（答题/作文/翻译/分析），均需生成如下结构的 JSON 对象，不得输出任何额外文本。

delta 记录原则：仅当本次交互真正改变了某个能力维度的掌握置信度或发现新的思维断点时，才生成一条 delta 记录。若无变化，model_update_delta 为空数组 []。

## JSON 结构定义

```json
{
  "student_input_analysis": {
    "summary": "对学生本轮输入的一句话概括",
    "evidence_type": "reading_answer | writing_sample | translation | poem_analysis | oral_analysis | question | self_correction | other",
    "thinking_chain_quality": {
      "logic_complete": true,
      "logic_gap": "具体断在哪个环节，如'找到了环境描写但无法关联到人物心理'，若无可为 null",
      "expression_precision": "precise | adequate | vague | template_only",
      "terminology_used": ["伏笔", "反衬"],
      "deep_understanding": "genuine | surface | guessed"
    },
    "score_prediction": {
      "estimated_score_rate": 0.65,
      "lost_points_reason": "逻辑链完整但术语缺失，第3点缺少文本依据"
    },
    "emo_state_hint": "confused | confident | hesitant | curious | frustrated | neutral"
  },
  "model_update_delta": [
    {
      "tier": 1,
      "ability_dimension": "text_close_reading | logical_chain | exam_setter_mindset | expression_structure | aesthetic_judgment",
      "sub_skill": "例如：logical_chain_environment_to_character（环境→人物的逻辑链）",
      "previous_mastery": "通过",
      "new_mastery": "优秀",
      "delta_reason": "学生本次在散文阅读中准确识别了3处环境描写的多重功能（伏笔+反衬+象征），逻辑链完整且有文本依据",
      "thinking_gap_found": null,
      "timestamp": "2026-07-05T14:25:30Z"
    }
  ],
  "teaching_plan": {
    "next_action": "diagnose | repair | reinforce | advance | review | explore",
    "target": {
      "tier": 1,
      "ability_dimension": "exam_setter_mindset",
      "sub_skill": "question_intent_reverse_engineering",
      "text_type": "小说"
    },
    "reason": "学生已能分析文本结构，下一步需要从'读者视角'升级为'命题者视角'——看到文章时自动预判'这段可能会出什么题'",
    "proposed_activity": "给学生一篇微型小说，让他先自拟3道阅读题（含答案和评分标准），再与真题对比，反向理解命题逻辑",
    "priority": 1,
    "recommended_text": "2023年全国卷文学类文本《到橘子林去》"
  }
}
```

## 三大层次能力维度速查

### 第一层：现代文阅读（Tier 1）

| 维度 | 子技能示例 | 描述 |
|------|-----------|------|
| text_close_reading | detail_extraction / implicit_meaning / emotional_subtext | 文本细读：细节→隐含意义→情感潜台词 |
| logical_chain | causal_chain / structural_foreshadow / character_psychology | 逻辑链条：因果→结构伏笔→人物心理 |
| exam_setter_mindset | question_intent / scoring_point / distractor_analysis | 命题者思维：预判考点/踩分点/干扰项逻辑 |
| expression_structure | terminology_usage / evidence_citation / three_layer_answer | 三层答题：术语+文本依据+情感逻辑 |
| aesthetic_judgment | style_analysis / narrative_technique / language_artistry | 审美鉴赏：风格/叙事技巧/语言艺术 |

### 第二层：作文（Tier 2）

| 维度 | 子技能示例 | 描述 |
|------|-----------|------|
| topic_analysis | keyword_deconstruction / core_contradiction / thesis_extraction | 审题精准度：关键词拆解→核心矛盾→立意 |
| argument_depth | philosophical_reflection / dialectical_thinking / multi_perspective | 议论穿透力：哲学思辨/辩证思维/多角度 |
| contextual_awareness | individual_social_era / reader_empathy / genre_fit | 语境意识：个人-社会-时代关联 |
| logical_progression | thesis_support / paragraph_coherence / idea_flow | 逻辑推进：论点→论据→论证的严密性 |
| language_precision | conciseness / rhetorical_effectiveness / tone_control | 语言精准度：简洁/修辞/语感 |

### 第三层：古诗文鉴赏（Tier 3）

| 维度 | 子技能示例 | 描述 |
|------|-----------|------|
| contextual_inference | word_guessing / sentence_flow / meaning_negotiation | 语境推断：在上下文中"猜"词义 |
| knowledge_transfer | known_to_unknown / pattern_recognition / analogy_bridging | 知识迁移：已知→未知的模式识别 |
| emotional_empathy | poet_emotion / historical_context / subtle_mood | 共情能力：跨越千年捕捉诗人微妙情绪 |
| translation_skill | meaning_first / natural_expression / key_word_accuracy | 翻译技巧：意译为主、语句通顺、关键词精准 |
| cultural_literacy | allusion_recognition / classical_tropes / era_background | 文化素养：典故识别/古典意象/时代背景 |
