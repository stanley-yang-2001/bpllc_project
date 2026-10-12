# Changelog — Language Tutor with Langflow

Entries are newest first. Dates come from the git history; the project has no versioned releases.

## Unreleased — M3: `tutor_core` extraction and per-learner, fail-closed tools

Done as the design requires, in two commits so a regression can be blamed on the move or on the behaviour.

**Baseline** (commit 22c8ed3, before touching anything): root tests 17/17 (run in a rebuilt container-like harness: `/app` paths, host
`postgres`, `langflow.*` mapped to the real `lfx` library), API 191 passed + 3 skipped, `tutor_core` 32.

**Commit 1, pure move** (86ed65c): the story prompts, language handling, Groq call, vocabulary access and story pipeline moved from the
components into `tutor_core.prompts`, `.groq`, `.vocab`, `.story`; components became thin wrappers; tests and scripts changed only their
import paths. After it: root 17/17, API and core unchanged. Equivalence was measured against the original `story_tool.py` taken from git:
both classic templates byte-identical, 162 `build_story_prompt` combinations identical under identical randomness (an unseeded
comparison showed 51 differences, which were the code's own random topic choice, not the move), and `describe_prompt`, `choose_topic`,
`choose_story_type`, `extract_final_passage`, `normalize_language` identical.

**Commit 2, behaviour:**
- `tutor_core.vocab`: per learner and language on `tutor.words` (`add_word`, `load_words`, `sample_words` with the 150-word cap from `MAX_PROMPT_WORDS`);
  an unknown learner or language is refused, never created; the one word rule is still `tutor_core.words` (newlines collapse, bounded).
- `tutor_core.story.generate_story`: the cache key is (learner, language, type, topic) (it was the language alone: one learner's story could be served
  to another); returns the type and topic used and how many words went in; the enabled-language gate is inside it (as designed), so Story Studio and chat obey it equally.
- `tutor_core.tools`: what the tools do. **Fail closed**: without a usable `learner_id` the tool says so and touches nothing; ids are ASCII digits only; a
  learner id that is sent but malformed is refused even in dev mode; only a request that sends NOTHING may use `TUTOR_DEV_USER_ID` (empty in compose by default).
  Unexpected errors reach the learner as their type only, never connection details.
- `tutor_core.db` and `.groq`: no credentials, host or model name left in the code (`DATABASE_URL`, `GROQ_API_KEY`, `GROQ_MODEL`).
- Components: hidden `learner_id` and `active_language` inputs (text fields, advanced, not tool-mode), so the Agent still sees exactly one argument per tool;
  the Agent-facing tool descriptions and argument definitions are byte-identical to the originals (checked against git), because Step 10 measured routing with them.
  The reply now names the language ("Added 'bread' to your Spanish vocabulary").
- API client: the language tweak is `active_language` (the story tool already has a visible `language` argument); the tools' own refusal messages are flagged as failures in the trace.
- `flows/language-tutor.json` synced by the new `scripts/sync_flow_nodes.py` (code, hash, hidden field templates); `--check` and tests catch drift between canvas and repo.
- `langflow/Dockerfile` (base pinned to 1.12.2; installs `tutor_core` into the interpreter Langflow runs on, then imports it as the runtime user so a bad build fails), compose builds it, passes
  `DATABASE_URL`, `GROQ_MODEL`, `MAX_PROMPT_WORDS`, `TUTOR_DEV_*`, and makes langflow wait for the api (which runs the migrations that create the `tutor` schema).
- `scripts/run_routing_tests.py` now runs as THROWAWAY learners (one seeded in English, Spanish, French and Japanese, one empty), sends each request through tweaks
  (the production mechanism), and deletes them in a `finally`; the snapshot/restore of a real vocabulary is gone (`--cleanup-leftover` replaces `--restore-leftover`).
  `scripts/run_story_batch.py` takes `--learner-id` and uses that learner's own list per language (old result files still re-score). `scripts/m3_check.py` is the new live acceptance check.

**Where the removed tests went** (all cases kept): `test_add_word`, `test_add_word_normalization`, `test_word_loader` -> `api/tests/test_tutor_core_vocab.py`,
`test_tutor_tools.py`, `tutor_core/tests/test_word_normalization_cases.py`; `test_story_tool`, `test_empty_response_handling` -> `api/tests/test_tutor_core_story.py`,
`test_tutor_tools.py`, `tutor_core/tests/test_groq_request.py`; the two pipeline cases in `test_story_prompt_language` and `test_story_variety` -> the same files. Cases with no
equivalent anymore: "the table does not exist" (the schema comes from migrations).

**Verified here** (real Postgres 16, Python 3.12): root tests **16/16** (the 17 of the baseline, minus 5 replaced by per-learner tests, plus 4 new), API **397 passed + 3 skipped** (was 191), `tutor_core` **59** (was 32), host script tests 4/4, web 77 and type check unchanged. New tests were written first and mutation-checked: breaking each of these made a test fail
(load ignoring the learner or the language, add writing to learner 1, cache key without the learner or without the language, word cap ignored, a malformed id falling back to the dev user, a
learner id accepting unicode digits, a story for a missing learner, error detail leaking, the client sending integers or raw tool names). Gaps found and fixed by that process: dev-fallback behaviour for non-string ids.
`scripts/m3_check.py` was itself tested as a command against a fake Langflow that runs the REAL tools on the REAL database: it passes a healthy flow and fails flows whose tools ignore the learner, whose Agent
controls the learner, whose Agent never calls a tool, or that leave the developer fallback on; a failing request is an ERROR for its step only; it always cleans up. That test found a bug in the script (it
judged a learner's whole list rather than what was added).

**Not verified (needs your machine):** the image build; the container-side tests under Python 3.14.7; `m3_check.py` and the routing matrix against the live Agent; whether the Agent still routes as well with the unchanged tool text
(the routing run answers that). **Open decisions** are in design section 17A, the important one being that the non-English story prompt still calls the vocabulary list English.

## Unreleased — M0: PLAN A VERIFIED (node-id key) on Langflow 1.12.2

**Third live run** (`SpikeWhoAmI-KuKYY`, 2 users, learner ids as strings): control PASS, parallel PASS, overlap PASS, override PASS,
Plan B evidence PASS. The raw file confirms it: learners 101 and 102 ran their tool calls on different threads with windows
overlapping 1.463 s of 1.500 s, and each tool call saw exactly its own `learner_id` and `language`; with no tweaks the tool saw
`NONE`; the override attempt (asking the Agent to use user 999) still ran as learner 7, and the only argument the Agent could give
the tool was `note`, since the hidden inputs are not in the tool's schema. The tool reported one call per request even though the
response lists the tool block twice, so counting it once is right. The session id is readable from the graph, so Plan B stays
available as a fallback.

**Decision:** Plan A. The hidden inputs are `learner_id` (a string) and `language`, addressed by node id. `LANGFLOW_TWEAK_KEYS`
now defaults to `AddWord-WhP5g,StoryGeneratorTool-RQpvc` (node ids in `flows/language-tutor.json`), the style that was verified; the
display-name key (`"Who Am I (spike)"`) is not yet verified under the string-id fix. Node ids stay put while a flow is edited, but
re-check them after re-exporting a flow.
**Three things the spike taught us, all fixed or recorded:** (1) never name a hidden input `user_id` (Langflow reserves it); (2) send
the id as a string (Langflow silently drops anything else on a text field); (3) Langflow reports tools by snake_case name
(`spike_who_am_i`, so `add_word`), not the canvas name: `langflow_client.canonical_tool_name` maps `add_word`, `AddWord`, `Add Word`
to "Add Word" and `story_generator_tool` to "Story Generator Tool", otherwise the page would have shown "Used add_word" and a
successful word add would not have refreshed the vocabulary list. Reverting each of these makes tests fail.
**First real fixture:** `api/tests/fixtures/langflow/whoami_run.json` (one edit: the Langflow account UUID zeroed), with a real-data
test (reply path, one call from two blocks, name, arguments). Greeting, story and stored-messages fixtures are still to capture.
**Still open in M0:** the display-name key under string ids; `scripts/capture_fixtures.py --probe-delete` (what Langflow stores, and
whether a learner's chat can be deleted); which model actually answers (the Agent node names a Gemini model, the edge wires the Groq
node; this response does not say; check Groq's usage page or Langflow's logs); then M3 (tools read `learner_id`, fail closed).

## Unreleased — M0 second live run: Langflow silently drops a non-string tweak on a text field

**Run:** `SpikeWhoAmI-KuKYY`, 2 users, `--pause 30`. The control passed (no tweaks: `learner_id=NONE`, so the canvas node has the
`learner_id` code and the tool fails closed). The parallel and override checks failed: the tool saw `learner_id=NONE` while `language`
arrived correctly **and differently per request**: users 101 and 102 ran at the same moment (tool windows overlapping by about 10 ms)
and each got its own language (`es`, `fr`) on a different thread. No 429 this time (`--pause` worked).
**Cause (from Langflow 1.12.5's source, `graph/vertex/param_handler.py`; your container is 1.12.2, so the string run confirms it):** for a
`str` field the value is matched against a list, a string or a `Data` object only. Anything else, such as the integer
`learner_id` we sent, matches no case and is silently dropped (no error, no warning). The component itself handles integers fine
(checked by instantiating it under lfx), so the loss is in the graph, not in our code.
**Fix:** learner ids are sent as strings (`"101"`): `spike_tweaks.py` (default; `--int-ids` reproduces the drop; `--string-ids` still
accepted), and `langflow_client.build_tweaks`. The M3 tools take the string, convert with `int()` and refuse anything else.
Tests: the fake Langflow now drops non-string tweaks the same way; a CLI test shows `--int-ids` failing and the default passing; an
API test asserts every tweak value is a string (reverting the client to integers fails 6 tests).
**Design note:** the drop is why the fail-closed rule matters: the tool saw nothing and acted as nobody, instead of guessing.
**Plan A status:** still not proven for `learner_id`. Next run: strings, expecting PASS on control, parallel, overlap and override.

## Unreleased — fix: `spike_tweaks.py --pause` was not registered

**Bug (mine):** patch 3 documented and used `--pause` but never registered it with the argument parser (a search-and-replace
silently matched nothing), so the first real run died with "unrecognized arguments" and, had it parsed, `args.pause` would have
raised. The unit tests called `run_suite()` directly and never `main()`, so nothing saw it.
**Fix:** the option is registered, plus `--out-dir`. **Gap closed:** `tests/fake_langflow.py` (a fake Langflow on a real local
socket, with a switch that reproduces the first live run's shadowing bug) and `tests/test_cli_end_to_end.py`, which run
`spike_tweaks.py` and `capture_fixtures.py` as subprocesses with the exact options a person types: parser, HTTP, API-key creation,
output files, exit codes. Removing `--pause` again makes them fail. `make test-scripts` runs them (and is part of `make check`).

## Unreleased — M0 first live spike run: the hidden input must not be called `user_id`

**Found (first run against Langflow 1.12.2):** with no tweaks, and with tweaks, the tool reported a UUID where the learner id should
be, while `language` arrived correctly. Langflow gives every component a read-only `user_id` property that returns the id of the
Langflow **account** running the flow (the owner of the API key), and it shadows an input of the same name (confirmed in
`lfx/custom/custom_component/custom_component.py`: `def user_id(self)`). Names reserved on a component: `trace_name`, `graph`,
`user_id`, `flow_id`, `flow_name`, `tracing_service`, `tree`, `template_config`, `enabled_tools`, `ctx`.
**Fix:** the hidden input is `learner_id` everywhere: `spike_whoami.py` (which also reports `langflow_user`, the shadowing value, as
a diagnostic), `scripts/spike_tweaks.py`, and `langflow_client.build_tweaks`, which would otherwise have sent a field the real tools
could never read. Live chat was off by default, so nothing leaked. The design's Plan A text and the M3 tool work use `learner_id`.
Regression tests: the account id is never treated as a learner, and the client never sends `user_id`.

**Evidence so far:** the `language` tweak reached the tool under both key styles (node id `SpikeWhoAmI-KuKYY` and display name
`Who Am I (spike)`), so tweaks do arrive; and `self.graph.session_id` equalled the session id the API sent, so Plan B is possible.
Plan A itself is **still unproven**: isolation under parallel load has not yet been seen to hold, because the first run tested the
shadowed field and the second hit Groq's rate limit.

**Found (Groq free tier):** `openai/gpt-oss-120b` allows about 8000 tokens per minute, and one Agent turn costs a couple of thousand,
so roughly three or four chat turns a minute across ALL learners. The AI gate limits concurrency (2 at once) but not tokens per
minute, so it cannot prevent 429s. A token-budget limiter, or a larger Groq tier, is needed before live chat; not built yet.
`spike_tweaks.py` gained `--pause` (waits between phases and keys), defaults to 2 users, and explains a rate-limit failure instead
of reporting it as an isolation result.

## Unreleased — M5 groundwork: chat that does not depend on M0's answer

**Added (API):**
- `POST /api/chat` (`routes/chat.py`): login required; the learner's id comes from the session cookie and is never read from the
  body; the Langflow session id is built on the server as `u<user id>-<32 hex from the browser>`, so a learner cannot name another
  learner's conversation; messages are trimmed, 1 to 2000 characters; language must be supported.
- `services/ai_gate.py`: at most `AI_GATE_SLOTS` (default 2) AI calls at once across all learners and one per learner; a caller who
  cannot get a slot within `AI_GATE_WAIT` seconds gets `tutor_busy` (429, Retry-After). Tested with real threads.
- `services/langflow_client.py`: builds the run payload (numeric user id, language and session id only; a test proves no email, name
  or password can reach Langflow), reads the reply and tool calls from the run response and, if none, from the stored messages
  (parsing ported from `scripts/routing_checks.py` and the relay), flags failed tools, maps failures to `langflow_unavailable` (503),
  `ai_failed` (502) and `tutor_busy` (429) with learner-safe messages. Whether tweaks are sent is `LANGFLOW_TWEAK_KEYS` (empty = Plan B).
- `services/chat_stub.py` (`AI_MODE=stub`): deterministic stand-in so the whole Chat path works without Langflow or Groq; its Add Word
  really writes to the calling learner's own list.
- Settings and compose variables: `LANGFLOW_URL`, `LANGFLOW_FLOW`, `LANGFLOW_API_KEY`, `LANGFLOW_TWEAK_KEYS`,
  `LANGFLOW_PER_USER_TOOLS`, `AI_GATE_SLOTS`, `AI_GATE_WAIT`, `LANGFLOW_TIMEOUT`.
- **Live chat is OFF by default.** Until `LANGFLOW_PER_USER_TOOLS=1`, `/api/chat` in live mode answers 503 "not switched on yet": the
  flow's tools still read one shared word list, so answering would mix learners' vocabulary. The flag is the operator's statement
  that M0 and M3 are done.
- `.env.example` (it was referenced by the README and this changelog but missing from the repository).

**Added (web):** the Chat page (`routes/Chat.tsx`), `chat/ChatContext.tsx` and `chat/ToolTrace.tsx`. The conversation is held in memory
only (never localStorage, sessionStorage or the URL) under the per-user key, so the next person on the browser starts empty. The
call goes through a React Query mutation so a 401 (`session_changed` after another tab logged in) reaches `AuthProvider`: found by
a test that failed, then fixed. Enter sends, Shift+Enter is a new line, and Enter does not send while an input method is composing
(Japanese, Chinese, Korean). One request at a time, a "still working" note after 8 s, Try again on a failed message, New chat starts
a new session. A successful Add Word refreshes the vocabulary queries and the language list.

**Verified:** API 176 passed and 3 skipped (the skips are the real-fixture tests, waiting for `scripts/capture_fixtures.py`); core 32;
web 77 (was 56); type check and production build clean. Test-first, and mutation-checked: each of these broken on purpose made a
test fail (user id from the body, session id without the user prefix, stub writing to user 1, email in the payload, user lock never
released, conversation in localStorage, provider not keyed by user, failed Add Word refreshing, new session id every message). Two
mutants first survived and showed real test gaps (a user-1 fixture coincidence; no test of the two-tabs path); both were fixed.

**Not verified:** anything against a live Langflow or Groq; the browser (Playwright could not be installed in the build sandbox), so
the end-to-end and accessibility scans of `/chat` have not run (white text on the brand-coloured bubble is the thing to watch); the
privacy page still says chat is "not available yet", which is true while live chat is off and must change, with a policy version
bump, before it is switched on.

## Unreleased — M0 groundwork (spike built, not yet run against a live Langflow)

**Facts recorded:** Langflow **1.12.2**, Python **3.14.7** inside the image (`langflow --version`, `python --version` in the
container). `tutor_core` declares `requires-python >=3.10`, so it is compatible. The exported flow (`language tutor`, node ids
`AddWord-WhP5g`, `StoryGeneratorTool-RQpvc`, `ToolResultRelay-G5PjB`, ...) matched the repo: every component's code on the canvas
was identical to `custom_components/`, and the Agent instructions matched `docs/AGENT-INSTRUCTIONS.md`.

**Found:** the exported flow contained a live Groq API key in the Groq model node. The key was rotated; the copy kept in the repo
has the field empty. `endpoint_name` was empty, so the flow could not be run by name. The Agent node's own model field names a
Gemini model while the edge wires in the Groq node (assumed to win; the first live run must show which model answers).

**Added:**
- `flows/language-tutor.json`: the flow, key removed, `endpoint_name` set to `language-tutor`.
- `custom_components/groq_language_model.py`: an empty key field now falls back to `GROQ_API_KEY` (the flow file ships without a
  key). The component code embedded in the flow file and its `code_hash` were updated to match. `tests/test_groq_language_model.py`.
- `docker-compose.yml`: Langflow pinned to `1.12.2` (was `:latest`), `./flows` mounted, `LANGFLOW_LOAD_FLOWS_PATH=/app/flows`.
- `custom_components/spike_whoami.py`: a throwaway tool with hidden `user_id` and `language` inputs (tool mode off) that reports what
  it received, holds 1.5 s so parallel calls overlap, and reports the session id as the graph sees it (Plan B evidence).
- `scripts/spike_tweaks.py`: control (no tweaks), parallel (several users at once), and override (the Agent is asked to use user 999)
  for each tweaks key style; sequential success is reported INCONCLUSIVE, never PASS. `tests/test_spike_tweaks.py` drives it against
  a fake Langflow in correct and deliberately broken forms (shared state, ignored tweaks, no overlap, Agent skips the tool, Agent
  obeys the override, request errors).
- `scripts/capture_fixtures.py`: saves real run and stored-message responses for the `langflow_client` fixtures (key-shaped values
  redacted) and, with `--probe-delete`, tests whether a session's stored messages can be listed and deleted through Langflow's
  monitor API. `tests/test_capture_fixtures.py`.

**Verified here:** the three new test files and the Groq component test pass (standard library only). **Not verified:** everything
that needs a live Langflow or Groq: that the `1.12.2` image tag exists, that `LANGFLOW_LOAD_FLOWS_PATH` loads the flow, that tweaks
reach tool components (by id or by name, integer or string ids), that `self.graph.session_id` exists, and the monitor delete
endpoints. Plan A or B is decided by running `scripts/spike_tweaks.py`; the result goes here.

## Unreleased — Web app adapted to the Step 10 results

The remote moved while the web app was being built (`eace656`: patch files and caches untracked, `.gitignore`;
`3c67c80`: Step 10 complete, story variety). The web app commits were rebased onto it (conflicts only in `.gitignore`,
`README.md` and this changelog) and adapted:
- **Languages:** stories are now enabled for Spanish, French and Japanese (measured 30/30 in the requested language;
  15/15 through the Agent). German, Italian, Portuguese, Chinese and Korean stay off until measured. The flag is in
  `tutor_core/languages.py` with the evidence in a comment, and the tests changed accordingly.
- **Story types:** the design's `style` (narration/dialogue) became `story_type` (eight types) plus `topic`, matching
  `story_tool.py`; the quality report rules follow the owner's decision (≤ 5 strays, 4–10 sentences).
- **Seed:** the demo account now also loads `sample_data/suggested_words.csv` (the owner's remedy for samey stories).
- **Docs:** design section 18 lists every change and why; Step 11 is described as delivered by the web app.
Verified after the rebase: 32 core + 90 API + 56 web tests and the API-types check. The Langflow-container test scripts
under `tests/` cannot run outside the Langflow image (they import `langflow`), so they were not run; no web app commit
touches them.

## Unreleased — Email sign-up, privacy policy, Settings, dark mode, dialogs

- **Accounts are now identified by name and email** (the separate username is gone, so the policy's "only name and email"
  is true). Sign-up needs an explicit privacy-policy checkbox; the date and policy version are stored. Migration 0003
  gives existing development accounts a placeholder `<name>@legacy.invalid` address and no consent record.
- **Privacy Policy** page (`/privacy`, public) written to match what the code does; design section 12B maps each claim to
  the code and test that keep it true, lists the operator's checklist, and says plainly that it is a template, not legal advice.
- **Settings:** edit name and native language; change email and password (current password required; wrong guesses share
  the login lockout; a password change logs out other devices); Light/Dark/System; **Download my data** (JSON of
  everything held, a test fails if a future table is left out); **Delete account** (password required, permanent,
  every table cascades; other tabs are logged out; the email can be reused).
- **Dark mode** with no white flash (script before first paint), following the OS or an explicit choice.
- **Styled confirmation dialogs** on the browser's `<dialog>` (replaces the plain `confirm` box); Cancel is focused first.
- Verification: 90 API tests, 56 web tests, 27 real-browser tests (including an axe accessibility scan of every screen and
  dialog in both themes), and 16 deliberate breakages: 14 were caught at once, 2 survived until their tests were rewritten.

Bugs found by the new tests: sign-up **without** the `accept_privacy` field created an account with no consent (a Pydantic
default skips the validator; the field is now required); the dialog's "focus Cancel first" never worked (React `autoFocus`
runs while the dialog is closed), now focused after opening; light-theme muted text was 4.43:1 and 4.46:1 on tinted
backgrounds; two tests proved nothing until rewritten (the "no flash" test could not see a flash, and "Cancel cancels" was
untested).
Not done: forgot-password (no email sending), non-ASCII email addresses, re-accepting the policy when its version changes,
and the check that names/emails never reach the AI prompts (chat and stories do not exist yet; required for M5/M6).

## Unreleased — User separation hardening and UI polish

**Security (audit found 6 gaps beyond the per-user query filters; all fixed, each with a test):**
- Logout only deleted the browser cookie; the token stayed valid for 8 hours. Sessions are now server-side
  (`tutor.sessions`, migration 0002): logout, "Log out everywhere" (`POST /auth/logout-all`), a new login over an old
  one, and user deletion all revoke immediately.
- API responses had no cache headers: now `no-store`, `Vary: Cookie`, `nosniff`, `X-Frame-Options: DENY` on every response,
  including errors and CSRF refusals.
- Two tabs share one cookie: a tab showing A could act as B after B logged in elsewhere. Requests now carry
  `X-Expected-User`; a mismatch is refused (`401 session_changed`) and the tab drops A's data and adopts the real user.
  Tabs also notify each other of login/logout.
- Cached queries are keyed by user id; logout/user change/401 empties the cache first-thing; Back after logout reloads.
- nginx serves a strict CSP (no inline scripts or styles) and clickjacking protection.
- A test now fails automatically if any new route is added without a login check.
- Verification: 53 API tests (11 deliberate breakages, each caught), 31 web tests (6 breakages, each caught; one survivor
  led to an extra test), and 9 real-browser (Playwright + Chromium) tests against real nginx + API + Postgres, with
  3 more breakages confirmed to fail them. See design section 12A for the threat table and the known limits.

**Style:** new design tokens, Inter font (self-hosted), icons, two-row header, polished login/home/vocabulary/settings,
toasts, skeletons, empty states. Seeing the real render found and fixed black table borders, a pink "disabled" delete
button, a header that wrapped badly at 1280 px, and light-grey icons below 3:1 contrast. Details: `docs/STYLE-GUIDE.md`.

Found while testing: `app.routes` no longer lists included routers in current FastAPI (route enumeration now uses the
OpenAPI schema); TypeScript 7 still unusable with `openapi-typescript`. Playwright specs run here against a Chromium
bundled in an npm package, not the usual `playwright install` build.

## Unreleased — Web app, first slice (M1, M2, M4; M0 and M3 not started)

Built: `tutor_core/` (language codes, one word-validation rule), `api/` (FastAPI, Alembic schema `tutor`, accounts,
vocabulary, CSV upload, typed errors, CSRF guard, login lockout, seed script), `web/` (React + TypeScript + Tailwind:
login/register, protected routes, per-user language, Vocabulary page, Settings), Dockerfiles, nginx, compose,
`.env.example`, `Makefile`. Verified here: 32 core + 36 API (real Postgres 16) + 20 web tests, API-types drift
check, and a curl session through the real nginx config. **Not verified:** Docker builds, the compose file, any
Langflow behaviour, any browser rendering (no browser available).

Found while testing (and fixed):
- Logout kept showing the previous user: `queryClient.clear()` detaches the `me` query from its observer.
- The word validator does not stop a short letters-only prompt-injection phrase (design wording corrected).
- `openapi-typescript` crashes on TypeScript 7; pinned to 5.x.
- Isolation tests were mutation-checked: removing the per-user filter from list, delete or edit makes them fail.

Left as they were: Langflow still on `:latest` with `admin123` (defaults overridable from `.env`, port now bound to
localhost) and the `../shared-components` mount. Postgres password defaults stay `langflow` so an existing volume
keeps working. Root `*.patch` files remain tracked (now git-ignored for future ones); `__pycache__` and
`relay_debug.log` were untracked.

## Unreleased — Web app design v4 (hardening pass)

Revised `docs/WEB-APP-DESIGN.md` (v3 to v4) before any code is written; section 17 of the doc has the full
34-row list of what changed and why. The most important fixes:
- **Data leaks:** the story cache is keyed by (user, language, style) and used only on the Agent path (it was
  keyed by language alone); Langflow tools fail closed when no `user_id` arrives; the client no longer supplies the
  quality report; query cache and storage are cleared per user on logout.
- **Unverified Langflow assumptions** are now an explicit **Milestone 0** (tweaks with a parallel two-user test,
  endpoint-name runs, flow auto-load via `LANGFLOW_LOAD_FLOWS_PATH`, real-response fixtures), with a written fallback.
- **Model:** ISO language codes instead of free text, a per-language "stories enabled" gate tied to measurement,
  schema `tutor` with Alembic, one word-validation rule (limits prompt injection, does not eliminate it), `meaning` instead of
  `meaning_en`, German keeps capitals.
- **Quality report** states which checks apply per language (strict for English only) and moves to `tutor_core`.
- **Operations:** pinned Langflow, Postgres healthcheck, root build context for `tutor_core`, localhost-only ports,
  `.env.example`, nginx timeout above the 60 s AI deadline, an AI gate for the shared Groq limit.
- The duplicate root copy of the design doc was removed; the canonical file is `docs/WEB-APP-DESIGN.md`.
- Research note: Langflow tweaks (by component ID or name), `LANGFLOW_LOAD_FLOWS_PATH` and the 1.12.x
  `LANGFLOW_TWEAKS_POLICY` were checked against Langflow's docs; behavior with this project's Agent Tool Mode is
  still untested and is the first thing M0 settles.

## Unreleased — Story variety measured; measurement fixes

**Measured (20 English stories, 10 each Spanish/French/Japanese, `--delay 3`):**
- Variety: mean overlap **0.24** (target ≤ 0.30, was 0.44), **6** distinct types (target ≥ 6),
  most common opening **20%** (target ≤ 20%, was 44%).
- **Not met:** the most repeated vocabulary word is still in **100%** of stories ("water"; the model
  stuffs the whole word list into every story), and the English pass rate is **2/20** at ≤ 5 stray
  words. New-type stories have 29% of their words outside the vocabulary (classic: 3%); the topic
  seeds force new nouns, and the model ignored "at most 5 everyday words". Most strays are verbs the
  starter vocabulary lacks.
- Non-English language stays correct (27/27 generated); the Spanish and French samples are the most
  natural stories so far. Latency p50 0.8–2.6s.
- 3 of 10 Japanese stories failed to generate (about 3.4s each), probably rate-limit retries running
  out under `--delay 3`; **cause unconfirmed**.

**Fixed (tests first):**
- Japanese/Chinese sentences ending in 。！？ with no space were counted as one (false "off-length").
- A narration line like "Marc dit : ..." was taken for a speaker label (false "bad format").
- Names that only start sentences (Sam, Maya, Anna) were counted as stray words.
- The batch runner now records the model's error (type and message, or "empty response") on every
  failed generation, so the next failure can be diagnosed.
Corrected scores: French 10/10 (was 9/10), Japanese 7/10 generated (was 6/10), English strays
14.25 → 13.65 per story.

**Next (in the test plan):** add `sample_data/suggested_words.csv` and re-run the English batch with
`--delay 10`; if one word still dominates, sample focus words per story; then vocabulary-fit topics.

## Unreleased — Story variety (tuning change #2)

**Why:** the owner found stories too alike: mostly conversations, the same words, the same shape.
Measured on 48 stories: 81% mention water, about 75% are somebody asking for something, mean
overlap 0.44 between English stories, "today" in 100%, 44% opening "Hello, I am...".

**Changed (`story_tool.py`, tests first):**
- Six new story types (a story with a problem and an ending, diary, letter, place description,
  daily routine, funny anecdote) next to the two classic styles, drawn at random with
  conversations about 19% of the mix. The classic templates are untouched (checksum pins still pass).
- A topic seed from 21 topics, chosen in code, never repeating the last 8.
- A looser word rule for the new types: the vocabulary stays central, plus grammar words, simple
  verbs and at most 5 very common everyday words; 6–9 short sentences of up to 12 words.
- `generate_story_for_learner(..., story_type=None, topic=None)`; explicit requests are cached
  separately, the random default keeps the plain language key. `describe_prompt` recovers the type
  and topic from a prompt.

**Measuring (`scripts/`):** `variety_report` / `format_variety` (distinct types, mean overlap of
content words, most repeated vocabulary word, most common opening); the batch runner records each
story's type and topic, prints the variety line (also for `--rescore`) and has `--story-type`.

**Decision change (owner's request):** pass rule is now ≤ 5 stray words (was 2) and 4–10 sentences
(was 4–8); `--max-oov` defaults to 5 in the batch runner, checker CLI and routing tests. Earlier
runs can be re-scored with `--max-oov 2`.

**Added:** `sample_data/suggested_words.csv` (50 verbs, nouns and adjectives to add for more
varied stories) and `tests/test_story_variety.py`. Targets and the before/after procedure are in
`docs/STEP-10-TEST-PLAN.md` (tuning change #2).

**Not measured yet. Not changed:** the Agent-facing tool still takes only `language` (exposing a
type and topic is a separate change that needs a routing re-run); `story_prompt_builder.py` (Step 8
canvas pipeline) keeps the old templates.

## Unreleased — Step 10 complete

**Final routing run through the Agent (45 turns, after replacing the canvas nodes):** 43 passed.
Tool 42/42, argument 36/36, relay 36/36, empty-vocabulary guard 3/3, Add Word wording 9/9 (the
case-variant case A3 now passes), language switching passed in all 3 repeats, and **15/15
non-English story turns were in the requested language** (Spanish, French and Japanese, plus the
Spanish and French turns of the switching sequence). The 2 failures were English stories with 3–4
everyday stray words (the rule tolerates 2). Turn latency p50 3.0s, p90 5.0s, max 8.7s.

**Confirmed:** every tool call used to appear twice in the saved results because of the parser; 37
of 38 tool turns now show one call. English stories 41/48 (85%) overall.

**Result:** all seven criteria in `docs/STEP-10-TEST-PLAN.md` are met, and the LO 8 verdict (cost,
latency, quality, rate limits) is final. Step 10 is done; Step 11 (per-learner vocabulary) is next.

## Unreleased — Step 10: language fix measured, LO 8 verdict drafted

**Measured (Groq `gpt-oss-120b`):**
- **Non-English stories in the requested language: 5/15 → 30/30** (Spanish 10/10, French 10/10,
  Japanese 10/10) after tuning change #1. Structure was also 30/30 and the read samples were
  natural. The prompt change did three things at once (translate-the-meanings rule, no English
  example, normalized language name), so the run cannot attribute the gain to one of them.
- **English: 9/10** in a back-to-back burst (`--delay 0`), 34/39 (87%) across all English runs.
- **No failures in 60 story generations; no rate-limit effect in a 10-story burst** (p50 1.4s,
  p90 2.0s, same as spaced runs).

**Fixed:** the batch summary printed "Written in the requested language: 10/10" for English runs,
which are not language-checked. The line now appears only when some passages were checked and
counts only those (test first).

**Docs:** results, criteria status, the filled tuning-log row, and a draft LO 8 verdict (cost,
latency, quality, rate limits) in `docs/STEP-10-TEST-PLAN.md`. Remaining for Step 10: replace the
Add Word and Story Generator Tool canvas nodes and re-run the routing suite once through the Agent.


## Unreleased — Web app design (React)

Added `docs/WEB-APP-DESIGN.md`: a design for a local demo web app (not hosted) around the tutor.
- **Stack:** React + TypeScript (Vite, React Router, TanStack Query, Tailwind), a small FastAPI
  backend, the existing Langflow flow as the AI layer, Postgres, Groq. React cannot hold the Groq or
  Langflow keys or reach Postgres, so it talks only to the API.
- **Two backend paths:** chat goes through the Langflow Agent (exact output via the Tool Result
  Relay); vocabulary, stories and practice call shared Python (`tutor_core`) directly.
- **Login:** local accounts, bcrypt, JWT in an httpOnly cookie; every query filtered by the user.
- **Target-language vocabulary:** `words` gains `user_id` and `language` (unique per user,
  language and word); stories use the words directly.
- Includes architecture, auth and chat sequence diagrams, an ER diagram, an API table, wireframes,
  code structure, testing strategy, milestones and risks. Streamlit was considered and dropped.
- Open items it depends on: exporting the Langflow flow into the repo, extracting `tutor_core`,
  passing the user id to Langflow tools (verify Langflow `tweaks` with Agent Tool Mode).

## Unreleased — Step 10: language-aware story prompt (tuning change #1)

**Why:** only 5/15 non-English stories were written in the requested language. Two probable
causes: the vocabulary list is English and "use words from this list" keeps the model in English;
and the tone examples in the prompt are English, which primes English output.

**Changed (`story_tool.py`, tests first):**
- For any language other than English, the prompt opens with a language rule (write the entire
  story in the language; the list is English *meanings* to express in it; no English words left in;
  names excepted), ends with a final-check reminder, and the English tone example is left out.
- `normalize_language`: a language given by its own name is mapped to its English name
  ("日本語" → Japanese, "español" → Spanish, "français" → French, ...), used in the prompt and as
  the cache key (so "日本語" and "Japanese" share one cached story).
- **English prompts are unchanged**, pinned by SHA-256 of both templates in the tests, so the
  English baseline (85%) is not put at risk.

**Tests:** `tests/test_story_prompt_language.py` (no database). The existing database-free story
tests still pass.

**Not measured yet.** Run the baseline batch before applying, the same batch after, and record both
in the tuning log in `docs/STEP-10-TEST-PLAN.md`.

**Not changed:** `story_prompt_builder.py` (Step 8 canvas pipeline) keeps the old templates;
its drift from `story_tool.py` is on the deferred list.

## Unreleased — Step 10: first live routing run, language check, runner fixes

**Live result (45 turns on the real flow):** right tool 42/42, right argument 36/36, reply
identical to the tool output 36/36 (the Relay), language switching 12/12, empty-vocabulary guard
3/3, English story quality 8/9. The harness, the Relay and the language-switching fix all work.

**Found: non-English stories were mostly not in the requested language.** The structure-only
check passed them. Reading the replies: 2/3 "Spanish" and 3/3 "Japanese" stories were English, and
all French stories had English words left in. Re-scored, only 5/15 were in the right language.

**Added (tests first)**
- `language_check` in `scripts/vocab_adherence.py`: non-Latin languages must be mostly in their
  script; other languages must have a low share of English words (grammar words plus the
  vocabulary; ambiguous ones like "no", "a", "me" excluded): ≥ 50% English = "english", ≥ 20% =
  "mixed". Used by `check_passage(language=...)`, the batch runner (`--languages Spanish,French`),
  `--rescore` and the routing tests; the summary reports "written in the requested language".
  Tested on the real outputs from the run. Thresholds separate real data cleanly (good Spanish and
  French 0.00–0.05, mixed French 0.25–0.29, English 0.66–0.72).
- Routing cases for non-English stories now name their language.

**Fixed in the runner**
- `--repeat`: the throwaway word is removed before every repeat (it only was at the end, so A1
  failed from the second repeat on) and case-insensitively.
- Tool calls listed twice in the response are collapsed by id; the id is saved in the results.
- Per-turn latency is saved and summarized.
- The runner's snapshot table is now `words_autotest_snapshot` (a manual `words_snapshot`
  backup no longer blocks a run), and restoring **merges** missing words back (`INSERT ... ON
  CONFLICT (word) DO NOTHING`) instead of replacing the table, so nothing added meanwhile is lost.

**Tests:** 74 checks in `test_vocab_adherence.py`, 40 in `test_routing_checks.py`, 23 in
`test_routing_runner_with_fake_langflow.py`.

**Config, not code:** the Add Word node on the canvas must be replaced with a fresh copy for the
normalization fix to apply (the first run showed "AutoTestApple" stored as a separate word).

## Unreleased — Step 10: automated routing tests

**Added (tests first)**
- `scripts/routing_checks.py` + `tests/test_routing_checks.py` (32 checks): parses a Langflow
  `/api/v1/run` response (final reply, tool calls in any nesting) and checks each turn: right tool
  (or none), right argument (case-insensitive, accepted alternatives such as "español"), reply
  identical to the tool output, add-word reply wording, English story quality (vocabulary, length,
  format) or structure only for other languages, and the empty-vocabulary guard.
- `scripts/run_routing_tests.py`: runs 12 cases (add word, duplicate and case variant, English /
  Spanish / French / Japanese stories, English→Spanish→English→French in one session, small talk,
  an unrelated question, a story request without a language, the empty-vocabulary guard) through the
  flow's HTTP API, with one fresh session per test, a report, and a JSON file of every reply.
  It logs in with the superuser from `docker-compose.yml` and creates an API key (or takes
  `--api-key`). It adds and removes a throwaway word and snapshots, empties and restores the
  vocabulary in a `finally` block; a leftover snapshot stops the next run until
  `--restore-leftover`. `--only`, `--repeat N`, `--delay`, `--list`, `--debug`.
- `tests/test_routing_runner_with_fake_langflow.py` (15 checks): runs the runner against a fake
  Langflow server on localhost. A healthy flow passes (exit 0); the Step 9 bugs (previous language
  reused, reply differing from the tool output) are caught (exit 1); the database is restored even
  after failing tests; a leftover snapshot is refused and can be restored.

**Not verified against the real Langflow:** the response shape and the authentication calls were
written from Langflow's documented API and a fake server. Run `--only N1,S1 --debug` first.

## Unreleased — Step 10: baseline measured, pass rule relaxed

**Baseline (20 English stories, Groq `gpt-oss-120b`, strict rule of 0 stray words):** 7/20 passed
(35%). All of the failures were vocabulary: 0 failures to generate, 0 leaked plans, 0 off-length
and 0 bad-format stories. Mean 1.30 stray words per story. Most common strays: bring, drink,
together, share, eat, sure, happily, offers, bake. Latency p50 / p90: 1.1s / 2.1s.

**Decision (owner):** the strays are ordinary everyday words, and the starter vocabulary has almost
no verbs, so a zero-stray rule was unrealistic. The pass rule is now **≤ 2 stray words per story**;
the strict rule remains available. This is recorded in the test plan so the target is not moved
silently.

**Added (tests first, 45 → 58 checks in `tests/test_vocab_adherence.py`)**
- Readability metrics: mean and longest words per sentence/line in every result and summary;
  `max_unit_words` / `--max-unit-words` enforces a limit when wanted.
- `rescore_results` and `run_story_batch.py --rescore FILE`: re-score a saved run under different
  rules, with no generation, no Groq calls, no database.
- `--max-oov` now defaults to 2 in the batch runner and the checker CLI (the `check_passage`
  function itself still defaults to 0).

## Unreleased — Step 10 in progress: measuring tools and test plan

**Added**
- `scripts/vocab_adherence.py` + `tests/test_vocab_adherence.py` (45 checks): scores a passage
  against the vocabulary. Handles inflections (plural, -ed, -ing, y→ies, doubled consonants),
  phrase vocabulary ("thank you"), grammar words and simple verbs the prompt allows, character
  names (speaker labels and capitalised mid-sentence words), contractions, sentence/line count
  (4–8), dialogue format, leaked planning text, and failure/fallback messages. Non-English
  passages skip the vocabulary check.
- `scripts/run_story_batch.py`: generates N stories per language through the production path
  (`generate_story_for_learner`, cache off), scores them, records latency, saves JSON. Wiring
  tested with fakes; not yet run against Groq.
- `docs/STEP-10-TEST-PLAN.md`: pass criteria fixed before tuning, a routing matrix (R1–R15),
  edge cases, the LO 8 write-up template and a tuning log.

**Fixed: Add Word created duplicate vocabulary.** The `words` column is `UNIQUE` but
case-sensitive, and only the ends were stripped, so "Water", "water" and "water." were separate
rows (and an Agent passing `'bread.'` stored the punctuation). `normalize_word` now lowercases,
collapses whitespace and strips edge punctuation/quotes; the confirmation shows the stored form.
Tests: `tests/test_add_word_normalization.py` (no database needed). Existing rows are not
rewritten.

**Findings so far (hypotheses to test, not conclusions)**
- The story prompt's own tone example uses words outside its vocabulary rule ("hungry", "shop",
  "bread", "eat", "happily").
- Rule 3 lists six simple verbs, but the example also uses "say"; the checker allows a few basic
  verbs by default and has a strict mode.
- The tool has no `style` input, so a request for a "dialogue" may return a narration.

## Unreleased — Step 9 complete

- **Fixed: language handling.** After a non-English story the Agent refused English ("I can only
  generate stories in languages other than English"), and a non-English request could return an
  English story. Nothing in the code rejected English; the Agent inferred it from the "target
  language" wording. Added an explicit instruction ("any language name is valid, including
  English ... use the language in the LATEST message"), removed the "call a tool at most once"
  rule (the Agent's leaked reasoning showed it confusing that rule across turns), and reworded
  the `language` input's description in `story_tool.py`. Verified: stories now come back in the
  requested language across a mixed sequence. Final instructions recorded in
  `docs/AGENT-INSTRUCTIONS.md`.
- **Recorded:** the story call and the Agent now both use `openai/gpt-oss-120b`; docs updated
  (the Step 8 canvas pipeline still uses 20b).
- **Skipped:** the planned 120b-vs-20b orchestrator A/B comparison. The Tool Result Relay made the
  Agent's reply text irrelevant to correctness, so the orchestrator only has to pick the right
  tool and argument.
- **Still to do:** a formal acceptance run (folded into Step 10) and an export of the canvas flow.

## Unreleased — Step 9: Tool Result Relay (verified in the Playground)

**Problem:** even with a working tool and strict Agent Instructions, the Agent sometimes
shortened the tool's output ("... Ben: Yes, we have water today — ..."), reworded it, or added
its own note. Several instruction rewrites did not stop it, because an LLM writes the Agent's
final reply and exact relay cannot be guaranteed by prompting.

**Added:** `custom_components/tool_result_relay.py`, placed between the Agent and Chat Output
(Chat Input → Agent → Tool Result Relay → Chat Output). If the Agent called a tool, the reply
text is replaced with that tool's own output exactly (last successful, non-empty call; errored
calls are skipped). If no tool was called, the Agent's text passes through. The Agent still
chooses the tool and its argument, so LO 5 and LO 6 are unaffected.

**Implementation notes:** the tool outputs are read from the Message's `content_blocks`
(`ToolContent.output`). The same Message object is returned, so Chat Output should update the
existing bubble instead of adding a second one, and the tool-call trace stays visible.

**Fix after first live run:** a debug log from the Playground showed the Agent message's
`content_blocks` is `[ToolContent, TextContent]` — the tool call sits *directly* in the list,
not inside a `ContentBlock` wrapper as the first version (and its tests) assumed, so nothing was
ever relayed. The extractor now walks both shapes. It also unwraps tool outputs recorded as
structured data (a dict with `text`, or a JSON/Python-repr string), while leaving plain stories
untouched. New tests use the real flat shape.

**Tests:** `tests/test_tool_result_relay.py` (20 checks; real Langflow `Message` / `ToolContent`
objects, no database or network).

**Verified in the Playground:** the chat reply now matches the tool's Result, including runs
where the Agent's own draft was garbled. Note: a canvas node keeps its own copy of a component's
code, so after updating the file, replace the node with a fresh Tool Result Relay.

## Unreleased — Fix: Story Generator Tool returned an empty string

**Symptom (Step 9 Playground):** the tool ran, but its output (Result) was empty. The Agent
then filled the gap itself: a made-up story, or a made-up error ("Invalid language specified.
Please provide a supported language.") that exists nowhere in the code.

**Root cause:** `openai/gpt-oss-20b` is a reasoning model, and hidden reasoning tokens count
against `max_tokens`. With `max_tokens=400`, 398 tokens went to reasoning, so Groq returned
`finish_reason: "length"` with `content: ""`. The empty passage was then cached as a *success*
for 20 seconds, so repeat calls got the same empty answer.

**Fixed in `story_tool.py`:**
- `max_tokens` 400 → 1500, and `reasoning_effort: "low"`, so the plan and passage fit after the
  model's reasoning.
- An empty or whitespace-only passage (including an empty passage after `===STORY===`) is now
  treated as a failure: the fallback message is returned and cached briefly, never an empty
  string.

**Tests:** `tests/test_empty_response_handling.py` (new; no Postgres needed).

**Note:** this is separate from the relay problem documented below. Earlier traces show the
Agent also discarding *successful* tool output, so that investigation continues. Re-run the
Step 9 test set now that the tool no longer returns empty results.

## Unreleased — Step 9 in progress: agent-based orchestration with a 120b orchestrator

**Why:** the deterministic keyword router (prototyped, not included in this repo) solved the reliability problem
(the Agent discarding tool output and substituting its own unconstrained story) but abandoned the
project's core teaching objective — demonstrating real multi-agent tool orchestration (LO 5,
LO 6). The tutorial's own agent instructions are nearly identical to what we'd already tried,
confirming its reliability came from using `gpt-4.1`, not a technique we were missing.

**Changed (canvas/UI only — no files modified):**
- Re-enabled Tool Mode on `Add Word` and `Story Generator Tool` (the code already supported
  this; the toggle had been turned off when we built the router).
- Added a second Groq model node ("Groq Orchestrator — 120b", model `openai/gpt-oss-120b`) as the
  default Language Model for the top-level Agent — a larger model for the orchestrator, since
  instruction-following under agentic tool use is where model size matters most.
- Kept the original Groq 20b node on the canvas, disconnected, for A/B comparison against the
  120b orchestrator using identical instructions and tools.
- Rebuilt the top-level **Language Agent**, with instructions matching the tutorial's wording:
  > "You will help the user practice their language skills... When using a tool, your
  > answer should just be the result from the tool and nothing else."
- Wired: Chat Input → Agent → Chat Output; Add Word + Story Generator Tool → Agent's Tools
  input; Groq 120b → Agent's Language Model input.

**Docs:**
- Rewrote the stale docs (`OVERVIEW.md`, architecture, class, concept, state, and workflow
  diagrams) to reflect Groq instead of Ollama/Hugging Face and the consolidated
  `story_tool.py`.
- Added `docs/IMPLEMENTATION-GUIDE.md` with per-step status and `docs/LEARNING-OBJECTIVES.md`
  (with implementation notes on LO 6 and LO 8, which changed from the original plan).
- Updated the README (current status, full project structure, complete test list).
- Added a "Known code issues" section to `DEVELOPER-DIARY.md`.

**Not changed:**
- `story_tool.py`'s internal story-generation call stays on `openai/gpt-oss-20b` — that call was
  never the source of the relay-reliability problem.
- The deterministic router approach is kept as a fallback if the 120b orchestrator still
  proves unreliable.

**Testing plan:** run identical requests (add a word, request a story in a named language, an
unrelated message) with the 120b orchestrator wired in, then swap to 20b and repeat, to compare
agentic obedience between the two model sizes on the exact same instructions and tools.

## 2026-10-02 — Reliability work and deterministic router (Steps 8–9)

- Consolidated the four-component story pipeline into `story_tool.py`, because Tool Mode returns
  only a component's own output (see `DEVELOPER-DIARY.md`).
- Added retry with backoff on Groq HTTP 429 (3 attempts, 1.5s).
- Added a short-lived result cache keyed by language (success 20s, failure 15s), because the
  Agent sometimes calls the story tool 3–5 times per request. Failures are cached too, so a
  rate-limited burst doesn't run the full retry loop on every call.
- Made an empty `language` argument fall back to English rather than raising, so the Agent
  doesn't give up on the tool.
- Built a deterministic keyword-based router with no LLM discretion,
  as a reliability fallback (later unwired, see above).

## 2026-09-25 — Story pipeline components (Steps 6–8)

- Added `word_loader.py`, `story_prompt_builder.py`, `story_guard.py`, and
  `final_passage_extractor.py`, each with tests written first.
- Prompt design iterated five times: forced every word in → "use words that fit" with coherence
  rules → hidden Character/Want/Event/Resolution plan behind a `===STORY===` delimiter, stripped
  in code → richer Event/Resolution shapes → random narration/dialogue styles, 5–6 sentence
  length, and word inflection.

## 2026-09-21 — Language agent and environment check (Steps 1–2, 4–5)

- Added `scripts/smoke_test.py` (Postgres + Groq reachability) and `docker-compose.yml` fixes:
  explicit Langflow superuser and a pinned `LANGFLOW_SECRET_KEY`.
- Added `upload_word_file.py`, `add_word.py`, and `groq_language_model.py`, with tests.
- Switched the model provider from the planned local Ollama to Groq (insufficient local
  hardware); replaced the deprecated Groq Llama models with `openai/gpt-oss-20b`.

## 2026-09-20 — Documentation

- Added `docs/` with the overview, user stories, and architecture, class, concept, state,
  use-case, and workflow diagrams.

## 2026-09-16 — Initial commit
