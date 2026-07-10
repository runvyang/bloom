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

## 四大层次能力维度速查

### 第一层：字词基础（Tier 1）

| 维度 | 子技能示例 | 描述 |
|------|-----------|------|
| character_mastery | recognition / writing / stroke_order / similar_char | 识字写字：认读/书写/笔顺/形近字 |
| vocabulary | understanding / synonym_antonym / collocation / sentence_making | 词语运用：理解/近反义词/搭配/造句 |
| sentence_basics | transformation / expansion / error_fix / punctuation | 句子基础：句式变换/扩缩写/病句/标点 |

### 第二层：阅读理解（Tier 2）

| 维度 | 子技能示例 | 描述 |
|------|-----------|------|
| reading_fluency | read_aloud / silent_reading_speed / retelling | 朗读与默读：流利度/速度/复述 |
| comprehension | main_idea / detail_finding / simple_inference / key_sentence | 理解能力：大意/细节/推断/关键词句 |
| reading_thinking | questioning / connecting_to_life / comparing / predicting | 阅读思维：提问/联系生活/比较/预测 |

### 第三层：写作表达（Tier 3）

| 维度 | 子技能示例 | 描述 |
|------|-----------|------|
| writing_basics | sentence_fluency / paragraph_structure / observation | 写作基础：句子通顺/段落结构/观察力 |
| narrative_skills | six_elements / engaging_beginning / detailed_process / feeling_ending | 记叙文：六要素/开头/经过/结尾感受 |
| creative_writing | picture_composition / story_continuation / imagination / figurative_language | 创意写作：看图写话/续写/想象/修辞 |

### 第四层：古诗文启蒙（Tier 4）

| 维度 | 子技能示例 | 描述 |
|------|-----------|------|
| poetry_recitation | textbook_poems / extra_reading / accurate_dictation / author_dynasty | 古诗背诵：课内/课外/默写/作者朝代 |
| poetry_understanding | surface_meaning / imagery_perception / emotion_feeling / rhythm | 古诗理解：字面意思/画面感/情感/韵律 |
| classical_initiation | short_classical_text / common_words / story_retelling | 文言启蒙：小古文/常见字词/故事复述 |
