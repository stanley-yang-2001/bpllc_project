# Developer Diary — Language Tutor with Langflow

## What's been done

**Environment.** Docker Desktop required enabling virtualization in BIOS and the Windows
WSL2/Virtual Machine Platform features before it would even start. Once running, Langflow
itself needed `LANGFLOW_SUPERUSER`/`LANGFLOW_SUPERUSER_PASSWORD` explicitly set (newer
versions don't auto-generate an admin account), and later a pinned `LANGFLOW_SECRET_KEY` —
without one, container restarts silently invalidate previously-saved encrypted secrets
(API keys), surfacing as a cryptic `InvalidToken` decryption error.

**Model choice.** Local Ollama was ruled out early — not enough RAM/GPU on this machine to
run a model comfortably. Switched to Groq (free, hosted, OpenAI-compatible API) instead.
Groq's `llama-3.1-8b-instant` and `llama-3.3-70b-versatile` turned out to be deprecated
(shut down Aug 16, 2026); replaced with `openai/gpt-oss-20b`. Connecting Groq into Langflow
required routing through the generic OpenAI component with a custom `base_url`, since no
dedicated Groq component was available in this Langflow version — then later replaced with
a self-contained custom component once the OpenAI-component UI proved unreliable
(hidden/missing advanced fields across versions).

**Core components, test-first throughout:**
- `upload_word_file.py` — seeds the `words` table from a CSV. Standalone, not agent-facing.
- `add_word.py` — agent-callable tool, inserts one word. Required switching from `StrInput`
  to `MessageTextInput` with `tool_mode=True` before Langflow's Tool Mode toggle would even
  appear — a field-type requirement that isn't obvious from the UI alone.
- `story_tool.py` — the story-generation pipeline. Originally four separate Langflow
  components (Word Loader → Prompt Builder → Agent → Extractor), consolidated into one
  self-contained component after discovering that **Tool Mode only returns a component's
  own output — it does not execute anything wired downstream of it on the canvas.** The
  four-component chain would have leaked its hidden planning summary straight to the
  learner, since the cleanup step (the Extractor) would never run as part of a tool call.

**Prompt engineering, several real iterations:**
1. First version forced every vocabulary word in — produced grammatically broken fragments
   ("Please water and food.") since conversational words like `yes`/`no` had no verb
   support to attach to.
2. Loosened to "use words that fit, don't force every one," added explicit coherence
   rules — fixed fragment issues but produced logically disconnected sentences.
3. Restructured around a hidden planning step — Character/Want/Event/Resolution (a
   compressed "Somebody Wanted But So" story-structure framework) — with the plan hidden
   behind a `===STORY===` delimiter, stripped from the model's raw output in code (not
   trusted to the model to simply "not show").
4. Refined Event to require a genuine question/problem (not just "something happens"), and
   Resolution to vary in shape (agreement, farewell, thanks, a plan) rather than always
   being a bare yes/no answer — fixed a recurring "yes/no inserted as a non-sequitur" issue.
5. Added interchangeable narration/dialogue styles (randomized in code, not left to the
   model to self-vary), extended length from "3–4" to "aim for 5–6" sentences/lines, and
   allowed word inflection (tense, plural) for future verb vocabulary.

**Reliability engineering on the Groq call itself:**
- Automatic retry-with-backoff on HTTP 429 (rate limit), since Groq's free-tier TPM budget
  is a small rolling window.
- A short-lived cache (language → result), added after discovering the orchestrating Agent
  sometimes calls the same tool 3–5 times for one request despite explicit "at most once"
  instructions — caching makes repeat calls free instead of repeat-hammering Groq.
- Caching extended to *failures* too, after finding the first cache design only cached
  successes — meaning a rate-limited burst caused every repeat call to independently run
  its own full retry cycle, compounding the exhaustion rather than absorbing it.

## Current obstacle

**The orchestrating Agent doesn't reliably relay tool output.** Confirmed via trace
inspection: on a single multi-call burst, the Agent (a) sent an empty `language` argument
on at least one call, and (b) ultimately discarded every tool result — including a
successful one — and wrote its own unconstrained, undelimited story from scratch, despite
an explicit instruction never to do so under any circumstances.

Checked the original tutorial's own agent instructions for a missed technique — they are
nearly word-for-word what we'd already tried. The tutorial's reliability comes from running
on `gpt-4.1`, not from any particular prompt pattern. This is a real, documented gap in
agentic instruction-following between frontier and small open-weight models, not a bug in
our setup.

**Built and tested a deterministic alternative** (`language_tutor_router.py`) that removes
the Agent's discretion entirely — intent classification and parameter extraction via plain
keyword matching, no LLM positioned to override the result. Confirmed working. Trade-off:
no real natural-language flexibility in how a request can be phrased.

**Decision (current):** the project's actual goal is to demonstrate genuine multi-agent
tool orchestration, so reverted to the agent-based architecture rather than keep the
router as the production path. Currently set up for an A/B comparison: the orchestrating
Agent's model swapped from `openai/gpt-oss-20b` to the larger `openai/gpt-oss-120b`
(story-generation itself stays on 20b, since that call was never the source of the relay
problem) — hypothesis being that a larger model is meaningfully more obedient at "just
relay this tool's result," without needing a paid model. The deterministic router stays on
disk, unwired, as a fallback if 120b doesn't close the gap.

**Open question, not yet resolved:** whether 120b's improvement (if any) is reliable enough
in practice, or whether this project ultimately has to choose between "genuinely agentic"
and "reliably correct output" as long as it stays on free infrastructure.
