# Step 10 — End-to-end test plan and tuning log

Covers Stories 5 and 6 holistically, **LO 7** (iterate a constrained prompt against real output)
and **LO 8** (the real cost/latency/quality trade-offs of free open-weight models).

Design decision for this step: the stored vocabulary stays **English words**, and stories in
other languages are translations of it. The automatic vocabulary check therefore applies to
**English** stories only; other languages are checked for structure and read by a human.

## Pass criteria (fixed before tuning, so the target doesn't move)

| # | Criterion | Target |
|---|-----------|--------|
| 1 | Routing: correct tool **and** correct argument (R1–R12, 3 runs each, fresh sessions) | ≥ 90% of runs |
| 2 | Relay: chat reply is identical to the tool's Result when a tool was called | 100% |
| 3 | English stories: pass = **≤ 2 stray words** (see decision below), 4–8 sentences/lines, correct dialogue format, no leaked plan (≥ 20 passages) | ≥ 80% |
| 4 | Stories that fail to generate (fallback message, empty) | ≤ 10% |
| 5 | Non-English stories: **actually written in the requested language** (automatic language check, `--count 10` per language) and read by a person for naturalness | ≥ 90% |
| 6 | Empty-vocabulary guard (R13) | 3 of 3 |
| 7 | Written verdict on cost, latency, quality, rate limits (section D) | done |

If a target is missed, tune one thing, re-run the same set, and record it in the tuning log.

### Decision change after the first baseline (owner's call, recorded so the target isn't moved silently)

The first criterion was "0 words outside the vocabulary". The baseline showed that was unrealistic:
the starter vocabulary is 12 words with almost no verbs, so even natural beginner stories need
"eat", "drink" or "bring". The stray words found were ordinary everyday words, and the owner
decided they are acceptable as long as stories stay short and suit a beginner. Criterion 3 now
tolerates up to **2 stray words per story** (`--max-oov 2`, the default of the batch runner and the
CLI). The strict rule (`--max-oov 0`) is still available and is recorded for comparison.
Readability (words per sentence/line) is reported for every run; to enforce a limit use
`--max-unit-words N`. Rescore any saved run under a different rule, without calling Groq:

```
docker compose exec langflow python /app/scripts/run_story_batch.py --rescore /app/scripts/step10_results_<time>.json
```

## Track A — Story quality (the prompt, Agent bypassed)

Uses `scripts/run_story_batch.py` and `scripts/vocab_adherence.py`. Don't use the Playground while
it runs (shared rate limit).

```
docker compose exec langflow python /app/scripts/run_story_batch.py --languages English --count 20
docker compose exec langflow python /app/scripts/run_story_batch.py --languages Spanish,French --count 5
```

It reports pass rate, failures, styles, off-length and bad-format counts, the most common
out-of-vocabulary words, and latency p50/p90, and saves every passage to
`scripts/step10_results_<time>.json`. To check a story copied from the Playground, put it in a
text file (separate stories with a line containing only `---`) and run
`python scripts/vocab_adherence.py stories.txt --words "hello, water, ..."`.

Ideas to test, one at a time (hypotheses, not facts):
1. The prompt's own **tone example** uses words outside the vocabulary rule ("hungry", "shop",
   "fresh bread", "eat", "happily"), which may teach the model to break the rule. Replace it with
   an example built only from the starter vocabulary.
2. Rule 3 says the allowed simple verbs are "is, have, want, like, go, see" but the examples also
   use "say". Decide whether the allowed verbs are a closed list; try `--strict-verbs` to see how
   often the model breaks the closed list.
3. Add the full list of verbs the model is allowed to use, and tell it to re-check each content
   word against the list before the delimiter.
4. `reasoning_effort` (`low` now) and `max_tokens` (1500): check whether stories get truncated.

## Track B — Routing and behavior (through the Agent)

### Automated (preferred): `scripts/run_routing_tests.py`

Sends the messages to the flow over Langflow's HTTP API, one fresh session per test, and checks
every response: right tool, right argument (the language in the **latest** message), reply identical
to the tool output, story quality, and the empty-vocabulary guard. The flow id is the long id in
the browser URL (`localhost:7860/flow/<flow-id>`).

```
# first time: confirm the response is parsed correctly (prints the raw response)
docker compose exec langflow python /app/scripts/run_routing_tests.py --flow-id <flow-id> --only N1,S1 --debug

# the full suite (about 4 minutes)
docker compose exec langflow python /app/scripts/run_routing_tests.py --flow-id <flow-id>

# three runs of every case, for an actual pass rate (about 12 minutes)
docker compose exec langflow python /app/scripts/run_routing_tests.py --flow-id <flow-id> --repeat 3
```

| Automated case | Replaces manual row | What it checks |
|---|---|---|
| A1, A2, A3 | R1, R2, R3 | add a word; the same word again; a case variant (needs normalization) |
| S1 | — | English story: tool, argument, relay, vocabulary/format rules |
| S2, S3, S4 | R6, R7, R8 | Spanish / French / Japanese (asked by its own name) stories |
| M1 | R10 | English → Spanish → English → French in one session |
| N1, N2 | R11, R12 | greeting and unrelated question: no tool |
| I1 | R9 | "Tell me a story" with no language (recorded, never fails) |
| E1 | R13 | empty vocabulary returns the guard message, not an invented story |

It temporarily changes the database and puts it back: a throwaway word (`autotestapple`) is added
and removed, and for E1 the `words` table is snapshotted, emptied and restored in a `finally`
block. If a run is killed hard, `--restore-leftover` restores it. Don't use the Playground while it
runs (shared Groq rate limit). Not automated: R4, R5, R14, R15 (optional manual checks) and the
quality of non-English stories, which a person must read.

### Manual (optional): Playground

Fresh session for each run (**+** next to Sessions), wait about 60 seconds between runs, and
for every run expand the tool row and compare its Arguments and Result with the chat reply.
Record 3 runs per row (✔ / ✘ and a note).

| ID | Setup | Message | Expected | Run 1 | Run 2 | Run 3 |
|----|-------|---------|----------|-------|-------|-------|
| R1 | — | "Add the word bread" | Add Word once, `word` = bread; reply is the tool's confirmation | | | |
| R2 | after R1 | "Add the word bread" | "'bread' is already in your vocabulary." | | | |
| R3 | after R1 | "Add the word Bread" | already in vocabulary (case-folded) | | | |
| R4 | — | "Teach me the word gato" | Add Word with `gato` | | | |
| R5 | — | "Add thank you very much" | Add Word with the phrase, stored as one entry | | | |
| R6 | — | "Tell me a story in Spanish" | story tool, `language` = Spanish, passage in Spanish | | | |
| R7 | — | "Write a dialogue in French" | story tool, `language` = French, passage in French (see limitation below) | | | |
| R8 | — | "Story in 日本語" | story tool, language Japanese (or 日本語), passage in Japanese | | | |
| R9 | — | "Tell me a story" | acceptable: asks which language, or an English story; record which | | | |
| R10 | one session | English → Spanish → English → French (separate messages) | each `language` argument matches the latest message | | | |
| R11 | — | "hi" | no tool, brief reply | | | |
| R12 | — | "What's the weather like?" | no tool, brief reply | | | |
| R13 | empty vocabulary (below) | "Tell me a story in English" | the empty-vocabulary message, no invented story | | | |
| R14 | — | "Tell me a story in Klingon" | no crash; either an attempt or a graceful reply | | | |
| R15 | — | "Add the word" (no word) | does not add an empty word; asks or reports | | | |

**Emptying the vocabulary safely for R13** (a backup is kept; restore afterwards):

```
docker compose exec postgres psql -U langflow -d langflow -c "CREATE TABLE words_backup AS SELECT * FROM words; DELETE FROM words;"
-- run R13 --
docker compose exec postgres psql -U langflow -d langflow -c "INSERT INTO words SELECT * FROM words_backup ON CONFLICT DO NOTHING; DROP TABLE words_backup;"
```

**Known limitation (found while planning):** the Story Generator Tool has no `style` input; it
picks narration or dialogue at random, so "write a dialogue" may return a narration. If R7
shows this matters, add an optional `style` input to the tool (a small, test-first change).

## Track C — Edge cases (Add Word)

Unit-tested without a database in `tests/test_add_word_normalization.py`: case, whitespace, edge
punctuation, quotes, phrases, empty input. Live checks: R3, R5, R15. Existing rows are **not**
rewritten: if the table already holds an un-normalized word (for example "Hello"), adding
"hello" will create a second row until the table is cleaned up.

## Track D — Performance, rate limits and the LO 8 write-up

1. Send 5 story requests back to back, with no waiting. Record how many returned the fallback
   message, and the "Finished in" time of each.
2. Fill in the table from the batch runs and the Playground:

| Measure | Value |
|---------|-------|
| API cost | $0 (Groq free tier) |
| Story latency p50 / p90 (batch runner) | 1.1s / 2.1s (baseline, 20 English stories) |
| Agent turn latency (Playground "Finished in") | |
| Fallback / failure rate under spaced load | |
| Fallback / failure rate under back-to-back load | |
| Routing pass rate (Track B) | |
| English story pass rate (Track A) | |
| Times the relay changed the Agent's reply | |

3. Write a short verdict (a paragraph each): **cost** (what free costs you), **latency**,
   **quality/consistency** (what the small model could and couldn't do reliably, and what the
   relay and cache had to compensate for), and **rate limits** (what they allowed in practice).

## Results so far

### First live routing run (automated, 3 repeats of 12 cases = 45 turns, `gpt-oss-120b`)

| Measure | Result |
|---|---|
| Right tool called (small talk: none) | 42/42 |
| Right argument (the language in the latest message / the word) | 36/36 |
| Chat reply identical to the tool's output (the Relay) | 36/36 |
| Language switching, English → Spanish → English → French in one session (M1) | 12/12 turns |
| Empty-vocabulary guard (E1) | 3/3 |
| English story quality (≤ 2 stray words, length, format) | 8/9 |
| Add Word reply wording | 6/9, none of them a routing failure (below) |
| **Non-English stories actually in the requested language** (re-scored with the new language check) | **5/15** |

Routing criteria (1, 2, 6) are met. Criterion 3 is met for English (8/9, and 17/20 in the batch).
**Criterion 5 is not met**, and the original structure-only check hid it. Reading the replies:
2 of 3 "Spanish" stories and all 3 "Japanese" stories were written in English, and every
French story had English words left in ("je veux water", "Thank you", "Tomorrow je aiderai").
Good Spanish and French did appear (5/15 overall), so the model can do it; the prompt doesn't
make it reliable. Likely cause (hypothesis): the vocabulary is a list of English words and the
prompt tells the model to use those words, which pulls the story back into English.

Things the run exposed that were not product bugs:
- **A3 failed because the Add Word node on the canvas was still the old version** (case-sensitive,
  so "AutoTestApple" was added as a new row). Replacing the node fixes it.
- **A1 failed in repeats 2 and 3: a runner bug.** The throwaway word was cleaned up only at the
  end. Fixed: every repeat starts clean, case-insensitively.
- **Every tool-using turn listed two identical tool calls.** Probably the parser reading one call
  twice; calls are now collapsed by id and the id is saved, so the true count will show next run.

### Tuning change #1 (implemented): a language-aware prompt for non-English stories

Order matters, so the effect is measurable: **run the baseline before applying the change**, then
apply it and run the identical batch.

```
docker compose exec langflow python /app/scripts/run_story_batch.py --languages Spanish,French,Japanese --count 10
```

The summary reports "Written in the requested language" for each language. The change, in
`story_tool.py` (English prompts are untouched, pinned by checksum in the tests):
1. For any language other than English the prompt now opens with a language rule: write the entire
   story in that language; the vocabulary list is English *meanings* to be expressed in it; no English
   words may remain (names excepted); plus a final-check reminder before "Begin:".
2. The English tone examples ("I am hungry today...", "Mia: Hello! Do you have any bread?") are
   left out of non-English prompts, because an English example primes English output.
3. A language given by its own name is normalized ("日本語" → Japanese, "español" → Spanish) before
   it goes into the prompt and the cache key.

Not changed: `story_prompt_builder.py` (the Step 8 canvas pipeline, kept for debugging) still has
the old templates, so it will differ from the production path until the duplicated logic is cleaned
up (deferred list).

## Tuning log

| # | Change (one thing at a time) | Why | Before | After |
|---|------------------------------|-----|--------|-------|
| 0 | Baseline, no change (20 English stories, strict rule: 0 stray words) | | — | **7/20 pass (35%)**; 0 failures, 0 leaks, 0 off-length, 0 bad format; mean 1.30 stray words/story; top stray words: bring 5, drink 4, together 4, share 2, eat 2, sure 2, happily, offers, bake, shares |
| 0c | Routing run: non-English stories re-scored with the language check | The structure-only check passed stories written in English | 15 passed on structure | **5/15 in the requested language** (Spanish 3/6, French 2/6, Japanese 0/3) |
| 1 | Language-aware prompt for non-English stories (translate-the-meanings rule, no English example, normalized language name) | Only 5/15 non-English stories were in the requested language; the English vocabulary list and English examples pull stories back to English | *run the baseline batch first and record it here* | *run the same batch after applying and record it here* |
| 0b | Same baseline, re-scored with the relaxed rule (≤ 2 stray words) | The strict rule was unrealistic for a 12-word vocabulary; the stray words are everyday words | 35% | *run `--rescore` and record here* |
