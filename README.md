# Language Tutor with Langflow

A free, agent-orchestrated language-learning tutor: it generates short, vocabulary-constrained
stories (or dialogues) using only words a learner already knows, and lets the learner grow
that vocabulary just by chatting. Based on DataCamp's ["13 LLM Projects For All Levels"](https://www.datacamp.com/tutorial/langflow)
tutorial, adapted to run entirely on free infrastructure.

## Current status

Implementation Steps 1–10 are complete: the Language Agent (`gpt-oss-120b`) routes chat messages
to the Add Word and Story Generator tools, and a Tool Result Relay makes sure the learner sees
the tool's exact output. **Step 10 (end-to-end testing and prompt tuning) is complete**: results, tuning log and the LO 8 verdict are in `docs/STEP-10-TEST-PLAN.md`. Step 11 (per-learner vocabulary) is being delivered by the web app (`docs/WEB-APP-DESIGN.md`), whose first
slice is built: accounts, per-language vocabulary and the React shell (`api/`, `web/`, `tutor_core/`);
chat, Story Studio, Library and Practice are not built yet. See
`docs/IMPLEMENTATION-GUIDE.md` for the full build order and per-step status, and
`DEVELOPER-DIARY.md` for the current obstacle and a list of known code issues deferred until all
steps are done.

## What this project is about

The core idea is **comprehensible input**: a learner reads more easily, and learns faster,
from text built almost entirely from words they already know, with just a little new
context around it. This project automates building that text on demand — a short story or
conversation, freshly generated each time, that never uses vocabulary the learner hasn't
seen yet.

## Focus points

- **Zero cost.** Every piece of this — the LLM, the database, the orchestration layer —
  runs on a free tier or entirely locally. No OpenAI subscription, no paid infrastructure.
  The model choice is explained in `docs/OVERVIEW.md`.
- **Real multi-agent tool orchestration.** This is the project's actual teaching point: an
  LLM Agent autonomously deciding, through its own reasoning, which of two tools to invoke
  (add a word, or generate a story) and relaying the result — not a hardcoded if/else. A
  deterministic keyword-router alternative was prototyped for comparison (it is not part of
  this repo), but the intended architecture is agent-based.
- **Test-first development.** Every piece of real logic — vocabulary parsing, prompt
  building, the empty-vocabulary guard, rate-limit retry, caching — has tests written
  *before* the implementation. See `tests/`.
- **Honest engineering about model-size trade-offs.** A free, open-weight model is
  meaningfully less reliable at agentic instruction-following than a frontier model like
  GPT-4.1 (which the original tutorial uses). This project documents that trade-off rather
  than hiding it — see `CHANGELOG.md` and `DEVELOPER-DIARY.md`.

## Tech stack

| Piece | What it is | Role here |
|---|---|---|
| **Langflow** | Low-code AI agent workflow builder | Hosts the Agent, tools, and chat UI |
| **Docker / Docker Compose** | Container orchestration | Runs Langflow + Postgres locally, one command |
| **Postgres** | Relational database | Stores the learner's vocabulary (`words` table) |
| **Python** | Custom component language | `psycopg2` for Postgres, stdlib `urllib` for Groq |
| **Groq** | Free LLM hosting (OpenAI-compatible API) | Serves `openai/gpt-oss-120b` (Language Agent and story generation) and `openai/gpt-oss-20b` (Step 8 canvas pipeline) |

## Quick start

```bash
# create .env (see docs/ENVIRONMENT.md) with GROQ_API_KEY, JWT_SECRET (>= 32 chars), LANGFLOW_SECRET_KEY, TOOLS_DB_PASSWORD (letters and digits; the Langflow tools' database login), ...
docker compose up -d
docker compose exec langflow python /app/scripts/smoke_test.py   # confirm Postgres + Groq are reachable
```
Open `http://localhost:7860`, log in with the superuser credentials set in `docker-compose.yml`.

### Web app (accounts + vocabulary)

```bash
docker compose up --build -d                       # starts postgres, langflow, api, web
docker compose exec api python -m app.seed         # optional demo account demo@example.com (needs DEMO_PASSWORD in .env)
docker compose exec api python -m app.seed --import-legacy   # also copy the old single-user words table
```
Open `http://localhost:8080`. Development without Docker: `make dev-api` and `make dev-web` (Vite proxies
`/api` to port 8000). `make check` runs every test suite and the API-types drift check; it needs a Postgres
reachable at `TEST_DATABASE_URL` (default `postgresql://langflow:testpw@localhost:5432/langflow`).
`make e2e` runs the real-browser tests (user separation, sessions, CSP) against a running stack; first install a
browser once with `cd web && npx playwright install chromium`. The look of the app is described in
`docs/STYLE-GUIDE.md` (including dark mode). Before letting anyone else sign up, set `PRIVACY_CONTACT` in `.env`
and read the operator checklist in `docs/WEB-APP-DESIGN.md` section 12B: the privacy policy is a template, not legal advice. The Docker builds and the new compose services have not been run yet (see the changelog).

## Project structure

This reflects what's actually in the directory as of the last update:

```
.env                             # Real credentials (GROQ_API_KEY, LANGFLOW_SECRET_KEY) — gitignored
.gitignore
docker-compose.yml               # Langflow + Postgres services
README.md
CHANGELOG.md
DEVELOPER-DIARY.md

custom_components/
├── add_word.py                  # Tool: adds one word to the learner's vocabulary
├── story_tool.py                # Tool: generates a vocabulary-constrained story/dialogue
│                                #   (single atomic call; the production path for the Agent)
├── word_loader.py               # Debugging only, not wired to the Agent: one learner's words, comma-separated
├── groq_language_model.py       # Langflow Language Model component for Groq
└── tool_result_relay.py         # After the Agent: shows the tool's output exactly

tests/
├── test_tool_wrappers.py        # M3: what the Agent can see of each tool, and the hidden inputs
├── test_call_groq_retry.py
├── test_tool_result_relay.py
├── test_vocab_adherence.py
├── test_routing_checks.py
├── test_story_prompt_language.py
├── test_story_variety.py
├── test_run_story_batch.py
├── test_run_story_batch_cli.py  # M3: the batch script as a command, against the real database
├── test_routing_runner_with_fake_langflow.py
├── test_routing_learner_db.py   # M3: the runner's throwaway learners, against the real database
└── test_m3_check.py             # M3: scripts/m3_check.py against a fake Langflow running the real tools

scripts/smoke_test.py            # Environment health check (Postgres + Groq)
scripts/vocab_adherence.py       # Step 10: scores a story against the vocabulary (pure functions + CLI)
scripts/run_routing_tests.py      # Step 10: automated end-to-end routing tests over Langflow's HTTP API (as throwaway learners since M3)
scripts/m3_check.py              # M3: live check that the real tools are per-learner and fail closed
scripts/sync_flow_nodes.py       # M3: keeps the tool nodes in flows/language-tutor.json in step with custom_components/
scripts/routing_checks.py        # Step 10: the pure checking logic behind run_routing_tests.py
scripts/run_story_batch.py       # Step 10: generates N stories through the production path and scores them (--rescore re-scores a saved run)
sample_data/starter_vocabulary.csv
sample_data/suggested_words.csv   # ~50 verbs, nouns and adjectives to add, for more varied stories

docs/
├── OVERVIEW.md                  # Project overview, technology, components, user stories
├── IMPLEMENTATION-GUIDE.md      # Build order (Steps 1–11 + bonus) with per-step status
├── AGENT-INSTRUCTIONS.md        # The Language Agent's final instructions (canvas-only setting)
├── STEP-10-TEST-PLAN.md         # Step 10 pass criteria, routing matrix, results and tuning log
├── STYLE-GUIDE.md               # Visual style of the web app: tokens, components, contrast, known gaps
├── SITE-AND-AI-INTEGRATION.md   # How the site works, how it talks to the API, and how Chat/Studio will connect to Langflow
├── WEB-APP-DESIGN.md            # Design of a local React + FastAPI web app (login, per-language vocabulary) around the Langflow flow
├── LEARNING-OBJECTIVES.md       # LO 1–8, with implementation notes
├── architecture-diagram.md      # Deployment diagram
├── class-diagram.md
├── concept-map.md
├── state-diagram.md             # Story request lifecycle (cache, retry, failure)
├── use-case-diagram.md
└── workflow-diagram.md          # One chat message, end to end
```

`story_tool.py` is one component on purpose: Langflow's Tool Mode returns only a component's own
output, so a multi-step pipeline can't be called as one tool unless it lives in one component. The
old Step 8 canvas pipeline (upload word file, story prompt builder, story guard, final passage
extractor) was deleted on 18 October 2026; the logic lives in `tutor_core` and is tested there.
Only `word_loader.py` stays on the canvas, unwired, for debugging.

For more information about this project, see the markdown files in the `docs` folder.

## Running the tests

```bash
# everything that runs inside the langflow container (needs Postgres and the api's migrations: `docker compose up -d` first)
make test-langflow

# the same, one file at a time, e.g.
docker compose exec langflow python /app/tests/test_tool_wrappers.py
docker compose exec langflow python /app/tests/test_m3_check.py

# the shared logic (tutor_core) and the API run on the host against a Postgres, see `make check`
```

The tests that used to cover the shared-table Add Word, Word Loader and story pipeline (`test_add_word.py`,
`test_add_word_normalization.py`, `test_word_loader.py`, `test_story_tool.py`, `test_empty_response_handling.py`) were
replaced in M3 by per-learner tests: `api/tests/test_tutor_core_vocab.py`, `test_tutor_core_story.py`,
`test_tutor_tools.py`, and `tutor_core/tests/` (see the changelog for where each old case went).

## M3: checking the tools against the real flow

After `docker compose up -d --build` (the langflow image now has `tutor_core` installed):

```bash
docker compose exec langflow python /app/tests/test_tool_wrappers.py        # the Agent sees one argument per tool
docker compose exec langflow python /app/scripts/m3_check.py --flow-id language-tutor --pause 30   # the live check
docker compose exec langflow python /app/scripts/run_routing_tests.py --flow-id language-tutor --delay 20
```

`m3_check.py` is the acceptance check: throwaway learners, the real Agent, and it reads the database to see whether anything
crossed between learners. `run_routing_tests.py` is the Step 10 routing matrix, now run as throwaway learners.
