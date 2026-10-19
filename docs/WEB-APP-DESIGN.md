# Language Tutor Web App — Design (React)

**Status:** Draft v5 · **Date:** 2026-10-10 · **Runs:** locally with Docker Compose (a demo, not hosted) · **Stack:** React + TypeScript, FastAPI, Langflow, Postgres, Groq

v5 brings the document up to the state of the repository and adds the design for three personalisation features (sections 3F and 3G, milestone M8); nothing in them is built yet. v4 was a hardening pass over v3: every change fixes something that would have produced a bug, a data leak or a dead end during the build. Section 17 lists what changed and why. Items marked **[verify in M0]** depend on Langflow behavior that has not been tested in this project yet; M0 exists to settle them before feature work starts.

**Companion document:** [SITE-AND-AI-INTEGRATION.md](SITE-AND-AI-INTEGRATION.md) is the shorter, plainer map of what the site does today, how it talks to the backend, and how Chat and Story Studio will connect to the Langflow flow. This file is the detailed design and the source for the milestones.

## Where we are (10 October 2026)
*A snapshot written on 10 October 2026. For the current state of each milestone, see section 19.*

| Area | State |
|---|---|
| Repository | The web app is in the repository (commit `1d1406d`), on top of the owner's Step 10 work (`3c67c80`). That commit lacked three files and carried one stray test-output file. A follow-up (not yet in the remote) restores `.env.example`, `.dockerignore` and `docs/SITE-AND-AI-INTEGRATION.md`, restores the executable bit of `scripts/check_api_types.sh` (without it `make check` cannot run), and stops tracking `web/test-results/`. |
| Built and tested | Milestones M1, M2 and M4; user separation and security hardening (12A); email sign-up with consent, privacy policy, Settings (profile, email, password, data download, account deletion), light/dark theme, styled dialogs. Tests today: **32** `tutor_core`, **90** API, **56** web unit, **27** real-browser (including an accessibility scan of every screen in both themes). |
| Not built | M0 (the Langflow per-user check), M3 (`tutor_core` extraction), M5 Chat, M6 Story Studio, M7 Library and Practice. Their pages are placeholders. |
| Designed, not built | Native-language display names, the site shown in the study language, themes with a custom color wheel, **display preferences stored on the account**, and a **privacy policy shown as a separate approved copy per language** (3F to 3I, M8). A first draft of the message table and the Chinese display-name change are parked on branch `wip/i18n-themes` and are in no patch. |
| Not verified | The Docker builds and compose file have never been run (the image build steps were simulated outside Docker); Langflow behaviour with per-user inputs; the 15 test scripts that run only inside the Langflow container; any browser other than Chromium. |
| Known gaps | No password recovery (the app cannot send email); no email verification; the policy has not been reviewed by a lawyer; Chat history kept by Langflow is not covered by account deletion (section 12B, and the companion document). |

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
| Interface text | a typed message table in `web/src/i18n/` (no i18n library) | nine fixed languages; a missing translation fails to compile. Planned (3F) |
| Color handling | a small color-math module and a custom color-wheel component (no color library) | built (3G, M8c) |
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
- **Passwords:** 8 to 72 **bytes** (bcrypt silently ignores everything after byte 72, so longer passwords are rejected rather than truncated). Stored only as hashes, each with its own salt (M5): the `users` row holds `password_salt` (16 random bytes, hex) beside `password_hash`, and the hash is `bcrypt(base64(SHA-256(salt bytes || password bytes)))`. bcrypt also puts its own salt inside the hash string, so there are two. The 44-byte digest means bcrypt's 72-byte cut-off no longer applies, but the 72-byte limit stays as the input rule. Accounts made before M5 have no salt (NULL), still log in with plain bcrypt, and are given a salt on their next successful login.
- **Login errors** are one generic message ("wrong username or password"). When the username does not exist, the API still runs a bcrypt check against a dummy hash so response time does not reveal which usernames exist.
- **Failed-login limit:** 5 failures per username in 15 minutes returns `login_locked` with `retry_after`. The counter lives in API memory (single uvicorn worker, resets on restart); that is acceptable for a local demo and is stated so nobody assumes it survives a restart.
- **Sessions are server-side and revocable.** Each login inserts a row in `tutor.sessions` and the JWT carries its id (`jti`). A token is honoured only while that row exists, belongs to the user named in the token, and has not expired. Logout deletes the row, so a copied cookie stops working immediately; `POST /auth/logout-all` deletes every row of the user ("Log out everywhere"); logging in over an existing session revokes the old one; deleting a user cascades. (v3/v4 only deleted the browser cookie on logout, leaving the token valid for 8 hours.)
- **Token:** JWT with `sub` = user id, `jti` = session id and a short expiry (8 hours), no refresh; expiry sends the learner to `/login`. The API refuses to start if `JWT_SECRET` is missing, shorter than 32 characters or equal to a known placeholder.
- **Cookie:** httpOnly, `SameSite=Lax`, `Secure` off for local http (a setting, on by default outside local).
- The API reads `user_id` from the verified token, never from the request body; services take it as an argument.
- React keeps only the user profile in an auth context. **On logout or user change the TanStack Query cache is cleared and per-user state is dropped**, otherwise the next person on the same browser would briefly see the previous learner's words.

## 3C. Languages
Free-text language names create junk (`"Spanish"`, `"español"`, `"spanish "` as three lists). Languages are therefore a fixed list in `tutor_core/languages.py`, stored and exchanged as **ISO 639-1 codes**:

| code | name | native name (as in the code today) | tier | stories enabled |
|---|---|---|---|---|
| en | English | English | 1 | yes |
| es | Spanish | Español | 1 | yes (measured, Step 10) |
| fr | French | Français | 1 | yes (measured, Step 10) |
| de | German | Deutsch | 1 | not until measured |
| it | Italian | Italiano | 1 | not until measured |
| pt | Portuguese | Português | 1 | not until measured |
| ja | Japanese | 日本語 | 2 | yes (measured, Step 10) |
| zh | Chinese | 中文 | 2 | not until measured |
| ko | Korean | 한국어 | 2 | not until measured |

The native name is what the site is meant to show wherever a language is picked or named. Changed in M8a (3F): `zh` is now “Chinese (Simplified)” with the native name **中文简体**, and the old names keep resolving to `zh`.

- **Tier 1** = space-delimited with a `simplemma` lemmatizer. **Tier 2** = needs an optional tokenizer; vocabulary checks and cloze practice stay off until the extra installs and is tested.
- **`stories enabled` is a measured flag, not a hope.** A language is switched on only after its in-language rate reaches the Step 10 criterion 5 (≥ 90%). Step 10 measured **Spanish, French and Japanese at 30/30** in the requested language (10 stories each, structure also 30/30, the samples read as natural) and 15/15 non-English turns through the Agent, after tuning change #1 (it had been 5/15). Those three are enabled. German, Italian, Portuguese, Chinese and Korean have not been measured and stay off until a batch of their own reaches the bar. Japanese is enabled even though its vocabulary check is unavailable (Tier 2): the language and structure checks still run. The gate lives in `tutor_core.story.generate`, so Story Studio and the chat tool obey it equally. Vocabulary management works for every listed language regardless. `STORY_ALLOW_UNMEASURED=1` bypasses the gate for the measurement scripts.
- `normalize_language(text)` maps any name or native name to a code (the existing `_NATIVE_LANGUAGE_NAMES` table moves here). An unknown language returns a clear message that lists the supported ones; it never creates a new partition. The Agent instructions change accordingly (see 3D).

## 3D. Passing the learner to Langflow tools
Today's components read one global `words` table. For the web app, `user_id` and the active `language` must arrive per request, and the model must never be able to choose or change them.

**Plan A (verified in M0).** Add two hidden inputs, `learner_id` and `active_language` (`active_language`, not `language`, because the story tool already has a visible `language` argument that the Agent fills in; the name `user_id` is reserved by Langflow: every component has a read-only `user_id` property returning the Langflow *account's* UUID, which silently shadows an input of that name; found by the first M0 spike run; send the id as a **string**, because Langflow's text-field handling silently drops any value that is not a string, list or Data object, so an integer `learner_id` never arrived while the string `language` did (second run), and the tool converts it back with `int()` and refuses anything else), to Add Word and to Story Generator Tool, with `tool_mode=False` so the Agent does not see them. The API sets them per run through Langflow `tweaks`, which are keyed by component ID or component name. Langflow's docs confirm tweaks are one-time per-request overrides.
- Key tweaks by the component's **name**, not an auto-generated ID that changes if the flow is re-imported; confirm name keys work in the pinned version.
- Recent Langflow versions (the 1.12.x docs) offer `LANGFLOW_TWEAKS_POLICY` (`permissive` by default, `declared` accepts only fields marked "API" on the canvas). If the pinned version has it, use `declared` and mark exactly these fields; otherwise stay permissive and rely on the network rules in section 3.
- **Fail closed.** If `learner_id` is missing, the tools return an error message and touch no data. They must never fall back to a shared list. A dev fallback exists only when `TUTOR_DEV_USER_ID` is set in the Langflow container, so the Playground and `run_routing_tests.py` keep working during development.
- **Which language each tool uses.** Add Word always stores into the active language (the hidden `active_language` input); the reply names the language ("Added 'bread' to your Spanish vocabulary") so a mix-up is visible immediately. The story tool keeps its Agent-supplied `language` argument (the learner may say "story in French" while Spanish is active); the hidden `language` input is only its default when the message names none.
- **Concurrency check.** The spike must run parallel requests for different users against the same flow and prove each tool call saw its own `learner_id`. Sequential success does not prove isolation.

**Plan B (fallback).** Build `session_id` as `u{user_id}-{uuid}` and have the tools read it from the running graph (`self.graph.session_id`, **verify**). Add Word then needs the language as an Agent argument. Use B only if A fails the concurrency check; the decision and the evidence get written into the changelog.

**Chat sessions.** The client sends only a random 32-hex id; the server builds `u{user_id}-{id}` itself, so one learner cannot address another learner's session.

**Agent instructions.** `docs/AGENT-INSTRUCTIONS.md` currently says "any language name is valid". For the web app change that line to "use the language the learner names; the tool will say if it is not supported", and update the file when the canvas changes.

## 3E. API surface
All routes live under `/api` inside FastAPI itself (an `APIRouter(prefix="/api")`), so nginx and the Vite dev proxy forward paths unchanged and there is no rewrite rule to get wrong. Non-GET requests must carry `X-Requested-With: tutor` (CSRF defence) and an `Origin` matching the app. Requests from the page also carry `X-Expected-User` (section 12A); a mismatch returns `401 session_changed`.

| Method and path | Purpose |
|---|---|
| `POST /auth/register`, `/auth/login`, `/auth/logout`, `/auth/logout-all`; `GET /me` | accounts and sessions (`logout-all` ends every device) |
| `PATCH /me`; `POST /me/email`, `/me/password`, `/me/delete`; `GET /me/export` | edit name and language; change email or password (current password required, wrong guesses share the login lockout); permanently delete the account (password required); download everything held about you |
| `PATCH /me/preferences` (3H) | change the display preferences (theme, custom colors, site language, active language); `GET /me` also returns them |
| `GET /policy?lang=` (public, 3I) | the approved privacy-policy copy for a language (the English copy if there is none, or if the copy is out of date), with its version |
| `GET /meta` (public) | policy version and the operator's privacy contact, for the policy page (also `policy_languages`: the languages that have an approved, current policy copy) |
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

## 3F. Language display and the site's own language (built in M8)
**The request.** (1) Show every language in its own language: English, 中文简体, Español (with the ñ), and so on. (2) A checkbox in Settings that lets the site itself use the language the learner is currently studying, and follow along when they switch to another language.

### What the request contains
| Part | What it means in practice | Decision |
|---|---|---|
| Names in their own language | One display name per language, used wherever a language is chosen or mentioned: the header picker, “study another language”, sign-up, the native-language picker, headings | `Language.native` from `GET /api/languages` is the only source. Chinese becomes **中文简体** (Simplified), so `name` becomes “Chinese (Simplified)”; “Chinese”, “中文”, “简体中文” and “中文简体” all keep resolving to `zh` |
| A checkbox in Settings | A preference with two values | Off by default. Kept **on the account** (3H), so it follows the learner to every browser and device |
| The site uses the study language | Menus, buttons, labels, messages and dialogs appear in the **active** study language, and switching the active language switches the site at once | Interface locale = (checkbox on) ? active study language : English |
| Implied, not stated | Which text counts as “the site”; what happens to text that cannot be translated; translation quality; fonts; layout; accessibility | Covered below |

### Design
1. **Message catalog.** `web/src/i18n/messages.ts` is one TypeScript table. Each key maps to a nine-entry tuple in the fixed order en, es, fr, de, it, pt, ja, zh, ko, so a missing translation does not compile. `t(key, {name})` fills `{placeholders}`. Plurals use paired keys (`.one`, `.other`) chosen with the browser's `Intl.PluralRules`. A missing or empty entry falls back to English. No i18n library is needed: the languages are fixed, nothing needs full ICU, and one table lets a reviewer read all nine languages side by side. A first draft (about 190 messages) is parked on branch `wip/i18n-themes` and has had no native-speaker review.
2. **Which locale is active.** An `I18nProvider` at the app root holds the locale. The active-language provider moves from the logged-in area to the app root (keyed by user), so the Privacy and sign-in pages can see it. One effect sets locale = (checkbox on and logged in) ? active study language : `en`. Logged-out pages stay English. `<html lang>` follows the locale (`zh` becomes `zh-Hans`), and each language option carries its own `lang` attribute so screen readers pronounce it correctly.
3. **What is translated, and what is not.** All interface text in the logged-in app is translated: header, Home, Vocabulary, Settings, dialogs, toasts and placeholder pages. The **Privacy Policy is not translated by the app**: it is provided as a separate copy per language, shown only once approved (3I). Two things are not translated, on purpose:
   - **Server messages.** Errors are translated by `error.code` where a code has a single meaning (login failed, wrong password, locked, session changed, not found, network error). Others (field validation, “already exists”) stay in the server's English until the API returns stable message keys, which is a later change.
   - **The learner's own data** (words, meanings).
4. **Fonts and layout.** Inter has no CJK glyphs. Per-language font stacks, selected with `:lang()` (`ja`, `zh-Hans`, `ko`), let each script use a suitable system font and the right regional Han shapes. Text length varies (German runs about a third longer, CJK is shorter), so components must wrap, not truncate; every locale is checked at 1280 px and 390 px.
5. **Settings.** A new “Site language” card: the checkbox (a real `<input type="checkbox">` with a label), one sentence about what stays English (some server messages), and a line saying which language the site is shown in now.
6. **Privacy policy.** Provided as one separate copy per language and kept in step by tests (3I). The policy text is updated once for the stored preferences, and `POLICY_VERSION` is bumped once, when all of M8's features are final.
7. **Rejected alternative: keep the choice on the device only.** This was the first design: no migration and no API field. It was dropped because the learner would have to set the site up again on every browser, and the costs that made it attractive turned out to be small (the existing guard tests cover export and deletion of any new table automatically). The decision is in 3H.

### Testing
- **Catalog:** every row has nine non-empty, trimmed entries (length checked by the compiler, content by a test); the set of `{placeholders}` is identical across the nine languages of a row; every `.one` key has its `.other`; a short allow-list covers entries that are legitimately the same as English.
- **Behaviour:** checkbox off gives English whatever the study language; on follows the active language and changes immediately when it changes; the choice is saved on the account and applies on a second browser; a second learner on the same browser does not inherit it (3H); logout returns to English; `<html lang>` updates; a missing key falls back to English.
- **Errors:** each mapped code shows the translated text; unmapped codes show the server's text.
- **Real browser:** tick the box and the navigation turns Spanish; switch to 日本語 and it turns Japanese; a reload keeps it. An accessibility scan of the main screens in every locale catches `lang` mistakes and contrast, and screenshots of German and Japanese are reviewed at both widths.
- **Mutation checks, as before:** break the follow rule, the per-user key, the fallback and the placeholder fill; each must fail a test.

### Not included, and open points
Right-to-left languages (none supported). Traditional Chinese (needs its own code such as `zh-Hant`, and the database check `^[a-z]{2}$` allows only two letters). An interface language independent of the study language (a separate dropdown, possible later). Open: a native-speaker review of the eight translations; **decided (owner, 10 October): the sign-in and sign-up pages stay in English and store nothing.** Following the browser's language with a switcher, so that someone can sign up in their own language, would be a later, separate change; whether the language picker should also show the English name for disambiguation.

## 3G. Themes and custom colors (built in M8)
**The request.** More theme options than Light, Dark and System, plus a **custom theme** where the learner chooses colors on a **color wheel** for different parts of the site. The parts keep their existing classes and ids; a custom theme only recolors what is already grouped together.

### How color works today
- Colors are CSS variables defined once in `web/src/index.css`: a brand scale (`brand-50` to `brand-900`), a `surface` token, and Tailwind's `slate` scale, which every neutral in the app uses (page, borders, text, hints).
- Dark mode is a `.dark` class on `<html>` that re-points the slate scale and `surface`. A few components also carry explicit `dark:` classes where one token plays two roles (brand tints, status colors).
- `ThemeProvider` keeps the choice (`light`, `dark` or `system`) in `localStorage` (`tutor:theme`), and `public/theme-init.js` applies `.dark` before the page paints.
- So the parts are **already together** in the tokens. A custom theme is a different set of token values; no class or id changes.

### Constraints this puts on the design
| Constraint | Consequence |
|---|---|
| Buttons use `text-white` on the brand color, and classes may not change | The accent must always be dark enough for white text (at least 4.5:1). The app darkens it automatically and says so |
| One token is text in one place and a background in another (`brand-700`) | Never recolor tokens one by one. Derive the whole scale from the picks so the roles stay consistent |
| Status colors (error red, success green, warning amber) carry meaning | They are not themeable; the readability panel warns when a chosen background makes them hard to read |
| Components with explicit `dark:` classes expect `.dark` on dark backgrounds | The base (light or dark) is detected from the picked background, and sets or clears `.dark` |
| The CSP forbids inline `style` attributes in markup | Colors are applied through the browser's style API (`style.setProperty`), which the policy allows. This must be proved in a real browser with no CSP violation |
| No white flash on load | The finished color map is saved when a theme is applied, and the init script only applies it, so no color math is duplicated there |

### Design
1. **Five parts, five wheels.**

| Part (as shown to the learner) | What it recolors | Tokens it drives |
|---|---|---|
| Page background | the area behind everything | `slate-50` |
| Cards and panels | cards, inputs, header, dialogs | `surface` |
| Text | headings and body text | `slate-900`, with `slate-800/700/600` derived toward the background |
| Borders | lines, dividers, input outlines | `slate-200`, with `slate-300` derived |
| Buttons, links and menu | primary buttons, links, active menu item, focus rings, the sign-in panel | the `brand` scale |

2. **Derivation.** `derivePalette(five colors)` is a pure function that returns every token plus the base. The subtle fill (`slate-100`) sits between background and border. The hint tone (`slate-500`) is the lightest tone on the line from the text color toward the background that still reaches 4.6:1 against the page, the cards and the subtle fill, so hints stay readable whatever the learner picks, as long as the text itself is readable. Descriptions (`slate-600`) target 7:1. The accent is darkened until white text on it reaches 4.5:1. The brand scale mixes the accent with white (50, 100, 200, 500) and with black (700, 800, 900). The base is dark when the background is dark.
3. **Presets.** Light, Dark and System stay exactly as they are, with no overrides. The new presets are named sets of the same five colors, so they use the same derivation and the same tests. Confirmed by the owner (10 October) as the starting set; final values are still fixed when the contrast tests run:

| Preset | Page | Cards | Text | Borders | Accent |
|---|---|---|---|---|---|
| Ocean | #eef6ff | #ffffff | #0b2540 | #c9dcf0 | #0369a1 |
| Forest | #f1f7f0 | #ffffff | #14301c | #cfe2cc | #15803d |
| Sunset | #fff6ec | #fffdf9 | #3b1d0e | #f0d8c0 | #c2410c |
| Rose | #fff0f4 | #ffffff | #4a1424 | #f4cbd8 | #be123c |
| Midnight | #070b1a | #0e1530 | #e8ecff | #222c52 | #4f46e5 |
| Graphite | #101010 | #1a1a1a | #f2f2f2 | #2e2e2e | #2563eb |
| High contrast | #ffffff | #ffffff | #000000 | #000000 | #0000b3 |

4. **The color wheel.** A custom component with no library: a hue-and-strength wheel drawn with CSS gradients, a draggable marker, a brightness slider and a hex box. It works by pointer, by touch (`touch-action: none`) and by keyboard (left and right change the hue, up and down the strength; the wheel is a `slider` with a spoken value), and the hex box is the accessible fallback. The browser's built-in color input is not used: it is not a wheel and looks different in every browser.
5. **Applying and saving.** The choices live on the account (3H): the theme id and the five custom colors. `ThemeProvider` becomes a reader of the preferences provider and grows from three themes to the three built-ins, the presets and `custom`. The derived variable map is computed in the browser and written, with the theme id, to the device copy (`tutor:prefs:cache`), which `public/theme-init.js` applies before the first paint; the init script is a plain applier with no color math. Choosing Light, Dark or System removes the inline variables. Other tabs follow through the `storage` event. A stored value that is invalid, or a theme id this version of the app does not know, is ignored and the app uses System.
6. **Settings, Appearance.** The radio group (names “Light”, “Dark” and “System” unchanged) becomes a grid of tiles with a small color preview each, then “Custom”, which opens the editor:

```
+--------------------------------------------------------------+
| Appearance                                                   |
|  (o) Light  ( ) Dark  ( ) System  ( ) Ocean  ( ) Forest ...  |
|  ( ) Custom                                                  |
|  Customize colors                       Start from [Ocean v] |
|  Part:  (o) Page background  ( ) Cards and panels  ( ) Text  |
|         ( ) Borders          ( ) Buttons, links and menu     |
|        .-----.   Brightness  [----o-------]                  |
|       /  wheel \  Hex color   [#eef6ff]                      |
|       \   o    /                                             |
|        '-----'    Readability                                |
|                    Text on page     14.2:1  Good             |
|                    Text on cards    15.8:1  Good             |
|                    Button text       6.3:1  Good             |
|                                       [ Reset colors ]       |
+--------------------------------------------------------------+
```

7. **Readability panel.** Shows the real contrast ratios for the pairs that matter (text on page, text on cards, button text) with “Good” or “Hard to read”. It warns and never blocks, because the learner may choose what they like. A note appears when the accent had to be darkened.
8. **The header's quick switch** keeps flipping between Light and Dark. From a preset or custom theme it moves to the built-in whose base matches the current one.

### Testing
- **Color math:** hex, RGB and HSV round trips; luminance and contrast against known values (black on white is 21:1); mixing.
- **Derivation properties over many random inputs:** accent with white text at least 4.5:1; hint tone at least 4.5:1 on page, cards and subtle fill whenever text against page is at least 7:1; base detection; the output contains every token the CSS actually references.
- **Presets:** every preset passes all of the above, so a new preset cannot ship unreadable.
- **Provider:** applying sets the variables and `.dark` correctly; switching back clears them; stored junk is ignored; the applied map is what the init script reads; cross-tab update.
- **Wheel:** pointer position gives the expected hue and strength; keyboard steps; the hex box accepts `#rgb` and `#rrggbb` and rejects the rest; the value is announced.
- **Real browser:** a real mouse click on the wheel changes the variable and the page; the choice survives a reload with **no flash** (app script blocked, page already themed); **no CSP violation**; an accessibility scan of the main screens under every preset and a few extreme custom palettes (very light, very dark, saturated); screenshots.
- **Mutation checks:** remove the accent fix, the hint search, the `.dark` toggle or the cleanup; each must fail a test.

### Not included, and risks
Not included: per-element colors beyond the five parts; gradients, fonts or spacing; importing, exporting or sharing themes; scheduled themes; recoloring the status colors. Risks: a custom background close to a status color (a red page with red error text) is hard to read even when the main pairs pass, so the panel warns but cannot prevent it; any new component using brand or status colors needs a `dark:` variant (already a documented rule); the init script must stay a tiny applier, because duplicated color math would drift.

## 3H. Display preferences on the account (built in M8)
**Decision, changed from the first design.** The site-language choice and the theme choices are kept **on the account**, not only on the device, so they follow the learner to every browser. The device keeps only a short-lived copy, for fast loading.

### What is stored
| Preference | Type | Notes |
|---|---|---|
| Site language follows the study language | yes or no, default no | the checkbox of 3F |
| Active study language | one of the learner's languages, optional | **Decided (owner, 10 October):** kept on the account too. The site language follows “the language you are currently studying”, so a per-device value would make two devices disagree |
| Theme | text id (`light`, `dark`, `system`, a preset id or `custom`), default `system` | 3G |
| Custom colors | five hex colors, optional | kept even while another theme is selected, so switching back does not lose the palette |

Not stored: the derived color map (computed in the browser from the five colors) and anything chosen on the sign-in pages.

### Data model
Table `user_preferences(user_id PK → users ON DELETE CASCADE, active_language, ui_follows_study_language boolean, theme, custom_colors jsonb, updated_at)`. A separate table keeps `users` clean. The row is created on the first save, and no row means defaults. Because the table has a `user_id` column, the two existing guard tests apply by themselves: “Download my data” must contain it (key `user_preferences`) and account deletion must remove it. Constraints: language `^[a-z]{2}$` and one of the learner's languages; theme slug `^[a-z][a-z0-9-]{0,23}$`; colors strictly `#rrggbb`. The server checks the *shape* of a theme id and the client decides what it *means*, falling back to System for an id it does not know, so an older client and a newer server never break each other. A new migration, numbered when it is written (the `stories` table takes the next free number).

### API
- `GET /me` gains `preferences` (null if never saved), so the app has everything from its first request.
- `PATCH /me/preferences` changes any subset. Login required, like every route; unknown keys are rejected; errors use the existing error body.
- Nothing about preferences is public.

### How the app uses them
- A `PreferencesProvider`, inside the auth provider, is the single source. It exposes the values and setters, and `ThemeProvider` and the active-language provider become readers of it instead of owning `localStorage` keys.
- **Changes apply at once** (optimistic) and are saved after a short debounce, and on release while the learner drags the color wheel, as one request with the latest values. A failed save keeps the local look and shows a small inline note, and the next change retries. Across devices, last write wins.
- **Device copy.** After a load or a save the app writes `tutor:prefs:cache` (user id, the values, and the derived color map for the init script). `public/theme-init.js` reads it before the first paint, so there is no flash. When the account's values arrive they replace the copy. The copy is **wiped on logout, on user change and on any “not logged in” answer**, like all other per-user data, so the next person on a shared computer does not inherit it (the isolation rules of 12A).
- **Before login.** The sign-in and policy pages follow the operating system's light or dark setting and show English. The light/dark switch there is temporary, for that tab only (`sessionStorage`), and never remembered.
- **Existing device-only settings.** The first time someone with no saved preferences opens the app after this ships, their old device values (`tutor:theme`, `tutor:lang:<id>`) are uploaded once and then removed.

### Privacy policy additions (written once, in every copy: 3I)
- A new row in “what we collect”: **Your display preferences** (theme and custom colors, whether the site is shown in the language you study, and the language you are studying now). Used to show the site the way you chose on every device. Included in the download. Deleted with the account.
- The browser-storage section changes: the sign-in cookie, plus a temporary copy of the display preferences kept so pages load in the right colors and removed when you log out; nothing is stored on the sign-in pages beyond the current tab.
- `POLICY_VERSION` is bumped once, after the policy text for all of M8 is final (3I explains why only once).

### Testing
- **API:** defaults when there is no row; partial updates; every validation rule (bad theme slug, a bad or extra color, an extra key, a language that is not one of the learner's); `GET /me` returns only the caller's; learner B can neither read nor change A's; the export contains `user_preferences` and deletion removes the row (the guard tests cover this, and a mutation check proves it); the “every route needs login” test covers the new route by itself.
- **Web:** an optimistic apply and one debounced save; a failed save keeps the look and retries; legacy device values are adopted once and then removed; the device copy is written, used by the init script, and wiped on logout, user change and a 401; a second learner on the same browser never sees the first one's theme or language; sign-in pages ignore stored preferences.
- **Real browser:** change the theme and site language in one browser, sign in from a second browser, and both apply; a reload keeps them with no flash; logout and a different user on the same browser start from defaults; deleting the account removes the preferences.

### Risks
Chatty saves while dragging the wheel (debounce, and save on release); last-write-wins surprises across devices (acceptable for a look-and-feel setting); after a session expires, the first paint can briefly show the old colors before the 401 arrives (cosmetic, then wiped).

## 3I. The privacy policy in the learner's language: separate copies, not translations (built in M8)
**History of this decision.** First design: the policy stays English-only. Second: translate it and label each translation with a review status. **Now (owner decision, 10 October 2026): do not rely on translation. Keep a separate, complete copy of the policy for each language.** The reason is risk: a legal text that is machine-translated, or translated and never checked, can mislead.

### What “a copy” means
- Each language has its own **complete policy document**, stored as its own file. The app never translates the policy and never builds one language's text from another's; it only chooses which copy to show.
- Each copy is written, or at least checked, by someone who can vouch for it in that language and for the place where the app is used. A first draft can be prepared by anyone, including with machine help, but it stays a **draft**, invisible to learners, until it is approved.
- Every copy contains the same short statement of **which copy governs** if copies ever disagree. The wording is the operator's decision; the proposed default is that the English copy governs.

### The safety rule: only approved, current copies are shown
| Copy state | Meaning | Shown to learners? |
|---|---|---|
| `approved` | an approver's name and the date are recorded in the file, and the copy's version equals `POLICY_VERSION` | yes |
| `approved`, but stale | its version is older than `POLICY_VERSION` (the policy changed after it was approved) | **no**: withdrawn automatically, English is shown instead |
| `draft` | exists in the repository, not yet approved | **no**: learners cannot tell it exists |

English is the first and, at the start, the only approved copy. A language therefore appears only when someone has approved its copy, and a policy change can never leave an outdated copy on display.

### Design
1. **Which copy is shown.** The learner's interface language (3F: the study language when the site-language checkbox is on, otherwise English) if an approved, current copy exists for it, otherwise English. The policy page also has a picker listing English plus the languages that currently have an approved copy, each in its own name, so a visitor who is not signed in can choose. If the chosen language has no approved copy, English is shown with a short notice in the learner's language (an ordinary interface message, 3F): “This policy is not available in your language yet. Showing the English copy.”
2. **Where the copies live.** On the API, one JSON file per language under `api/app/policy/`, each with its own `version` and `status` and, when approved, `approved_by` and `approved_on`. A public `GET /policy?lang=<code>` returns the copy that the rule above selects, with its version and language, and `fallback: true` when it had to use English. `GET /meta` lists only the languages that have an approved, current copy.
3. **Content shape.** A copy is data, not JSX: sections, each with blocks (paragraph, list, table). The English copy defines the shape and **every** copy, drafts included, must match it block for block, so copies cannot drift apart structurally. Inline formatting is a tiny safe subset (`**bold**`, a `{contact}` placeholder for the operator's address, links); the page builds React elements from it and never injects HTML.
4. **The page.** Shows the selected copy, its version, the picker and, when relevant, the fallback notice. Its chrome (back link, theme switch) follows the interface language. The parked draft's `p.englishOnly` message becomes the fallback notice, and the sentence in `s.uiHelp` saying the policy stays English is removed.
5. **Consent.** Sign-up stays in English and its checkbox links to the policy page. Consent is recorded against the policy **version**. The app does not record which language copy was opened; the governing-copy statement covers any disagreement.
6. **The cost, and why it is acceptable.** Every policy change that matters means updating each copy that should stay available, plus one `POLICY_VERSION` bump. A copy nobody updates is **withdrawn automatically** (stale), so the price of neglect is that learners see the English copy, never a wrong text. Edit once, after all of M8's features are final, bump once, then update the copies.

### Testing
- **API:** every file parses; every copy, draft or approved, has the English shape (same sections, block types and counts); no empty strings; every `{placeholder}` of the English copy appears in every copy; the English copy is approved and current; approved copies carry an approver and a date. The selection rule: a draft is never served, a stale approved copy is never served, an unknown language falls back to English with `fallback: true`, and `GET /meta` lists only approved, current languages. The route is public (listed as public on purpose in the “every route needs login” test).
- **Mutation checks:** serving a draft, serving a stale copy and skipping the shape check must each fail a test.
- **Web:** the page follows the interface language when an approved copy exists and falls back with the notice when not; the picker lists only approved languages; a signed-out visitor can switch; markup inside a string is shown as text; the governing-copy statement is present in every approved copy.
- **Real browser:** an accessibility scan of the policy page for English and for every approved language, and screenshots of any non-Latin copy.
- **Claims map (12B):** each row's key phrases are checked in the English copy, and the shape tests carry the other copies along.

### Not included
The legal review itself (a person has to do it); a per-jurisdiction variant of the policy; recording which copy a learner opened; asking learners to re-accept after a later change (the app records the version only); policies for languages the app does not support.

### Open
Which copy governs if they disagree (proposed default: English, an operator decision). Whether the policy should follow the **study language** even when the site-language checkbox is off (proposed: it follows the interface language, plus the picker).

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
  USERS ||--o| USER_PREFERENCES : prefers
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
  USER_PREFERENCES {
    int user_id PK
    text active_language
    bool ui_follows_study_language
    text theme
    jsonb custom_colors
    timestamptz updated_at
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
| Display preferences (3H) | on the **account** (`user_preferences`), delivered with `GET /me`, changed with `PATCH /me/preferences` | follow the learner to every device; included in the data download; deleted with the account |
| Device copy of the preferences (3H) | `localStorage` key `tutor:prefs:cache` | only for first-paint speed (read by the init script); wiped on logout, user change and any 401; replaced by the account's values when they arrive |
| Sign-in-page light/dark switch | `sessionStorage`, this tab only | never remembered |
| Selected language, style | context, remembered in `localStorage` under a key that includes the user id | so two learners on one browser do not share the setting (3H: the active language now lives on the account) |

**Optimistic updates** only for delete. Add and edit wait for the server because the server normalizes the word and may reject it as a duplicate; an optimistic add could show something that is never stored. Calls to Groq or Langflow never retry automatically, to protect the shared rate limit.

## 11. Errors and rate limits
Groq's free tier is shared by everyone using the app, so limits will show up with more than one learner.

**AI gate (API side).** Every call that reaches Groq, direct or through Langflow, passes through one gate: a process-wide semaphore of 2 concurrent calls (wait up to 5 s, then `tutor_busy`) a per-user lock so a double-click or two tabs cannot submit two AI requests at once, and (M5) a **tokens-per-minute budget** (`AI_TOKENS_PER_MINUTE`, default 8000, 0 = off): a sliding 60-second window shared by every learner. A chat turn reserves an estimate first (1500 plus about one token per three characters of the message, above the 618 and 1344 measured on 14 Oct 2026) and is corrected to the real total Langflow reports (`properties.usage`); a turn that fails keeps its estimate, a turn that reports nothing keeps its estimate. When the window is full the answer is `tutor_busy` (429) with `Retry-After` set to when enough tokens will have left it, before any slot is waited for. The stub tutor is never charged. `call_groq` gets a **total deadline of 60 s** instead of "3 attempts of 30 s each" (which could reach 90 s). nginx waits 120 s, and the Langflow call times out at 100 s. The UI shows "this is taking longer than usual" after 20 s.

| Code (HTTP) | Situation | What the learner sees |
|---|---|---|
| `chat_cleanup_failed` (503) | Account deletion could not confirm the learner's stored chat was removed | "We couldn't remove your chat history just now, so your account has not been deleted. Please try again in a moment." Nothing is deleted. |
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
| The password is a one-way hash nobody can read | salted bcrypt; no password, hash or salt in any response, log or export | `test_export_contains_my_data_and_no_secrets`; browser test on the export file |
| One cookie, httpOnly, up to 8 hours, no analytics or third-party cookies | session cookie only; CSP allows only our own origin (`default-src 'self'`) | browser tests (cookie flags, "no CSP violations") |
| Download my data gives everything held about you, and only yours | `services/export.py`; keys are table names | `test_export_covers_every_table_that_holds_user_data` (fails when a future table with `user_id` is left out), isolation test in the export test |
| Delete account removes everything immediately | hard delete; every reference to `users` is `ON DELETE CASCADE` | `test_delete_account_removes_everything_and_ends_all_sessions`, `test_every_reference_to_users_deletes_with_the_user`; browser test deletes, then re-registers the same email with nothing carried over |
| Deleting needs your password | `_reauthenticate`, shared lockout | `test_delete_account_needs_the_right_password`, mutation "delete without password" fails a test |
| Changing your password logs out other devices | `revoke_others` | `test_change_password_ends_other_sessions_but_keeps_this_one` |
| You can correct your name, email, password | Settings forms, `PATCH /me`, `/me/email`, `/me/password` | `test_account.py`; browser test "changing name, email and password works end to end" |
| The app sends no email | no mail code exists | (true by absence; if mail is added, the policy sentence in section 3 must change first) |
| **Your name and email are not sent to the AI service** | the identity of the learner reaches Langflow only as a numeric `learner_id` tweak and the `u<id>-` session id; the message is the learner's own text | Chat (M5): `test_a_learners_name_email_and_password_never_reach_langflow` registers a learner called "Zebulon Quux", chats and deletes the account, and fails if any request body, URL or header holds the name, email or password. Story Studio (M6): `test_the_prompt_never_holds_the_learners_name_email_or_password` (`test_stories_generate.py`) fails if the name, email or password appears in the prompt sent to Groq; only this learner's words in this language are in it (`test_only_this_learners_words_in_this_language_reach_the_prompt`) |
| Your chat is stored, and deleting your account deletes it | `chat_sessions` table (ids only); `/me/delete` removes each session through Langflow's monitor API and confirms it is empty first, or refuses with `chat_cleanup_failed` | `test_chat_deletion.py` (client, route, account deletion order and failure, end to end against a fake Langflow that really forgets); real Langflow not yet run |
| Download my data lists chat sessions, not their messages | `services/export.py` key `chat_sessions` | `test_the_export_lists_chat_sessions_but_never_their_content`; the table-coverage guard test |
| Each account has its own password salt | `password_salt` beside `password_hash`; `bcrypt(base64(SHA-256(salt \|\| password)))` | `test_password_salt.py` |
| Chat is available when switched on; Story Studio sends your words (a random selection if the list is long), the kind and the topic to the AI service, and a story you do not save is not kept | Chat page (live only when `LANGFLOW_PER_USER_TOOLS=1`); `POST /api/stories/generate` saves nothing (`test_nothing_is_saved_by_generating`); only `POST /api/stories` stores | `test_nothing_is_saved_by_generating`, Privacy page test (the sentences are present) |
| A saved story is kept with its quality report only, and deleting your account deletes it; the download lists your saved stories | `tutor.stories` (migration 0006, `ON DELETE CASCADE`); `services/export.py` key `stories`; the report is made by the server | `test_deleting_the_account_deletes_the_library`, the table-coverage guard test, `test_a_page_cannot_claim_a_pass_or_send_its_own_report`; delete dialog test lists "your saved stories" |
| Policy version | `2026-10-16` (Story Studio and saved stories; before that `2026-10-15` for chat storage, deletion, export and salt wording) | Privacy page tests |
| The browser remembers your light/dark choice and your selected language on your own device only (policy section 4) | `localStorage` keys `tutor:theme` and `tutor:lang:<user id>`, never sent | true today. **It stops being true when 3H ships**, because the choices then live on the account. The policy must say so (next rows) and `POLICY_VERSION` must be bumped |
| Your display preferences are stored on your account, included in the download and deleted with it (3H) | `user_preferences` with `ON DELETE CASCADE`; export key `user_preferences` | the two guard tests (export covers every table with a `user_id`; deletion leaves no rows) plus a mutation check |
| The browser keeps only a temporary copy of the preferences, removed when you log out (3H) | `tutor:prefs:cache`, wiped on logout, user change and any 401 | web tests; a browser test that a second user on the same browser starts from the defaults |
| The policy is available as a separate approved copy per language; drafts and out-of-date copies are never shown (3I) | `GET /policy` serves only approved copies whose version equals `POLICY_VERSION`, otherwise English | selection, shape and version tests with mutation checks; a web test for the fallback notice |

**Operator checklist (things code cannot do):** set `PRIVACY_CONTACT` to a real address; serve the app over HTTPS before exposing it beyond localhost (`COOKIE_SECURE=1`); decide how long database backups are kept and say so if asked; check the age wording ("under 16") and any legal requirements for the place where the app is used. **This policy is a plain-language template written alongside the code, not legal advice. It has not been reviewed by a lawyer.** For each language copy of the policy (3I), have someone who can vouch for it write or check it before it is marked `approved`, and decide which copy governs if copies differ (default: English). Until then the copy stays a draft that learners never see.

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
- **Personalisation (built in M8):** the testing lists in 3F and 3G. The browser suite gains locale runs and theme runs of the existing accessibility scan.

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
| 8a | Display names: `zh` becomes “Chinese (Simplified)” / 中文简体 with aliases; every language picker and heading shows the native name with a `lang` attribute; CJK font stacks | none | pickers show English, Español, 中文简体 and the rest; old names still resolve; accessibility scan clean |
| 8p | Display preferences on the account (3H): the `user_preferences` table and migration, the `GET /me` field, `PATCH /me/preferences`, export and deletion coverage, `PreferencesProvider`, the device copy read by the init script, adoption of old device settings, the English policy text updated (version not yet bumped) | none | the API and web tests of 3H pass; a second browser shows the same preferences; logout wipes the device copy |
| 8b | Site language (3F): message table, `I18nProvider`, the active-language provider moved to the root and reading the account's preferences, Settings checkbox, error-code mapping | 8a, 8p | the checkbox behaves as in 3F on every device; catalog tests pass; every locale passes the accessibility scan; German and Japanese reviewed at both widths |
| 8c | Themes (3G): color math, derivation, presets, `ThemeProvider` reading the preferences, init script, color wheel, Settings editor | 8p | every preset and the sample custom palettes pass the contrast tests; real-browser wheel, no-flash and CSP tests pass |
| 8d | The policy as separate copies per language (3I): files on the API with a status, `GET /policy` and the selection rule, the picker and the fallback notice, shape and version tests, and the single `POLICY_VERSION` bump for all of M8 | 8b, and the final policy text from 8p to 8c | English is served; an approved current copy of another language is served; drafts and stale copies never appear; an accessibility scan for every approved language |

M8 is independent of M0 to M7 (front end, one new table and a few routes), so it can be built before, between or after them. Suggested order: 8a, 8p, 8b, 8c, 8d. Write the English policy text once after 8p to 8c are final, bump the version once, and translate once (8d).

### Implementation status (updated as work lands)
| M | Status | Notes |
|---|---|---|
| 0 | **Plan A verified** | tweaks reach the tool per request and stay separate under concurrency on Langflow 1.12.2 (node-id key; hidden input `learner_id` sent as a string). The chat-deletion probe has run: per-session delete works (changelog). Still open: display-name key, committing the captured greeting/story fixtures, which model answers. See changelog |
| 1 | built, verified except the web image | `make check` green; real nginx + API + Postgres exercised with curl. The langflow and api images build and run under compose on the author's machine (Langflow waits for a healthy api); the web image build was not reported separately |
| 2 | built | schema migration, register / login / logout / me, lockout, CSRF, isolation tests (mutation-checked) |
| 3 | **built, verified live** | extraction done in two commits (pure move, then behaviour); tools are thin wrappers over `tutor_core.tools`, per learner, fail closed, `TUTOR_DEV_USER_ID` fallback; `tutor.words`; cache keyed by (learner, language, type, topic); word cap; credentials and model from the environment; flow synced by `scripts/sync_flow_nodes.py`. Verified here against real Postgres. **Run on the author's machine (14 Oct 2026):** the image builds and runs, `sync_flow_nodes.py --check` is in step, `scripts/m3_check.py` passed (tools per learner, fail closed), routing matrix 13/15 (both failures are English story quality, not routing). `make test-langflow`: all 16 files pass (the relay test's fixture imported the wrong `ContentBlock` class in the 1.12.2 image; fixed and re-run). See changelog |
| 4 | built | vocabulary API and page (list, search, add, edit, bulk delete, CSV upload, add language) |
| 5 | **partly built** | the parts that do not depend on M0's answer: `POST /api/chat`, the AI gate (2 at once, 1 per learner), `langflow_client` (payload, parsing, error mapping), a stub tutor (`AI_MODE=stub`), the Chat page with tool trace. **Live chat is deliberately OFF** until `LANGFLOW_PER_USER_TOOLS=1` (the tools must read the learner's own words first: M0 and M3). Still to do: pass `user_id` per the M0 result, save-to-library, the `/health` Langflow check, privacy wording and policy version for live chat, per-user deletion of Langflow's stored chat (the probe shows `DELETE /api/v1/monitor/messages/session/<id>` works; the API call and its test are still to write), the real-fixture tests (the responses are captured but not yet in `api/tests/fixtures/langflow/`, so 3 tests still skip), browser and accessibility specs for `/chat` |
| 6-7 | not started | the pages exist as "coming soon" placeholders |
| hardening | built | server-side sessions, `no-store` and security headers, CSP, expected-user check, per-user cache keys, cross-tab sync, back-cache guard (section 12A) |
| style | built | see `docs/STYLE-GUIDE.md` (tokens, components, measured contrast, honest gap list) |
| tests on 10 October | built | 32 `tutor_core`, 90 API, 56 web unit and 27 real-browser tests; the real-browser suite includes an accessibility scan of every screen in both themes. Later counts are in section 19.1 |
| M8a, 8p, 8b, 8c, 8d | built and tested here (not yet run on the author's machine; the final patch waits for the owner's word) | sections 3F to 3I. English is the only approved policy copy: its approval record (`approved_by`, `approved_on` in `api/app/policy/en.json`) names "Project owner" and must be confirmed or changed by the operator. `POLICY_VERSION` is `2026-10-17`. The Spanish catalog and the other eight are not native-reviewed |
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
10. **Translation quality.** The eight non-English translations were written without a native-speaker review. The strings are short and plain, but mistakes are especially visible to someone learning that very language. Have a speaker of each language read the table before real learners rely on it.
11. **Partly translated screens.** Some server messages (field validation, “already exists”) stay in English by design (3F), so a learner will sometimes see two languages on one screen until the API returns stable message keys. The privacy policy is shown as a separate copy per language when an approved one exists (3I).
12. **Layout in other languages.** German runs longer and CJK needs different fonts. Navigation and buttons must wrap rather than truncate; this needs a screenshot review per locale.
13. **Unreadable custom themes.** A custom palette can defeat any automatic derivation (a red page with red errors). The readability panel warns, and nothing prevents it.
14. **Preferences now live on the account.** Saves while dragging the color wheel must be debounced; two devices can overwrite each other (last write wins, acceptable for a look-and-feel setting); and the privacy policy changes to say so (3H, 12B).
15. **A wrong or out-of-date policy copy is worse than a wrong button.** Mitigations: the copies are separate documents, never machine-derived at run time; a copy is shown only when approved and current, otherwise learners see the English copy; tests keep every copy's structure and version in step; every copy states which copy governs (3I). Whether to approve a copy at all is the operator's call.
16. **Maintaining several copies.** Every policy change that matters means updating each copy that should stay available. A copy nobody updates is withdrawn automatically, so neglect costs a fallback to English, not a wrong text.

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

### 17A. Findings from building M0 and M3 (for the next revision of this document)
1. **Hidden tool inputs are named `learner_id` and `active_language`, never `user_id`**: Langflow reserves `user_id` (and `graph`, `flow_id`, `flow_name`, `trace_name`, `tracing_service`, `tree`, `template_config`, `enabled_tools`, `ctx`) on every component and silently shadows an input of that name (M0).
2. **The id is sent as a string**: Langflow silently drops a non-string value sent to a text field (M0). The tool turns it back into an integer and refuses anything else.
3. **Langflow reports tools by their snake_case names** (`add_word`, `story_generator_tool`), not the canvas names; the API client maps them back (M0).
4. **Tweaks are keyed by node id** (`AddWord-WhP5g`), the style that was verified; display-name keys are not yet verified.
5. **The language gate lives in `tutor_core.story.generate_story`** (as designed), so chat and Story Studio obey it equally; the tool layer just relays its message.
6. **OPEN, needs a decision and a measurement: the non-English story prompt calls the vocabulary list English.** Step 10 measured Spanish, French and Japanese at 30/30 with ONE English vocabulary and a prompt that says "the list below is written in English: treat each entry as a MEANING and use its natural Spanish word". With per-language lists (3C) a Spanish learner's list holds Spanish words, so that sentence is false for them. M3 deliberately did not change measured prompts. Before non-English stories are relied on: add a variant of the prompt for target-language vocabulary and re-measure it (`scripts/run_story_batch.py --learner-id N --languages Spanish` now uses the learner's own Spanish list), or decide that stories use the learner's English meanings.
7. **The tools connect with the same database account as the API.** A least-privilege role for the Langflow tools (read/insert on `tutor.words` only) is a worthwhile hardening step, not done in M3.
8. **The API's own add-word INSERT is still separate from `tutor_core.vocab.add_word`**; both share the one rule that matters (`tutor_core.words.validate_word`). Consolidating the INSERT is a small follow-up.
9. **Legacy:** the Step 8 canvas components (`upload_word_file`, `story_prompt_builder`, `story_guard`, `final_passage_extractor`) **were deleted on 18 October 2026** with their four tests; the logic they duplicated lives in `tutor_core` (tested there). `word_loader` stays, unwired, for debugging. Built, not yet run on the author's machine (the flow was re-synced with `scripts/sync_flow_nodes.py`).
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

## 19. Progress log and next steps

*This section records where the project stands. The changelog has the detail; this is the map.*

### 19.1 Where each milestone stands
| M | Status | Evidence | Still open |
|---|---|---|---|
| 0 | **Plan A verified** | live runs on Langflow 1.12.2: tweaks reach each tool per request and stay separate under concurrent calls (overlap 1.46 s of 1.50 s), the Agent cannot change a hidden input, no tweak means no learner | display-name tweak key unverified; greeting/story fixtures captured but not yet committed (the chat-deletion probe is done: per-session delete works); which model actually answers (Gemini named in the Agent node, Groq node wired in) |
| 1, 2, 4 | built | API 458 tests (0 skipped), web 77, real Postgres; the api image builds and runs on the author's machine | the web image build (nginx) is not reported |
| 3 | **built, verified live** | extraction in two commits (pure move proven byte-identical to the original; then behaviour); tools per learner and fail closed; 59 core tests, 16 root tests; live on 14 Oct 2026: `m3_check.py` passed, routing 13/15 | English story quality (the 2 routing failures: 18 and 9 stray words, the known tuning-change-2 tension) |
| 5 | **built here, live chat OFF** | `POST /api/chat`, AI gate, Langflow client with real fixtures (whoami, greeting, story; none skipped), stub tutor, Chat page; **15 Oct 2026:** account deletion removes the learner's Langflow chat (`chat_sessions`, migration 0004), per-account password salt (0005), `/health` reports Langflow, prompt-privacy test, privacy page and delete dialog reworded, policy version 2026-10-15; API 458 passed, web 77 | run the deletion once against the real Langflow; switch live chat on (below); **save-to-library (needs the `stories` table, which the design puts in M6: decide whether M5 owns it)**; re-run routing case I1 for the no-language story default; **15 Oct 2026, later:** token-per-minute limiter in the AI gate (API 490 passed); Langflow's other run logs unexamined; token limiter built (above; its estimate is a guess until a real busy minute has been watched) |
| 6 | **built here, not run against Groq** | 16 Oct 2026: `tutor_core.quality` (the checker moved out of `scripts/`, plus `report()`), `tutor.stories` (migration 0006), `POST /api/stories/generate` and `GET /api/stories/options`, the library API (`POST/GET/DELETE /api/stories`), Story Studio page, Save to library in Chat and Studio, `/health` reports Groq (cached 60 s), policy 2026-10-16; stub-tested only | run one real story and one real chat story; `docker compose build` (Langflow image holds `tutor_core`); watch real tokens against `STORY_TOKENS` (2000); the non-English prompt decision (17A item 6) is still open |
| 7 | **built here, not run against your stack** | 16 Oct 2026: `GET /api/practice/flashcards` and `/cloze` (nothing stored, no AI call, blanks only from the learner's own single-word entries, English inflections matched, at most 8 items, Tier 2 languages refused), Library page (list, open with report, delete with confirmation, paging, Practice this story), Practice page (flashcards with a score, fill-in-the-blank with feedback), Practice link after saving in Studio, the seed script adds one saved story in English and one in Spanish, Playwright spec `library-practice.spec.ts` (4 tests, run here against the stub stack), a dark and light axe scan of the story screens, `docs/DEMO-WALKTHROUGH.md` | run the walkthrough once on your machine; the two older browser tests (CSP headers, no white flash) need the nginx build, not the dev server |

### 19.2 Where things were verified
- **In the build sandbox** (real Postgres 16, Python 3.12, Langflow's `lfx` library standing in for `langflow`): every automated suite, run test-first and mutation-checked. Fakes are used only for Langflow and the Agent, never for the database or `tutor_core`.
- **On the author's machine** (Langflow 1.12.2, Python 3.14.7, Groq, 14 Oct 2026): the M0 spike runs, and M3 in full: the langflow image build, `sync_flow_nodes.py --check`, `m3_check.py` (all six checks), the routing matrix (13 of 15; both failures English story quality) `make test-langflow` (all 16 files, after one test-fixture fix) and the chat-deletion probe (per-session delete through Langflow's monitor API works; the probe re-reads stored messages only, so any other Langflow run logs are unexamined).
- **On the author's machine, 16 Oct 2026 (after M6's move of the quality checker and the image rebuild):** `make test-langflow` (all files), `sync_flow_nodes.py --check` (in step) and `m3_check.py` (all five checks, throwaway learners cleaned up) passed. **Routing matrix, 16 Oct 2026 (19.3 step 5): 14 of 15 turns passed** (the last run was 13 of 15), p50 2.5 s and p90 4.8 s per turn. The one failure is S1, the English story: the story had 20 words outside the learner's list (the same kind of English story-quality failure as before, not a routing problem; one of the strays was the test word `autotestapple` itself). Case I1 ("Tell me a story" with no language) recorded one story-tool call with `language: English`; the harness cannot tell whether that came from the hidden active-language default or from the Agent's own habit, so the I1 re-check is recorded, not settled. Live chat was switched on and works; chat shows the "tutor is busy" message when asked too often, which is the limiter doing its job. The chat-deletion check against the real Langflow and a real Groq Studio story have not been confirmed yet.
- **Nowhere yet:** the web image build, live chat through the API (M5: `LANGFLOW_PER_USER_TOOLS` is still 0), and the new M5 code against the real Langflow (account deletion's call to the monitor API is tested only against a fake that mimics the probe's results; `/health`'s Langflow check likewise).

### 19.3 What to run next, in order
*Steps 1 to 5 were run on 14 October 2026 and passed (details in the changelog); step 6 is next (its probe has also run: see the changelog).*

1. Apply the patches, then `docker compose up -d --build`. If the langflow image fails to build, the Dockerfile prints which interpreter and user it assumed; `docker run --rm --entrypoint sh langflowai/langflow:1.12.2 -c 'id; command -v python; python --version'` shows the real values (set `LANGFLOW_RUN_AS_USER` in `.env` if the user is not `user`). Back up the canvas flow first: Langflow loads `flows/language-tutor.json` at startup and it has the same id as your canvas copy.
2. `make test-langflow`: every container-side test under Python 3.14.7.
3. `docker compose exec langflow python /app/scripts/sync_flow_nodes.py --check`: the loaded flow still matches the repo.
4. `docker compose exec langflow python /app/scripts/m3_check.py --flow-id language-tutor --pause 30`: the live acceptance check. `TUTOR_DEV_USER_ID` must be empty for check 1 to be judged.
5. `docker compose exec langflow python /app/scripts/run_routing_tests.py --flow-id language-tutor --delay 20`: the routing matrix as throwaway learners; compare with Step 10 (43 of 45 routing, 30 of 30 non-English). The Agent-facing tool text is unchanged, so routing should not move; if it does, that is a finding.
6. If 4 and 5 pass: set `LANGFLOW_API_KEY` and `LANGFLOW_PER_USER_TOOLS=1` in `.env` (live chat then turns on), The privacy page and policy version are already updated. The deletion code is written (19.4 item 5): after setting the key, send one chat as a test learner, delete that account, and check in Langflow that the session's messages are gone.

### 19.4 Decisions waiting for the author
1. **Non-English story prompt** (17A item 6): variant for target-language vocabulary plus re-measurement, or stories from English meanings.
2. **Token budget**: **decided and built (15 October 2026):** a tokens-per-minute limiter in the AI gate (see section 11). Moving off Groq's free tier is still open; raising `AI_TOKENS_PER_MINUTE` is the only change that would need.
3. **Tools' database role** (17A item 7): worth a least-privilege account before real learners.
4. Whether to delete the legacy Step 8 components (17A item 9). **Decided and done (18 October 2026):** deleted.
5. **How account deletion removes Langflow chat** (M5 acceptance item, mechanism proven by the probe). **Decided and implemented (15 October 2026): a `chat_sessions` table** (migration 0004, ids only, cascades with the user), so the existing guard tests cover it; deletion removes each session through the monitor API and confirms it is empty before the user row is deleted, and refuses with `chat_cleanup_failed` (503) if it cannot. Still true either way: "Download my data" and the privacy policy must say what chat is kept, and the probe did not examine Langflow's other run logs.

