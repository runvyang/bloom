# World Model Skills

The Learning World Model is stored entirely in Markdown.

Every skill operates on Markdown files.

Never keep important information only in conversation context.

Always update the world model.

---

# Skill 1 — Read State

## Purpose

Understand the current student before taking any action.

## Read

Before every lesson, read:

* learning_world_model.md
* student_state.md
* planner.md
* latest history log

## Goal

Answer:

* What is the student learning?
* What is the current mastery?
* What are the active misconceptions?
* What should happen today?

Never teach without reading the current state.

---

# Skill 2 — Record Observation

## Purpose

Record objective evidence during the lesson.

## Action

Append new observations to today's history log.

Only record facts.

Examples:

* solved correctly
* required hint
* confused by denominator
* explained clearly
* lost attention after 15 minutes
* showed confidence

Do not update mastery here.

Only collect evidence.

---

# Skill 3 — Update State

## Purpose

Update the student model after enough evidence has been collected.

## Action

Modify student_state.md.

Possible updates include:

* mastery
* confidence
* misconceptions
* strengths
* weaknesses
* interests
* review queue

Every update should be supported by observations recorded in the history log.

Small evidence → small change.

Repeated evidence → larger change.

Never invent information.

---

# Skill 4 — Plan Next Step

## Purpose

Generate the next learning objective.

## Action

Update planner.md.

Select the next learning target according to:

1. prerequisite dependency
2. lowest mastery
3. active misconception
4. scheduled review
5. expected learning gain

The planner should always produce:

* Today's Goal
* Why this goal was selected
* Expected mastery improvement
* Exit criteria

Never simply move to the next textbook chapter.

Always plan from the current student state.

---

# Execution Loop

Every lesson follows exactly this workflow:

1. Read State
2. Record Observation
3. Update State
4. Plan Next Step

The Markdown files are the single source of truth.

Conversation history is temporary.

The world model is permanent.
