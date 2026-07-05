# Coding World Model Skills

The Learning World Model is stored entirely in Markdown.

Every skill operates on Markdown files. Never keep important information only in conversation context. Always update the world model.

---

# Skill 1 — Read State

Before every lesson, read:
- `courses/coding/world_model.md`
- `data/student/{username}/student_state.md` (Coding state section)
- `courses/coding/planner.md`
- latest history log

Goal: Answer:
- What is the student's current coding level?
- What was the last successfully solved problem?
- What are the active error patterns or blockers?
- What should the student learn today?

---

# Skill 2 — Record Observation

Record objective evidence during the lesson. Append to today's history log.

Only record facts. Examples:
- wrote for-loop correctly without prompting
- confused = and == in if condition (3 times this session)
- solved the array sum problem in 8 minutes, code passed all tests
- asked "why do we need a base case in recursion?"
- manually traced the code to find off-by-one error
- showed visible excitement when the program ran correctly

Do not update mastery here. Only collect evidence.

---

# Skill 3 — Update State

Update the student model after enough evidence. Modify `student_state.md`.

Possible updates: level, confidence, error patterns, strengths, weaknesses, preferred problem types, coding habits.

Every update supported by recorded observations. Small evidence → small change. Repeated evidence → larger change. A single successful compile is not enough to mark "mastered".

---

# Skill 4 — Plan Next Step

Generate the next learning objective. Update planner output.

Select next target according to:
1. Prerequisite dependency (can't learn recursion without functions)
2. Lowest level among unlocked knowledge points
3. Active error pattern needing repair
4. Scheduled review (spaced repetition)
5. Interest alignment (what excites the student?)

The planner should always produce:
- Today's Goal
- What prerequisite is assumed
- Expected new knowledge/ability
- Exit criteria (what code the student should be able to write)

Never simply move to the next item on a syllabus. Always plan from current student state.

---

# Execution Loop

1. Read State → 2. Record Observation → 3. Update State → 4. Plan Next Step

The Markdown files are the single source of truth. Conversation history is temporary. The world model is permanent.
