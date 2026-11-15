# Story score (0 to 100) and the example bank

Added 6 November 2026 (patch 0057). Code: `tutor_core/tutor_core/quality/score.py`, `example_bank.py`, `prompts/example.py`; table `tutor.story_examples` (migration 0016); refresh script `api/scripts/refresh_story_bank.py`.

## The score (version 3, 7 Nov 2026)

Version 3 (patch 0062) changes only requirement 5. It used to see list-like text, repeats and blanks, so a wrong article or verb ending was invisible. It is now **100 × (share of sentences with no mistake) − 34 per structural problem**. Mistakes come from up to three sources, all reported as one `Hit` (`quality/grammar/`): (1) built-in rules, always on, no network, tuned for no false alarms (a/an, he/she/it verbs, article and noun gender in es/fr/it/pt/de, de el / di il / em a, subject pronoun and verb, German noun capitals, Chinese measure words, Japanese particles, Korean particles); (2) LanguageTool, only when you run a server and set `LANGUAGETOOL_URL` (grammar and spelling matches only; learners' text never goes to a public server); (3) a model review (`audit`), only when the caller passes its hits in: the model lists mistakes as JSON, every quoted mistake must really be in the text or it is dropped. A sentence with several mistakes counts once; a spelling mistake counts half; a style remark counts nothing. `score_story(..., hits=None)` never calls anything itself, so the same text scores the same.

**How good is it?** `python scripts/grammar_probe.py` injects known mistakes into clean texts (9 languages, 54 mistakes) and reports recall and false alarms per layer. Built-in rules alone: 0 false alarms, about half of the injected mistakes found (gender, contractions, particles, measure words well; verb agreement with a noun or name as subject is the gap). Add `--audit` (needs the key) or set `LANGUAGETOOL_URL` to see the other layers. Use a different model for the review than for the story (`GROQ_AUDIT_MODEL`): a model marks its own writing leniently, and Groq counts the free tier per model.

**Options considered:** a larger rule set by hand (cheap, but never reaches the real errors: missing articles, wrong prepositions); LanguageTool (broad and deterministic; Java service; Italian weak, Korean none); a model review with verification (broad, costs a call, can miss); a morphology analyser such as spaCy (strong for agreement, heavy install per language; not built); the earlier model *rating* of grammar (a number with no evidence; not used).

## Free checks and the next score (patch 0065)

`tutor_core/story_gates.py` gives a pass/fail verdict next to the score: length range, own words within [target, max(target+3, 2x target)], words tacked on after a comma, fragment-heavy text, structural problems, too many sentences with a mistake, and a failed story from the score itself (`passed` is False). Score version 4 (patch 0066, `quality/score.py`) weights grammar 40, naturalness 25 (optional), own words 15, the rest 3 to 6, and cuts a failed story to 60%. Known gap: a text made only of the learner's words in 5 to 6 word sentences still passes.

## Version 2 (kept for history)

Version 2 came from your second comparison run (32 scored stories): five of six parts sat at 97 or more, so only length moved the total and the weights were equal on paper only. Changes: length is less strict (15% / 60%); the your-words part now punishes stuffing; the grammar part sees blanks, one word repeated and Chinese run-ons. Parts that really are met stay at 100: that is the story following the requirement, not a flaw in the score. Saved examples scored under version 1 yield to any version 2 story, because the numbers cannot be compared. Re-score a saved run without calling the model: `python /app/scripts/compare_story_versions.py --rescore compare_<time>.json`.

Six requirements, each 0 to 100, **equal weight**; the story score is their mean. The existing pass/fail quality report (rules version 6) is unchanged and separate.

| # | Requirement | 100 when | 0 when |
|---|---|---|---|
| 1 | Length | within 15% of the target (the tier's length; with no tier 50 words for dialogue and narration, 80 for other kinds; characters for Chinese and Japanese) | 60% off or more; a straight line between |
| 2 | Your words | all of the target count appear (the tier's own-words number, else 3, never more than the list holds) | none; score = found ÷ target. **Stuffing:** 5 points off for every point the learner's words make up above 25% of the story |
| 3 | Uncommon words | the share is at or below the target % (the tier's, else 10) | target + 20 points or more; a straight line between |
| 4 | Sentence length | the mean sentence is 6 to 12 words (8 to 24 characters in Chinese and Japanese) | 15 points off per word outside the range (7.5 per character), and 15 more when any sentence is over 20 words (40 characters) |
| 5 | Grammar and fluency | no sentence with a mistake (see version 3 above), and none of the code-visible problems: list-like text, a sentence written twice, most sentences opening alike, a blank left in ("[Votre nom]"), one word repeated (4 times and at least 12% of the story), a Chinese or Japanese run-on (4 or more commas in one sentence) | every sentence has a mistake; 34 more off per structural problem |
| 6 | Language and format | 25 each: in the requested language; ends on a finished sentence; no blank left in or leaked plan; the format fits the kind | none |

**Gate:** a story that is empty, a failure message, a leaked plan or recognisably in the wrong language scores 0 and is never saved. The language check separates English or the wrong script from the target language; it cannot tell Spanish from German.
**Partial:** if the uncommon-word share cannot be measured, that requirement is left out and the others share the weight (`partial: true`).
**Limit:** without LanguageTool or the model review, requirement 5 sees only what the built-in rules see. It is a floor, not proof of correct grammar.

## The bank

- At most **two stories per language** (database: `UNIQUE (language, slot)`, slot 1 or 2).
- A new story goes in when the language has fewer than two, or **replaces the lower of the two only if its score is strictly higher**; the text and the score change together. A tie keeps the older story.
- A saved story under 85 is marked *provisional*: kept only until a better one arrives.
- Candidates are written **only from the starter-pack words** (about 48 per language), never from a learner's list, topics or stories, so no learner's text reaches another learner's prompt.
- Only the refresh script writes (as the database owner). The story tool's role (`tutor_tools`) may read.
- Refresh: `docker compose exec api python scripts/refresh_story_bank.py` (see `--help`; `--status` shows what is saved with no model calls). It exits with a failure code while any language has fewer than two.

## Using an example in the prompt (off by default)

`STORY_EXAMPLES=1` quotes the best saved example of the language before the final instruction of the story prompt. The wording is explicit, not vague: *use it only to see how natural and correct the sentences are; do not copy its topic, characters, sentences or words, and do not take its length or format from it; the requirements above decide what to write.* A vague "use it as a reference" leaves the model to guess what to take, and it then copies or ignores the example unevenly. Whether it helps is measured with the comparison page, not assumed. It does not yet reach the draft call of two-pass generation.


## Version 4.1 (9 November 2026): what reading 38 stories showed

Two runs of `run_story_methods.py` (en, es, fr; GPT-OSS-120B and Qwen 3.8 writing, judging and reviewing) were read by hand and graded 0-100, then compared with the scores. The offline v4 score agreed only loosely (Pearson 0.54): it passed stories with a markdown leak, gender mistakes hidden by it, 34 four-word lines, words stuck on after commas at 22% of the sentences, and sentences cut off on "y". Fixes are listed at the top of `quality/score.py`. Each reviewer misses things the other finds (GPT-OSS missed "una libro"; Qwen missed padding words such as "inside still", "outside today"), so `merge_reviews` joins their findings. Findings that overlap on the same words count once.

Still not seen by any check: stories that read as nonsense but are grammatical ("Cinco amigos comen pasto"), and filler adverbs added to every line. A model review of naturalness (the optional `naturalness=` 1-5 input, weight 25) is the planned answer.


## Naturalness review (patch 0068)

The part with the most weight after grammar (35 of 104; the score divides by the weights of the parts present, so a story without a rating is scored on the rest). A model reads the story as a native reader and answers 1 to 5: 5 flows and makes sense; 3 is stiff (padding words, word lists, choppy lines); 2 or less fails the story. It is asked separately from the grammar review so a model cannot hide a stiff text behind "no mistakes found". Use a different model than the writer, and read the ratings of both reviewers side by side in "Reviewers compared": if they disagree a lot, trust the one whose ratings match your own reading of a few stories.


## Offline signals (patch 0072)

Can something that is not an LLM judge grammar and naturalness? `scripts/eval_signals.py` measures every story in a saved run with signals that need no Groq call and checks each against my hand grades (`scripts/data/hand_grades.json`, 38 stories graded 9 November).

| Signal | What it measures | Needs |
|---|---|---|
| `languagetool` | errors per 100 words (style hints excluded) | a LanguageTool server, `LANGUAGETOOL_URL` (default `http://localhost:8010`); none for Korean |
| `perplexity` | how surprised a local multilingual model is by the text (lower is more natural) | `pip install torch transformers`; model from `MODEL` (default `Qwen/Qwen2.5-0.5B`) |
| `worst_sentence` | the same, for the single most surprising sentence | same |

Run it after the overnight run (so it does not compete for Docker):

    docker run -d -p 8010:8010 erikvl87/languagetool
    PYTHONPATH=tutor_core:scripts python scripts/eval_signals.py scripts/*methods_*.json --signals languagetool,perplexity,worst_sentence

The table shows Pearson and Spearman against the hand grades, after z-scoring within each language so a harder language does not look like a worse signal; a `meta` row averages the signals with no fitting (38 grades is too few to fit anything). Baseline to beat, with no signals: story score v4.1 Pearson 0.69, model review 0.72. A signal is worth adding to the score only if it correlates at least as well as these and the correlation holds on the next run; with this few grades, treat differences under about 0.2 as noise. To add a signal, write one class with `name`, `higher_is_better` and `measure(text, language)` in `story_eval/signals.py`.


## Refine: check, then fix only what was found (patch 0073)

`refine` = one writer call, then a bounded loop (max 2 rounds): **observe** (rules, gates, LanguageTool if set, a model review) → **plan** (flagged sentences, whole-text needs) → **repair** (one call, only the flagged sentences) → **verify** (keep only if the score rises by 0.5, the text changed, and at least 70% of the unflagged sentences are untouched). It is a fixed loop, not a free-form agent, so every run is comparable and costs at most 1 + 2 repair calls + 3 reviews.

Test on 10 English stories (a part at a time, because of the daily Groq limit):

    docker compose exec langflow python /app/scripts/run_story_methods.py --variants refine --languages en --count 10 --limit 5 --no-translate --audit-models gpt,qwen --out /app/scripts/refine_en.html
    docker compose exec langflow python /app/scripts/run_story_methods.py --variants refine --languages en --count 10 --no-translate --audit-models gpt,qwen --resume /app/scripts/refine_en.json

Add `--variants baseline,refine` to see the same ten requests written by the plain one-call pipeline next to the refined one. The report's "Pipeline detail" lists each phase; the JSON keeps the full `trace` for every story.

### What the 13 November Kaggle run showed, and what patch 0085 changed

10 English stories, baseline against refine, reviewed by gpt-oss-120b and qwen3.8 (20 reviews per method):

| | baseline | refine |
|---|---|---|
| mean score with review | 63.0 | 66.5 |
| **failed reviews** (naturalness 2 or less, too many mistakes, stuffing) | **8 of 20** | **8 of 20** |
| medium stories (3), failed reviews of 6 | 5 | 0 |
| hard stories (3), failed reviews of 6 | 1 | 5 |
| easy stories (3), failed reviews of 6 | 0 | 1 |
| model calls / seconds per story | 1.8 / 3.1 | 4.9 / 49.8 |

- **The mean score misleads.** A naturalness rating of 2 fails the story and roughly halves its score, so scores sit in two groups (75 to 92, or 23 to 45) and the mean mostly counts how many ratings landed on 2 instead of 3. The two reviewers agree on the exact rating for 10 of 20 texts (within one point for 19 of 20); qwen rates about half a point lower (mean 2.7 against 3.15), and that is enough to decide pass or fail. The report now shows failed reviews and the mean rating next to the mean score.
- **Refine fixes grammar and breaks naturalness.** On medium stories the loop fixed real mistakes (missing articles, "wake" for "wake up"): 5 failed reviews became 0. On hard stories it made the text read worse in all three (rating 4, 3, 4 became 2, 2, 2), with filler such as "this bright morning today" and "happy today indeed", and 14 to 34 words longer than the baseline story.
- **Why.** (1) The loop's own score left naturalness out, so it recorded 83.2 to 96.2 for a text the same reviewer then rated 2 of 5. (2) The whole-text needs (reach 180 to 220 words, use fewer of the learner's words, simpler words) were sent to the model together with the flagged sentences: it padded the text, or rewrote all of it and was rejected (3 of 10: "rewrote too much"). (3) The comparison itself was unpaired: refine writes its own first draft, so the difference to the baseline story is mostly the difference between two drafts.

Patch 0085 changes: the loop rates naturalness at every observe (one more call each) and throws a repair away when the rating drops; only the flagged sentences are sent to the model and the whole-text needs are recorded as "measured, left alone"; the first draft travels with the result (`StoryResult.draft`), and the runner reviews it with the same reviewers (`entry["draft"]`, only when the loop changed it) so the report can show **the draft against its own repair**; a run that stops says why in `meta["stopped"]` (rate limit, interrupt or crash, with the story and method).

### Writer rules (patch 0086, idea 1 built, off by default)

Three sentences added to the story prompt before its last line, for every language (the example is English only): *small words stay* (never drop an article, possessive, preposition, particle or verb ending that the language needs, with "the drawer, not drawer" for English); *use a listed word only where it belongs* (leave it out instead of attaching it after a comma or adding a sentence just to use it); *no filler* ("today", "now", "still", "indeed") at the end of sentences. The text is in `prompts/builder.py` (`_WRITER_RULES`). The two-pass route puts the same rules in its adapt prompt, the step that writes the final text.

Off unless `StoryOptions.rules` (environment `STORY_WRITER_RULES=1`), so the default prompt, the English prompts pinned by tests and every stored story's cache key are unchanged. It is **not measured on Groq yet**: the evidence is the reviewers' findings on ten first drafts, not a before and after. To measure (10 English stories, two methods: about 26 writer calls and 80 review calls, two reviewers each making an audit call and a rating call per story):

    docker compose exec langflow python /app/scripts/run_story_methods.py --variants writer --languages en --count 10 --no-translate --audit-models gpt,qwen --out /app/scripts/writer_en.html

Read **failed reviews** and the mean naturalness first, then the findings per story in the reviewer table: the rules work if the findings that were articles, tacked-on words and adverbs fall and the ratings do not. Then `--variants baseline,rules,refine,rules_refine` to see whether the loop still helps once the drafts are cleaner. A rule that lowers the ratings (for example, texts that avoid the learner's words) is to be dropped or reworded; the words are what the learner came for, so also look at "own words used" in the baseline column.

### Ideas not built yet, with the evidence

1. **Tell the writer what the reviewers punish** (built as patch 0086, to be measured). Of 25 findings on the ten refine first drafts, 10 were a missing article or possessive ("to kitchen", "in house", "opened drawer", "friend on the phone"), 4 an unneeded word or phrase ("please", "thank you", "goodbye today", "to me"), 4 an adverb in the wrong form or place ("bright", "gone still", "tired slowly"); my grouping, by the wording of each finding. The classic writer prompt asks for short sentences (5 to 10 words) and only says articles "may" be added; it never asks to keep them or not to pad (the story-type prompts were not re-read for this). One added rule per language family (keep every article, possessive and particle even in short sentences; leave a learner word out rather than tack it on; no "today", "now", "still" at the end of lines) targets 18 of the 25 findings at no extra call. Measure with `--variants baseline` before and after.
2. **Write again instead of repairing when the draft reads unnatural.** Sentence repair cannot fix a rating of 2. About one baseline review in three (6 of 18, leaving out the stuffed story) rates the draft 2 or less. Whether a second draft of the same request would pass is not measured yet: write each of the ten requests three times with the plain pipeline and rate each draft (30 stories) before building this. One new draft chosen by the same rating, only when the rating of the first is 2 or less or a free gate fails, costs 3 calls on a third of the stories.
3. **Fit the word target to the list.** Hard asks for at least 8 of the learner's words in 200 words. With a list of 12 greetings and interjections ("please", "yes", "no", "sorry", "excuse me") the hard stories used 10 to 12 of them, and in each of the three pairs the version that used more words was rated lower. Try a hard minimum of 6, or a minimum that scales with how many of the words are nouns and verbs.
4. **A softer cliff.** Today a single 2 fails the story and halves the score. With one reviewer that is a coin flip near the boundary. Options: rate twice and take the mean; count 2 as a warning and fail only at 1.5 or below; or ask for a 1 to 10 scale.
5. **Free gates cannot see naturalness.** On the 20 texts a reviewer failed 10; the free gates failed 3 of those (the "stuffed" ones). Simple offline detectors (share of lines ending in "today", "now", "again") did not separate failed from passed texts on this sample, so the model rating stays the judge; a better offline signal is a question for `eval_signals.py` with LanguageTool and perplexity on the hand grades.
6. **Cost.** Refine is 5 calls and about 50 seconds per story on the free tier; the rating adds up to 3 calls. Worth it only if the paired table shows a gain on every level, otherwise use it on medium and hard only after fixing idea 1.


## What is left on each key (patch 0075)

`scripts/key_status.py` makes one 1-token call per key and model and prints and saves Groq's counters (`key_status.json`, names only). Each call uses one request of the day. A key that is already refused reports which limit it hit (per-minute or per-day tokens) and how much it used. The run JSON's `meta["key events"]` lists every refusal a story test saw, with the same fields.

## Story Test Desk (patch 0076)

A local page for watching tests while they run. Start it with `test-desk.bat` (port 8090; `--port` to change). It reads `test-reports\overnight-*\SUMMARY.txt`, the step logs, and `scripts\overnight_*.json` / `refine_*.json`, and refreshes every 10 seconds. A run counts as running when it has no Finished line, no exit code, and a log written within 15 minutes. `run-overnight.bat` starts the desk itself. The refine step is shown as its own run with the phase-by-phase trace for each story. "Check keys now" runs `key_status.py` inside the Langflow container.
