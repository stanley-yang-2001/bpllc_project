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

## Step 9 bug found and fixed: empty tool output

During Step 9 testing, the tool's Result was sometimes **empty**, and the Agent invented its
own answer (including a fake "Invalid language specified" error). Cause: `gpt-oss-20b` spends
hidden reasoning tokens against `max_tokens`; at 400, nearly all were used, so Groq returned
`finish_reason: "length"` and `content: ""`. Fixed by raising the budget, lowering reasoning
effort, and treating empty output as a failure. Lesson: when the Agent says something the code
could never produce, expand the tool row and read the actual Result before blaming the model.

## Step 9 update: relaying the tool output exactly

Prompt rewrites (stricter rules, removing a line that made the Agent add a note) did not stop
the Agent from cutting or rewording the story. The Playground shows the tool Result and the
Agent's reply separately, and the tool Result was always correct, so the fix is in code: a
`Tool Result Relay` after the Agent copies `ToolContent.output` from the message's
`content_blocks` into the reply. Lesson: when exact wording matters, don't let an LLM write
the final text; let it choose the tool and let code deliver the result.

First live run: the relay changed nothing. A file-based debug log (container `print` output never
reached `docker logs`) showed `content_blocks` held `ToolContent` directly, not inside a
`ContentBlock`, so the extractor found no tool calls. Lesson: my tests had been built from my own
assumption of the data shape, so they passed while the real shape failed; capture one real
object before writing fixtures.

## Step 10: measuring before tuning

Built the instruments first: a vocabulary adherence checker (pure functions, test-first), a batch
runner that goes through the same pipeline the tool uses, and a test plan with pass criteria
fixed in advance. First real use of the checker, on stories copied from the Playground: the
clean ones pass, and the prompt's own tone example fails its own vocabulary rule, which is the
first tuning candidate. Design call: vocabulary stays English, so only English stories are
vocabulary-checked; other languages need a human. Decision recorded in the plan.

Add Word edge case found by reading the code, not by luck: the UNIQUE constraint is
case-sensitive, so case/punctuation variants became separate rows. Fixed with normalization
(lowercase is right for an English vocabulary; revisit if vocabulary is ever stored in a language
where case carries meaning, such as German nouns).

First baseline: structure was already perfect (no failures, leaks, off-length or bad-format
stories) and the 35% pass rate was entirely my own zero-stray-words rule. The stray words were
ordinary everyday words, and the 12-word vocabulary has almost no verbs, so the strict rule could
hardly be met. Lesson: look at what the failing items actually are before tuning the prompt; here
the right fix was the measuring stick, not the model. The owner relaxed the rule to at most 2
stray words, and that decision is written into the test plan.

Automated the Playground routing matrix: a runner drives the flow through Langflow's HTTP API and
a pure checker scores each turn against the failures seen in Step 9 (wrong language reused, no tool
call, reply differing from the tool output). The runner is tested against a fake Langflow server,
so its mechanics (login, sessions, snapshot/restore) are proven, but whether the real response
carries the tool calls where the parser looks is only known after a live `--debug` run; if it
doesn't, the runner falls back to Langflow's stored messages for the session.

First live routing run: routing was solid, but reading the actual replies (not just the
pass/fail table) showed that most non-English stories were in English or half-English, which the
structure-only check had passed. Lesson: a check that can't fail isn't a check; a test passing
across 45 turns said nothing about the thing a language tutor exists to do. The language check was
built from the real outputs. The run also showed my runner had its own bugs (cleanup between
repeats, every tool call listed twice), so the harness needs the same scepticism as the product.

Tuning change #1 targets the language problem the checker exposed. Reading the prompt with that
problem in mind, the English tone examples stood out: a request for a Spanish story was shown an
English example. So the fix has two parts (translate-the-meanings rule, no English example for
other languages) and the English prompt is pinned by checksum so it cannot regress. Both are
hypotheses until the before/after batches are compared. New deferred item:
`story_prompt_builder.py` (Step 8 canvas pipeline) now differs from `story_tool.py`.

Tuning change #1 worked: 5/15 → 30/30 non-English stories in the requested language, 0 failures in
60 generations. Two honest notes. First, three things changed at once, so the result supports the
hypothesis (English vocabulary list and English examples pulled stories toward English) without
isolating the cause. Second, my own summary line printed a meaningless "10/10" for English runs,
a reminder that the instruments need the same suspicion as the product.

Step 10 closed. Through the Agent: 43 of 45 turns passed, all routing and relay checks were
100%, and 15/15 non-English stories were in the right language, so the change that fixed the batch
also fixed the chat path once the canvas nodes were replaced (their stale copy of the code was the
last obstacle, as predicted). Small follow-ups worth remembering, not blockers: a request for a
"dialogue" is not honored (no style input on the tool); "Tell me a story" with no language
sometimes asks and sometimes defaults to English.

Story variety: the owner said stories felt the same, so before changing anything I counted: 81% of
48 stories mention water, ~75% are a request-and-reply, mean overlap 0.44. The prompt explains it
(the plan's Event is defined as a request needing a response; two forms; a 5–6 sentence cap; no
topic variation in code), and so does the data (a 14-word vocabulary with almost no verbs). The fix
has three parts that live in code, not in hoping the model varies on its own: more types, a topic
seed that avoids recent topics, and a looser word rule. Targets were fixed before measuring, and
the stray-word tolerance moved from 2 to 5 as an explicit owner decision. The biggest remaining
lever needs no code: add the verbs and nouns in `sample_data/suggested_words.csv`.

Story variety, measured: overlap 0.44 → 0.24 and six types, but the new stories carry 29% unknown words
(classic: 3%) and one vocabulary word is in 100% of them. Reading the stories explained the numbers:
the model stuffs every word of the list into the story ("He says hello to his house"), the topic
seeds ("a bus ride") demand nouns the learner doesn't know, and it ignores a numeric cap ("at most
5 words"); and the vocabulary has almost no verbs, so most strays were "read", "drink", "eat".
Lessons: (1) a good variety number can hide a worse learner experience, so read stories next to
the metrics; (2) models follow category rules better than counts; (3) my own instruments had bugs
again (Japanese sentence split, a French colon, names), found only by reading the saved stories;
(4) don't suggest a pacing change (`--delay 3`) without saying it might make the free tier fail,
which it probably did for 3 Japanese stories.

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

**Built and tested a deterministic alternative** (a keyword router, not included in this repo) that removes
the Agent's discretion entirely — intent classification and parameter extraction via plain
keyword matching, no LLM positioned to override the result. Confirmed working. Trade-off:
no real natural-language flexibility in how a request can be phrased.

**Decision (current):** the project's actual goal is to demonstrate genuine multi-agent
tool orchestration, so reverted to the agent-based architecture rather than keep the
router as the production path. Currently set up for an A/B comparison: the orchestrating
Agent's model swapped from `openai/gpt-oss-20b` to the larger `openai/gpt-oss-120b`
(story-generation itself stays on 20b, since that call was never the source of the relay
problem) — hypothesis being that a larger model is meaningfully more obedient at "just
relay this tool's result," without needing a paid model. The deterministic router approach remains
available as a fallback if 120b doesn't close the gap.

**Resolved (Step 9):** the project did not have to choose. The Agent stays genuinely agentic (it
picks the tool and the argument) and a Tool Result Relay delivers the tool's output in code.
See the Step 9 update above.

## Known code issues (deferred)

To be resolved once all steps in `docs/IMPLEMENTATION-GUIDE.md` are finished — not before.

- **Hardcoded DB credentials.** `DB_CONFIG` (`langflow`/`langflow`@`postgres`) is duplicated in
  `upload_word_file.py`, `add_word.py`, `word_loader.py`, `story_tool.py`, and
  `scripts/smoke_test.py`, and the tests. Move to environment variables or one shared config.
- **Hardcoded model name.** `story_tool.py` pins `openai/gpt-oss-20b` inside `call_groq`; it
  should be configurable (and could use the Bonus universal model component).
- **Possibly unused component.** `groq_language_model.py` isn't called by any code in the repo;
  confirm whether the canvas still uses it, and whether it should be replaced by the Bonus
  universal model component.
- **Duplicated logic.** `load_words`, `build_story_prompt`/the templates, `extract_final_passage`,
  and the empty-vocabulary message exist in both `story_tool.py` and the Step 8 components
  (`word_loader.py`, `story_prompt_builder.py`, `final_passage_extractor.py`, `story_guard.py`).
  This is deliberate for now (Tool Mode limitation, and Langflow's component scanner makes
  cross-file imports unreliable), but the two copies can drift apart.
- **Starter data.** `sample_data/starter_vocabulary.csv` has a duplicate `hello` row and a
  trailing blank line.
- **Cache comment is stale.** `generate_story_for_learner`'s docstring mentions
  `_CACHE_TTL_SECONDS`, which was split into `_SUCCESS_CACHE_TTL_SECONDS` and
  `_FAILURE_CACHE_TTL_SECONDS`.
- **Repo hygiene.** `.gitignore` is empty and `custom_components/__pycache__/*.pyc` is committed
  (including a stale `prompt_template.cpython-314.pyc`). The README says `.env` is gitignored.
- **Stale Langflow credentials.** The Langflow log repeats "API key decryption failed ...
  SECRET_KEY mismatch" (`InvalidToken`) on each run, probably from keys stored before
  `LANGFLOW_SECRET_KEY` was pinned. Runs still work; re-enter any stored keys or variables.
- **Agent leaks its reasoning.** The orchestrator's draft reply often contains its own reasoning
  and stray non-breaking / zero-width spaces. The relay hides this, but it wastes tokens and time.
  Try a low reasoning effort on the orchestrator (check how `groq_language_model.py` can pass it).
- **Both model names are hardcoded** (the orchestrator on the canvas, the story call in
  `story_tool.py`).
- **Canvas copies of components.** A Langflow node keeps its own copy of a component's code, so
  file edits don't reach existing nodes until the node is replaced. Export the flow JSON to the
  repo so the canvas wiring is versioned.
- **Debug leftovers.** Delete `custom_components/relay_debug.log` if it exists, and make sure no
  canvas node still carries the temporary debug `relay()`.
