# English World Model Skills

The Learning World Model is stored entirely in Markdown.

Every skill operates on Markdown files. Never keep important information only in conversation context. Always update the world model.

---

# Skill 1 — Read State

Before every lesson, read:
- `courses/english/world_model.md`
- `data/student/{username}/student_state.md` (English state section)
- `courses/english/planner.md`
- latest history log

Goal: Answer:
- What is the student's current CEFR level across skills?
- What is the weakest skill that most blocks progress?
- What are the active error patterns?
- What should happen today?

---

# Skill 2 — Record Observation

Record objective evidence during the lesson. Append to today's history log.

Only record facts. Examples:
- used past tense correctly 3/5 times
- confused "since" and "for" in present perfect
- read PET part 3 passage with 80% comprehension
- pronounced "th" as "s" consistently
- showed confidence in speaking about hobbies
- lost focus after 12 minutes

Do not update mastery here. Only collect evidence.

---

# Skill 3 — Update State

Update the student model after enough evidence. Modify `student_state.md`.

Possible updates: mastery level, confidence, error patterns, strengths, weaknesses, vocabulary growth, review queue.

Every update supported by recorded observations. Small evidence → small change. Repeated evidence → larger change. Never invent information.

---

# Skill 4 — Plan Next Step

Generate the next learning objective. Update planner output.

Select next target according to:
1. Skill dependency (can't write paragraphs without sentence-level mastery)
2. Lowest mastery among unlocked skills
3. Active error pattern
4. Scheduled vocabulary review
5. PET exam readiness gap

The planner should always produce:
- Today's Goal
- Why this goal was selected
- Expected improvement
- Exit criteria

Never simply move to the next textbook unit. Always plan from current student state.

---

# Execution Loop

1. Read State → 2. Record Observation → 3. Update State → 4. Plan Next Step

The Markdown files are the single source of truth. Conversation history is temporary. The world model is permanent.
