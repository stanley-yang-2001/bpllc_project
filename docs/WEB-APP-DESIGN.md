# Language Tutor Web App — Design (React)

**Status:** Draft v3 · **Date:** 2026-10-04 · **Runs:** locally with Docker Compose (a demo, not hosted) · **Stack:** React + TypeScript, FastAPI, Langflow, Postgres, Groq

## 1. Purpose and scope
A local demo web app for the language tutor. One `docker compose up` starts the React site, a FastAPI backend, Langflow and Postgres. A learner creates an account, logs in, studies in a **target language** (vocabulary is stored in that language), chats with the tutor, manages words, and generates stories with a quality report.

**Langflow stays the AI layer.** The Agent, tools and Tool Result Relay do the chat work; the web app is a client of the flow, so the project's learning objectives stay intact.

**In scope:** accounts and login, per-user and per-language vocabulary, chat tutor, vocabulary manager, story studio with quality report, saved stories, simple practice, diagnostics.
**Out of scope:** public hosting, payments, password reset by email, voice, real-time collaboration.

## 2. Users and stories
| # | As a learner I want to... | Page |
|---|---|---|
| U1 | chat naturally ("add the word bread", "story in Spanish") | Chat |
| U2 | see and edit my words, upload a CSV, add a word | Vocabulary |
| U3 | pick a language and style (narration or dialogue) and get a story | Story Studio |
| U4 | see which words in a story are outside my vocabulary | Story Studio |
| U5 | keep stories I liked and reread them | Library |
| U6 | quiz myself on my words | Practice |
| U7 | (admin) check that Postgres, Groq and Langflow are healthy | Settings |
| U8 | create an account and log in so my words are private | Login |
| U9 | keep a separate word list for each language I study | Vocabulary |

## 3. Architecture
A browser cannot hold the Groq or Langflow keys or reach Postgres, so React talks only to a small **FastAPI backend** (`tutor-api`). Two backend paths coexist on purpose:

- **Agent path (`POST /chat`):** the API calls the Langflow flow. The Agent picks the tool; the Tool Result Relay returns its exact output. The learner's id and language are passed per request (Langflow `tweaks`).
- **Direct path (vocabulary, stories, practice):** the API calls shared Python (`tutor_core`). Faster, deterministic, and it can offer controls the Agent tool lacks (narration or dialogue).

```mermaid
flowchart LR
  U["Learner browser, localhost:8080"] --> W
  subgraph FE["Front end"]
    W["React app: Login, Home, Chat, Vocabulary, Story Studio, Library, Practice, Settings"]
  end
  subgraph BE["tutor-api, FastAPI"]
    R["Routes and auth, JWT in httpOnly cookie"]
    SV["Services: auth, vocab, story, quality, langflow_client"]
    R --> SV
  end
  W -->|"REST JSON, same origin /api"| R
  SV -->|"HTTP run, user_id and language in tweaks"| LF["Langflow flow: Agent, tools, Tool Result Relay"]
  SV -->|"SQL"| DB[("Postgres: users, words, stories")]
  SV -->|"HTTPS direct"| GQ["Groq API"]
  LF -->|"SQL, filtered by user and language"| DB
  LF --> GQ
```

## 3A. Tech stack
| Layer | Choice | Notes |
|---|---|---|
| Front end | **React + TypeScript**, built with **Vite** | SPA served by nginx |
| Routing and data | **React Router**, **TanStack Query** | server state, caching, retries |
| Styling | **Tailwind CSS** | component library (for example shadcn/ui) is optional |
| Forms | **React Hook Form** + **Zod** | validation shared by form and API types |
| API client | types generated from the FastAPI **OpenAPI** schema (`openapi-typescript`) | keeps the two codebases in sync |
| Backend | **FastAPI** (Python 3.12), Pydantic, uvicorn | thin routes over services |
| AI orchestration | **Langflow** (existing flow) | Agent, Add Word, Story Generator, Tool Result Relay |
| LLM | **Groq**, `openai/gpt-oss-120b` | free tier; shared rate limit |
| Database | **PostgreSQL 16**, `psycopg2` | tables: users, words, stories |
| Auth | **bcrypt** + **JWT** in an httpOnly cookie | local accounts, no external provider |
| Shared logic | **`tutor_core`** Python package | prompts, normalization, checks; used by Langflow and the API |
| Target-language tokenizing | `simplemma`, `jieba`, `fugashi` + `unidic-lite`, `kiwipiepy` | optional per language; verify each installs |
| Tests | `pytest`, Vitest + React Testing Library, Playwright | plus the existing fake-Langflow tests |
| Packaging | **Docker Compose**, nginx, `.env` | new services: `web`, `api` |

## 3B. Login and authentication
Local accounts, deliberately simple.

```mermaid
sequenceDiagram
  actor L as Learner
  participant W as React app
  participant A as tutor-api
  participant DB as Postgres
  L->>W: submit login form
  W->>A: POST /auth/login
  A->>DB: look up user by username
  DB-->>A: password hash
  A->>A: bcrypt verify
  A-->>W: set httpOnly cookie with JWT
  W->>A: GET /me
  A-->>W: user, language list
  W-->>L: Home; every API call carries the cookie
```

- Passwords are stored only as bcrypt hashes; failed logins are rate-limited per username.
- The API reads `user_id` from the verified token, never from the request body; services take it as an argument.
- React keeps only the user profile in an auth context; the token is not readable by JavaScript.

## 3C. API surface

| Method and path | Purpose |
|---|---|
| `POST /auth/register`, `/auth/login`, `/auth/logout`; `GET /me` | accounts and session |
| `GET /words?language=`, `POST /words`, `DELETE /words/{id}`, `POST /words/upload` | vocabulary |
| `POST /chat` (message, session id) | Agent path through Langflow; returns reply and tool calls |
| `POST /stories/generate` (language, style) | direct path; returns story and quality report |
| `GET /stories`, `POST /stories`, `DELETE /stories/{id}` | library |
| `GET /health` | Postgres, Groq and Langflow status for Settings |

## 4. Navigation and pages
```mermaid
flowchart TD
  LG["Login or register"] --> H
  H["Home dashboard"] --> C["Chat"]
  H --> V["Vocabulary"]
  H --> S["Story Studio"]
  H --> L["Library"]
  H --> PR["Practice"]
  H --> ST["Settings"]
  V -->|"make a story from these words"| S
  S -->|"save"| L
  L -->|"reread or regenerate"| S
  L -->|"quiz on a story"| PR
```

| Route | Purpose | API | Main components |
|---|---|---|---|
| `/login` | register, log in | `/auth/*` | `LoginForm` |
| `/` Home | word count, recent stories, shortcuts | `/words`, `/stories` | `StatCard` |
| `/chat` | talk to the tutor; show the tool used | `/chat` | `ChatPanel`, `ToolTrace` |
| `/vocabulary` | list, search, add, delete, CSV upload | `/words` | `WordTable`, `CsvUpload` |
| `/studio` | generate a story, quality report | `/stories/generate` | `StoryCard`, `ReportPanel` |
| `/library` | saved stories | `/stories` | `StoryList` |
| `/practice` | flashcards, cloze from stories | `/words`, `/stories` | `Flashcard` |
| `/settings` | health checks, model, account | `/health`, `/me` | `StatusList` |

## 5. Wireframes
**Chat**
```
+--------------------------------------------------------------+
| Language Tutor      [Home] [Chat] [Vocab] [Studio] [Library] |
+--------------------------------------------------------------+
| You:  Tell me a story in Spanish                             |
| Tutor: Ana: Hola, tienes agua?                               |
|        Luis: Si, tengo agua en mi casa.   ...                |
|        > Tool used: Story Generator (language = Spanish)     |
|                                                              |
| [ Type a message...                                  ] [Send]|
| Sidebar:  Words: 16   Language: Spanish   [New session]      |
+--------------------------------------------------------------+
```

**Vocabulary**
```
+--------------------------------------------------------------+
| Vocabulary  Language [Spanish v]  (16)  [Search] [CSV] [Add]  |
+--------------------------------------------------------------+
|  word        meaning        |  [x] select    [Delete]        |
|  hola        hello          |                                |
|  agua        water          |  Add a word:  [ bread     ] [+]|
|  gracias     thank you      |  Words are stored lowercase;   |
|  ...                        |  duplicates are ignored.       |
|             [ Make a story from my words -> ]                |
+--------------------------------------------------------------+
```

**Story Studio**
```
+--------------------------------------------------------------+
| Language [Spanish v]  Style (o) Narration ( ) Dialogue ( ) Any|
|                                        [ Generate story ]    |
+--------------------------------------------------------------+
| Story                         | Quality report               |
| Ana: Hola, tienes agua?       | Language: ok (0% English)    |
| Luis: Si, tengo agua.         | Length: 6 lines   Format: ok |
| ...                           | Outside your words: bring    |
|                               | Read time: 20 s              |
| [Save] [Regenerate] [Practice this story]                    |
+--------------------------------------------------------------+
```

## 6. Key flows
**Chat turn (Agent path)**

```mermaid
sequenceDiagram
  actor L as Learner
  participant W as React Chat route
  participant A as tutor-api
  participant LF as Langflow API
  participant AG as Agent and tools
  participant R as Tool Result Relay
  L->>W: types a message
  W->>A: POST /chat
  A->>LF: run flow, session id and tweaks
  LF->>AG: message
  AG->>AG: tool call, then tool output
  AG-->>R: reply plus tool call
  R-->>LF: reply replaced by the exact tool output
  LF-->>A: JSON response
  A->>A: parse reply and tool calls
  A-->>W: reply and tool trace
  W-->>L: message bubble and expandable trace
```

**Story Studio (direct path):** `POST /stories/generate` runs `story_service.generate(user, language, style)`, which loads the learner's words in that language, builds the prompt, calls Groq, strips the planning text, then `quality.check(...)` scores it. If Groq rate-limits or fails, the API returns a typed error and the UI shows a retry message with a cooldown.

## 7. Data model
Vocabulary is stored **in the target language**, per learner. Today's `words` table (`id, word, created_at`, `word` unique) gains `user_id` and `language`, and uniqueness becomes `(user_id, language, word)`. `meaning_en` is optional (shown in tables and quizzes).

```mermaid
erDiagram
  USERS ||--o{ WORDS : owns
  USERS ||--o{ STORIES : saves
  USERS {
    int id PK
    text username UK
    text password_hash
    text display_name
    text native_language
    timestamp created_at
  }
  WORDS {
    int id PK
    int user_id FK
    text language
    text word
    text meaning_en
    timestamp created_at
  }
  STORIES {
    int id PK
    int user_id FK
    text language
    text style
    text body
    bool passed
    text report_json
    timestamp created_at
  }
```

**Consequences:** stories use the learner's words directly, so the "translate the English meanings" prompt rule (patch 0010) is only needed for any English-vocabulary mode; the no-English-example rule still helps. The adherence check works on lemmas of the target language, so inflections count as the same word. Migration: existing rows get `language = 'English'` and the demo user.

## 8. Code structure and a shared core
```
web/                       # React app (Vite)
  src/routes/              # one file per route
  src/components/          # ChatPanel, WordTable, StoryCard, ReportPanel...
  src/api/                 # generated types and a small fetch wrapper
  src/auth/                # auth context, protected-route wrapper
api/                       # FastAPI
  main.py, routes/, services/ (auth, vocab, story, quality, langflow_client)
  config.py                # env vars only
tutor_core/                # pure Python shared with the Langflow components
```

**Key decision:** `story_tool.py` and `add_word.py` import Langflow at the top, so the API cannot import them cheaply. Move the pure logic (`normalize_word`, `normalize_language`, `build_story_prompt`, `call_groq`, `load_words`, the checks) into `tutor_core/`, used by both Langflow and the API. This also clears the deferred items (duplicated logic, hardcoded credentials and model names). Langflow's component scanner has been unreliable with cross-file imports, so install `tutor_core` as a package or put it on `PYTHONPATH`.

## 9. State and caching
| Item | Where | Notes |
|---|---|---|
| Logged-in user | auth context, fed by `GET /me` | protected routes redirect to `/login` |
| Words, stories, health | TanStack Query cache | invalidated after add, delete, upload, save |
| Chat messages, session id | component state in the Chat route | new session = new Langflow `session_id` |
| Selected language, style | context, remembered in `localStorage` | per learner |
| Generated story | component state until saved | avoids regenerating on re-render |

Mutations that are cheap and safe (add or delete a word) update the cache optimistically; calls to Groq or Langflow never retry automatically, to protect the shared rate limit.

## 10. Errors and rate limits
Groq's free tier is shared by everyone using the app, so limits will show up with more than one learner.

| Situation | What the learner sees |
|---|---|
| Groq 429 or the fallback message | "The tutor is busy. Try again in a moment", button disabled for 15 s |
| Empty vocabulary | the guard message plus a link to Vocabulary |
| Langflow unreachable | banner on Chat; other pages keep working (direct path) |
| Story not in the requested language | quality report flags it; "Regenerate" offered |
| Duplicate or empty word | inline message, nothing stored |
| Unexpected error | friendly message; details in the log and Settings |

## 11. Security and configuration
- Secrets (`GROQ_API_KEY`, `LANGFLOW_API_KEY`, database URL, JWT secret) live in `.env`, git-ignored, and are only read by the API.
- JWT in an httpOnly, SameSite=Lax cookie; state-changing requests also need a custom header (CSRF defence). nginx serves the app and proxies `/api`, so the browser sees one origin and CORS stays closed.
- Parameterized SQL only; Pydantic validates every request; words normalized before storing; every query filtered by the token's `user_id`.
- React escapes text by default; render stories as text, never as raw HTML.
- Per-user separation is enforced in the services layer, so test it: user A must never read user B's words or stories.

## 12. Deployment
Local only. `docker-compose.yml` gains two services next to Langflow and Postgres:

```yaml
  web:
    build: ./web            # builds the React app, serves it with nginx
    ports: ["8080:80"]      # nginx proxies /api to the api service
    depends_on: [api]
  api:
    build: ./api
    environment:
      - LANGFLOW_URL=http://langflow:7860
      - LANGFLOW_FLOW_ID=${LANGFLOW_FLOW_ID}
      - LANGFLOW_API_KEY=${LANGFLOW_API_KEY}
      - DATABASE_URL=postgresql://langflow:langflow@postgres:5432/langflow
      - GROQ_API_KEY=${GROQ_API_KEY}
      - JWT_SECRET=${JWT_SECRET}
    volumes: ["./tutor_core:/app/tutor_core"]
    depends_on: [langflow, postgres]
```

**First run:** `docker compose up`; import the exported flow JSON into Langflow (export it into the repo first); create a Langflow API key; fill `.env`; run the seed script (demo user, sample words in two languages); open `localhost:8080`. For development run `npm run dev` (Vite proxies `/api` to the API).

## 13. Testing
- **API and services:** `pytest` with FastAPI's `TestClient` and fake connections, in the style of the current tests; the fake Langflow server already in the suite covers the chat path.
- **Auth and isolation:** register, wrong password, duplicate username, expired token, and a cross-user test (user A cannot read user B's words or stories).
- **Front end:** Vitest + React Testing Library for components and hooks, with the API mocked.
- **End to end:** Playwright: register, log in, add a word, generate a story, see the quality report (with Groq and Langflow stubbed in the API).
- **Contract:** the generated TypeScript client is rebuilt from the OpenAPI schema in CI, so a breaking API change fails the front-end build.
- **Quality:** the adherence and language checks double as a runtime feature (the quality report) and a regression test.

## 14. Milestones
| M | Deliverable | Depends on |
|---|---|---|
| 1 | API skeleton with `/health`, React shell and routing, compose services | none |
| 2 | Accounts and login (API and UI), `users` table | M1 |
| 3 | `tutor_core` extraction; schema migration (`user_id`, `language`) | existing tests |
| 4 | Vocabulary API and page, per language | M2, M3 |
| 5 | Chat route over the Langflow API with per-user tweaks | M3, flow exported, API key |
| 6 | Story Studio with quality report (target-language lemmas) | M4 |
| 7 | Library, Practice, seed script, end-to-end tests, demo walkthrough | M6 |

## 15. Risks and open questions
1. **Two codebases (TypeScript and Python)** double the surface to test. The generated API client and contract tests are the guard.
2. **Passing the user to Langflow tools.** The plan is Langflow `tweaks` setting hidden `user_id` and `language` inputs on Add Word and the Story tool per request. Verify in M5; the fallback is encoding the user in the `session_id`.
3. **`tutor_core` extraction** touches working components; keep the existing tests as the safety net.
4. **Tokenizers:** `fugashi`, `kiwipiepy` and `jieba` can be fiddly to install. Start with space-delimited languages (Spanish, French).
5. **Non-English story quality:** only 5 of 15 non-English stories were in the right language in the last measurement. Measure the prompt change before Story Studio offers those languages.
6. **Chat reliability depends on the Agent**; the direct pages are the safe fallback.
7. **Open decisions:** plain Tailwind or a component library; stream chat replies (SSE) or return them whole; keep an English-vocabulary mode as well as target-language.
