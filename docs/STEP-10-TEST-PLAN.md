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
| Story latency p50 / p90 (batch runner) | 1.1–1.5s / 1.9–2.1s across 60 generations (English, Spanish, French, Japanese) |
| Agent turn latency (Agent + tool + Relay, routing runner) | p50 3.0s, p90 5.0s, max 8.7s over 45 turns |
| Fallback / failure rate under spaced load | 0 of 50 story generations (20 English baseline + 30 non-English) |
| Fallback / failure rate under back-to-back load | 0 of 10 (English, `--delay 0`); latency unchanged (p50 1.4s, p90 2.0s), so the free-tier limit was not hit by a 10-story burst |
| Routing pass rate (Track B) | tool 42/42, argument 36/36, relay 36/36 in both live runs; **43/45 turns passed in the final run**, the 2 failures being English stories with 3–4 everyday stray words |
| English story pass rate (Track A) | 41/48 (85%): 17/20 batch, 8/9 first routing run, 9/10 burst, 7/9 final routing run, at ≤ 2 stray words |
| Times the relay changed the Agent's reply | not counted; the reply matched the tool output in 36/36 tool turns in each live run, and earlier debug logs showed garbled Agent drafts that the Relay replaced |

3. Write a short verdict (a paragraph each; see "LO 8 verdict" below): **cost** (what free costs you), **latency**,
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

## Criteria status (final)

| # | Criterion | Result |
|---|-----------|--------|
| 1 | Routing: right tool and argument | **Met.** Tool 42/42, argument 36/36 (final run; same in the first run) |
| 2 | Relay: reply identical to the tool output | **Met.** 36/36 in both live runs |
| 3 | English stories ≥ 80% | **Met.** 41/48 (85%) |
| 4 | Generation failures ≤ 10% | **Met.** 0 in 60 batch generations and 0 fallback replies in the final run |
| 5 | Non-English stories in the requested language ≥ 90% | **Met.** 30/30 in the batch and 15/15 through the Agent (S2, S3, S4, and the Spanish and French turns of M1); 9 read samples were natural |
| 6 | Empty-vocabulary guard | **Met.** 3/3 in the final run |
| 7 | Written verdict | **Done** (below) |

Other results from the final run: language switching (M1: English → Spanish → English → French in
one session) passed every routing check in all 3 repeats; Add Word's case variant (A3) now
passes, which confirms the normalization reached the canvas; the earlier "every tool call appears
twice" was a parser artifact (37 of 38 tool turns now show exactly one call; the other was a
genuine repeat of the same French request, absorbed by the story cache). Unprompted
"Tell me a story" (I1) asked which language once and defaulted to English twice: acceptable, not
consistent.

**Caveat on attribution.** The prompt change did three things at once: a translate-the-meanings
rule, no English tone example, and a normalized language name. It worked (5/15 → 30/30), but the
runs cannot say which of the three mattered; test them separately if one ever has to go. "In the
requested language" is a heuristic: the read samples were natural, but only a fluent reader can
judge naturalness (one French line, "seulement biscuit", dropped an article).

**Not covered:** requesting a *dialogue* (the tool has no style input, so a request may return a
narration), the optional manual rows R4, R5, R14 and R15, and daily rate limits.

## LO 8 verdict

**Cost.** $0 in API fees: Groq's free tier served every run in this project. The price is
operational: a shared rate limit and a model that has to be corralled (see quality).

**Latency.** Fast. A story generation takes about 1.1–1.5s at the median and about 2s at p90; a
chat turn through the Agent, tool and Relay took p50 3.0s and p90 5.0s (maximum 8.7s). Outputs are
short and reasoning is set to low, so a spinner is all an interface needs. No comparison with a
paid model was made.

**Quality and consistency.** Good at the task once measured and tuned, unreliable out of the box.
The model chose tools and arguments correctly every time (42/42 and 36/36 in two live runs), but
could not be trusted to relay text (it shortened, reworded, added notes and leaked its reasoning),
so a Tool Result Relay delivers the tool's output in code. Non-English stories were in the right
language only 5/15 times until the prompt was rewritten for the model's habits (an English example
and an English word list pulled stories back to English); after that, 30/30 in the batch and 15/15
through the Agent. English stories met the vocabulary rule 85% of the time at a tolerance of two
everyday words. What mattered most was not the model but the engineering around it: measure what
the product is for (a structure-only check hid the language problem), put a code-level safety net
around the model's weakest step, and read real outputs.

**Rate limits.** In practice they did not bind: a 10-story burst with no pause produced no
failures and no slowdown. Daily limits were not measured. A public site with many learners would
hit the shared free-tier limit quickly, so it would need a queue, per-user cooldowns or a paid plan.

### Tuning change #2 (implemented and measured): story variety

**Problem (owner's observation, then measured).** Stories felt the same: mostly conversations, the
same words, the same shape. Counting 48 stories from the two routing runs: 81% mention water (in any
language), about 75% are somebody asking for or receiving something, and the 18 English stories
overlap each other by 0.44 on average (content words only). Vocabulary words are in almost every
story ("today" in 100%), and 44% open with "Hello, I am...". Causes found in the prompt: only two
forms (first-person narration and dialogue); the plan's "Event" is by definition "a question or
request needing a response"; a cap of 5–6 short sentences; "no new content words"; and nothing in
the code that varies the topic. The vocabulary itself is tiny and almost all nouns, which limits
variety whatever the prompt does (see `sample_data/suggested_words.csv`).

**Change (`story_tool.py`; the two classic templates are untouched and still pinned by checksum).**
1. **Six new story types**, drawn at random with conversations only a part of the mix (about 19%):
   a short story with a problem and an ending, a diary entry, a letter, a place description, a daily
   routine, a funny anecdote. Each has its own form, length (6–9 short sentences of up to 12 words)
   and structure rule; none is built around a request-and-reply.
2. **A topic seed chosen in code** from 21 topics (market day, a lost key, a rainy day, a trip by
   train...), never repeating the last 8, so each story has its own subject.
3. **A looser word rule for the new types**: the learner's vocabulary stays central, plus basic
   grammar words, simple verbs and at most 5 very common everyday words. Non-English prompts get
   the same language rule as before and no English example.
4. `generate_story_for_learner(..., story_type=None, topic=None)` can force a type or topic (cached
   separately from the random default). The Agent-facing tool still takes only `language`;
   exposing an optional type and topic to the Agent would also fix the "write a dialogue" request,
   but it changes the tool schema the Agent sees, so it is a separate change followed by a routing
   re-run.

**Decision change (owner's request, recorded so the target is not moved silently).** Stories are
allowed to be less constrained, so the pass rule is now **≤ 5 stray words** (it was ≤ 2), stories
may be **4–10 sentences or lines** (was 4–8), and `--max-oov` defaults to 5 in the batch runner,
the checker CLI and the routing tests. Any earlier saved run can be re-scored under the old rule
with `--rescore ... --max-oov 2`.

**Measurements added.** `variety_report` (in `scripts/vocab_adherence.py`) reports, for a set of
stories: how many distinct types, mean overlap of content words between stories, the most repeated
vocabulary word (greetings and politeness words excluded), and the most common opening. The batch
runner prints it after each language's summary, also for `--rescore`, and saves each story's type
and topic.

**Targets, fixed before measuring** (20 English stories, then the language checks):

| Measure | Baseline | Target |
|---|---|---|
| Mean overlap between stories (content words) | 0.44 | ≤ 0.30 |
| Most repeated vocabulary word | 100% ("today") | ≤ 60% of stories |
| Most common opening | 44% ("hello i am") | ≤ 20% |
| Distinct story types in 20 stories | 0 recorded (2 forms) | ≥ 6 |
| Pass rate at ≤ 5 stray words, length 4–10, format and language ok | — | ≥ 80% |
| Non-English stories in the requested language (no regression) | 30/30 | ≥ 90% |
| Story latency p50 | 1.1–1.5s | ≤ 3s |
| Human read of 10 random stories: makes sense / interesting / right level | — | ≥ 8 / ≥ 6 / ≥ 8 of 10 |

**How to measure.**

```
# 1. "Before" variety, instantly and with no Groq calls: re-score the 20-story English baseline
dir scripts\step10_results_*.json
docker compose exec langflow python /app/scripts/run_story_batch.py --rescore /app/scripts/<English baseline file> --max-oov 2

# 2. "After": the same sizes as the baselines
docker compose exec langflow python /app/scripts/run_story_batch.py --languages English --count 20 --delay 3 --out /app/scripts/variety_english.json
docker compose exec langflow python /app/scripts/run_story_batch.py --languages Spanish,French,Japanese --count 10 --delay 3 --out /app/scripts/variety_nonenglish.json

# 3. Read 10 random English stories (the numbers cannot tell whether a story makes sense)
docker compose exec langflow python -c "import json,random; d=json.load(open('/app/scripts/variety_english.json', encoding='utf-8')); [print('---', r['story_type'], '|', r['topic'], chr(10), r['text'], chr(10)) for r in random.sample(d['results']['English'], 10)]"

# 4. Optional: one type at a time
docker compose exec langflow python /app/scripts/run_story_batch.py --languages English --count 5 --story-type letter --delay 3
```

**Watch for.** Richer stories use more words outside the list (allowed now, up to 5, but check that
they stay everyday words); the language-correctness fix must not regress (check step 2's
non-English summary); and the 20-second story cache means asking for "another story" within 20
seconds returns the same one (it exists to absorb the Agent's repeated calls).

#### Results (20 English stories, then 10 each in Spanish, French, Japanese; `--delay 3`)

| Measure | Baseline | Target | Result | |
|---|---|---|---|---|
| Mean overlap between stories | 0.44 | ≤ 0.30 | **0.24** | met |
| Distinct story types in 20 | 0 recorded | ≥ 6 | **6** | met |
| Most common opening | 44% ("hello i am") | ≤ 20% | **20%** ("hello sam") | met, at the limit |
| Most repeated vocabulary word | 100% ("today") | ≤ 60% | **100% ("water")** | **not met** |
| Pass rate at ≤ 5 stray words | — | ≥ 80% | **2/20 (10%)** | **not met** |
| Non-English stories in the requested language | 30/30 | ≥ 90% | 27/27 generated (27/30 counting failures) | met, no regression |
| Story latency p50 | 1.1–1.5s | ≤ 3s | 0.8s (English), 1.1–2.6s (others) | met |
| Human read of 10 stories | — | ≥ 8 / ≥ 6 / ≥ 8 | not done by the owner yet; my read of 7 samples below | open |

**What happened: variety went up, and staying inside the learner's vocabulary went down.**
- New-type English stories have **29% of their words outside the vocabulary** (about 14 stray words
  per story, 8–25), against 3% for the two classic stories in the run. The pass rate by tolerance:
  ≤ 5 words 2/20, ≤ 10 5/20, ≤ 15 13/20, ≤ 20 17/20. The prompt's "at most 5 everyday words" was
  ignored.
- **Topic seeds force new nouns.** "A bus ride", "a new pet" and "a picnic" need bus, driver,
  rabbit, basket, and the model uses them. The topics themselves are outside a 16-word vocabulary.
- **The model stuffs the whole word list into every story**, which is why one word is in 100% of
  stories: "He says hello to his house", "You can drink water and say thank you for the snack". The
  stories read as stilted. This is the "forced every word in" failure from the first prompt
  iteration, back again.
- **Most strays are verbs** (read 11, drink 8, eat 5, together, soon, happy), because the starter
  vocabulary has almost no verbs. That part is fixed by data, not prompts: `sample_data/suggested_words.csv`.
- **Letters were 8 of 20 English stories**, which looks wrong for a type drawn 12.5% of the time
  (1 in 650 for one run). Pooled over all 50 stories it is 9/50 (18%), so it is most likely chance,
  and the selection code has no bias in 1,600 test draws.
- **My read of the samples:** the Spanish and French stories are natural and the best we have
  produced (a Spanish evening at home: María prepares water and bread, a friend calls, they share a
  biscuit and say goodbye). The English new-type stories are varied in form but stuffed and stilted.
  The owner's read of 10 stories is still needed.

**Measurement bugs this run exposed (all fixed, tests first):**
1. A Japanese story written on one line with 。 and no spaces was counted as 1 sentence ("off-length").
   Sentences now split after 。！？ without needing whitespace.
2. A French narration line "Marc dit : « ... »" was read as a speaker label ("bad format"). A label
   must not start with a lower-case word.
3. Names that only ever start sentences (Sam, Maya, Anna) counted as stray words. A capitalised
   non-vocabulary word seen twice and never in lower case is now a name (mean strays 14.25 → 13.65).
4. 3 of 10 Japanese stories came back as the fallback message with latencies of about 3.4s, which
   looks like retries running out (rate limit): the batch ran about 50 stories with `--delay 3`,
   while earlier runs used 20s with no failures. The cause was not recorded, so it is **unconfirmed**;
   the runner now records the model error for every failed story.

Corrected scores: English unchanged at 2/20; French 10/10 (was 9/10); Japanese 7/10 generated
(was 6/10), language 7/7.

**Verdict: partly met.** Variety and the form of stories improved; vocabulary fit and the pass rate
did not. Not done yet: the owner's read, and a clean Japanese re-run.

**Next, one change at a time:**
1. **Grow the vocabulary (data, not code).** Upload `sample_data/suggested_words.csv` (50 verbs,
   nouns, adjectives) with the Upload Word File component, then re-run the English batch with
   `--delay 10`. Most strays are verbs and everyday nouns that would now be in the list.
2. **If one word is still in most stories:** give each story a random subset of 4 focus words
   (the rest optional) and shuffle the list order, so the model stops stuffing the whole list.
3. **If strays are still high:** pick topics only when their key words are in the vocabulary (the
   topic list then unlocks as the vocabulary grows), and replace "at most 5 words" with a rule the
   model follows better: no new nouns, only simple verbs and adjectives.
4. **Owner decision if needed:** how many unknown words per story is acceptable for a beginner.
   Today's tolerance (5) is a guess; `--rescore ... --max-oov N` shows any other value instantly.

## Tuning log

| # | Change (one thing at a time) | Why | Before | After |
|---|------------------------------|-----|--------|-------|
| 0 | Baseline, no change (20 English stories, strict rule: 0 stray words) | | — | **7/20 pass (35%)**; 0 failures, 0 leaks, 0 off-length, 0 bad format; mean 1.30 stray words/story; top stray words: bring 5, drink 4, together 4, share 2, eat 2, sure 2, happily, offers, bake, shares |
| 0c | Routing run: non-English stories re-scored with the language check | The structure-only check passed stories written in English | 15 passed on structure | **5/15 in the requested language** (Spanish 3/6, French 2/6, Japanese 0/3) |
| 1 | Language-aware prompt for non-English stories (translate-the-meanings rule, no English example, normalized language name) | Only 5/15 non-English stories were in the requested language; the English vocabulary list and English examples pull stories back to English | **5/15** in the requested language (Spanish 3/6, French 2/6, Japanese 0/3), from the routing run re-scored with the language check | **30/30** (Spanish 10/10, French 10/10, Japanese 10/10); structure also 30/30; read samples were natural |
| 2 | Story variety: more story types, topic seeds, a looser word rule, longer flexible lengths | Reading 48 stories: 81% mentioned water, ~75% were somebody asking for something; baseline overlap 0.44, 'today' in 100% of English stories, 44% opened "Hello, I am..." | 0.44 overlap, 'today' in 100%, 44% "Hello, I am..." (18 English routing stories) | overlap **0.24**, 6 types, top opening 20%; but 'water' in **100%**, 29% of words outside the vocabulary, pass rate **2/20** at ≤ 5 strays; non-English language 27/27 (3 Japanese generation failures, cause unconfirmed) |
| 0b | Same baseline, re-scored with the relaxed rule (≤ 2 stray words) | The strict rule was unrealistic for a 12-word vocabulary; the stray words are everyday words | 35% | *run `--rescore` and record here* |
