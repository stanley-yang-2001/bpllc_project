# Changelog — Language Tutor with Langflow

## Architecture: reverted to agent-based tool orchestration

**Why:** the deterministic router (`language_tutor_router.py`) solved the reliability
problem (the Agent discarding tool output and substituting its own unconstrained story)
but abandoned the project's core teaching objective — demonstrating real multi-agent tool
orchestration (LO 5, LO 6). Checked the original tutorial's own agent instructions; they
are nearly identical to what we'd already tried, confirming the tutorial's reliability came
from using `gpt-4.1`, not a technique we were missing.

**Changed (canvas/UI only — no files modified):**
- Re-enabled Tool Mode on `Add Word` and `Story Generator Tool` (code already supported
  this; the toggle had been turned off when we built the router).
- Added a second Groq model node ("Groq Orchestrator — 120b", model
  `openai/gpt-oss-120b`) as the default Language Model for the top-level Agent — a larger
  model specifically for the orchestrator, since instruction-following under agentic
  tool-use is where model size matters most.
- Kept the original Groq 20b node on the canvas, disconnected, for direct A/B comparison
  against the 120b orchestrator using identical instructions/tools.
- Rebuilt the top-level **Language Agent**, instructions now matching the tutorial's exact
  wording:
  > "You will help the user practice their language skills... When using a tool, your
  > answer should just be the result from the tool and nothing else."
- Wired: Chat Input → Agent → Chat Output; Add Word + Story Generator Tool → Agent's Tools
  input; Groq 120b → Agent's Language Model input.

**Not changed:**
- `story_tool.py`'s internal story-generation call stays on `openai/gpt-oss-20b` — that
  call was never the source of the relay-reliability problem.
- `language_tutor_router.py` and `tests/test_router.py` — left on disk, unwired, as a
  working fallback if the 120b orchestrator still proves unreliable.
- `OVERVIEW.md` / `IMPLEMENTATION-GUIDE.md` — already describe this agent-based
  architecture from when Step 9 was first written, so nothing needs updating there.

**Testing plan:** run identical requests (add a word, request a story in a named language,
an unrelated message) with the 120b orchestrator wired in, then swap to 20b and repeat, to
compare agentic obedience between the two model sizes on the exact same instructions/tools.
