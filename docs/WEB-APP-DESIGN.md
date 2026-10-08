# Language Tutor Web App — Design (React)

**Status:** Draft v4 · **Date:** 2026-10-05 · **Runs:** locally with Docker Compose (a demo, not hosted) · **Stack:** React + TypeScript, FastAPI, Langflow, Postgres, Groq

v4 is a hardening pass over v3: every change fixes something that would have produced a bug, a data leak or a dead end during the build. Section 17 lists what changed and why. Items marked **[verify in M0]** depend on Langflow behavior that has not been tested in this project yet; M0 exists to settle them before feature work starts.

**Companion document:** [SITE-AND-AI-INTEGRATION.md](SITE-AND-AI-INTEGRATION.md) is the shorter, plainer map of what the site does today, how it talks to the backend, and how Chat and Story Studio will connect to the Langflow flow. This file is the detailed design and the source for the milestones.

## 1. Purpose and scope
A local demo web app for the language tutor. One `docker compose up` starts the React site, a FastAPI backend, Langflow and Postgres. A learner creates an account, logs in, studies in a **target language** (vocabulary is stored in that language), chats with the tutor, manages words, and generates stories with a quality report.

**Langflow stays the AI layer for chat.** The Agent, tools and Tool Result Relay do the chat work; the web app is a client of the flow, so the project's learning objectives stay intact.

**In scope:** accounts and login, per-user and per-language vocabulary, chat tutor, vocabulary manager, story studio with quality report, saved stories, simple practice, diagnostics.
**Out of scope:** public hosting, payments, password reset by email, voice, real-time collaboration, spaced repetition (practice results are not stored), mobile layout.

**Decisions made here** (these were open questions in v3):
- Plain Tailwind, no component library.
- Chat replies are returned whole, no streaming (the Relay replaces the reply after the Agent finishes, so there is nothing useful to stream).
- No separate English-vocabulary mode. English is just one language among the others; the migrated starter words become the `en` list.
- This work supersedes Implementation Step 11 (per-learner vocabulary). The owner's Step 11 is the minimal version, a user column on `words` that the Add Word tool and the Word Loader filter by; here `tutor_core` does that filtering for both tools on the production path, inside a full account system.

## 2. Users and stories
| # | As a learner I want to... | Page |
|---|---|---|
| U1 | chat naturally ("add the word bread", "story in Spanish") | Chat |
| U2 | see, search, edit and delete my words, upload a CSV, add a word | Vocabulary |
| U3 | pick a language, a story type (conversation, narration, story, diary, letter, place, daily routine, anecdote, or a random mix) and optionally a topic, and get a story | Story Studio |
| U4 | see which words in a story are outside my vocabulary | Story Studio |
| U5 | keep stories I liked and reread them | Library |
| U6 | quiz myself on my words and on my saved stories | Practice |
| U7 | check that Postgres, Groq and Langflow are healthy | Settings |
| U8 | create an account and log in so my words are private | Login |
| U9 | keep a separate word list for each language I study, and add a new language | Vocabulary |
| U10 | save a story the tutor wrote in chat | Chat, Library |

## 3. Architecture
A browser cannot hold the Groq or Langflow keys or reach Postgres, so React talks only to a small **FastAPI backend** (`tutor-api`). Two backend paths coexist on purpose:

- **Agent path (`POST /api/chat`):** the API calls the Langflow flow. The Agent picks the tool; the Tool Result Relay returns its exact output. The learner's id and active language reach the tools as hidden inputs (section 3D).
- **Direct path (vocabulary, stories, practice):** the API calls shared Python (`tutor_core`). Faster, deterministic, and it offers controls the Agent tool lacks (narration or dialogue, a fresh story on every "Regenerate").

```mermaid
flowchart LR
  U["Learner browser, localhost:8080"] --> N
  subgraph FE["web container"]
    N["nginx: serves the React build, proxies /api"]
  end
  subgraph BE["api container: FastAPI"]
    R["Routes, auth, error mapping"]
    SV["Services: auth, vocab, story, quality, practice, langflow_client"]
    GATE["AI gate: concurrency limit, one AI call per user"]
    R --> SV
    SV --> GATE
  end
  N -->|"REST JSON, same origin /api"| R
  GATE -->|"HTTP run, hidden inputs via tweaks"| LF["Langflow flow: Agent, tools, Tool Result Relay"]
  GATE -->|"HTTPS direct, via tutor_core"| GQ["Groq API"]
  SV -->|"SQL, schema tutor"| DB[("Postgres")]
  LF -->|"SQL via tutor_core, filtered by user and language"| DB
  LF --> GQ
```

**Network rules.** Only `web` is reachable from the browser (`127.0.0.1:8080`). `api` and `postgres` are not published to the host. Langflow is published on `127.0.0.1:7860` only, for editing the flow. The tools trust the `user_id` they receive, so anyone who can reach Langflow's API can read any learner's words; keeping it on localhost is a security requirement, not a convenience.

## 3A. Tech stack
| Layer | Choice | Notes |
|---|---|---|
| Front end | **React + TypeScript**, built with **Vite** | SPA served by nginx |
| Routing and data | **React Router**, **TanStack Query** | server state, caching |
| Styling | **Tailwind CSS** | no component library |
| Forms | **React Hook Form** + **Zod** | client-side validation mirrors server rules |
| API client | types generated from the FastAPI **OpenAPI** schema (`openapi-typescript`) | `npm run gen:api` |
| Backend | **FastAPI**, Pydantic, uvicorn | thin routes over services; blocking routes are plain `def` (run in the threadpool) because `call_groq` and `psycopg2` block |
| AI orchestration | **Langflow**, **pinned to an exact version** | Agent, Add Word, Story Generator, Tool Result Relay. `latest` is not allowed: this project's diary shows UI and component changes between versions caused repeated breakage |
| LLM | **Groq**, `openai/gpt-oss-120b` | free tier; one rate limit shared by all learners |
| Database | **PostgreSQL 16**, `psycopg2` with a connection pool in the API | migrations with **Alembic**, tables in schema `tutor` |
| Auth | **bcrypt** + **JWT** in an httpOnly cookie | local accounts |
| Shared logic | **`tutor_core`**, a pip-installable Python package | used by Langflow and the API |
| Target-language tokenizing | `simplemma` (Latin-script languages) in core; `jieba`, `fugashi` + `unidic-lite`, `kiwipiepy` as **optional extras** (`tutor_core[ja]`, ...) | the code checks at runtime which are installed (section 8) |
| Tests | `pytest`, Vitest + React Testing Library, Playwright | plus the existing fake-Langflow tests |
| Packaging | **Docker Compose**, nginx, `.env` | new services: `web`, `api` |

**Python version rule.** `tutor_core` is imported inside the Langflow image, so it must run on that image's Python. Check it first (`docker compose run --rm langflow python --version`) and set `requires-python` to match; the repo's committed `__pycache__` files show a local Python 3.14, which is not necessarily what Langflow uses. Do not pull tokenizers into `tutor_core`'s required dependencies.

## 3B. Login and authentication
Local accounts, deliberately simple.

```mermaid
sequenceDiagram
  actor L as Learner
  participant W as React app
  participant A as tutor-api
  participant DB as Postgres
  L->>W: submit login form
  W->>A: POST /api/auth/login
  A->>DB: look up user by username
  DB-->>A: password hash, or nothing
  A->>A: bcrypt verify, against a dummy hash if no user
  A-->>W: set httpOnly cookie with JWT
  W->>A: GET /api/me
  A-->>W: user, language list
  W-->>L: Home, and every API call carries the cookie
```

- **Accounts are identified by email** (no separate username). Sign-up asks for exactly three things: name, email, password (plus which language to start with, and the privacy-policy checkbox). The email is trimmed, lowercased and unique; the format check is deliberately simple (shape only, ASCII only) because the app sends no email and so cannot confirm an address.
- **Consent is recorded**: sign-up requires `accept_privacy: true` (a missing value counts as no) and stores the time and the policy version (`users.privacy_accepted_at`, `privacy_version`).
- **Passwords:** 8 to 72 **bytes** (bcrypt silently ignores everything after byte 72, so longer passwords are rejected rather than truncated). Stored only as bcrypt hashes.
- **Login errors** are one generic message ("wrong username or password"). When the username does not exist, the API still runs a bcrypt check against a dummy hash so response time does not reveal which usernames exist.
- **Failed-login limit:** 5 failures per username in 15 minutes returns `login_locked` with `retry_after`. The counter lives in API memory (single uvicorn worker, resets on restart); that is acceptable for a local demo and is stated so nobody assumes it survives a restart.
- **Sessions are server-side and revocable.** Each login inserts a row in `tutor.sessions` and the JWT carries its id (`jti`). A token is honoured only while that row exists, belongs to the user named in the token, and has not expired. Logout deletes the row, so a copied cookie stops working immediately; `POST /auth/logout-all` deletes every row of the user ("Log out everywhere"); logging in over an existing session revokes the old one; deleting a user cascades. (v3/v4 only deleted the browser cookie on logout, leaving the token valid for 8 hours.)
- **Token:** JWT with `sub` = user id, `jti` = session id and a short expiry (8 hours), no refresh; expiry sends the learner to `/login`. The API refuses to start if `JWT_SECRET` is missing, shorter than 32 characters or equal to a known placeholder.
- **Cookie:** httpOnly, `SameSite=Lax`, `Secure` off for local http (a setting, on by default outside local).
- The API reads `user_id` from the verified token, never from the request body; services take it as an argument.
- React keeps only the user profile in an auth context. **On logout or user change the TanStack Query cache is cleared and per-user state is dropped**, otherwise the next person on the same browser would briefly see the previous learner's words.

## 3C. Languages
Free-text language names create junk (`"Spanish"`, `"español"`, `"spanish "` as three lists). Languages are therefore a fixed list in `tutor_core/languages.py`, stored and exchanged as **ISO 639-1 codes**:

| code | name | native name | tier | stories enabled |
|---|---|---|---|---|
| en | English | English | 1 | yes |
| es | Spanish | Español | 1 | yes (measured, Step 10) |
| fr | French | Français | 1 | yes (measured, Step 10) |
| de, it, pt | German, Italian, Portuguese | | 1 | not until measured |
| ja | Japanese | 日本語 | 2 | yes (measured, Step 10) |
| zh, ko | Chinese, Korean | | 2 | not until measured |

- **Tier 1** = space-delimited with a `simplemma` lemmatizer. **Tier 2** = needs an optional tokenizer; vocabulary checks and cloze practice stay off until the extra installs and is tested.
- **`stories enabled` is a measured flag, not a hope.** A language is switched on only after its in-language rate reaches the Step 10 criterion 5 (≥ 90%). Step 10 measured **Spanish, French and Japanese at 30/30** in the requested language (10 stories each, structure also 30/30, the samples read as natural) and 15/15 non-English turns through the Agent, after tuning change #1 (it had been 5/15). Those three are enabled. German, Italian, Portuguese, Chinese and Korean have not been measured and stay off until a batch of their own reaches the bar. Japanese is enabled even though its vocabulary check is unavailable (Tier 2): the language and structure checks still run. The gate lives in `tutor_core.story.generate`, so Story Studio and the chat tool obey it equally. Vocabulary management works for every listed language regardless. `STORY_ALLOW_UNMEASURED=1` bypasses the gate for the measurement scripts.
- `normalize_language(text)` maps any name or native name to a code (the existing `_NATIVE_LANGUAGE_NAMES` table moves here). An unknown language returns a clear message that lists the supported ones; it never creates a new partition. The Agent instructions change accordingly (see 3D).

## 3D. Passing the learner to Langflow tools
Today's components read one global `words` table. For the web app, `user_id` and the active `language` must arrive per request, and the model must never be able to choose or change them.

**Plan A (preferred) [verify in M0].** Add two hidden inputs, `user_id` and `language`, to Add Word and to Story Generator Tool, with `tool_mode=False` so the Agent does not see them. The API sets them per run through Langflow `tweaks`, which are keyed by component ID or component name. Langflow's docs confirm tweaks are one-time per-request overrides.
- Key tweaks by the component's **name**, not an auto-generated ID that changes if the flow is re-imported; confirm name keys work in the pinned version.
- Recent Langflow versions (the 1.12.x docs) offer `LANGFLOW_TWEAKS_POLICY` (`permissive` by default, `declared` accepts only fields marked "API" on the canvas). If the pinned version has it, use `declared` and mark exactly these fields; otherwise stay permissive and rely on the network rules in section 3.
- **Fail closed.** If `user_id` is missing, the tools return an error message and touch no data. They must never fall back to a shared list. A dev fallback exists only when `TUTOR_DEV_USER_ID` is set in the Langflow container, so the Playground and `run_routing_tests.py` keep working during development.
- **Which language each tool uses.** Add Word always stores into the active language (the hidden `language` input); the reply names the language ("Added 'bread' to your Spanish vocabulary") so a mix-up is visible immediately. The story tool keeps its Agent-supplied `language` argument (the learner may say "story in French" while Spanish is active); the hidden `language` input is only its default when the message names none.
- **Concurrency check.** The spike must run parallel requests for different users against the same flow and prove each tool call saw its own `user_id`. Sequential success does not prove isolation.

**Plan B (fallback).** Build `session_id` as `u{user_id}-{uuid}` and have the tools read it from the running graph (`self.graph.session_id`, **verify**). Add Word then needs the language as an Agent argument. Use B only if A fails the concurrency check; the decision and the evidence get written into the changelog.

**Chat sessions.** The client sends only a random 32-hex id; the server builds `u{user_id}-{id}` itself, so one learner cannot address another learner's session.

**Agent instructions.** `docs/AGENT-INSTRUCTIONS.md` currently says "any language name is valid". For the web app change that line to "use the language the learner names; the tool will say if it is not supported", and update the file when the canvas changes.

## 3E. API surface
All routes live under `/api` inside FastAPI itself (an `APIRouter(prefix="/api")`), so nginx and the Vite dev proxy forward paths unchanged and there is no rewrite rule to get wrong. Non-GET requests must carry `X-Requested-With: tutor` (CSRF defence) and an `Origin` matching the app. Requests from the page also carry `X-Expected-User` (section 12A); a mismatch returns `401 session_changed`.

| Method and path | Purpose |
|---|---|
| `POST /auth/register`, `/auth/login`, `/auth/logout`, `/auth/logout-all`; `GET /me` | accounts and sessions (`logout-all` ends every device) |
| `PATCH /me`; `POST /me/email`, `/me/password`, `/me/delete`; `GET /me/export` | edit name and language; change email or password (current password required, wrong guesses share the login lockout); permanently delete the account (password required); download everything held about you |
| `GET /meta` (public) | policy version and the operator's privacy contact, for the policy page |
| `PATCH /me` | display name, native language |
| `GET /languages` (public); `POST /me/languages` | supported list with flags; start studying a language |
| `GET /words?language=&q=&limit=&offset=` | list with `total`; limit default 50, max 200 |
| `POST /words` (`language`, `word`, optional `meaning`) | add one |
| `PATCH /words/{id}` (`meaning`, `word`) | edit |
| `POST /words/delete` (`ids`) | delete several (the UI has a multi-select) |
| `POST /words/upload` (multipart: `language`, CSV file) | bulk add |
| `POST /chat` (`message`, `session_id`, `language`) | Agent path |
| `POST /stories/generate` (`language`, optional `story_type`, optional `topic`) | direct path. `story_type` is one of the eight types (`narration`, `dialogue`, `story`, `diary`, `letter`, `place`, `routine`, `anecdote`) or omitted for the weighted random mix; `topic` is omitted to let the code pick one that avoids the last 8. Returns the story, the type and topic actually used, and the report; never cached |
| `GET /stories?language=`, `GET /stories/{id}`, `POST /stories`, `DELETE /stories/{id}` | library |
| `GET /practice/flashcards?language=&limit=` | shuffled words with meanings |
| `GET /practice/cloze?story_id=` | fill-in-the-blank items from a saved story |
| `GET /health/live` (public), `GET /health` (login required) | liveness; full status |

**Request and response rules**
- `POST /stories` takes only `language`, optional `story_type` and `topic`, and `body`. **The server computes the quality report itself**; it never trusts a report sent by the client. This is also how a chat story is saved (U10), where `style` is unknown and stored as null.
- `POST /chat` returns `{reply, tool_calls: [{name, args, output}], session_id}`. `reply` is the Relay's output; `tool_calls` feeds the `ToolTrace`.
- **CSV upload:** UTF-8 (a BOM is stripped), at most 1 MB and 5,000 rows, a required `word` column, an optional `meaning` or `definition` column (the starter file uses `definition`). Valid rows are inserted in one transaction. The response is `{added, duplicates, invalid: [{row, reason}]}` with the first 20 invalid rows. The sample file contains `hello` twice, which exercises the duplicate path.
- `GET /health` calls Postgres (`SELECT 1`), Langflow's health route, and Groq's lightweight models-list route. The Groq result is cached for 60 s so the Settings page cannot burn the shared rate limit; in `AI_MODE=stub` it reports "not checked". The public `/health/live` only says the process is up.
- Another learner's resource is answered with `404`, never `403`, so existence is not revealed.

**Error body (every non-2xx):** `{"error": {"code": "...", "message": "...", "retry_after": 15, "details": {}}}`. The codes are listed in section 11.

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
  C -->|"save the story"| L
  S -->|"save"| L
  L -->|"reread or regenerate"| S
  L -->|"quiz on a story"| PR
```

| Route | Purpose | API | Main components |
|---|---|---|---|
| `/login` | register or log in (two tabs on one page) | `/auth/*` | `LoginForm` |
| `/` Home | word count, recent stories, shortcuts | `/words`, `/stories` | `StatCard` |
| `/chat` | talk to the tutor; show the tool used; save a story | `/chat`, `/stories` | `ChatPanel`, `ToolTrace` |
| `/vocabulary` | list, search, add, edit, delete, CSV upload | `/words` | `WordTable`, `CsvUpload` |
| `/studio` | generate a story, quality report | `/stories/generate` | `StoryCard`, `ReportPanel` |
| `/library` | saved stories | `/stories` | `StoryList` |
| `/practice` | flashcards, cloze from stories | `/practice/*` | `Flashcard`, `ClozeItem` |
| `/settings` | health checks, languages, account | `/health`, `/me` | `StatusList` |
| `*` | not-found page | | |

Every page defines three states before it is considered done: loading, empty (with the next action, such as "add your first words") and error (the message from the error body).

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
|        [Save to library]                                     |
|                                                              |
| [ Type a message...                                  ] [Send]|
| Sidebar:  Adding words to: Spanish (16)   [New session]      |
+--------------------------------------------------------------+
```

**Vocabulary**
```
+--------------------------------------------------------------+
| Vocabulary  Language [Spanish v] [+ language]  (16) [Search] |
|                                          [Upload CSV] [Add]  |
+--------------------------------------------------------------+
|  [ ] word      meaning (editable)  |  Add a word:            |
|  [ ] hola      hello               |  [ bread     ] [+]      |
|  [ ] agua      water               |  Stored lowercase (German|
|  [ ] gracias   thank you           |  keeps capitals);       |
|  ... page 1 of 1                   |  duplicates ignored.    |
|  [Delete selected]                                           |
|             [ Make a story from my words -> ]                |
+--------------------------------------------------------------+
```

**Story Studio**
```
+--------------------------------------------------------------+
| Language [Spanish v]  Type [Any v]  Topic [Any v]            |
|                                        [ Generate story ]    |
+--------------------------------------------------------------+
| Story                         | Quality report               |
| Ana: Hola, tienes agua?       | Language: ok                 |
| Luis: Si, tengo agua.         | Length: 6 lines   Format: ok |
| ...                           | Words not in your list: bring|
|                               | Read time: about 20 s        |
| [Save] [Regenerate] [Practice this story]                    |
+--------------------------------------------------------------+
```
Languages whose stories are not enabled appear greyed out with "not available yet".

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
  W->>A: POST /api/chat
  A->>A: take the user's AI lock, acquire a slot in the AI gate
  A->>LF: run flow, built session id and tweaks
  LF->>AG: message
  AG->>AG: tool call, then tool output
  AG-->>R: reply plus tool call
  R-->>LF: reply replaced by the exact tool output
  LF-->>A: JSON response
  A->>A: parse reply and tool calls, fall back to stored messages
  A-->>W: reply and tool trace
  W-->>L: message bubble and expandable trace
```

**Reading the tool trace.** The existing `scripts/routing_checks.py` (`find_tool_calls`, `with_tool_blocks`) and `scripts/run_routing_tests.py` already solve this against the real Langflow response, including the fallback to `GET /api/v1/monitor/messages?session_id=`. `langflow_client` ports that logic into the API, and its tests use a **real captured response** saved in M0 as the fixture. The diary records that fixtures built from assumptions passed while the real shape failed; this design does not repeat that.

**Story Studio (direct path):** `POST /stories/generate` runs `story_service.generate(user, language, story_type, topic)`:
1. Check the language is enabled for stories.
2. Load the learner's words in that language; fewer than **5** returns `not_enough_words` (no Groq call).
3. Sample at most `MAX_PROMPT_WORDS` (default 150) words into the prompt. Without a cap, a 5,000-word list would exceed Groq's free-tier token budget and fail. The quality check still uses the **full** list, because the learner knows all of it.
4. Build the prompt (the code picks the story type and a topic when none is given, never repeating the last 8 topics; `describe_prompt` recovers which were used), call Groq, strip the planning text.
5. `quality.check(...)` scores it and the response returns story, `story_type`, `topic` and report.
The direct path **never reads or writes the story cache**: "Regenerate" must produce a new story.

## 7. Data model
Everything lives in a dedicated Postgres **schema `tutor`** inside the existing `langflow` database. A separate schema keeps Alembic away from Langflow's own tables and lets the migration read the legacy `public.words` table, which a separate database could not.

```mermaid
erDiagram
  USERS ||--o{ USER_LANGUAGES : studies
  USERS ||--o{ WORDS : owns
  USERS ||--o{ STORIES : saves
  USERS {
    int id PK
    text email UK
    text password_hash
    text display_name
    text native_language
    timestamptz privacy_accepted_at
    text privacy_version
    timestamptz created_at
  }
  USER_LANGUAGES {
    int user_id PK
    text language PK
    timestamptz created_at
  }
  WORDS {
    int id PK
    int user_id FK
    text language
    text word
    text meaning
    timestamptz created_at
  }
  STORIES {
    int id PK
    int user_id FK
    text language
    text style
    text body
    bool passed
    jsonb report
    timestamptz created_at
  }
```

- `words`: `UNIQUE (user_id, language, word)`, index on `(user_id, language, id)`. `meaning` is optional and written in the learner's native language (v3 called it `meaning_en`, which was wrong for a non-English native language).
- `stories.story_type` is one of the eight types or null (null for stories saved from chat, where the type is unknown) and `stories.topic` is optional text. `report` carries a `rules_version`, so old reports stay interpretable if the pass rule changes.
- `user_languages` lets a learner add a language before adding any word, so it can appear in the selector.
- All foreign keys cascade on delete. Timestamps are `timestamptz` (the current table already uses it).

**Word rules (one function, used by the API, CSV upload and the Add Word tool).**
`normalize_word(word, language)`: Unicode NFC, collapse whitespace, strip edge punctuation, lowercase (except German, where nouns are capitalized; German uniqueness is therefore case-sensitive and `Haus` and `haus` may coexist). Then validate: 1 to 40 characters, at most 5 words, only letters and combining marks plus apostrophe, hyphen and space. Everything else is rejected with a reason. Besides keeping data clean, this **limits prompt injection**: vocabulary is pasted into the story prompt, so no line breaks, symbols or long text can get in. It cannot stop a short letters-only phrase ("ignore previous rules" is legal), so the prompt builder must also present the list as quoted data, not instructions (done when the prompt is built in M6).

**Migrations.** Alembic lives in `api/migrations`, `version_table_schema='tutor'`, and `include_object` ignores everything outside `tutor`. The API container runs `alembic upgrade head` at startup, before serving. Migrations create tables only; they never create users with passwords. The legacy import (existing `public.words` rows become the demo user's `en` list) is a **seed-script step**, `scripts/seed.py --import-legacy`, and leaves `public.words` in place as a backup.

## 8. Quality report
The report is computed by `tutor_core.quality`, moved out of `scripts/vocab_adherence.py` (scripts cannot be imported by the API or by Langflow). The existing tests move with it. What can be checked depends on the language, so the report says which mode it used instead of implying every check ran:

| Check | Tier 1, English | Tier 1, other languages | Tier 2 |
|---|---|---|---|
| Written in the requested language | yes (`language_check`) | yes (share of English words must be low) | yes (script share) |
| Structure: length 4 to 10 sentences or lines, dialogue format (conversations only), no leaked plan, not empty | yes | yes | yes |
| Words outside the vocabulary | **strict**: pass/fail, at most 5 strays (the owner raised it from 2 in tuning change #2) | **informational**: listed, not scored | not available |

Why informational for other languages: the strict English rule works because the checker has an English list of allowed grammar words. No such list exists for Spanish or French yet, so articles and prepositions would be flagged as strays and every story would fail. The learner still sees the list ("Words not in your list"), which is what U4 asks for.

**Pass** = language ok **and** structure ok **and** no leaked plan **and** (English only) at most 5 strays. Lemmas come from `simplemma` when available, so inflections count as the same word. **Read time** = `ceil(word_count / 2)` seconds, a slow beginner pace.

**Known tension (Step 10, tuning change #2).** The six newer story types use a looser word rule (a few very common everyday words are allowed), and the last measurement found 29% of their words outside the vocabulary against 3% for the classic styles, and an English pass rate of 2/20 at ≤ 5 strays. The model also tends to stuff the whole word list into every story. The owner's next steps are a larger word list (`sample_data/suggested_words.csv`) and sampling a few focus words per story; `tutor_core` should adopt whichever lands, next to the `MAX_PROMPT_WORDS` cap. Studio shows the report honestly rather than hiding failures. The report shape: `{rules_version, status, language, structure, vocabulary: {mode, outside, limit}, read_seconds}`.

## 9. Code structure and a shared core
```
web/                       # React app (Vite) + nginx.conf + Dockerfile
  src/routes/              # one file per route
  src/components/          # ChatPanel, WordTable, StoryCard, ReportPanel...
  src/api/                 # generated types and a small fetch wrapper
  src/auth/                # auth context, protected-route wrapper
api/                       # FastAPI + Dockerfile
  main.py, routes/, services/ (auth, vocab, story, quality, practice, langflow_client, ai_gate)
  migrations/              # Alembic
  config.py                # env vars only; fails fast on missing secrets
tutor_core/                # pyproject.toml; pure Python, no langflow import
  languages.py, words.py, prompts.py, groq.py, story.py, quality.py, db.py
langflow/Dockerfile        # pinned Langflow + tutor_core installed
flows/language-tutor.json  # exported flow, auto-loaded
custom_components/         # thin Langflow wrappers over tutor_core
```

**Key decision.** `story_tool.py` and `add_word.py` import Langflow at the top, so the API cannot import them. The pure logic (`normalize_word`, `normalize_language`, `build_story_prompt`, `call_groq`, `load_words`, the checks) moves into `tutor_core`, used by both Langflow and the API. This also clears the deferred items (duplicated logic, hardcoded credentials and model names).

**Rules for `tutor_core`**
- Install it as a package into the Langflow image (`langflow/Dockerfile`), not via `PYTHONPATH` or cross-file imports; the diary records the component scanner being unreliable with those. Install into the same Python environment Langflow runs in (verify the path in M0).
- Configuration comes from environment variables (`DATABASE_URL`, `GROQ_API_KEY`, `GROQ_MODEL`), never from constants in the code.
- Functions receive a connection or a client as an argument; the only module-level state is the Agent-path story cache.
- **Do the extraction as two separate commits:** first a pure move with only import paths changed and all existing tests green, then the behavior changes (language codes, word validation, cache key, word cap, story type and topic returned). A failing test then points at one cause.
- The prompt templates stay pinned by their SHA-256 in the tests (the classic narration and dialogue templates are untouched by tuning change #2 and their pins still pass). Step 10 is complete (final routing run 43/45, non-English 30/30, story variety measured), so the baseline exists: note the commit and the test-plan row before the extraction. Move the new functions with the code (`choose_story_type`, `choose_topic`, `describe_prompt`, `generate_story_for_learner(..., story_type, topic)`, `ALL_STORY_TYPES`, `TOPICS`) together with `tests/test_story_variety.py` and the variety report in `scripts/vocab_adherence.py`.

**The story cache** exists only because the Agent has been seen calling the tool 3 to 5 times per request. It is therefore restricted to the Agent path and keyed by **(user_id, language, style)**. v3 kept the existing language-only key, which would have served one learner's story, built from their words, to another learner.

## 10. State and caching (front end)
| Item | Where | Notes |
|---|---|---|
| Logged-in user | auth context, fed by `GET /api/me` | protected routes redirect to `/login`; cleared on logout |
| Words, stories, health | TanStack Query cache | invalidated after add, edit, delete, upload, save |
| Chat messages, session id | a `ChatProvider` above the router, mirrored to `sessionStorage` | component state would be lost when the learner navigates to another page and back |
| Generated, unsaved story | a small `StudioProvider` | same reason; cleared on logout and when the language changes |
| Selected language, style | context, remembered in `localStorage` under a key that includes the user id | so two learners on one browser do not share the setting |

**Optimistic updates** only for delete. Add and edit wait for the server because the server normalizes the word and may reject it as a duplicate; an optimistic add could show something that is never stored. Calls to Groq or Langflow never retry automatically, to protect the shared rate limit.

## 11. Errors and rate limits
Groq's free tier is shared by everyone using the app, so limits will show up with more than one learner.

**AI gate (API side).** Every call that reaches Groq, direct or through Langflow, passes through one gate: a process-wide semaphore of 2 concurrent calls (wait up to 5 s, then `tutor_busy`) and a per-user lock so a double-click or two tabs cannot submit two AI requests at once. `call_groq` gets a **total deadline of 60 s** instead of "3 attempts of 30 s each" (which could reach 90 s). nginx waits 120 s, and the Langflow call times out at 100 s. The UI shows "this is taking longer than usual" after 20 s.

| Code (HTTP) | Situation | What the learner sees |
|---|---|---|
| `tutor_busy` (429) | Groq 429, gate full, or the fallback message | "The tutor is busy. Try again in a moment", AI buttons disabled for `retry_after` (default 15 s) |
| `not_enough_words` (422) | fewer than 5 words in that language | message with the counts and a link to Vocabulary |
| `language_unavailable` (422) | stories not enabled for that language | "Stories in X are not available yet"; vocabulary still works |
| `langflow_unavailable` (503) | Langflow unreachable | banner on Chat only; other pages keep working (direct path) |
| `ai_failed` (502) | Groq error, empty output | "Couldn't write a story right now"; Regenerate offered |
| `validation_error` (422) | bad word, duplicate in a form, bad CSV | inline message next to the field; nothing stored |
| `login_failed` (401), `login_locked` (429) | wrong credentials, too many failures | generic message; lock shows the wait time |
| `conflict` (409) | username taken | inline message |
| `not_found` (404) | missing or another learner's resource | not-found page |
| `internal_error` (500) | anything else | friendly message; details in the log and Settings |

A story that is not in the requested language is not an error: the quality report flags it and Regenerate is offered.

## 12. Security and configuration
- **Secrets** (`GROQ_API_KEY`, `LANGFLOW_API_KEY`, database password, `JWT_SECRET`, Langflow admin password) live in `.env`, which is git-ignored. The repo gets a committed **`.env.example`** with placeholders, and Langflow's `admin123` default is replaced by a value from `.env`. The browser never sees them: only the API holds the Langflow key, and only the API and Langflow hold the Groq key.
- **Cookies and CSRF:** see 3B and 3E. nginx serves the app and proxies `/api`, so the browser sees one origin and CORS stays closed.
- **SQL:** parameterized only; Pydantic validates every request; every query is filtered by the token's `user_id`, enforced in the services layer.
- **Rendering:** React escapes text by default; render stories as text, never as raw HTML.
- **Logging:** one request id per request, passed to Langflow calls. Never log passwords, tokens or keys. The committed `custom_components/relay_debug.log` is a debug leftover and goes into `.gitignore`.
- **Per-user separation** is tested directly: user A must never read or change user B's words, stories or chat session, including through `POST /stories` and `/chat`.

## 12A. Keeping users apart
"User A logs in and user B can reach A's information" can happen in several different ways. Each has its own defence and its own test; none relies on another.

| # | How it could happen | Defence | Proven by |
|---|---|---|---|
| 1 | A request asks for someone else's rows (changed id, search, bulk delete, CSV) | every query filters by the token's `user_id`; other people's ids answer `404`; a test fails if any route lacks the login check | `test_isolation.py`; `test_every_route_requires_login_unless_explicitly_public` (reads the OpenAPI schema, so a new route is covered automatically); each filter was removed in turn and a test failed |
| 2 | A's login token is copied (shared computer, log, malware) and used after A logged out | server-side sessions (above) | `test_logout_revokes_the_session_on_the_server`; browser test "a copied cookie stops working once the owner logs out" |
| 3 | A shared browser or proxy caches A's JSON and replays it to B | every API response, errors included, is `Cache-Control: no-store` with `Vary: Cookie` | `test_responses_are_never_cacheable`; browser test on headers |
| 4 | Two tabs, one cookie: B logs in on tab 2, tab 1 still shows A and now acts as B | every request carries `X-Expected-User` (the id the tab is showing); a mismatch is refused (`session_changed`) and the tab drops A's data, then adopts whoever is really signed in; tabs also tell each other about logins and logouts (`BroadcastChannel`) | `test_other_tab_logged_in_as_someone_else_is_refused_not_misrouted`; browser tests "logging in as B in tab 2 stops tab 1..." and "logout in one tab logs the other tab out" |
| 5 | A's data stays in the page's memory after logout and B sees it | on logout, user change or any 401 the cache and `sessionStorage` are emptied (`me` is set to logged-out first, so nothing stays on screen); cached queries are keyed by user id, so even a leftover entry is never read for another user; toasts are discarded with the user | web tests (6 mutations each made one fail); browser test "Back after logout..." |
| 6 | The browser's back/forward cache restores A's page after logout | a restored page is reloaded (`pageshow` with `persisted`) | `bfcache.ts` unit test; browser test |
| 7 | A script injected into the page reads data or frames it | strict Content-Security-Policy (`script-src 'self'`, no inline scripts or styles, `frame-ancestors 'none'`), `X-Frame-Options: DENY`, `nosniff`, httpOnly cookie; React escapes text | browser tests: headers, and "the whole app works under the CSP (no violations)" |
| 8 | A page of another website makes the browser send a request with the cookie | custom `X-Requested-With` header required on writes, `Origin` check, `SameSite=Lax` | `test_csrf_header_and_origin` |

**Known limits (not defended):** someone who can read the machine's memory or the learner's open browser is the learner; the login lockout counter is in memory and resets when the API restarts; accounts have no email verification or password reset; the Vite dev server (`make dev-web`) sends no CSP, only the nginx build does; and a person with access to Langflow's port can read any learner's words, which is why it is bound to localhost only.

## 12B. Privacy policy: what it promises and where the code keeps the promise
The policy page (`/privacy`, text in `web/src/routes/Privacy.tsx`, version in `api/app/policy.py`) is only worth having if it is true. Each claim below is tied to the code and the test that would fail if it stopped being true. **When behaviour changes, change the text and bump `POLICY_VERSION`.**

| The policy says | Kept by | Checked by |
|---|---|---|
| Sign-up asks only for name and email (plus a password) | `RegisterBody` has no other personal field; the form shows exactly these | web test "registration asks for name and email"; browser test "the form asks for exactly name, email and password" |
| You must accept the policy to sign up; we record that you did | `accept_privacy` is required (a default would have skipped the check, which an early test caught); date and version stored | `test_signup_requires_accepting_the_privacy_policy`, `test_consent_is_recorded_with_the_policy_version`, web test for the unchecked box |
| The password is a one-way hash nobody can read | bcrypt; no password in any response, log or export | `test_export_contains_my_data_and_no_secrets`; browser test on the export file |
| One cookie, httpOnly, up to 8 hours, no analytics or third-party cookies | session cookie only; CSP allows only our own origin (`default-src 'self'`) | browser tests (cookie flags, "no CSP violations") |
| Download my data gives everything held about you, and only yours | `services/export.py`; keys are table names | `test_export_covers_every_table_that_holds_user_data` (fails when a future table with `user_id` is left out), isolation test in the export test |
| Delete account removes everything immediately | hard delete; every reference to `users` is `ON DELETE CASCADE` | `test_delete_account_removes_everything_and_ends_all_sessions`, `test_every_reference_to_users_deletes_with_the_user`; browser test deletes, then re-registers the same email with nothing carried over |
| Deleting needs your password | `_reauthenticate`, shared lockout | `test_delete_account_needs_the_right_password`, mutation "delete without password" fails a test |
| Changing your password logs out other devices | `revoke_others` | `test_change_password_ends_other_sessions_but_keeps_this_one` |
| You can correct your name, email, password | Settings forms, `PATCH /me`, `/me/email`, `/me/password` | `test_account.py`; browser test "changing name, email and password works end to end" |
| The app sends no email | no mail code exists | (true by absence; if mail is added, the policy sentence in section 3 must change first) |
| **Your name and email are not sent to the AI service** | the identity of the learner reaches Langflow only as a numeric `user_id`; prompts are built from words and messages | **Not yet testable: chat and stories are not built.** Requirement for M5/M6: a test that builds every prompt for a user with a recognisable name and email and asserts neither appears |
| Chat and Story Studio are "not available yet" | placeholder pages | must be reworded when M5/M6 ship |

**Operator checklist (things code cannot do):** set `PRIVACY_CONTACT` to a real address; serve the app over HTTPS before exposing it beyond localhost (`COOKIE_SECURE=1`); decide how long database backups are kept and say so if asked; check the age wording ("under 16") and any legal requirements for the place where the app is used. **This policy is a plain-language template written alongside the code, not legal advice. It has not been reviewed by a lawyer.**

**Known gaps:** accounts created before consent recording (the development demo accounts) have no consent record and a placeholder address `<name>@legacy.invalid`; there is no "forgot password" because the app cannot send email; email addresses must be ASCII; there is no prompt to re-accept the policy when the version changes.

## 13. Deployment
Local only. Compose gains `web` and `api`; Postgres gets a healthcheck so the API does not start (and fail its migration) before the database is ready; Langflow is pinned and built with `tutor_core`.

```yaml
services:
  postgres:
    image: postgres:16
    environment:
      - POSTGRES_USER=langflow
      - POSTGRES_PASSWORD=${POSTGRES_PASSWORD}
      - POSTGRES_DB=langflow
    volumes: ["postgres_data:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U langflow -d langflow"]
      interval: 5s
      retries: 10

  langflow:
    build: { context: ., dockerfile: langflow/Dockerfile }   # FROM langflowai/langflow:<exact version>
    ports: ["127.0.0.1:7860:7860"]
    environment:
      - LANGFLOW_DATABASE_URL=postgresql://langflow:${POSTGRES_PASSWORD}@postgres:5432/langflow
      - LANGFLOW_COMPONENTS_PATH=/app/custom_components
      - LANGFLOW_LOAD_FLOWS_PATH=/app/flows
      - LANGFLOW_SUPERUSER=admin
      - LANGFLOW_SUPERUSER_PASSWORD=${LANGFLOW_SUPERUSER_PASSWORD}
      - LANGFLOW_SECRET_KEY=${LANGFLOW_SECRET_KEY}
      - DATABASE_URL=postgresql://langflow:${POSTGRES_PASSWORD}@postgres:5432/langflow
      - GROQ_API_KEY=${GROQ_API_KEY}
    volumes: ["./custom_components:/app/custom_components", "./flows:/app/flows", "./scripts:/app/scripts", "./tests:/app/tests"]
    depends_on: { postgres: { condition: service_healthy } }

  api:
    build: { context: ., dockerfile: api/Dockerfile }        # context is the repo root so tutor_core can be COPYed
    expose: ["8000"]                                          # not published to the host
    environment:
      - LANGFLOW_URL=http://langflow:7860
      - LANGFLOW_FLOW=language-tutor
      - LANGFLOW_API_KEY=${LANGFLOW_API_KEY}
      - DATABASE_URL=postgresql://langflow:${POSTGRES_PASSWORD}@postgres:5432/langflow
      - GROQ_API_KEY=${GROQ_API_KEY}
      - JWT_SECRET=${JWT_SECRET}
      - AI_MODE=${AI_MODE:-live}
      - MAX_PROMPT_WORDS=150
    depends_on: { postgres: { condition: service_healthy } }

  web:
    build: ./web
    ports: ["127.0.0.1:8080:80"]
    depends_on: [api]

volumes:
  postgres_data:
```

- The old mount of `../shared-components/universal-model-selector` points outside the repo and breaks on any other machine. Drop it from compose (it belongs to the unstarted Bonus step) or move the component into the repo.
- **nginx:** `location /api/` proxies to `http://api:8000` with no path rewriting and `proxy_read_timeout 120s` (nginx's default of 60 s would cut a slow story); everything else falls back to `index.html` for client-side routes.
- **Flow identity.** `flows/language-tutor.json` is auto-loaded at startup, which removes the manual import step. The API calls the flow by **endpoint name** (`language-tutor`) rather than a UUID that changes on re-import **[verify in M0]**; if names do not work in the pinned version, take the flow id from `GET /api/v1/flows/` at API startup. Flows loaded this way belong to the superuser, so the API key must be created for that same user.
- **Langflow API key bootstrap.** The key cannot exist before Langflow does. `scripts/bootstrap_langflow.py` (the key-creation code already exists in `run_routing_tests.py`) logs in as the superuser, creates a key and prints it for `.env`.

**First run:** copy `.env.example` to `.env` and fill it in; `docker compose up -d postgres langflow`; run the bootstrap script and put the key in `.env`; `docker compose up -d`; run `scripts/seed.py` (a demo user from `DEMO_EMAIL`/`DEMO_PASSWORD` in `.env`, sample words in two languages, optional `--import-legacy`); open `localhost:8080`. For development run `npm run dev` (Vite proxies `/api` to `http://localhost:8000` without rewriting).

## 14. Testing
- **`tutor_core`:** the existing tests move with the code and must keep passing unchanged apart from import paths. Add tests for language-code mapping, `normalize_word` per language, word validation (newlines, control characters, overlong input), the word cap, and the cache key (two users, same language, never a shared result).
- **API and services:** `pytest` with FastAPI's `TestClient` and a throwaway test schema. `AI_MODE=stub` swaps Groq and Langflow for fakes, so the same switch serves unit tests, Playwright and offline demos.
- **Langflow client:** parse the **captured real response** fixture and the stored-messages fallback; reuse the fake Langflow server from `tests/test_routing_runner_with_fake_langflow.py` for the transport.
- **Auth and isolation:** register, wrong password, duplicate username, 72-byte password limit, expired token, lockout, and cross-user tests on words, stories and chat sessions.
- **Migrations:** `alembic upgrade head` on an empty database and on one that already has the legacy `public.words` table.
- **Front end:** Vitest + React Testing Library for components and hooks with the API mocked, including "cache cleared on logout".
- **End to end:** Playwright with the stubbed AI: register, log in, add a word, upload a CSV with a duplicate, generate a story, see the report, save it, log out and confirm the next user sees nothing of it.
- **Contract:** `npm run gen:api` regenerates the TypeScript client from the OpenAPI schema and `git diff --exit-code` fails on drift. The repo has no CI, so `make check` runs this together with `pytest`, `vitest` and `tsc`; add a GitHub Action later if wanted.
- **Quality:** the adherence and language checks double as a runtime feature (the report) and a regression test.

## 15. Milestones
| M | Deliverable | Depends on | Done when |
|---|---|---|---|
| 0 | Spikes and groundwork, no features: pin Langflow and check its Python; export the flow to `flows/`, auto-load it, run it by endpoint name; **tweaks spike** (hidden inputs reach both tools, with a parallel two-user run); capture a real run response and stored-messages response as fixtures (Step 10 is complete, so no measurement is outstanding) | none | `scripts/spike_tweaks.py` passes; fixtures committed; plan A or B chosen and recorded in the changelog |
| 1 | API skeleton with `/health/live`, React shell and routing, compose services with healthchecks, nginx, `.env.example`, `.gitignore` fixes (`.env`, `__pycache__`, `*.log`, root `*.patch`) | M0 | `docker compose up` shows the shell at `localhost:8080`; `make check` is green |
| 2 | Alembic base schema, accounts and login (API and UI), protected routes, first isolation tests | M1 | register, login, logout work; cross-user test on `/me` and a sample resource passes |
| 3 | `tutor_core` extraction (move, then change); Langflow components become thin wrappers; fail-closed tools; `tutor.words` replaces `public.words` for the tools | M0, existing tests | all pre-existing tests pass; English prompt hashes unchanged; a short `run_routing_tests.py` run passes against the rebuilt flow |
| 4 | Vocabulary API and page, per language, CSV upload, edit, bulk delete | M2, M3 | vocabulary flows work in the browser; upload report shows duplicates and invalid rows |
| 5 | Chat route over the Langflow API with per-user tweaks, trace, save-to-library | M0, M3, M4 | two users chat in parallel and each only touches their own words |
| 6 | Story Studio with quality report; language gate; AI gate | M3, M4 | stories generate for `en`; report shows the right mode; Regenerate returns a new story |
| 7 | Library, Practice, seed script, end-to-end tests, demo walkthrough | M5, M6 | Playwright suite green; walkthrough script reproduces the demo from a clean checkout |

### Implementation status (updated as work lands)
| M | Status | Notes |
|---|---|---|
| 0 | **not started** | needs a running Langflow and Groq; nothing below depends on its result except M3 and M5 |
| 1 | built, partly verified | `make check` green; real nginx + API + Postgres exercised with curl. **Dockerfiles and compose were not run** (no Docker where this was built) |
| 2 | built | schema migration, register / login / logout / me, lockout, CSRF, isolation tests (mutation-checked) |
| 3 | **not started** | `tutor_core` so far holds only new code (`languages`, `words`); existing components still carry their own copies until the extraction |
| 4 | built | vocabulary API and page (list, search, add, edit, bulk delete, CSV upload, add language) |
| 5-7 | not started | the pages exist as "coming soon" placeholders |
| hardening | built | server-side sessions, `no-store` and security headers, CSP, expected-user check, per-user cache keys, cross-tab sync, back-cache guard (section 12A); 53 API + 31 web tests + 9 real-browser tests |
| style | built | see `docs/STYLE-GUIDE.md` (tokens, components, measured contrast, honest gap list) |
| accounts and privacy | built | email sign-up with consent, privacy policy page, Settings (profile, email, password, appearance, data download, account deletion), dark mode, styled dialogs; section 12B |

Deviations from this document: the `stories` table is not in migration 0001 (it arrives with Story Studio in M6, so no untested schema ships early); `GET /languages` is public because the registration form needs it; the upload response also carries `invalid_count`; TypeScript is pinned to 5.x because `openapi-typescript` does not run on TypeScript 7.

## 16. Risks and open questions
1. **Tweaks and concurrency** (3D) are the largest unknown; M0 settles it and decides plan A or B.
2. **Two codebases (TypeScript and Python)** double the surface to test. The generated API client and `make check` are the guard.
3. **`tutor_core` extraction** touches working components; the two-commit rule and the existing tests are the safety net.
4. **Tokenizers** (`fugashi`, `kiwipiepy`, `jieba`) can be fiddly to install. They are optional extras, so a failed install disables a language tier and breaks nothing else.
5. **Story quality for the languages not yet measured** (German, Italian, Portuguese, Chinese, Korean). Spanish, French and Japanese measured 30/30 in Step 10; the rest stay disabled until a batch of their own reaches 90% (3C). English variety versus vocabulary fit is still being tuned (section 8, tuning change #2).
6. **Chat reliability depends on the Agent**; the direct pages are the safe fallback, and `tutor_busy` handling covers the shared rate limit.
7. **Langflow version drift:** field names such as the Agent's instruction field and the tweaks policy differ between versions. Everything version-specific is checked in M0 against the pinned version.
8. **Shared Groq limit:** the AI gate reduces bursts but cannot raise the free-tier limit; with several simultaneous learners some `tutor_busy` responses are expected and the UI is designed for them.
9. **Remaining product choice:** whether the Agent-path `Story Generator Tool` should gain `story_type` and `topic` arguments. Today it takes only `language`: the Step 10 notes record that a request for a "dialogue" is not honored, and that "tell me a story" with no language sometimes asks and sometimes defaults to English. Exposing a type and topic is a separate change that needs a routing re-run. In M5 the hidden active language becomes the default for the no-language case, which must be re-checked with routing case I1. Until then chat stories use a random type while Studio lets the learner choose.

## 17. What changed from v3
| # | v3 problem | Fix in v4 |
|---|---|---|
| 1 | Story cache keyed by language only: one learner could get another's story | Cache only on the Agent path, keyed by (user, language, style) |
| 2 | "Regenerate" would return the cached story for up to 20 s | Direct path never uses the cache |
| 3 | Tools fell back to a shared global word list if no user arrived | Fail closed; explicit dev-only fallback |
| 4 | Tweaks plan unverified, and tweaks keyed by auto-generated IDs | M0 spike with a parallel two-user test; key by component name; `declared` policy where available; plan B written down |
| 5 | Which language Add Word and the story tool use was undefined | Add Word uses the active language and names it in the reply; story tool uses the Agent's language with the active one as default |
| 6 | Free-text languages could create duplicate or junk lists | Fixed language list with ISO codes; unknown languages rejected |
| 7 | Stories offered in languages measured at 5/15 correct | Per-language "stories enabled" flag, switched on only after measurement (since measured: Spanish, French and Japanese 30/30, now enabled) |
| 8 | Quality report claimed lemma checks everywhere, but the checker is English-only | Three modes (strict, informational, unavailable), stated in the report |
| 9 | Checker lived in `scripts/`, which neither the API nor Langflow can import | Moved to `tutor_core.quality` |
| 10 | Whole vocabulary pasted into the prompt: a large list would exceed the token budget | `MAX_PROMPT_WORDS` sampling; full list still used for checking |
| 11 | No minimum vocabulary for a story | 5-word minimum with a friendly `not_enough_words` |
| 12 | Uploaded "words" could carry prompt-injection text | One validation rule for all entry points (limits it; the prompt builder must also treat the list as data) |
| 13 | Lowercasing breaks German nouns (noted in the diary) | Lowercase except German |
| 14 | `meaning_en` wrong for non-English native languages | Renamed `meaning` |
| 15 | Schema ownership unclear; Alembic would clash with Langflow tables | Schema `tutor`, Alembic with a filtered `include_object`, legacy import in the seed script |
| 16 | `/health` public and able to burn Groq quota | Public liveness only; full health needs login; Groq result cached 60 s |
| 17 | API gaps: no edit, no multi-delete, no practice routes, undefined error format, undefined CSV rules | Added all, plus a typed error body and CSV limits |
| 18 | Client-supplied quality report on save | Server recomputes it |
| 19 | bcrypt 72-byte truncation, username enumeration by timing, in-memory lockout not stated | Byte limit, dummy-hash check, limitation written down |
| 20 | Query cache and localStorage survived logout/user switch | Clear on logout; per-user storage keys |
| 21 | Chat and unsaved story lost on navigation | Providers above the router, `sessionStorage` |
| 22 | Optimistic add could show unnormalized or duplicate words | Optimistic delete only |
| 23 | `build: ./api` cannot copy sibling `tutor_core`; volume mount alone does not work for the Langflow scanner | Root build context, pip-installable package, Langflow image built with it |
| 24 | `langflowai/langflow:latest`, Python version assumed | Exact pin; check Langflow's Python before setting `requires-python` |
| 25 | API started before Postgres was ready | Healthcheck and `service_healthy` |
| 26 | Default nginx 60 s timeout vs. up to 90 s of AI retries | 60 s total AI deadline; nginx 120 s |
| 27 | Path rewriting between nginx, Vite and FastAPI | Routes served under `/api` in FastAPI; no rewrites |
| 28 | Manual flow import and flow UUID in `.env` | `LANGFLOW_LOAD_FLOWS_PATH` and endpoint name; API-key bootstrap script |
| 29 | Langflow, Postgres and API ports all open; `admin123` default | Localhost-only binds, internal-only API and Postgres, secrets from `.env` |
| 30 | Duplicate copies of this doc at the repo root and in `docs/` | One canonical copy in `docs/` |
| 31 | "Rebuilt in CI" with no CI in the repo | `make check` |
| 32 | Playwright stubbing mechanism unspecified | `AI_MODE=stub` fakes |
| 33 | No milestone for the unverified assumptions; milestones had no exit criteria | M0 added; "done when" column added |
| 34 | `tutor_core` extraction could silently lose the unmeasured Step 10 baseline | Measure or record first; extraction as two commits (the measurement is now done: Step 10 is complete) |

## 18. Changes after the owner's Step 10 results (7 October 2026)
The remote repository moved while this design was being built (`eace656`, `3c67c80`). What changed in the plan as a result:

| Remote change | Effect here |
|---|---|
| Non-English stories 5/15 → 30/30 (es, fr, ja); 15/15 through the Agent | `stories_enabled` is now true for en, es, fr, ja; de, it, pt, zh, ko stay off until measured |
| Pass rule ≤ 5 strays (was 2) and 4–10 sentences (was 4–8) | Quality report rules updated (section 8) |
| Six new story types, 21 topic seeds, `generate_story_for_learner(..., story_type, topic)`, `describe_prompt` | Studio's `style` became `story_type` plus `topic`; `stories.style` became `story_type` and `topic` |
| Variety measured: not all targets met (strays, one word in 100% of stories) | Documented as a known tension; focus-word sampling to be adopted from the test plan |
| `sample_data/suggested_words.csv` (50 words, same CSV format) | Usable through CSV upload; the seed script loads it into the demo account |
| Step 10 closed, "Step 11 is next" | Web app delivers Step 11 for the production path (section 1) |
| Diary: no style input on the tool; no-language requests inconsistent | Open item for M5 (risk 9) |
| Patch files and caches are no longer tracked; `.gitignore` added | `.gitignore` merged with the web app's rules |
