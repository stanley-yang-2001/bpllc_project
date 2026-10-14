# Language Tutor: how the site works, and how Chat and Studio will connect to Langflow

Prepared from the repository as of 7 October 2026, after the owner's Step 10 results (commit `3c67c80`) and the web app patches 0014 to 0018. Anything marked **Built** is implemented and tested. **Planned** means designed but not written yet. Where something depends on behaviour nobody has tested yet, the text says so.

> This file is the maintained copy. A Claude Doc snapshot of the same text was made on 7 October 2026; if the two differ, this file wins. The full design is in [WEB-APP-DESIGN.md](WEB-APP-DESIGN.md); this document is the shorter, plainer map of how the pieces fit.

## 1. Summary

Language Tutor is a local web app for learning vocabulary. A learner signs up with a name and an email, keeps a separate word list for each language they study, and (soon) talks to an AI tutor and generates short stories written from their own words.

The one idea that shapes the whole design: **the AI chooses what to do, but code decides what the learner sees and whose data is touched.** The model never picks a user, never writes to the database directly, and its words are never trusted to be the final answer.

| Area | Status | Where it lives |
|---|---|---|
| Accounts, sign-up with consent, sessions, privacy policy | **Built** | API `auth` and `me` routes; Login, Privacy and Settings pages |
| Vocabulary: per language, search, edit, delete, CSV upload | **Built** | API `words` routes; Vocabulary page |
| Settings: profile, email, password, light/dark theme, data download, account deletion | **Built** | API `me` routes; Settings page |
| Keeping users apart (sessions, headers, cache rules, tests) | **Built** | API and React app; 8 layers listed in section 2.5 |
| Chat with the AI tutor | **Planned** (milestone M5) | Langflow flow plus `POST /api/chat` |
| Story Studio with a quality report | **Planned** (M6) | shared `tutor_core` plus `POST /api/stories/generate` |
| Library and Practice | **Planned** (M7) | `stories` table and practice routes |
| The Langflow flow (one shared learner) | **Built, must change** | `custom_components/`, `docs/AGENT-INSTRUCTIONS.md` |

**Not yet verified anywhere:** the Docker builds and the compose file have never been run, and no one has tested whether Langflow can pass a per-request user id to its tools (the first task in milestone M0, section 11).

## 2. What the site does today

### 2.1 Pages

| Route | What a learner can do | Status |
|---|---|---|
| `/login` | Log in with email and password, or create an account (name, email, password, first language, privacy checkbox). Light/dark switch. | Built |
| `/privacy` | Read the privacy policy. Public, no login needed. | Built |
| `/` Home | See the word count for the active language and shortcuts. | Built |
| `/vocabulary` | Add, search, edit meanings, delete several, upload a CSV, start another language. | Built |
| `/settings` | Edit name, native language, email, password; choose Light/Dark/System; download or delete all data; log out everywhere; see service status. | Built |
| `/chat`, `/studio`, `/library`, `/practice` | Show a “not built yet” page naming the milestone. | Placeholders |

### 2.2 Accounts and privacy

- Sign-up asks for exactly a **name, an email and a password**, plus the first language and a required checkbox for the privacy policy. The email is the login. The server stores the time and the version of the policy that was accepted.
- A login creates a **server-side session**. Logging out, “Log out everywhere”, changing the password (other devices only) and deleting the account all end sessions immediately.
- Changing the email or password, and deleting the account, ask for the current password again. Wrong guesses count toward the same lockout as logging in (5 failures in 15 minutes).
- **Download my data** returns one JSON file with everything held about the learner. **Delete account** permanently removes the account and every row that belongs to it.
- The privacy policy page states what is kept (name, email, password hash, words, languages, sign-in records, proof of consent) and what is not. Design section 12B maps every sentence of it to the code and test that keep it true.

### 2.3 Vocabulary

- One list **per language**. Nine languages are supported (English, Spanish, French, German, Italian, Portuguese, Japanese, Chinese, Korean), stored as two-letter codes so “Spanish”, “español” and “ES” can never create three lists.
- One rule cleans and checks every word, whether typed, uploaded or (later) added by the Agent: lowercase (German keeps capitals), at most 40 characters and 5 words, letters, apostrophes, hyphens and spaces only. Duplicates are refused, not stored twice.
- CSV upload: UTF-8, up to 1 MB and 5,000 rows, a `word` column and an optional `meaning` or `definition` column. The result shows how many were added, duplicates and invalid rows with the reason. The repository’s `sample_data/suggested_words.csv` (50 verbs, nouns and adjectives, the owner’s remedy for samey stories) uploads as it is, and the demo seed loads it.
- Search matches the word or its meaning. Lists are paged (50 per page).

### 2.4 Look and feel

Indigo and slate palette, Inter font, a two-row header, dark mode that follows the device or an explicit choice (with no white flash on load), styled dialogs that focus Cancel first, short confirmation toasts, and an accessibility scan of every screen in both themes. [STYLE-GUIDE.md](STYLE-GUIDE.md) has the details and the honest list of what is not done.

### 2.5 Keeping users apart

Each layer has its own test, and none relies on another.

1. Every database query is filtered by the logged-in user; other people’s ids answer “not found”.
2. A test fails if any route is added without a login check.
3. Sessions are rows in the database, so a copied cookie dies when the owner logs out.
4. Every API response is marked “do not cache”.
5. Each request carries the id of the user the tab is showing (`X-Expected-User`). If another person logged in on a second tab, the old tab is refused instead of quietly acting as the new person.
6. Tabs tell each other about logins and logouts; cached data is keyed by user and wiped on logout, user change or any “not logged in” answer.
7. A page restored by the browser’s Back button after logout reloads instead of showing old data.
8. A strict Content-Security-Policy (no inline scripts) and clickjacking protection.

## 3. How the site talks to the backend

### 3.1 The pieces

```
 Browser (React app)
    |  same origin, JSON, cookie
    v
 nginx  (web container)  serves the built app, forwards /api/* unchanged
    |
    v
 FastAPI (api container) ------> Postgres, schema "tutor"        BUILT
    |
    +--> tutor_core (shared Python) ------> Groq                  PLANNED (Studio)
    |
    +--> Langflow flow "language-tutor" --> Groq                  PLANNED (Chat)
              \__ its tools use tutor_core ----> Postgres
```

The browser only ever talks to nginx. It never sees a Groq or Langflow key, and it cannot reach Postgres or Langflow. Postgres and the API are not published to the host; Langflow is published on `127.0.0.1` only (checked against `docker-compose.yml`).

### 3.2 Rules every request follows

| Rule | Detail |
|---|---|
| One origin, one prefix | Everything is under `/api`. nginx and the dev server forward paths unchanged, so there is no rewrite rule to get wrong. |
| Login | An httpOnly cookie `tutor_session` (SameSite=Lax, up to 8 hours) that points at a session row. |
| Writes | Every non-GET request must carry `X-Requested-With: tutor` (and a matching `Origin`, if the browser sends one), or it is refused with 403. |
| Who is asking | After login, every request also carries `X-Expected-User: <id>`. A mismatch returns 401 `session_changed`. Login, register, logout, `/me` and `/meta` skip it. |
| Not cacheable | Every response, errors included, has `Cache-Control: no-store` and `Vary: Cookie`. |
| Errors | Always `{ "error": { "code", "message", "retry_after"?, "details"? } }`. |
| Timeouts | nginx waits up to 120 seconds, which is above the longest planned AI wait. |

### 3.3 The endpoints

| Group | Endpoints (all under `/api`) |
|---|---|
| Sessions | `POST /auth/register`, `/auth/login`, `/auth/logout`, `/auth/logout-all` |
| Account | `GET /me`, `PATCH /me`, `POST /me/email`, `/me/password`, `/me/delete`, `/me/languages`, `GET /me/export` |
| Public | `GET /languages`, `GET /meta` (policy version and the operator’s contact), `GET /health/live` |
| Vocabulary | `GET /words?language=&q=&limit=&offset=`, `POST /words`, `PATCH /words/{id}`, `POST /words/delete`, `POST /words/upload` |
| Status | `GET /health` (login required: Postgres now; Langflow and Groq later) |
| **Planned** | `POST /chat`, `POST /stories/generate`, `GET /stories`, `POST /stories`, `GET` and `DELETE /stories/{id}`, `GET /practice/flashcards`, `GET /practice/cloze` |

The TypeScript types the React app uses are generated from the API’s own OpenAPI description (`npm run gen:api`), and `make check` fails if they are out of date.

### 3.4 Error codes

In use today: `validation_error` (422), `unauthorized` (401), `session_changed` (401), `login_failed` (401), `login_locked` (429, with `retry_after`), `wrong_password` (403), `forbidden` (403), `not_found` (404), `conflict` (409), `internal_error` (500).

Planned for the AI features: `tutor_busy` (429, the shared Groq limit or too many requests at once), `not_enough_words` (422), `language_unavailable` (422), `langflow_unavailable` (503), `ai_failed` (502), `chat_cleanup_failed` (503, account deletion could not confirm the learner's stored chat was removed, so nothing is deleted). Section 9 says what the learner sees for each.

### 3.5 Inside the React app

- **API client** (`src/api/client.ts`): one small function wraps `fetch`, adds the headers above, and turns any error body into an `ApiError` with a code, a message and an optional retry time.
- **Providers**, outermost first: theme, query cache, auth, router. Inside the logged-in area, and re-created for each user: active language, toasts, confirm dialogs.
- **Server data** lives in TanStack Query. Every per-learner key includes the user id, for example `["words", userId, language, search, offset]`.
- **Auth** (`AuthContext`) holds the profile, handles logout, “log out everywhere” and account deletion, and reacts to a 401 from anywhere by emptying the cache and asking the server who is really logged in.
- **Forms** use React Hook Form with Zod rules that mirror the server’s rules. The server stays the authority.

### 3.6 Worked example: adding a word

```
1. Learner types "Agua." with meaning "water" and presses Add word
2. Browser -> API   POST /api/words
                    headers: X-Requested-With, X-Expected-User, cookie
                    body:    {"language":"es","word":"Agua.","meaning":"water"}
3. API checks the session and user, cleans the word ("agua"), inserts it
   for THIS user only, and records that the user studies Spanish
4. API -> Browser   201 {"id":..,"language":"es","word":"agua","meaning":"water",...}
5. Browser shows a toast, clears the form, and refreshes the word list.
   (A duplicate would be 409 "conflict", shown next to the field.)
```

The add is deliberately not optimistic: the server may change the spelling or refuse it, so the screen waits for the answer. Deleting words is optimistic and rolls back if the server fails.

## 4. What already exists on the Langflow side

### 4.1 The flow today

```
 Chat Input -> Agent (gpt-oss-120b on Groq) -> Tool Result Relay -> Chat Output
                  |  decides which tool to call
                  +-- Add Word               saves one word
                  +-- Story Generator Tool   writes a story from the saved words
```

The Agent’s instructions ([AGENT-INSTRUCTIONS.md](AGENT-INSTRUCTIONS.md)) tell it: call Add Word with just the word; call the story tool with the language named in the learner’s *latest* message; after a tool call, repeat the tool’s output exactly; otherwise answer briefly.

### 4.2 The parts

| Part | What it does |
|---|---|
| **Add Word** (`add_word.py`) | One input, `word`, filled in by the Agent. Cleans the word and inserts it into the single global `words` table (`ON CONFLICT DO NOTHING`). Returns a short result message. |
| **Story Generator Tool** (`story_tool.py`) | One input, `language`, filled in by the Agent. Loads every saved word, builds a prompt for one of **eight story types** (narration, dialogue, story, diary, letter, place, routine, anecdote), picked at random with a weighted mix, plus a topic seed from 21 topics that never repeats the last 8; calls Groq directly (30 seconds per attempt, with retries), removes the model’s planning text, and returns the passage. Keeps an in-memory cache (20 seconds for a success, 15 for a failure) keyed by language (an explicitly requested type or topic is cached separately). On failure returns a fixed apology message. |
| **Tool Result Relay** (`tool_result_relay.py`) | Replaces the Agent’s reply with the tool’s own output, character for character. Added because an LLM writing the final reply sometimes shortened or reworded the story. If no tool ran, the Agent’s text passes through. |
| Step 8 components (`word_loader`, `story_prompt_builder`, `story_guard`, `final_passage_extractor`, `groq_language_model`) | The earlier canvas-only pipeline, kept as learning material. The Agent flow above is the production path. |

**Measured (Step 10, complete):** the final run through the Agent passed 43 of 45 turns (right tool 42/42, right argument 36/36, exact relay 36/36). Non-English stories went from 5/15 to **30/30 in the requested language** (Spanish, French, Japanese, 10 each) after the language-aware prompt change, and 15/15 through the Agent. English stories pass their quality check 41 times out of 48 (85%). The pass rule is now at most 5 stray words and 4 to 10 sentences. **Still being tuned:** the owner added six story types for variety (overlap fell from 0.44 to 0.24), but the new types use more words outside the learner’s list (29% against 3% for the classic styles) and one vocabulary word still appears in every story. The next planned steps are the larger word list and a few focus words per story. This is why Studio enables a language only after it has been measured (section 8). Details: [STEP-10-TEST-PLAN.md](STEP-10-TEST-PLAN.md).

### 4.3 Why it cannot be used for the website as it is

- There is **one** `words` table and no idea who is asking, so every learner would share one vocabulary.
- The story cache is keyed by language only, so one learner could be served a story built from another learner’s words.
- Both tools import Langflow at the top of the file, so the web API cannot reuse their logic.
- Database passwords and the model name are hard-coded inside the components.
- The Agent instructions say “any language name is valid”, which would create stray language lists.
- The flow itself is not saved in the repository yet; it exists only on someone’s Langflow canvas.

## 5. Chat and Studio: two roads to the AI

The site will reach the AI in two different ways on purpose.

| | **Chat** (the Agent road) | **Studio** (the direct road) |
|---|---|---|
| Entry point | `POST /api/chat` | `POST /api/stories/generate` |
| Who decides what happens | The Agent, an LLM, picks a tool from free text | The learner picks language and style on a form; code runs it |
| Runs in | The Langflow flow | The API process, using shared `tutor_core` code |
| Controls offered | Whatever the tools expose: language only (a request for a “dialogue” is not honored today) | Language, story type (one of eight, or a random mix), topic, and Regenerate (never cached) |
| What comes back | The tool’s exact text plus a trace of which tool ran | The story, the style actually used, and a quality report |
| Model calls | Two (Agent, then story) | One |
| Typical failure | The Agent picks the wrong tool or refuses | Rate limit or Groq error; no guessing involved |
| Why it exists | It is the course’s Langflow agent-and-tools objective, and natural language is friendly | It is reliable, controllable and measurable |

They must behave the same for the same input: the same words, the same prompt rules, the same language gate, the same word checks. That is why they share code (next section).

## 6. How the two roads connect

### 6.1 One shared Python package

`tutor_core` is a small, framework-free package (no Langflow and no FastAPI inside). It will hold language codes, the word rule, the prompt templates, the Groq call, story generation and the quality checks. It is **installed into both containers**: the API image and a Langflow image built on a pinned Langflow version. The Langflow components shrink to thin wrappers that call it. Two parts of it exist today (languages and the word rule, 32 tests); the rest arrives in milestone M3, done as a pure move first, then the changes, and it now includes the story types, topics and variety logic added in Step 10.

### 6.2 One database

Both roads read and write the same tables in the `tutor` schema of the existing Postgres database, always filtered by the learner. A word added through Chat appears on the Vocabulary page, and a story generated in Studio uses exactly the words the Vocabulary page shows. Credentials come from environment variables, not from the code.

### 6.3 Knowing who is asking (the part to verify first)

Langflow must tell its tools which learner is asking, and the model must not be able to change that.

- **Plan A (preferred).** Add two hidden inputs, `user_id` and `language`, to Add Word and to the story tool, marked so the Agent cannot see or set them. For each request the API fills them in through Langflow’s per-request `tweaks`. Langflow’s documentation confirms tweaks are one-time overrides keyed by component id or name, and that recent versions can restrict tweaks to fields declared for API use. **How this behaves with this project’s Agent and tools is untested.**
- **Plan B (fallback).** Build the session id as `u<user id>-<random>` and have the tools read it from the running flow. The language would then have to come from the Agent.
- **Either way the tools fail closed.** With no user id they return an error and touch no data; they never fall back to a shared list. A developer-only setting lets the Playground and the old test scripts keep working.
- **Plan A passes only if** a parallel test with two different users at once shows each tool call saw its own user. A single user working proves nothing.

### 6.4 Wiring

- **Flow file.** The flow is exported to `flows/language-tutor.json` and loaded by Langflow at startup (`LANGFLOW_LOAD_FLOWS_PATH`), so no one imports it by hand. The API runs it by its **name**, `language-tutor`, because an id changes whenever a flow is re-imported (to be confirmed in M0).
- **API key.** The API needs a Langflow API key. A bootstrap script logs in as the Langflow admin, creates one, and prints it for `.env`. The code to do this already exists in `scripts/run_routing_tests.py`.
- **Environment.** The API gets `LANGFLOW_URL`, `LANGFLOW_FLOW`, `LANGFLOW_API_KEY`, `GROQ_API_KEY`, `DATABASE_URL`, `AI_MODE` (`live` or `stub`) and `MAX_PROMPT_WORDS`. Langflow gets `DATABASE_URL` and `GROQ_API_KEY`. Section 14 lists them.
- **Network.** Only the API may call Langflow. Because the tools trust the `user_id` they are given, anyone who can reach Langflow’s API could read any learner’s words, so Langflow stays bound to localhost.

### 6.5 What never goes to the AI

The learner’s **name and email are never put in a prompt, a tweak or a session id**. Langflow only ever receives a numeric user id, the learner’s own words, and the message they typed. The privacy policy promises exactly this, and it is not yet testable because the AI features do not exist: milestones M5 and M6 must add a test that builds every prompt for a user with a recognisable name and email and fails if either appears.

## 7. Chat in detail (planned)

### 7.1 What the learner sees

- A conversation box. The learner types in plain language: “add the word bread”, “tell me a story in Spanish”, “hi”.
- Under each tutor reply, a small expandable line saying which tool ran and with what argument.
- After a story, a **Save to library** button. After a word is added, the Vocabulary page refreshes itself.
- A note such as “Adding words to: Spanish”, because Add Word always uses the active language.
- The conversation survives moving between pages (held above the router and mirrored to session storage), is wiped on logout or when the user changes, and a **New session** button starts a fresh session id.

### 7.2 The contract: `POST /api/chat`

Request: `{ "message": "tell me a story in Spanish", "session_id": "<32 hex characters>", "language": "es" }`. The message is 1 to 2,000 characters, the session id is random and made by the browser, and the language is the active language code.

Response 200:

```
{ "reply": "<the tool's exact output, or the Agent's short answer>",
  "tool_calls": [ { "name": "Story Generator Tool",
                    "args": { "language": "Spanish" },
                    "output": "<the story>" } ],
  "session_id": "<same 32 hex characters>" }
```

### 7.3 One turn, step by step

```
1. Browser  -> API       POST /api/chat {message, session_id, language}
2. API      -> API       check login and X-Expected-User; take this user's lock
                         and one slot in the AI gate (section 9)
3. API      -> Langflow  POST /api/v1/run/language-tutor  (hidden user_id, language)
4. Langflow -> Groq      the Agent decides: Add Word, Story Generator, or no tool
5. Tool     -> Postgres  Add Word: insert into tutor.words for THIS user only
   Tool     -> Groq      Story: one call, built from THIS user's words
6. Relay    -> API       the reply becomes the tool's exact output
7. API      -> Browser   {reply, tool_calls, session_id}
8. Browser               shows the reply and the trace; if Add Word ran,
                         refreshes the word list
```

### 7.4 What the API sends to Langflow

```
POST {LANGFLOW_URL}/api/v1/run/language-tutor?stream=false
x-api-key: <LANGFLOW_API_KEY>
{ "input_value": "<the message>", "input_type": "chat", "output_type": "chat",
  "session_id": "u17-<32 hex characters>",
  "tweaks": { "<Add Word component>":      { "user_id": 17, "language": "es" },
              "<Story Generator component>": { "user_id": 17, "language": "es" } } }
```

This is the call shape the Step 10 test runner already uses, plus the tweaks. The server builds the session id itself (the browser only supplies the random part), so one learner can never address another learner’s session. Whether the component keys are names or ids, and whether tweaks reach the tools at all, is settled in M0. The payload never contains a name or email.

### 7.5 Reading Langflow’s answer

- **The reply** is the chat message text in the response, which is the Relay’s output.
- **The tool trace** comes from the tool blocks inside that message (`type: tool_use`, with name, input and output). If they are missing, the API asks Langflow for the stored messages of the session (`GET /api/v1/monitor/messages?session_id=...`). The repository already solves this against the real response shape in `scripts/routing_checks.py` (`find_tool_calls`, `with_tool_blocks`); the API will port that code. Its tests must use a **captured real response** as the fixture, because an earlier test built from assumptions passed while the real shape failed.
- A tool failure arrives as ordinary text (the fixed apology message) and is passed through; the matching `tool_calls` entry is flagged.

### 7.6 Which language each tool uses

| The learner says | Tool | Language used |
|---|---|---|
| “add the word bread” | Add Word | Always the **active** language (a hidden input the Agent cannot change). The reply names it: “Added ‘bread’ to your Spanish vocabulary”, so a mix-up is visible at once. |
| “story in French” while Spanish is active | Story Generator | French, the Agent’s argument, using the learner’s French list. If that list is empty, the “not enough words” message. |
| “tell me a story” with no language | Story Generator | Today the Agent sometimes asks and sometimes defaults to English (Step 10 notes). The hidden active language becomes the default, and routing case I1 must be re-run in M5 to confirm the Agent behaves. |
| A language the app does not support | Either | A message listing the supported languages. No new list is created. |
| A language whose stories are not enabled yet | Story Generator | “Stories in X are not available yet”, the same gate as Studio. |

### 7.7 Saving a story from Chat

The browser sends the story text back with `POST /api/stories` (language and body; style is unknown, so stored as empty). **The server computes the quality report itself** and never accepts one from the client.

### 7.8 Changes the flow needs

- Add the hidden `user_id` and `language` inputs and make both tools fail closed; move the logic into `tutor_core`.
- Change the Agent line “any language name is valid” to “use the language the learner names; the tool will say if it is unsupported”, and update `docs/AGENT-INSTRUCTIONS.md` at the same time.
- Keep the Tool Result Relay unchanged: it is what makes the reply trustworthy.
- Export the flow to `flows/language-tutor.json` and pin Langflow to an exact version instead of `latest`.

### 7.9 New front-end pieces

`routes/Chat.tsx`, `ChatPanel`, `ToolTrace`, and a `ChatProvider` above the router that stores messages under a per-user session-storage key. After each turn it refreshes the word list if Add Word ran, disables Send for the `retry_after` seconds when it gets `tutor_busy`, and treats a 401 like every other page (empty the cache, ask who is logged in).

## 8. Studio in detail (planned)

### 8.1 What the learner sees

- A small form: language (only enabled languages can be chosen; the rest are greyed out and marked “not available yet”), story type (a random mix, or one of the eight), an optional topic, and **Generate**.
- The story, and next to it a **quality report**: language check, length and format, words outside your list, and read time. Buttons: Save, Regenerate, and later Practice this story.
- With fewer than 5 words in that language, a friendly message that links to Vocabulary. No AI call is made.
- An unsaved story is kept while moving between pages and cleared on logout or when the language changes.

### 8.2 The contract: `POST /api/stories/generate`

Request: `{ "language": "es", "story_type": "diary", "topic": "a rainy day" }`. Both `story_type` (`narration`, `dialogue`, `story`, `diary`, `letter`, `place`, `routine`, `anecdote`) and `topic` are optional: leave them out and the code picks a type from the weighted mix and a topic that avoids the last 8. Response: `{ "body": "...", "story_type": "diary", "topic": "a rainy day", "language": "es", "report": { ... } }`.

```
1. Is the language known, and are stories enabled for it?   else language_unavailable
2. Load THIS learner's words for that language.            fewer than 5: not_enough_words
3. Take at most 150 of them (MAX_PROMPT_WORDS) for the prompt. A long list would
   exceed Groq's free token budget. The quality check still uses the FULL list.
4. Build the prompt for the chosen type and topic. The words are presented as quoted data, never as instructions.
5. Call Groq with a 60-second total deadline; remove the model's planning text.
6. Run the quality check.
7. Return the result. Nothing is cached, and nothing is saved until the learner saves it.
```

Step 4 matters: the word rule stops line breaks, symbols and long text, but a short letters-only phrase like “ignore previous rules” is still a legal entry, so the prompt builder itself must treat the list as data.

### 8.3 One generation, step by step

```
1. Browser -> API       POST /api/stories/generate {language, story_type?, topic?}
2. API      -> Postgres load this user's words (tutor.words)
3. API      -> Groq     one call through tutor_core, 60 s total deadline
4. API                  strip the plan, score the passage (tutor_core quality check)
5. API      -> Browser  {body, story_type, topic, language, report}
6. Learner clicks Save: POST /api/stories {language, story_type, topic, body}; the server
   scores it again and stores it. Regenerate repeats steps 1-5 with a new story.
```

### 8.4 The quality report

What can be checked depends on the language, and the report says which mode it used instead of implying every check ran.

| Check | English | Other Latin-script languages | Japanese, Chinese, Korean |
|---|---|---|---|
| Written in the requested language | Yes | Yes | Yes (by script) |
| Length 4 to 10 sentences or lines, dialogue format (conversations only), no leaked plan | Yes | Yes | Yes |
| Words outside your list | **Strict**: at most 5 strays to pass | **Informational**: listed, not scored (no grammar-word list exists yet, so articles would count as strays) | Not available |

Shape: `{ rules_version, status, language, structure, vocabulary: { mode, outside, limit }, read_seconds }`. A story passes when the language is right, the structure is right, no plan leaked and, for English only, there are at most 5 strays. Studio shows the report honestly, including when the newer story types fail the stray-word rule (see the tuning note in section 4.2).

### 8.5 When other languages open up

Each language has a “stories enabled” flag that is switched on only after a measured batch reaches 90% in the requested language (Step 10, criterion 5). Today English, Spanish, French and Japanese are on (Step 10 measured 30/30 for the three non-English languages); German, Italian, Portuguese, Chinese and Korean are off until a batch of their own is measured. The gate lives in `tutor_core`, so Chat obeys it too. A setting (`STORY_ALLOW_UNMEASURED=1`) lets the measurement scripts bypass it.

### 8.6 Library and Practice (M7)

Library stores saved stories (list, read, delete). Practice has flashcards from the word list and fill-in-the-blank exercises built by code from a saved story, with no AI. Practice results are not stored.

## 9. Rules shared by Chat and Studio

- **AI gate.** Every call that reaches Groq, direct or through Langflow, passes through one gate: at most 2 at a time (waiting up to 5 seconds), plus one AI request per user at a time so a double click or a second tab cannot spend the limit twice. The API runs a single worker, for the same reason the login lockout does.
- **Deadlines.** Groq 60 seconds in total, the Langflow call 100 seconds, nginx 120 seconds. The screen says “this is taking longer than usual” after 20 seconds. Nothing is retried automatically.
- **Login.** Both routes need a login and the expected-user header like every other route, and the automatic “every route needs login” test covers them the moment they exist.
- **Test mode.** `AI_MODE=stub` returns fixed replies instead of calling Groq or Langflow. Unit tests, browser tests and offline demos use it.
- **Logging.** One request id per request; never passwords, tokens or keys; story text only at debug level.

What the learner sees when something goes wrong:

| Code | When | What the learner sees |
|---|---|---|
| `tutor_busy` (429) | Groq rate limit, or the gate is full | “The tutor is busy. Try again in a moment.” AI buttons are disabled for `retry_after` seconds. |
| `not_enough_words` (422) | Fewer than 5 words in that language | The counts, and a link to Vocabulary. |
| `language_unavailable` (422) | Stories not enabled for that language | “Stories in X are not available yet.” Vocabulary still works. |
| `langflow_unavailable` (503) | Langflow cannot be reached | A banner on Chat only. Every other page, including Studio, keeps working. |
| `ai_failed` (502) | Groq error or empty output | “Couldn’t write a story right now.” Regenerate is offered. |

## 10. Data model additions

- **`stories`** (migration 0006, with M6; 0004 is `chat_sessions`, 0005 is `password_salt`): id, user id (deleted with the user), language, story type and topic (both empty for stories saved from Chat, where they are unknown), body, passed, report as JSON, created time.
- **Export and deletion stay honest automatically.** Two existing guard tests fail as soon as a table with a `user_id` exists that is missing from “Download my data”, or whose rows survive account deletion. Adding `stories` therefore forces it into both.
- **Words:** the tools move from the old global table to `tutor.words`. The old table is left as a backup and can be imported into a demo account with the seed script.
- **Chat history is a gap to close.** Langflow itself stores the messages of every session in its own database tables, under the session ids `u<user id>-...`. **Closed in code on 15 October 2026 (not yet run against the real Langflow):** the `chat_sessions` table, deletion before the user row, and the reworded policy. Original gap, kept for the record: our delete-account button did not remove those, and the privacy policy did not mention them. Before Chat ships, either deleting an account must also delete that user’s Langflow sessions (the API can list them by the id prefix, or record each session id in a small `chat_sessions` table so the same guard tests cover it), “Download my data” must include or explain them, and the policy text and version must change. This is an acceptance item for M5, not an afterthought. **Probe result (14 October 2026):** Langflow keeps both sides of each turn and the tool call per session; `GET /api/v1/monitor/messages/sessions` lists sessions (filtering by prefix worked); `DELETE /api/v1/monitor/messages/session/<session id>` removed a session's messages (2 before, 0 after, re-read). Not yet checked: any other place Langflow keeps run data (its build and transaction logs).

## 11. Rollout plan

| Step | What happens | Done when |
|---|---|---|
| **M0 Verify** | Pin Langflow and check its Python version. Export the flow to `flows/` and run it by name. **Tweaks spike:** hidden inputs reach both tools, proved with two users running in parallel. Capture a real run response and a stored-messages response as fixtures. Find out what Langflow stores for chat and how to delete it. Step 10 is complete, so no measurement is outstanding. | `scripts/spike_tweaks.py` passes; fixtures are committed; Plan A or Plan B is chosen and written down. |
| **M3 Extract** | Move the pure logic into `tutor_core` in two commits: first a pure move with only import paths changed, then the behaviour changes (language codes, word rule, cache key by user, word cap, story type and topic returned). The new Step 10 pieces move with the code: `choose_story_type`, `choose_topic`, `describe_prompt`, the eight types and 21 topics, and `tests/test_story_variety.py`. Components become thin wrappers that fail closed. | Every existing test passes unchanged apart from import paths; the English prompt hashes are unchanged; a short `run_routing_tests.py` run passes on the rebuilt flow. |
| **M5 Chat** | `POST /api/chat`, the `langflow_client`, the Chat page, save-to-library. | Two users chatting at once each touch only their own words; the prompt-privacy test passes; deleting an account removes that user’s Langflow history; the policy is updated. |
| **M6 Studio** | `POST /api/stories/generate`, quality report, language gate, AI gate, `stories` table. | English stories generate with the right report; Regenerate gives a new story; other languages stay off until measured; the prompt-privacy test passes. |
| **M7 Library and Practice** | Saved stories, flashcards, fill-in-the-blank, seed data, demo script. | The browser suite passes from a clean checkout. |

M0 must come first because Chat depends on its answer. M5 and M6 can then proceed separately once M3 is done.

## 12. How it will be tested

- **Pure logic:** the existing tests move with the code; the English prompt templates stay pinned by their SHA-256 hash.
- **Langflow client:** parse the captured real response and the stored-messages fallback, and reuse the repository’s fake Langflow server (`tests/test_routing_runner_with_fake_langflow.py`) for the transport.
- **Isolation:** the parallel two-user chat test from M0 stays in the suite as a regression test; the guard tests for “every route needs login”, export coverage and deletion coverage extend themselves.
- **Privacy:** a test that builds every prompt for a user with a recognisable name and email and fails if either appears.
- **Browser:** the Playwright suite runs with `AI_MODE=stub`: sign up, add a word, chat, add a word through Chat and see it appear, generate a story, read the report, save it, delete the account.
- **Routing quality:** `scripts/run_routing_tests.py` keeps running against the new flow (a developer-only `TUTOR_DEV_USER_ID` lets it work without tweaks).
- **Needs a human and a Groq key:** the Step 10 batches that decide when each language is enabled.

## 13. Risks and open questions

| Risk or question | Why it matters | Plan |
|---|---|---|
| Langflow may not pass per-request inputs to tools in Agent mode | Chat cannot be made multi-user without it | M0 decides between Plan A and Plan B before any Chat code |
| Langflow stores chat messages | Contradicts “delete removes everything” | Section 10 acceptance item for M5; the probe shows per-session delete works through Langflow's monitor API |
| Story quality in languages not yet measured (German, Italian, Portuguese, Chinese, Korean) | Would ship stories in the wrong language | Those languages stay off until a batch reaches 90%; Spanish, French and Japanese already did |
| English variety versus vocabulary fit | The newer story types use many words the learner does not know | Owner’s next steps: larger word list, focus words per story; Studio shows the report honestly |
| One shared Groq free-tier limit | Several learners at once will hit it | The AI gate smooths bursts; the UI is built for `tutor_busy` |
| Langflow version drift | Field names and tweak rules change between versions | Pin the exact version; check everything version-specific in M0 |
| Two codebases (TypeScript and Python) | Double the surface to test | Generated API types and `make check` |
| **Open:** should Chat’s story tool also accept a story type and topic? | Studio lets the learner choose; Chat picks at random today, and “dialogue” requests are not honored | Not decided; needs a routing re-run |
| **Open:** should the API keep its own copy of chat history? | Would make export, deletion and cross-device history simple | Not decided; affects the `chat_sessions` idea in section 10 |
| **Open:** how long may Langflow keep old chat messages? | A retention promise the policy would have to state | Not decided |

## 14. Quick reference

### Settings

| Setting | Used by | State |
|---|---|---|
| `DATABASE_URL`, `JWT_SECRET`, `GROQ_API_KEY`, `AI_MODE`, `MAX_PROMPT_WORDS`, `COOKIE_SECURE`, `PRIVACY_CONTACT`, `DEMO_EMAIL`, `DEMO_PASSWORD` | API | In use today |
| `LANGFLOW_URL`, `LANGFLOW_FLOW` (`language-tutor`), `LANGFLOW_API_KEY` | API | Planned (M5) |
| `LANGFLOW_LOAD_FLOWS_PATH` | Langflow | Planned (M0) |
| `TUTOR_DEV_USER_ID` | Langflow, developer only | Planned |
| `STORY_ALLOW_UNMEASURED` | Measurement scripts only | Defined in `tutor_core` |

### Where things live

| Path | What is there |
|---|---|
| `web/src` | The React app: `api/` client and generated types, `auth/`, `theme/`, `components/`, `routes/` |
| `web/e2e` | Real-browser tests (isolation, accounts, dark mode, accessibility) |
| `api/app` | The FastAPI app: `routes/`, `services/`, `security.py`, `migrations/` |
| `tutor_core` | Shared logic; languages and the word rule so far |
| `custom_components` | The Langflow components (to become thin wrappers) |
| `scripts` | The Step 10 routing tests and helpers; `check_api_types.sh` |
| `docs/WEB-APP-DESIGN.md` | The full design, including the privacy-claim map (12B) and milestones |
| `docs/STYLE-GUIDE.md`, `docs/AGENT-INSTRUCTIONS.md`, `docs/STEP-10-TEST-PLAN.md` | Look and feel; the Agent’s instructions; the quality targets and results |
