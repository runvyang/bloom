# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Overview

Bloom is an AI-powered intelligent math teaching assistant (智能教学助手) for Chinese elementary/secondary students. It maintains a persistent **Learning World Model** — a markdown-based student knowledge state that the LLM updates after each interaction. The system teaches, evaluates, and plans in a continuous loop, treating every student response as evidence to update its belief about what the student knows.

## Commands

```bash
# Install dependencies
./install.sh          # pip install mem0ai qdrant-client fastapi openai litellm[proxy]

# Run the app (dev, with hot reload)
./run.sh              # uvicorn app:app --reload
# or directly:
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

# Run LiteLLM proxy (optional, for model routing)
cd services && litellm -c litellm_config.yaml
```

## Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `DEEPSEEK_API_KEY` | Yes | DeepSeek API key (primary LLM provider) |
| `OPENROUTER_API_KEY` | Optional | OpenRouter API key (fallback provider) |

## Architecture

```
app.py                  FastAPI server — static files, SSE streaming, health check
runtime.py              ChatRuntime — core teach/eval/plan loop, context assembly
llm.py                  OpenRouterClient — OpenAI-compatible wrapper for DeepSeek / OpenRouter
session_manager.py      JSON file-based session store (data/sessions/*.json)
memory.py               mem0.ai client for long-term cross-session memory retrieval
utils.py                read_file / write_file / append_file helpers
data/                   Markdown world model files (the persistent source of truth)
  student_state.md        Student knowledge tracking table (grades 1-12 + olympiad)
  world_model.md          Core teaching philosophy (probabilistic, evidence-driven)
  planner.md              Real-time evaluation & curriculum planning rules
  teacher_prompt.md       JSON output schema for LLM evaluation responses
  world_model_skills.md   Agent skill manual — read/record/update/plan loop
  evaluator.md            Rules for calibration and anti-bias on mastery updates
  history/*.log           Per-user teaching logs
services/               LiteLLM proxy config
static/                 Frontend SPAs
  index.html              Dark-theme production UI with SSE streaming
  index_ds.html           Simpler gradient-themed UI
math/                   Math-specific planner and history (separate domain)
```

## Core Teaching Loop

The system runs a two-phase loop on every student message:

### Phase 1: `teach()` (synchronous, streamed to UI)
1. Load session, mem0 memory, student state, world model, current plan
2. Send context to LLM as system+user messages
3. Stream response tokens back to the browser via SSE (`/chat/stream`)
4. Append assistant response to session

### Phase 2: `eval()` (background task after teach)
1. Re-prepare context, send to LLM with `teacher_prompt.md` output schema (JSON mode)
2. Parse LLM response: extract `model_update_delta` and `teaching_plan`
3. Append delta updates to `data/student_state.md`
4. Update session's `current_plan` for next turn

### Key Design Decision: Dual LLM Calls

The same LLM is called twice per student message — once to generate the teaching response (streamed), once to evaluate and update the student model (background). The eval call uses `json=True` (DeepSeek JSON mode) and `reasoning=True`. The teach call uses `reasoning=True` but non-JSON streaming.

## Student State Format

`data/student_state.md` is a giant markdown table tracking mastery across grades 1-12 across difficulty levels. Mastery levels: `未开始` → `不及格` → `通过` → `优秀` → `精通`. Updates are appended as `# DELTA UPDATE` blocks at the bottom and must be manually reconciled into the table (currently the LLM appends deltas but the table itself isn't auto-updated by code).

## LLM Provider

Primary: DeepSeek (deepseek-v4-flash via `api.deepseek.com`). The `OpenRouterClient` uses the OpenAI Python SDK with provider URL routing. Set `reasoning=True` to enable thinking, `json=True` for structured JSON output mode.

## Architecture Philosophy: Prompts as Code

The teaching logic is not coded in Python — it's encoded in Markdown prompt files that the LLM reads and executes at runtime. The Python layer is a thin orchestration shell that: loads markdown files, assembles context, calls the LLM, and persists results. Key logic files:

- `data/world_model.md` — the LLM's identity and core teaching principles
- `data/planner.md` — how to choose the next knowledge point to teach
- `data/teacher_prompt.md` — exact JSON schema the LLM must output for eval
- `data/evaluator.md` — calibration rules: caps mastery updates at ±0.15 per session, requires 2+ repeated errors to confirm a misconception, uses formula `final_mastery = 0.5 * teacher_estimate + 0.3 * correctness_rate + 0.2 * consistency_score`
- `data/world_model_skills.md` — the execution loop: Read State → Record Observation → Update State → Plan Next Step

The `math/planner.md` defines a node scoring algorithm for selecting the next teaching target: `score = (1 - mastery) * 0.5 + misconception_weight * 0.3 + prerequisite_gap * 0.1 + review_need * 0.1`. Active misconceptions always win regardless of score.

## Known Issues / Gotchas

- **No tests, no lint configuration** — the project has zero test coverage and no mypy/ruff/pylint setup
- **Hardcoded API key** — `memory.py` contains a hardcoded Mem0 API key; should use env var
- **Duplicate file** — `chat_history.py` is a byte-for-byte copy of `utils.py`
- **Delta-only student_state updates** — `eval()` appends `# DELTA UPDATE` blocks to `data/student_state.md` but never modifies the table itself; the table and deltas drift apart over time
- **Synchronous eval blocks worker** — `eval()` runs as a FastAPI background task but uses synchronous LLM calls, blocking a uvicorn worker thread
- **No user auth** — `ChatRuntime` hardcodes `user_id="baozi4"`; multi-user support is TODO
- **`runtime.update_state()` is a stub** — the method exists but its body is incomplete (calls LLM but doesn't process the response)
- **Frontend references non-existent endpoints** — `index_ds.html` calls `/chat` (not implemented), and the settings modal in `index.html` references `main.py` (file is `app.py`)
- **Session file naming** — some sessions use `sess_` prefix, others use `session_`; the code uses `sess_` for generation but existing files show both conventions
