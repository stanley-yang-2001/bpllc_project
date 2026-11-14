# SOLID audit (14 November 2026)

Read-only review of `api/app`, `tutor_core`, `web/src` and `scripts`. Nothing was changed. The rule for every item below: **behaviour stays the same, the existing tests must pass unchanged (new tests only add), and each area ships as its own patch.**

## What is already good
- **Dependency direction is right:** `tutor_core` never imports `api`; routes call services; only one route (`health.py`) touches the database directly.
- **Dependency inversion is used where it matters:** the story writer, judge, clock, random source and HTTP transport are all passed in as callables (`call_groq_fn`, `judge_call`, `clock`, `rng`, `Transport`), which is why the stub stack and the fakes work. `make_story_llm` picks the model in one place.
- **No god files:** the largest source file is about 400 lines (a data file of grammar rules); the largest React file is 217 lines.
- **Open for extension in places:** badges, challenges and i18n catalogs are data tables (add a row, change no logic).

## Findings, ranked by value for the effort

| # | Principle | Where | Problem | Fix | Risk |
|---|---|---|---|---|---|
| 1 | **O**pen/closed, **S**RP | `web/src/routes/Practice.tsx` | The practice modes are a hard-coded `if/else` chain plus five inline tiles. Adding a mode means editing the mode type, the dispatch and the tile list; the page also owns picker state, progress queries and the tile markup (144 lines of JSX). | A small registry: each mode is `{id, icon, title, text, render, available}`; the page loops over it. Tiles move to their own components. | Low (page tests exist) |
| 2 | **D**RY, **S**RP | `Choices.tsx`, `Blanks.tsx`, `Dictation.tsx`, `PosPractice.tsx` | Four copies of the same state machine: `index / picked / right / record / think-timer / "score" screen / try again`. | One `useQuizRound` hook and one `QuizDone` component; each mode keeps only its own question view. | Low-medium |
| 3 | **S**RP | `web/src/practice/Flashcards.tsx` (217 lines) | One file does fetching, the session queue, keyboard handling, the countdown, grading, the question view and the summary screen. | Split into `useFlashcardRound` (logic), `FlashcardView`, `FlashcardSummary`. | Low |
| 4 | **D**IP, **S**RP | `tutor_core`: `story.py` (4 reads), `note.py`, `kinds.py`, `languages.py`, `groq.py` | Settings are read from `os.environ` in the middle of functions (e.g. `STORY_RANGE_PROMPT` is read in two places; `STORY_TWO_PASS`, `STORY_EXAMPLES`, `STORY_PROOFREAD` inside `generate_story`). `StoryOptions.from_env()` already exists but is bypassed. | One `Flags` object read once at the edge (`StoryOptions` / a new `StoryFlags`), passed down. The core functions stop touching the environment. | Medium (tests that set env vars need a look) |
| 5 | **I**SP | `tutor_core/story.py::generate_story` | 14 keyword arguments, several of which only some callers use (`call_groq_fn`, `judge_call`, `rng`, `clock`, `two_pass`, `options`). | Group the test/plumbing ones into a `StoryDeps` object (writer, judge, clock, rng); keep the old keywords working for one release. | Medium |
| 6 | **S**RP | long functions: `story_refine.refine_story` (92), `quality.score.score_story` (92), `quality.reporting.report` (88), `story._write_story` (67), `groq.call_groq` (65) | Each does several steps in one body. | Extract the named steps (observe/plan/repair/verify already exist as concepts). | Medium (heavily tested, so safe to attempt) |
| 7 | **S**RP | `api/app/services/rewards.py::overview` (65), `study_stats.stats` (64) | One function runs about ten queries and assembles the reply. (`overview` is mine from this week.) | One small query function per concern (`_records`, `_week`, `_challenge`, `_story_words`), `overview` only assembles. | Low |
| 8 | **D**IP | `GroqHealth.__init__` | Imports `os`, `time` and a transport inside the constructor and reads `GROQ_API_KEY` directly, although the other services receive such things. | Pass them in from `create_app` like the rest. | Low |
| 9 | **L**SP | `story_llm`: `stub_llm.calls_ai = False` | A function carries an attribute the caller must know about; a real model call has none, so callers use `getattr`. | Make the writer a tiny protocol/dataclass with `calls_ai`. | Low (cosmetic) |
| 10 | Hygiene | `scripts/spike_tweaks.py` and `spike_model_tweaks.py` (about 1000 lines plus 940 of tests) | Finished one-off spikes; `capture_fixtures.py` and `stream_probe.py` still import `spike_tweaks`. | Leave as is, or move spikes into `scripts/spikes/`. | Low, optional |

## Deliberately not recommended
- **A repository layer over psycopg2.** Services use SQL directly and a few import `psycopg2.errors`. Hiding that behind interfaces would add code without removing a real coupling (there is one database, and the tests use the real one).
- **Splitting `tutor_core` or `api` into more packages.** The current layout already separates pure rules from I/O.
- **Rewriting the i18n catalogs or `api/*.ts` modules.** They are already data-driven.

## Status
- **Items 1, 2, 3 done (patch 0083).** Practice page 144 to 57 lines: modes are a registry in `web/src/practice/modes/` (a new mode = one file and one line in `index.tsx`); the four quiz modes share `practice/quiz.tsx` (`useQuizRound`, `PromptPanel`, `QuizFeedback`, `QuizScore`), taking 233 lines from about 330; `Flashcards.tsx` 217 lines became `Flashcards.tsx` (view, 98), `useFlashcardRound.ts` (logic, 86) and `FlashcardSummary.tsx` (60). All 397 existing web tests pass unchanged; new tests only add.
- **Added while there:** the app had no error boundary, so one failing widget blanked the whole page (I hit this with a stale mock). `components/Quiet.tsx` now wraps the streak chip, the badge toasts and the Home rewards card, so a failure hides only that widget. Page-level boundaries are still not in place.
- **Items 7 and 8 done (patch 0084).** `rewards.overview` went from 65 lines of queries to an assembler over six small functions (`_activity`, `_totals`, `_records`, `_challenge`, `_story_words`, `_utc_today`); `study_stats.stats` likewise (`_standing`, `_recent`, `_all_time`, `_daily`, `_forecast`). `GroqHealth` no longer imports or reads the environment itself: its key, transport and clock are required arguments, wired in one place by `make_groq_health` (next to `make_story_llm`). API: 1076 tests pass, none changed except two new ones; the one failure is the local-database password test, unrelated.
- Items 4, 5, 6, 9 (`tutor_core`): not started, on purpose until the Kaggle comparison is measured.

## Suggested order
1. Web: items 1, 2, 3 (visible, safest, most duplication removed).
2. API: items 7, 8 (small).
3. `tutor_core`: items 4, 5, 6, 9 (largest payoff for the story pipeline you test most; do after the Kaggle results, so a refactor cannot confuse a measured comparison).
