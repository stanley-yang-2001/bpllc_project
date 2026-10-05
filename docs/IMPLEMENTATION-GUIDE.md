# Implementation Guide — Language Tutor with Langflow

A build order for the project, going from an empty environment to the full working tutor.
Each step names the story/acceptance criteria it satisfies (see `OVERVIEW.md`) and which
learning objective(s) it exercises (see `LEARNING-OBJECTIVES.md`, "LO 1–8").

## Progress

| Step | Status |
|------|--------|
| 1 — Local environment | Done |
| 2 — Free model serving | Done (Groq instead of Ollama) |
| 3 — Component/tool-calling groundwork | Done |
| 4 — Upload Word File | Done |
| 5 — Add Word tool | Done |
| 6 — Word Loader | Done |
| 7 — Story prompt template | Done (`story_prompt_builder.py`) |
| 8 — Story-generation pipeline | Done (consolidated into `story_tool.py`) |
| 9 — Top-level Language Agent | Done (120b orchestrator + Tool Result Relay) |
| 10 — End-to-end test and prompt tuning | **In progress** (tools and plan built; live runs to do) |
| 11 — Stretch: per-learner vocabulary | Not started |
| Bonus — Universal model-provider component | Not started |

> **Deviations from the original plan** are marked *Implemented as:* under each step. The
> original text is kept for traceability.

---

## Tech Stack

What each piece of the stack is, and specifically how it's used in this project.

**Langflow**
A low-code, node-based platform for building AI agent workflows: you connect pre-built or
custom "components" on a canvas, where each component takes typed inputs, performs one
action, and passes its output to the next node. In this project, Langflow is the framework
everything else plugs into — it hosts the custom Postgres-reading/writing components, the
Prompt component, and both Agent nodes, and it's what the learner actually chats with via its
built-in Chat Input/Output.

**Docker / Docker Compose**
Docker packages an application and its dependencies into isolated, portable containers;
Docker Compose defines and runs multiple linked containers (services) together from one
config file. Here, Compose is what brings up Langflow and Postgres as one linked
local stack with a single `docker compose up` — no service needs to be installed or configured
by hand outside its container.

**Postgres**
An open-source relational (SQL) database. In this project it's the single source of truth for
the learner's vocabulary: one `words` table that the Upload Word File component seeds, the Add
Word tool inserts into, and the Word Loader reads from before every story is generated.

**psycopg2**
The standard Python library for connecting to and querying a Postgres database. Every custom
Langflow component that touches the `words` table (Upload Word File, Add Word, Word Loader)
uses `psycopg2` internally to run its SQL.

**Python**
The language Langflow's custom components are written in. Anywhere the built-in nodes don't
cover what's needed — reading a CSV, running a SQL query, formatting a word list — a small
Python class with typed `inputs` and an `outputs` method fills the gap.

**Groq**
A hosted inference service with a free tier and an OpenAI-compatible API. It's the model
backend for this project: `openai/gpt-oss-120b` orchestrates the top-level Language Agent, and
`openai/gpt-oss-20b` generates the stories. It was chosen over local Ollama because the
development machine lacks the RAM/GPU to run a model comfortably, and over Groq's older
`llama-3.1-8b-instant` / `llama-3.3-70b-versatile`, which were deprecated (shutdown
Aug 16, 2026). Langflow reaches it through a custom component (`groq_language_model.py`,
wrapping `ChatOpenAI` with Groq's `base_url`); `story_tool.py` calls it directly with stdlib
`urllib`.

**Ollama / Hugging Face Inference (not used)**
Originally planned as the primary and fallback model providers. Dropped in favor of Groq (see
above). Multi-provider switching with automatic fallback is now the Bonus Challenge.

---

### Step 1 — Stand up the local environment
Install Docker, clone the official Langflow repo, and run `docker compose up` from its
`docker_example` folder. Confirm the Langflow UI loads in the browser and that the linked
Postgres service is reachable from inside the Langflow container.
- **Implemented as:** this repo's own `docker-compose.yml` (Langflow + Postgres 16). Langflow
  needed explicit `LANGFLOW_SUPERUSER` / `LANGFLOW_SUPERUSER_PASSWORD`, and a pinned
  `LANGFLOW_SECRET_KEY` so restarts don't invalidate saved API keys (`InvalidToken` error).
  Verified with `scripts/smoke_test.py`.
- **Satisfies:** Story 1.
- **Covers:** **LO 2** (stand up a local Langflow + Postgres environment via Docker).

### Step 2 — Add free, open-source model serving
Add an `ollama` service to the same `docker-compose.yml`, pull an instruction-tuned model
(e.g. Llama 3.1 8B Instruct or Mistral 7B Instruct), and confirm it responds to a test prompt.
Configure a Hugging Face Inference (free tier) model component as a fallback in case local
hardware struggles.
- **Implemented as:** Groq's free tier (`openai/gpt-oss-20b`, `openai/gpt-oss-120b`) with
  `GROQ_API_KEY` supplied via `.env`; the key and reachability are checked by
  `scripts/smoke_test.py`. The Ollama service and Hugging Face fallback were not built.
- **Satisfies:** Story 1b.
- **Covers:** **LO 8** (swap a hosted commercial model for a free, open-source one; reason
  about the cost/latency/quality trade-offs).

### Step 3 — Learn the component and tool-calling pattern
Before building anything custom, open Langflow's built-in "Simple Agent" template and trace
through it: a Chat Input, an Agent node with a couple of attached tools, and a Chat Output.
Change the model provider on that template's Agent node to the free model from Step 2
(Groq), and confirm it still runs. This is pure exploration — nothing here ships in the final
project, but it's what makes the later steps make sense.
- **Satisfies:** groundwork for Stories 3, 5, 6 (no dedicated story of its own).
- **Covers:** **LO 1** (explain Langflow's component model), **LO 5** (configure an Agent's
  tools and explain tool-calling).

### Step 4 — Build the "Upload Word File" component and seed the vocabulary
Write the custom Python component: typed inputs for a CSV file and a column name, an
`outputs` method that creates the `words` table if it doesn't exist and bulk-inserts the
words (skipping duplicates). Run it once against a starter vocabulary list to seed the
database — this is a standalone component, run by you as admin, not wired to any agent.
- **Implemented as:** `custom_components/upload_word_file.py`, tested by
  `tests/test_upload_word_file.py`; seed data in `sample_data/starter_vocabulary.csv`.
- **Satisfies:** Story 2.
- **Covers:** **LO 3** (build a custom Python component with typed inputs/outputs), **LO 4**
  (read/write Postgres via `psycopg2` from a component).

### Step 5 — Build the "Add Word" tool
Write a second custom component that inserts a single word into the `words` table, and mark
it as usable in "tool mode" so an Agent node can call it later. Test it standalone first
(call it directly with a hardcoded word) before wiring it to any agent.
- **Implemented as:** `custom_components/add_word.py`, tested by `tests/test_add_word.py`.
  The input must be a `MessageTextInput` with `tool_mode=True` before Langflow's Tool Mode toggle
  appears.
- **Satisfies:** Story 3 (partially — the DB-write half; agent wiring comes in Step 9).
- **Covers:** **LO 3**, **LO 4**, and a first look at **LO 5** (marking a component for tool
  use).

### Step 6 — Build the "Word Loader" component
Write the component that queries every row in `words` and returns them as a single
comma-separated string, handling the empty-table case gracefully. Test it standalone against
the vocabulary seeded in Step 4.
- **Implemented as:** `custom_components/word_loader.py`, tested by
  `tests/test_word_loader.py`.
- **Satisfies:** Story 4.
- **Covers:** **LO 3**, **LO 4**.

### Step 7 — Build the story prompt template
Add a Prompt component with two variables — `{language}` and `{words}` — that instructs a
model to write a short story in the target language using only the supplied vocabulary. Test
it by manually filling in sample values and checking the rendered prompt text looks right
before any LLM is involved.
- **Implemented as:** `custom_components/story_prompt_builder.py` (a Python component rather than
  Langflow's Prompt node), tested by `tests/test_story_prompt_builder.py`. It holds two
  interchangeable templates (first-person narration and two-person dialogue), picked at random in
  code. Each asks the model for a hidden Character/Want/Event/Resolution plan, a `===STORY===`
  delimiter, then the passage. The prompt went through five documented iterations (see
  `DEVELOPER-DIARY.md`).
- **Satisfies:** Story 5 (prompt half).
- **Covers:** **LO 7** (write and iterate on a constrained prompt template).

### Step 8 — Build the story-generation agent
Wire an Agent node to: the Prompt component (Step 7), the Word Loader (Step 6) feeding its
`{words}` variable, and your Groq model (Step 2) as its LLM. Run it end-to-end and check
the story actually stays inside the supplied vocabulary — if it doesn't, this is where you
iterate on the prompt wording. Mark this agent as a tool so it can be called by the top-level
agent in Step 9.
- **Implemented as:** a Step 8 canvas pipeline (Word Loader → Story Prompt Builder → Agent →
  `final_passage_extractor.py`, with `story_guard.py` mirroring the empty-vocabulary If-Else),
  followed by a consolidation into `custom_components/story_tool.py`. The consolidation was
  needed because **Tool Mode returns only a component's own output and does not run anything
  downstream of it**, so the extractor would never have run and the hidden plan would have leaked
  to the learner. `story_tool.py` also adds Groq 429 retry/backoff and a short-lived cache for
  successes and failures. Tested by `tests/test_story_tool.py`, `tests/test_call_groq_retry.py`,
  `tests/test_story_guard.py`, and `tests/test_final_passage_extractor.py`. The Step 8 canvas
  components remain for manual debugging.
- **Satisfies:** Story 5 (agent half).
- **Covers:** **LO 6** (design a sub-agent used as a tool by another agent), **LO 7**
  (iterating the prompt against real output), **LO 8** (using the open-source model for
  actual generation, not just a test prompt).

### Step 9 — Build the top-level Language Agent
Add the orchestrating Agent node, wired to Chat Input and Chat Output, with both the Add Word
tool (Step 5) and the story-generation agent (Step 8) attached as tools. Write its instruction
prompt: call the story tool for story requests, call the word tool for "add a word" requests,
and just return the tool's result without extra commentary.
- **Implemented as:** Chat Input → Language Agent → Tool Result Relay → Chat Output, with Add
  Word and Story Generator Tool (both in Tool Mode) attached as tools, and a "Groq Orchestrator —
  120b" node as the Agent's Language Model. The final instructions are recorded in
  `AGENT-INSTRUCTIONS.md`.
- **Relay fix:** a `Tool Result Relay` component (`tool_result_relay.py`) sits between the Agent
  and Chat Output (Chat Input → Agent → Tool Result Relay → Chat Output). It replaces the
  Agent's reply with the tool's exact output whenever a tool was called, because prompt tuning
  could not stop the Agent from shortening or rewording it.
- **Bug found and fixed during this step:** the story tool sometimes returned an *empty* result
  (reasoning tokens exhausted `max_tokens`), and the Agent invented its own answer. See
  `CHANGELOG.md`. Re-run the test set after this fix before judging the orchestrator model.
- **Language bug found and fixed:** after a non-English story the Agent refused English ("I can
  only generate stories in languages other than English"), and a non-English request could come
  back in English. Nothing in the code rejected English; the Agent inferred it from the wording
  "target language". Fixed by an explicit instruction ("any language name is valid, including
  English ... use the language in the LATEST message") and a clearer `language` input description.
- **Earlier orchestrator problems** (empty `language` argument, 3–5 repeated tool calls,
  discarded tool output) were observed with the 20b orchestrator.
- **A/B comparison not run:** the planned 120b-vs-20b (and Qwen) orchestrator comparison was
  skipped, because the Relay made the Agent's reply text irrelevant to correctness. The
  orchestrator now only has to choose the right tool and argument. Revisit the comparison in
  Step 10 if routing proves unreliable.
- **Finding for LO 5, LO 6 and LO 8:** a small free model chose tools reliably but could not be
  trusted to relay text faithfully. Let the model decide, and let code deliver the result.
- **Not yet done:** a formal acceptance run (folded into Step 10) and an export of the canvas
  flow to the repo.
- **Satisfies:** Story 6.
- **Covers:** **LO 5** (tool-calling configuration), **LO 6** (multi-agent orchestration).

### Step 10 — End-to-end test and prompt tuning
Run the full chat flow: add a few new words, request a story, and confirm the
vocabulary-empty guard (from Story 5's acceptance criteria) triggers correctly when the table
is empty. Because the project runs on a smaller open-source model rather than GPT-4.1, expect
to spend real time here tightening both the routing instructions (Step 9) and the story
constraint wording (Step 7) until behavior is reliable.
- **Note:** Groq free-tier rate limits are shared by the orchestrator and the story tool (both
  use `gpt-oss-120b`), so expect 429s during testing. Include a language-switching sequence in the
  routing tests (English → Spanish → English → French in one session).
- **Implemented so far:** `docs/STEP-10-TEST-PLAN.md` (pass criteria fixed before tuning, a
  15-row routing matrix, edge cases, the LO 8 write-up template and a tuning log);
  `scripts/vocab_adherence.py` (scores a story against the vocabulary: out-of-vocabulary words with
  inflections, names and grammar words handled, sentence/line count, dialogue format, leaked plan,
  failures) with `tests/test_vocab_adherence.py`; `scripts/run_story_batch.py` (N stories through
  the production path, cache off, scored, with latency); and Add Word normalization (case,
  whitespace, edge punctuation) with `tests/test_add_word_normalization.py`.
- **Automated routing tests:** `scripts/run_routing_tests.py` drives the flow through Langflow's
  HTTP API (one fresh session per test) and checks tool, argument, relay equality, story quality
  and the empty-vocabulary guard, replacing most of the manual Playground matrix; its logic is in
  `scripts/routing_checks.py`. Tested here against a fake Langflow server; the real response
  shape is confirmed on the first live run (`--debug`).
- **First live routing run (45 turns):** routing is solid (right tool 42/42, right argument 36/36,
  reply identical to the tool output 36/36, language switching 12/12, empty-vocabulary guard 3/3).
  The run also showed that non-English stories were mostly **not in the requested language** (5/15
  once checked), which the structure-only check had missed. A language-correctness check now
  covers it; fixing the prompt is the next tuning step. Details in `docs/STEP-10-TEST-PLAN.md`.
- **Tuning change #1 (language-aware prompt):** for non-English stories the prompt says the
  vocabulary list holds English meanings to be expressed in the target language, leaves out the
  English tone examples, and normalizes the language name. English prompts are unchanged. Measure
  with `run_story_batch.py --languages Spanish,French,Japanese --count 10` before and after.
- **Design decisions:** the stored vocabulary stays English, so the vocabulary check applies to
  English stories only; other languages are checked for structure and read by a person. After the
  first baseline (35% pass under a zero-stray-words rule, with only everyday words such as
  "eat" and "drink" as strays), the pass rule was relaxed to at most 2 stray words per story.
  Baseline and the decision are in `docs/STEP-10-TEST-PLAN.md`.
- **To do:** run the batch and the Playground matrix, tune one thing at a time, fill in the
  results and the tuning log, and write the trade-off verdict.
- **Satisfies:** Stories 5 and 6's acceptance criteria, holistically.
- **Covers:** **LO 7**, **LO 8** (the trade-off called out in the learning objective becomes
  concrete here).

### Step 11 — Stretch: per-learner vocabulary
Add a user/session identifier column to `words`, and filter both the Add Word tool (Step 5)
and Word Loader (Step 6) by it, so multiple learners don't share one word list.
- **Satisfies:** Story 7.
- **Covers:** **LO 4** (extending the Postgres read/write logic).

### Bonus Challenge — Universal model-provider component
Instead of wiring a single model component (currently the Groq one) directly into the
Language Agent and the story call, build a reusable component that can switch between multiple free providers
(Ollama, Groq, Hugging Face, etc.) through one input, with automatic fallback if the primary
provider fails. This one is **not** project-specific — it's meant to be built once and reused
across every project in the roadmap, so it belongs a level above this project directory, not
inside it.
- **Note:** the Ollama and Hugging Face examples are now moot for this project, which uses Groq; the
  component would add switching and fallback across providers. Not yet implemented, which is why
  `docker-compose.yml` still mounts a `shared-components/universal-model-selector` path.
- **Spec:** `../UNIVERSAL-MODEL-COMPONENT-CHALLENGE.md`
- **Satisfies:** none of Project 1's stories directly — this is a roadmap-level stretch item.
- **Covers:** extends **LO 8** into a reusable, runtime-configurable design.

---

### Learning objective coverage check

| LO | Covered in |
|----|------------|
| 1 — Explain Langflow's component model | Step 3 |
| 2 — Stand up Langflow + Postgres via Docker | Step 1 |
| 3 — Build a custom Python component | Steps 4, 5, 6 |
| 4 — Read/write Postgres via `psycopg2` | Steps 4, 5, 6, 11 |
| 5 — Configure tools and explain tool-calling | Steps 3, 5, 9 |
| 6 — Design a multi-agent (agent-as-tool) system | Steps 8, 9 |
| 7 — Write/iterate a constrained prompt template | Steps 7, 8, 10 |
| 8 — Swap to a free open-source model, reason about trade-offs | Steps 2, 8, 9, 10 |

Every objective is exercised at least once, and the ones that matter most for this project
(4, 5, 7, 8) get revisited more than once as the build progresses.
