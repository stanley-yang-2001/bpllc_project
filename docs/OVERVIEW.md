# Project 1: Building a Language Tutor with Langflow

Tutorial reference: https://www.datacamp.com/tutorial/langflow

---

## 2. Project Overview

This project builds an AI language-learning tutor using **Langflow**, a low-code AI agent
workflow builder. The agent generates short reading stories in a target language using only
vocabulary the learner already knows — pulled from a **Postgres** database — and lets the
learner add new words simply by chatting with it. Core stack: Langflow (agent
orchestration/UI), Postgres (vocabulary store), a **free, open-source LLM** served locally via
**Ollama** (the tutorial's OpenAI model is swapped out to avoid any per-token API cost) — with
a hosted **Hugging Face Inference** endpoint as a fallback — Python custom components (via
`psycopg2`), and Docker (local run environment).

---

## 3. Technology Explanation

**Langflow** is a low-code, node-based platform for building AI agent workflows: you connect
pre-built or custom "components" on a canvas, where each component takes typed inputs,
performs one action, and produces an output that feeds the next component. Two Langflow
concepts do most of the work in this project:

- **Custom components** — when the built-in nodes aren't enough, you write a Python class that
  declares a list of typed `inputs` and an `outputs` method. This is how the project talks to
  Postgres, since there's no built-in "vocabulary database" component.
- **Agents with tools** — a Langflow Agent node is backed by an LLM and can have other
  components attached to it in "tool mode." The LLM itself decides, based on each tool's
  description, which tool (if any) to call for a given chat message — this is what lets one
  agent both generate stories and add vocabulary from natural chat input, without hardcoded
  if/else routing.

**Docker** runs Langflow locally and, in the same step, spins up a **Postgres** instance
alongside it — which is why the custom components can connect directly to a database rather
than an external managed service. **Postgres** (accessed via the `psycopg2` Python library) is
the persistence layer for the learner's known-word list.

**LLM choice — open-source instead of OpenAI.** The tutorial's Agent nodes default to an
OpenAI GPT model, which bills per token. To keep this project free to run, that's swapped for
an open-source model:

- **Primary: Ollama, running locally.** Langflow ships a built-in Ollama model component, so
  the Agent node's model provider is pointed at a local Ollama server instead of OpenAI. Adding
  an `ollama` service to the existing `docker-compose.yml` (alongside Langflow and Postgres)
  keeps everything in the same one-command local stack. An instruction-tuned 7–8B model (e.g.
  Llama 3.1 8B Instruct or Mistral 7B Instruct) is a reasonable default — small enough to run
  on a modest GPU or even CPU, and capable enough for short constrained-vocabulary story
  writing and simple tool-routing decisions.
- **Fallback: Hugging Face Inference API (free tier).** If local hardware can't comfortably run
  a 7–8B model, Langflow's Hugging Face model component can call a hosted free-tier inference
  endpoint instead — still $0 in API fees, at the cost of external network dependency, rate
  limits, and less predictable latency than a local model.

The trade-off either way: no per-token bill, but lower output quality/consistency than
GPT-4.1 and (for the local option) a hardware requirement instead of a cloud one.

---

## 4. Software Components

| # | Component | Type | Responsibility |
|---|-----------|------|-----------------|
| 1 | Docker environment | Infra | Runs Langflow + Postgres + Ollama locally as linked containers |
| 2 | Postgres `words` table | Data store | Persists the learner's known vocabulary |
| 3 | Ollama model server (+ HF Inference fallback) | Model-serving | Serves the free, open-source LLM (e.g. Llama 3.1 8B / Mistral 7B) to both agents |
| 4 | Upload Word File | Langflow custom component (standalone) | One-off CSV import to seed the vocabulary table |
| 5 | Add Word tool | Langflow custom component (tool mode) | Inserts a single new word, callable by the agent |
| 6 | Word Loader | Langflow custom component | Reads all known words, outputs them as one string |
| 7 | Story prompt template | Langflow Prompt component | Templates `{language}` + `{words}` into a story-generation instruction |
| 8 | Story-generation agent | Langflow Agent node (tool mode), backed by the open-source LLM | Sub-agent that writes a story constrained to the known vocabulary |
| 9 | Language agent | Langflow Agent node (top-level), backed by the open-source LLM | Orchestrator: routes each chat message to the right tool and returns its result |
| 10 | Chat Input / Chat Output | Langflow built-in components | The learner-facing chat interface |

---

## 5. Requirements / User Stories

Each story below is kanban-card-ready: story, acceptance criteria, chosen stack, and a rough
time/cost estimate (per the Agile Methodology Reference, step 4).

### Story 1 — Local environment setup
**As a** developer, **I want** a local Langflow + Postgres environment running via Docker,
**so that** I can build and test the tutor without any external hosting.
- **Acceptance criteria:** `docker compose up` (from the Langflow repo's `docker_example`
  folder) brings up a reachable Langflow UI; the Postgres service is reachable from within the
  Langflow container; verified by running one trivial component end-to-end.
- **Stack:** Docker, Docker Compose, official Langflow repo.
- **Time:** ~1–2 hrs (mostly one-time).
- **Cost:** $0 infra (local only), $0 LLM (no LLM call in this story).

### Story 1b — Free, open-source model serving
**As a** developer, **I want** an open-source LLM available to the agents at no per-request
cost, **so that** the tutor can generate stories and route chat messages without an OpenAI
subscription.
- **Acceptance criteria:** an `ollama` service is added to the Docker Compose stack and an
  instruction-tuned model (e.g. Llama 3.1 8B Instruct or Mistral 7B Instruct) is pulled and
  responds to a test prompt; Langflow's Ollama model component is confirmed reachable from an
  Agent node; a Hugging Face Inference (free tier) model component is configured as a fallback
  in case local hardware can't run the model comfortably.
- **Stack:** Ollama (Docker service), an open-weights instruction-tuned model, Langflow's
  Ollama/Hugging Face model components.
- **Time:** 1–3 hrs (mostly first-time model download + hardware tuning).
- **Cost:** $0 in API fees either way; local option costs compute/electricity only, no ongoing
  monetary charge. (Note: response quality/speed will trail a frontier hosted model like
  GPT-4.1 — worth noting as a trade-off, not billed anywhere.)

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
- **Stack:** Langflow tool-mode component, `psycopg2`, Postgres, open-source LLM via Ollama
  (agent routing).
- **Time:** 1–2 hrs.
- **Cost:** $0 — no per-request API fee; the only "cost" is the local compute already running
  from Story 1b.

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
- **Acceptance criteria:** Prompt template receives `{language}` and `{words}`; the
  story-generation agent produces a short story using only the supplied vocabulary; the story is
  returned in chat; if the vocabulary list is empty, the agent asks the learner to add words
  first instead of generating.
- **Stack:** Langflow Prompt component + Agent node, open-source LLM via Ollama, Word Loader
  (Story 4).
- **Time:** 2–4 hrs (including prompt tuning — open-source models generally need more prompt
  iteration than GPT-4.1 to reliably follow the "only use these words" constraint).
- **Cost:** $0 per story — local compute only, no API billing.

### Story 6 — Route requests appropriately (top-level orchestration)
**As a** learner, **I want** to just chat naturally, **so that** the tutor figures out whether
I'm asking for a story or adding a word.
- **Acceptance criteria:** The Language agent has both the Add Word tool and the
  story-generation tool attached; "add word"-type phrasing correctly triggers the add-word tool
  and "tell me a story"-type phrasing triggers the story tool; per the agent's instructions, the
  reply is just the tool's result, with no extra commentary layered on top.
- **Stack:** Langflow Agent node, open-source LLM via Ollama, Chat Input/Output components.
- **Time:** 1–2 hrs, plus extra time for routing-accuracy testing — smaller open-source models
  are more prone to mis-routing between the two tools than GPT-4.1, so this story may need a
  few extra iterations on the instruction prompt.
- **Cost:** $0 — local compute only, no API billing.

### Story 7 — Per-learner vocabulary (stretch)
**As a** product owner, **I want** each learner's vocabulary tracked separately, **so that**
multiple people can use the tutor without their word lists mixing together.
- **Acceptance criteria:** `words` table includes a user/session identifier column; Add Word and
  Word Loader both filter by that identifier; a new learner starts with an empty list.
- **Stack:** Postgres schema change; minor updates to the Add Word and Word Loader components.
- **Time:** 2–3 hrs.
- **Cost:** $0 additional infra (still a single local Postgres instance).
