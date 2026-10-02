# Language Tutor with Langflow

A free, agent-orchestrated language-learning tutor: it generates short, vocabulary-constrained
stories (or dialogues) using only words a learner already knows, and lets the learner grow
that vocabulary just by chatting. Based on DataCamp's ["13 LLM Projects For All Levels"](https://www.datacamp.com/tutorial/langflow)
tutorial, adapted to run entirely on free infrastructure.

## What this project is about

The core idea is **comprehensible input**: a learner reads more easily, and learns faster,
from text built almost entirely from words they already know, with just a little new
context around it. This project automates building that text on demand — a short story or
conversation, freshly generated each time, that never uses vocabulary the learner hasn't
seen yet.

## Focus points

- **Zero cost.** Every piece of this — the LLM, the database, the orchestration layer —
  runs on a free tier or entirely locally. No OpenAI subscription, no paid infrastructure.
  See `FREE-LLM-PROVIDERS.md` (project root) for the reasoning behind the model choice.
- **Real multi-agent tool orchestration.** This is the project's actual teaching point: an
  LLM Agent autonomously deciding, through its own reasoning, which of two tools to invoke
  (add a word, or generate a story) and relaying the result — not a hardcoded if/else. A
  deterministic fallback exists (`language_tutor_router.py`) for comparison, but the
  intended architecture is agent-based.
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
| **Groq** | Free LLM hosting (OpenAI-compatible API) | Serves `openai/gpt-oss-20b` and `openai/gpt-oss-120b` |

## Quick start

```bash
# edit .env with your real GROQ_API_KEY and a fixed LANGFLOW_SECRET_KEY (there is no
# .env.example — .env already exists in this directory with placeholder values to replace)
docker compose up -d
docker compose exec langflow python /app/scripts/smoke_test.py   # confirm Postgres + Groq are reachable
```
Open `http://localhost:7860`, log in with the superuser credentials set in `docker-compose.yml`.

## Project structure

This reflects what's actually in the directory as of the last update:

```
.env                             # Real credentials (GROQ_API_KEY, LANGFLOW_SECRET_KEY) — gitignored
.gitignore
docker-compose.yml               # Langflow + Postgres services

custom_components/
├── upload_word_file.py          # Standalone admin tool — seeds vocabulary from a CSV
├── add_word.py                  # Tool: adds one word to the learner's vocabulary
├── story_tool.py                # Tool: generates a vocabulary-constrained story/dialogue
└── story_prompt_builder.py      # Prompt template for the agent
                                  # kept on disk, currently unwired on the canvas

tests/
├── test_upload_word_file.py
├── test_add_word.py
├── test_story_tool.py
├── test_call_groq_retry.py
└── test_router.py

scripts/smoke_test.py            # Environment health check (Postgres + Groq)
sample_data/starter_vocabulary.csv

For more information about this project, see the markdown files in the docs folder

## Running the tests

```bash
docker compose exec langflow python /app/tests/test_upload_word_file.py
docker compose exec langflow python /app/tests/test_add_word.py
docker compose exec langflow python /app/tests/test_story_tool.py
docker compose exec langflow python /app/tests/test_call_groq_retry.py
docker compose exec langflow python /app/tests/test_router.py
docker compose exec langflow python /app/tests/test_final_passage_extractor.py
docker compose exec langflow python /app/tests/test_story_guard.py
docker compose exec langflow python /app/tests/test_story_prompt_builder.py
```
