# PR: practice, own model, tiers, tools role and the test round (87 commits, 19 Oct to 5 Nov 2026)

Post this as the pull request description. Feature-by-feature dates are in `docs/FEATURES.md`; every patch is in `CHANGELOG.md`.

## Summary

87 commits on top of `origin/main`: 450 files, +140,340 / −6,358 lines (mostly tests, word lists and docs). The work adds practice that remembers progress, word sets, parts of speech, read aloud and dictation, difficulty tiers, stories in all nine languages, a least-privilege database role for the Langflow tools, chat that can run on a learner's own AI model, and a one-command test round with a single report. Migrations 0008 to 0015 are included.

## What changed, by theme

**Chat and the tutor's tools**
- Least-privilege `tutor_tools` database role for the Langflow tools (0008, needs `TOOLS_DB_PASSWORD`).
- The story tool takes a kind, a topic, a difficulty and a length (20 to 400 words); a language named in chat wins; replies in the study language (0009, 0010); tool limited to ticked word sets.
- Agent instructions rewritten for reliable routing of kinds (5 Nov); routing cases repeat and print pass rates.

**Stories and quality**
- Difficulty tiers (easy, medium, hard, custom), custom topic, stories in all nine languages, everyday-word lists, CJK length/ending fixes, quality rules v6.
- Richer English kinds behind `TUTOR_RICH_RANDOM` (off by default).

**Vocabulary and practice**
- Word sets (0012), multiple choice, tutor-written meanings in a chosen language (0013), parts of speech (0015), remembered spaced practice with streak (0014), starter packs and a first-run guide, dictation.
- Read aloud with browser voices, pronunciation guides, translation.

**Own AI model**
- Phase 1: stories, meanings, labels, translation and pronunciation on the learner's provider (0011), encrypted key, address safety checks.
- Phase 2 (option B): chat on the learner's model, behind `CHAT_OWN_MODEL=1`. The API acts as the model for Langflow with a one-turn throwaway token, so the key never leaves the API. A failed turn shows the provider's reason; there is no fallback to the shared model.
- Streaming chat reply is built but parked (`CHAT_STREAM=0`): Langflow's Agent sends no word-by-word events.

**Engineering**
- SOLID splits of large back-end and front-end files (no behaviour change); class diagrams updated.
- `run-checks.bat` and `scripts/run_all_checks.py`: unit tests, a throwaway stack, live checks, and `--round` with one `REPORT.txt` that quotes failing lines.
- Kanban board generated from `docs/kanban/cards.json`; CI workflow.

## Migrations

`0008_tools_role`, `0009_custom_story_type`, `0010_chat_in_study_language`, `0011_user_models`, `0012_word_sets`, `0013_meaning_mode`, `0014_word_progress`, `0015_word_pos`. They run on start (`RUN_MIGRATIONS`). All are additive.

## New settings (see `docs/ENVIRONMENT.md`)

| Setting | Default | Meaning |
|---|---|---|
| `TOOLS_DB_PASSWORD` | required | Password of the `tutor_tools` login used by the Langflow tools. |
| `LANGFLOW_PER_USER_TOOLS` | 0 | 1 for one word list per learner (live chat). |
| `MODEL_KEY_SECRET` | empty | 16+ characters; encrypts learners' API keys. Own model is off without it. |
| `ALLOW_PRIVATE_MODEL_URLS` | 0 | 1 lets a model address be on a private network (local models, tests). |
| `CHAT_OWN_MODEL` | 0 | 1 lets chat use the learner's own model. |
| `CHAT_STREAM` | 0 | Parked; leave off. |
| `TUTOR_RICH_RANDOM` | off | Diary, letter and place kinds in random picks. |

## Testing

- Unit and integration tests per area (back end, front end vitest, Playwright e2e, root script tests). Run everything with `run-checks.bat`; one round with live checks and a single report: `run-checks.bat --round`.
- Passed on the owner's stack: live chat, routing, own-model chat check with a fake provider (`own-model-chat-live`), e2e.
- Not run yet: patches 0046 to 0052 as one round; by-hand checks (chat length, story kinds, own model with a real provider and a wrong key, read aloud and dictation voices).
- Known flake: live Groq answers can differ run to run (routing case T1 is measured by pass rate for that reason).

## Not in this PR

- **Privacy policy.** The approved text and `POLICY_VERSION` are untouched. Six places where the code has moved on are listed in `docs/PRIVACY-POLICY-OPTIONS.md`, with wording to choose from. Merge only after you accept that gap or approve the changes.
- A way to ask existing learners to re-accept a new policy.
- Native-speaker review of the nine-language site text.
- Announcing the 400-word cap in chat (needs an API notice; the tool's output is relayed exactly).

## Review notes

- Large diffs are generated or data: word lists (`api/app/data`), the Langflow flow JSON, locale files.
- The flow's `system_prompt` must equal `docs/AGENT-INSTRUCTIONS.md` (test `test_flow_file.py`); tool text is synced by `scripts/sync_flow_nodes.py`.
- Own-model key handling: stored encrypted, decrypted only in the API, never given to Langflow; the round scans every text/json column for the key.

🤖 Generated with [Claude Code](https://claude.com/claude-code)

https://claude.ai/code/session_01GkMD3yJ8TAxBw1FDUiXWT9
