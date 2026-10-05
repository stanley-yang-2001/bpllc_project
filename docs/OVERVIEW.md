# Project 1: Building a Language Tutor with Langflow

Tutorial reference: https://www.datacamp.com/tutorial/langflow

> **Status:** Steps 1–9 complete; Step 10 (end-to-end testing and prompt tuning) is next. See
> `IMPLEMENTATION-GUIDE.md` for the build order and per-step status.

---

## 2. Project Overview

This project builds an AI language-learning tutor using **Langflow**, a low-code AI agent
workflow builder. The agent generates short reading passages (a first-person narration or a
two-person dialogue) in a target language using only vocabulary the learner already knows —
pulled from a **Postgres** database — and lets the learner add new words simply by chatting
with it. Core stack: Langflow (agent orchestration/UI), Postgres (vocabulary store), a **free,
open-weight LLM hosted on Groq** (`openai/gpt-oss-120b` for both the orchestrating agent
and story generation) — the tutorial's OpenAI model is swapped out
to avoid any per-token API cost — Python custom components (`psycopg2` for Postgres, stdlib
`urllib` for Groq), and Docker (local run environment).

---

## 3. Technology Explanation

**Langflow** is a low-code, node-based platform for building AI agent workflows: you connect
pre-built or custom "components" on a canvas, where each component takes typed inputs,
performs one action, and produces an output that feeds the next component. Two Langflow
concepts do most of the work in this project:

- **Custom components** — when the built-in nodes aren't enough, you write a Python class that
  declares a list of typed `inputs` and an `outputs` method. This is how the project talks to
  Postgres and Groq, since there's no built-in "vocabulary database" component.
- **Agents with tools** — a Langflow Agent node is backed by an LLM and can have other
  components attached to it in "tool mode." The LLM itself decides, based on each tool's
  description, which tool (if any) to call for a given chat message — this is what lets one
  agent both generate stories and add vocabulary from natural chat input, without hardcoded
  if/else routing.
  - **Important constraint discovered during the build:** Tool Mode only returns the tool
    component's *own* output; it does not execute anything wired downstream of it on the
    canvas. Any multi-step pipeline meant to be called as one tool therefore has to live
    inside a single component (see `story_tool.py`).

**Docker** runs Langflow locally and, in the same step, spins up a **Postgres** instance
alongside it — which is why the custom components can connect directly to a database rather
than an external managed service. **Postgres** (accessed via the `psycopg2` Python library) is
the persistence layer for the learner's known-word list.

**LLM choice — free hosted open-weight models on Groq instead of OpenAI.** The tutorial's Agent
nodes default to an OpenAI GPT model, which bills per token. To keep this project free to run,
that's swapped for open-weight models served by Groq's free tier through its OpenAI-compatible
API:

- **Original plan: Ollama, running locally.** Ruled out early — the development machine doesn't
  have enough RAM/GPU to run a 7–8B model comfortably. A Hugging Face Inference fallback was
  also planned but is not used.
- **Current: Groq (free tier).** Groq's `llama-3.1-8b-instant` and `llama-3.3-70b-versatile`
  were deprecated (shutdown Aug 16, 2026), so the project uses `openai/gpt-oss-120b` (the top-level Agent's
  Language Model, and the story-generation call in `story_tool.py`; the Step 8 canvas pipeline
  still uses `openai/gpt-oss-20b`). Langflow connects to Groq via a custom component
  (`groq_language_model.py`) that wraps `ChatOpenAI` with Groq's `base_url`; `story_tool.py` calls
  Groq directly with `urllib`.
- **Not yet implemented:** automatic fallback / switching between multiple providers (see the
  Bonus Challenge in `IMPLEMENTATION-GUIDE.md`).

The trade-off: no per-token bill, but a smaller open-weight model is meaningfully less reliable
than GPT-4.1 at agentic instruction-following — in particular, at relaying a tool's output
unchanged. This is the project's central documented finding (see `CHANGELOG.md` and
`DEVELOPER-DIARY.md` in the project root).

---

## 4. Software Components

| # | Component | Type | Responsibility |
|---|-----------|------|-----------------|
| 1 | Docker environment | Infra | Runs Langflow + Postgres locally as linked containers (`docker-compose.yml`) |
| 2 | Postgres `words` table | Data store | Persists the learner's known vocabulary |
| 3 | Groq API (`gpt-oss-20b`, `gpt-oss-120b`) | Hosted model serving | Serves the free open-weight LLMs used by the orchestrating agent and the story-generation call |
| 4 | Upload Word File (`upload_word_file.py`) | Langflow custom component (standalone) | One-off CSV import to seed the vocabulary table |
| 5 | Add Word (`add_word.py`) | Langflow custom component (tool mode) | Inserts a single new word, callable by the agent |
| 6 | Word Loader (`word_loader.py`) | Langflow custom component | Reads all known words, outputs them as one string (Step 8 canvas pipeline) |
| 7 | Story Prompt Builder (`story_prompt_builder.py`) | Langflow custom component | Builds the story prompt from `{language}` + `{words}`; picks narration or dialogue at random (Step 8 canvas pipeline) |
| 8 | Story Guard (`story_guard.py`) | Plain function | Empty-vocabulary check (mirrors the If-Else node on the Step 8 canvas) |
| 9 | Final Passage Extractor (`final_passage_extractor.py`) | Langflow custom component | Strips the hidden planning summary using the `===STORY===` delimiter (Step 8 canvas pipeline) |
| 10 | **Story Generator Tool** (`story_tool.py`) | Langflow custom component (tool mode) | **Production story path.** Consolidates 6–9 into one atomic call: load words, empty-vocabulary guard, build prompt, call Groq (retry on 429), strip planning, cache |
| 11 | Language Agent | Langflow Agent node (top-level), backed by Groq `gpt-oss-120b` | Orchestrator: routes each chat message to Add Word or Story Generator Tool |
| 11b | Tool Result Relay (`tool_result_relay.py`) | Langflow custom component | After the Agent: replaces its reply with the called tool's exact output (passes the Agent's text through when no tool was called) |
| 12 | Chat Input / Chat Output | Langflow built-in components | The learner-facing chat interface |
| 13 | Groq Language Model (`groq_language_model.py`) | Langflow custom component | Wraps Groq's OpenAI-compatible API as a Langflow Language Model |

Components 6–9 remain on the canvas as a standalone Step 8 pipeline for visual debugging in the
Playground; the Language Agent calls component 10.

---

## 5. Requirements / User Stories

Each story below is kanban-card-ready: story, acceptance criteria, chosen stack, and a rough
time/cost estimate (per the Agile Methodology Reference, step 4).

### Story 1 — Local environment setup
**As a** developer, **I want** a local Langflow + Postgres environment running via Docker,
**so that** I can build and test the tutor without any external hosting.
- **Acceptance criteria:** `docker compose up` brings up a reachable Langflow UI; the Postgres
  service is reachable from within the Langflow container (verified by
  `scripts/smoke_test.py`); one trivial component runs end-to-end.
- **Stack:** Docker, Docker Compose, Langflow image.
- **Time:** ~1–2 hrs (mostly one-time).
- **Cost:** $0 infra (local only), $0 LLM (no LLM call in this story).

### Story 1b — Free, open-weight model serving
**As a** developer, **I want** an open-weight LLM available to the agents at no per-request
cost, **so that** the tutor can generate stories and route chat messages without an OpenAI
subscription.
- **Acceptance criteria:** a Groq API key is configured via `.env`; `scripts/smoke_test.py`
  confirms the key is accepted; Langflow can use `openai/gpt-oss-20b` / `openai/gpt-oss-120b`
  from an Agent node.
- **Stack:** Groq (free tier, OpenAI-compatible API), custom `GroqLanguageModel` component.
- **Time:** 1–3 hrs (including working around deprecated models and Langflow's missing Groq
  component).
- **Cost:** $0 in API fees (free tier, subject to rate limits). Response quality trails a
  frontier hosted model like GPT-4.1 — a trade-off, not billed anywhere.
- **Change from original plan:** Ollama (local) + Hugging Face (fallback) was planned, but
  local hardware was insufficient, so the project moved to Groq.

### Story 2 — Seed vocabulary from CSV
**As a** learner, **I want** to upload a CSV of words I already know, **so that** the tutor has
a starting vocabulary to work from.
- **Acceptance criteria:** Upload Word File component accepts a CSV + target column name;
  creates the `words` table if it doesn't exist; inserts all words, silently skipping
  duplicates; returns a success/error message.
- **Stack:** Langflow custom component (Python), `psycopg2`, Postgres.
- **Time:** 2–3 hrs.
- **Cost:** $0 infra (local Postgres), $0 LLM (no LLM call).

### Story 3 — Add a new word via chat
**As a** learner, **I want** to tell the tutor a new word to add, **so that** future stories can
start including it.
- **Acceptance criteria:** Add Word tool is callable by the top-level agent; inserts the word if
  not already present; agent confirms the word was added; requires the `words` table to already
  exist (Story 2 run at least once).
- **Stack:** Langflow tool-mode component (`MessageTextInput` with `tool_mode=True`),
  `psycopg2`, Postgres, Groq-hosted LLM (agent routing).
- **Time:** 1–2 hrs.
- **Cost:** $0 — Groq free tier.

### Story 4 — Load known vocabulary for story generation
**As the** system, **I need to** retrieve the learner's full known-word list, **so that** the
story generator can be constrained to it.
- **Acceptance criteria:** Word Loader queries all words and returns them as a single
  comma-separated string; an empty vocabulary is handled gracefully rather than erroring.
- **Stack:** Langflow custom component, `psycopg2`, Postgres.
- **Time:** ~1 hr.
- **Cost:** $0 (no LLM call).

### Story 5 — Generate a story in the target language
**As a** learner, **I want** to ask for a story in a given language, **so that** I can practice
reading using only vocabulary I already know.
- **Acceptance criteria:** the prompt receives `{language}` and `{words}`; the model produces a
  short passage (narration or dialogue) using only vocabulary that fits plus basic grammar
  words; the hidden planning summary is stripped before the passage is returned; if the
  vocabulary list is empty, the learner is asked to add words first instead of generating.
- **Implementation:** `story_tool.py` (production, single tool call) and the Step 8 canvas
  pipeline (Word Loader → Story Prompt Builder → Agent → Final Passage Extractor) for debugging.
- **Stack:** Python custom components, Groq `openai/gpt-oss-120b` (production tool) / `openai/gpt-oss-20b` (Step 8 canvas pipeline), Postgres.
- **Time:** 2–4 hrs, plus several prompt iterations (open-weight models need more prompt
  iteration than GPT-4.1 to follow the vocabulary constraint).
- **Cost:** $0 per story — Groq free tier. Rate limits (429) are handled by retry with backoff
  and a short-lived result cache.

### Story 6 — Route requests appropriately (top-level orchestration)
**As a** learner, **I want** to just chat naturally, **so that** the tutor figures out whether
I'm asking for a story or adding a word.
- **Acceptance criteria:** The Language agent has both the Add Word tool and the Story Generator
  Tool attached; "add word"-type phrasing correctly triggers the add-word tool and
  "tell me a story"-type phrasing triggers the story tool; per the agent's instructions, the
  reply is just the tool's result, with no extra commentary layered on top.
- **Stack:** Langflow Agent node, Groq `openai/gpt-oss-120b`, Chat Input/Output components.
- **Time:** 1–2 hrs, plus extra time for reliability testing.
- **Cost:** $0 — Groq free tier.
- **Status:** Done. The Agent reliably chooses tools but cannot be trusted to relay the tool's
  text unchanged (it shortened, reworded and sometimes leaked its reasoning), so a Tool Result
  Relay component replaces its reply with the tool's exact output. Final Agent instructions are in
  `AGENT-INSTRUCTIONS.md`.

### Story 7 — Per-learner vocabulary (stretch)
**As a** product owner, **I want** each learner's vocabulary tracked separately, **so that**
multiple people can use the tutor without their word lists mixing together.
- **Acceptance criteria:** `words` table includes a user/session identifier column; Add Word and
  Word Loader both filter by that identifier; a new learner starts with an empty list.
- **Stack:** Postgres schema change; minor updates to the Add Word and Word Loader components.
- **Time:** 2–3 hrs.
- **Cost:** $0 additional infra (still a single local Postgres instance).
- **Status:** Not started.
