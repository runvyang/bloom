# PET World Model Skills

The Learning World Model is stored entirely in Markdown. Every skill operates on Markdown files. Never keep important information only in conversation context. Always update the world model.

---

# Skill 1 — Read State

Before every lesson, read:
- `courses/pet/world_model.md`
- `data/student/{username}/pet_map.md`
- `data/student/{username}/pet_progress.md`
- `courses/pet/planner.md`

Goal: Answer:
- What week/phase is the student in?
- What vocabulary did they learn yesterday (to review today)?
- What error patterns are active?
- What should today's 30-40 minutes cover?

---

# Skill 2 — Record Observation

Record objective evidence during the lesson.

Only record facts:
- spelled "breakfast" correctly on first try
- recognized 6/8 food words without hints
- confused "much" and "many" (2nd time)
- used "delicious" correctly in a sentence
- guessed "environment" meaning correctly from context
- spelled "because" wrong twice

Do not update mastery here. Only collect evidence.

---

# Skill 3 — Update State

Update the student model after enough evidence.

Possible updates: vocabulary mastery (recognition/application), spelling error patterns, word family mastery, review queue.

Every update supported by recorded observations. Small evidence → small change. Repeated evidence → larger change.

Special PET rules:
- Vocabulary has TWO dimensions: recognition and application
- Spelling errors tracked separately
- Word families tracked as a unit
- Review queue: words needing spaced repetition

---

# Skill 4 — Plan Next Step

Generate the next learning objective.

Select next target according to:
1. Current week in the 8-week plan
2. Yesterday's new vocabulary (must review today)
3. Active error patterns needing repair
4. Skill balance for the week's focus (Reading week vs Writing week)

The planner should always produce:
- Today's review list (old words/phrases)
- Today's new content (≤8 words or 1 grammar point)
- Today's reading/writing task
- Expected outcome

---

# Execution Loop

1. Read State → 2. Review (spiral) → 3. Teach New → 4. Practice → 5. Record Observation → 6. Update State

The Markdown files are the single source of truth. Conversation history is temporary. The world model is permanent.
