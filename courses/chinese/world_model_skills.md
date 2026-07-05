# Chinese World Model Skills

The Learning World Model is stored entirely in Markdown.

Every skill operates on Markdown files. Never keep important information only in conversation context. Always update the world model.

---

# Skill 1 — Read State

Before every lesson, read:
- `courses/chinese/world_model.md`
- `data/student/{username}/chinese_state.md` (the student's Chinese state)
- `courses/chinese/planner.md`
- latest history log

Goal: Answer:
- What is the student's strongest/weakest tier (阅读/作文/古诗文)?
- What is the most recent "thinking gap" discovered?
- What text type triggered the last breakthrough or struggle?
- What should happen today — and with what text?

Never teach without reading the current state.

---

# Skill 2 — Record Observation

Record objective evidence during the lesson. Append to today's history log.

Only record facts. Examples:
- identified environmental description as foreshadowing without prompting
- answered "表达了思乡之情" — used template expression, no textual evidence
- correctly inferred "诣" means "拜访" from context
- essay thesis stayed at "个人" level, did not connect to "社会" or "时代"
- showed genuine emotional response to the poem's last line
- answer structure: used terminology but missing specific text citation

Do not update mastery here. Only collect evidence.

---

# Skill 3 — Update State

Update the student model after enough evidence. Modify `chinese_state.md`.

Possible updates: mastery level, thinking gap discovered, expression improvement, knowledge accumulation, review queue.

Key principle: **One correct answer is not mastery; one mistake is not a gap.** Look for patterns across multiple interactions. Small evidence → small change. Repeated evidence → larger change. Never invent information.

Special attention: When a student answers correctly, distinguish between "genuine deep understanding" and "correct by chance / template matching." Only mark improvement when the thinking chain is demonstrated.

---

# Skill 4 — Plan Next Step

Generate the next learning objective. Update planner output.

Select next target according to:
1. Prerequisite dependency (can't analyze exam-setter intent without basic logical chain)
2. Lowest mastery among unlocked sub-skills
3. Active thinking gap needing repair
4. Scheduled review (spaced repetition)
5. Text availability (what text best trains this specific skill?)

The planner should always produce:
- Today's Goal (specific sub-skill + text recommendation)
- Why this goal was selected
- Expected mastery improvement
- Exit criteria (what evidence proves the student got it?)

Never simply move to the next item on a generic syllabus. Always plan from current student state.

---

# Execution Loop

1. Read State → 2. Record Observation → 3. Update State → 4. Plan Next Step

The Markdown files are the single source of truth. Conversation history is temporary. The world model is permanent.
