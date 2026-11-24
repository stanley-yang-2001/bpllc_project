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

### When a run is cut: what the files say (patch 0087)

The 13 and 14 November Kaggle runs of the overnight set ended after one story and the JSON could not say why. A run now leaves three files next to each other, and each one is enough on its own:

- **`.status.txt`** (read this first, rewritten on every save): `FINISHED`, `STOPPED` (with the reason) or `INCOMPLETE (no stop reason: the process was probably killed)`; stories done per method; the next one to make; how many reviews and ratings each reviewer answered and why the others did not; preflight problems; the command.
- **`.json`**: the numbers, plus `meta.stopped`, `meta.preflight`, `meta.run` (start, last save, command, commit, Python, platform, the STORY_* and model settings, never a key, and the earlier runs of the same file after a `--resume`) and `meta.log` (the last 400 lines the run printed, with times, without the organisation id or any key).
- **`.html`**: the same at the top of the Summary tab, in red when the file is not whole, and the log at the bottom.

A stop reason now reads like `limit too long to wait for: daily limit on openai/gpt-oss-120b (tokens per day: used 199,264 of 200,000, this call needs 3,118), retry in 8m26s (at en-0, cascade)`, or `interrupted (signal 15: the host or the notebook stopped the process)`, or `crashed: ValueError: ...`, or `the time budget (--max-minutes) ran out`, or `--limit 5 reached (planned ...)`.

New in the command:

- **Preflight** (on; `--no-preflight` skips it): one tiny call on each model the run will use, before anything is made. A wrong model id (404), a refused key (401), a bad request or a daily limit that will not lift for hours stops the run in the first minute and says why in all three files; a server blip only warns. It costs about 100 to 300 tokens per model.
- **`--max-minutes N`**: stops cleanly between two stories after N minutes, so a host that kills long jobs (Kaggle: 12 hours) never gets to kill it without a reason. Use 660 on Kaggle.
- A **kill signal** (SIGTERM, SIGHUP) is caught, written down and saved. SIGKILL cannot be caught: the file is then as the last save left it, and the `INCOMPLETE` line with "next to make" shows where it was.
- **`--limit N` now keeps all requests in the file** and only makes the first N in this run, so `--resume` makes the rest ("run it in parts" did not work before: the file held only the N requests).

#### Running on Kaggle

1. Apply patches 0085, 0086, 0087 to your checkout and push (`git am --3way`, then `git push`). Kaggle does not see local changes.
2. In the notebook, get the new code: if the notebook clones the repo, restart the session (or run `git -C <repo> pull`); if the repo is an attached dataset, create a new dataset version from the new checkout and attach that version. Check with `git -C <repo> log --oneline -1` (or open `scripts/story_eval/health.py`: it must exist).
3. Keep the keys in Kaggle secrets as before (Add-ons, Secrets; each one switched on for the notebook), exported into the environment before the command. The model names are secrets too: `GROQ_QWEN_MODEL`, and `GROQ_JUDGE_MODEL` / `GROQ_AUDIT_MODEL` if you use them (with no `GROQ_JUDGE_MODEL` the story model judges the cascade; before patch 0088 that crashed). The preflight tests a judge model you set with one tiny call, so a misspelled model id stops the run in the first minute.
4. Run the step with `--out` in `/kaggle/working` (only that folder is kept) and a time budget, for example:

       python scripts/run_story_methods.py --variants writer --languages en --count 10 --no-translate --audit-models gpt,qwen --max-minutes 660 --out /kaggle/working/writer_kaggle.html

5. Run the cell that checks the result even when the step failed (put it in its own cell, or end the step line with `; true`): `!cat /kaggle/working/writer_kaggle.status.txt`.
6. If it says `STOPPED` or `INCOMPLETE`, run the same command again with `--resume /kaggle/working/writer_kaggle.json` (the resume reads the earlier reason and keeps the log), after the limit has lifted (the status file says when) or with another key in `GROQ_API_KEY_2`.
7. Send back `writer_kaggle.status.txt` and `writer_kaggle.json` (the `.html` is optional: it is made from the JSON).

### Writer rules (patch 0086, idea 1 built, off by default)

Three sentences added to the story prompt before its last line, for every language (the example is English only): *small words stay* (never drop an article, possessive, preposition, particle or verb ending that the language needs, with "the drawer, not drawer" for English); *use a listed word only where it belongs* (leave it out instead of attaching it after a comma or adding a sentence just to use it); *no filler* ("today", "now", "still", "indeed") at the end of sentences. The text is in `prompts/builder.py` (`_WRITER_RULES`). The two-pass route puts the same rules in its adapt prompt, the step that writes the final text.

Off unless `StoryOptions.rules` (environment `STORY_WRITER_RULES=1`), so the default prompt, the English prompts pinned by tests and every stored story's cache key are unchanged. First measured on 15 November (next section). To measure (10 English stories, two methods: about 26 writer calls and 80 review calls, two reviewers each making an audit call and a rating call per story):

    docker compose exec langflow python /app/scripts/run_story_methods.py --variants writer --languages en --count 10 --no-translate --audit-models gpt,qwen --out /app/scripts/writer_en.html

Read **failed reviews** and the mean naturalness first, then the findings per story in the reviewer table: the rules work if the findings that were articles, tacked-on words and adverbs fall and the ratings do not. Then `--variants baseline,rules,refine,rules_refine` to see whether the loop still helps once the drafts are cleaner. A rule that lowers the ratings (for example, texts that avoid the learner's words) is to be dropped or reworded; the words are what the learner came for, so also look at "own words used" in the baseline column.

### What the 15 November Kaggle runs showed (patch 0088)

The same 10 English requests (`en-0` to `en-9`) written four ways, 20 reviews each (gpt-oss-120b and qwen3.8):

| | baseline | writer rules | refine | rules + refine |
|---|---|---|---|---|
| **failed reviews** of 20 | 10 | 10 | 8 | 8 |
| mean naturalness (1 to 5) | 2.6 | 2.7 | 2.9 | 3.0 |
| first draft, failed reviews of 20 | 10 | 10 | 14 | 7 |
| findings per story, gpt / qwen | 2.1 / 2.0 | 1.8 / 1.0 | 0.9 / 0.7 | 0.9 / 0.7 |
| model calls / seconds per story | 1.8 / 7.6 | 1.7 / 8.7 | 7.7 / 90.6 | 8.0 / 99.8 |

- **The words and the topic decide, not the method** *(corrected 16 Nov: with 30 requests the request explains 9% and the word pack 6%; this was exaggerated by having only ten requests, see the next section)*. Of the variation in the 80 ratings (4 methods, 10 stories, 2 reviewers) the request explains 49%, the starter pack alone 27%, the method 3%, the reviewer 4%. The three "basics" requests (hello, goodbye, please, thank you, yes, no, sorry, excuse me, good morning, good night, welcome, how are you) failed 18 of 24 reviews (mean rating 2.25), against 2 of 16 for numbers (3.25), 5 of 16 for people (2.88) and 11 of 24 for food (3.00): half of the 36 failed reviews came from 3 of the 10 requests. All 8 ratings of `en-4` were 2, whatever the method.
- **Why basics fail.** These are things people say. As narration they read as nonsense: "I say excuse me to the wind", "she cried sorry", "said thank you bright", "I think, how are you feeling when you watch today?". The reviewers write "discourse markers misused as speech", "forced vocabulary usage", "nonsensical interactions". Of the 31 ratings of 2 or less, 18 name illogical, nonsensical or disjointed text; of the 49 ratings of 3 or more, 2 do (my grouping, by keyword).
- **One comparison of two arms is too noisy to read.** The same prompt failed 10 of 20 reviews as the baseline and 14 of 20 as the refine arm's first draft. A gap smaller than about 4 failed reviews is not a difference.
- **The writer rules lean positive, not proven** *(settled 16 Nov: with 30 requests there is no effect)*. The arms look flat (10 against 10, 8 against 8). Pooling the first drafts of both arms (40 reviews each) gives 24 failed without the rules and 17 with; the mean rating per request is +0.25 higher with them (about 95% interval 0.00 to +0.50), better on 7 of 10 requests and worse on 1 (sign test p about 0.07). The reviewers' findings fall from 41 to 28 (articles 13 to 5, verb forms 12 to 2, extra words 6 to 3), but "missing word" rose from 3 to 7 and "meaning" from 3 to 5. More requests are the way to settle it: `--count 30` makes 30 English requests (the same ten first).
- **Refine removes mistakes, not the "reads unnatural" verdict.** Findings per story fall from 2.5 to 0.9 (gpt) and from 2.9 to 0.7 (qwen) between the draft and the result, so the gain is not one model marking its own repair. Failed reviews, draft to result: 14 to 8 for plain refine; 7 to 8 with the rules (those drafts were already cleaner and the loop added nothing). Ratings, draft to result: plain refine, gpt up on 4 of 7 changed stories and never down, qwen up on 2 and down on 1; with the rules, 1 up and 3 down of 14. Of 27 verify rounds 19 were kept and 8 thrown away (4 for a lower rating, 4 for no gain in score), so the guard from patch 0085 works. In 9 of the 34 planning rounds the loop's own list ended with "Rewrite it so it reads naturally", which sentence repair cannot do and leaves alone. It costs 4 to 5 times the calls and about 12 times the seconds (the rate limit included).
- **The cascade crashed on Kaggle (fixed).** `overnight_kaggle` stopped after three stories with `AttributeError: 'NoneType' object has no attribute 'meter'` at `en-0`, `cascade`, and the cell ran it 8 times in all, about 30 minutes apart (06:23 to 10:12 UTC), with the same crash every time. The notebook had no `GROQ_JUDGE_MODEL` (the cell copied the keys and `GROQ_QWEN_MODEL` only), so the run had no separate judge channel, the story model judges, and `run_one` read `.meter` from the missing channel to record which model judged. The earlier overnight run that ended at the same place was most likely this crash. Fixed in `run_one` (a judging method without a judge channel is judged, and recorded, by the story model) with a test that fails without the fix. The Kaggle cell now also copies `GROQ_JUDGE_MODEL`, `GROQ_JUDGE_EFFORT`, `GROQ_AUDIT_MODEL`, `GROQ_AUDIT_EFFORT` and `GROQ_MODEL`, prints which secrets it found, and gives up a test that crashes twice in a row with the same text instead of retrying it 8 times.

### What the 16 November round showed (patch 0090)

Three files from one Kaggle round of about an hour: `writer_kaggle_30` (30 English requests, baseline and writer rules, 60 stories, both reviewers), `overnight_kaggle` (the cascade set: 5 methods on the first 4 requests, en-0, en-1, es-2, es-3, stopped by `--limit 4`) and `rating_lab_kaggle` (60 stories x 2 reviewers x 2 rating prompts x 3 repeats).

- **The writer rules do nothing.** 9 of 30 stories were passed by both reviewers in each arm; failed reviews 32 and 34 of 60; mean rating change -0.1 (-0.4 to +0.3), better on 13 requests, worse on 12, the same on 5, sign test p 1.0. The "lean positive" of the ten-request runs (24 failed reviews against 17) was chance. They stay off.
- **A story fails more often than it passes.** Of the 60 stories, 18 were passed by both reviewers, 18 split them and 24 were failed by both. Failed reviews by word pack: basics 22 of 32 (68%), food 59%, numbers 50%, people 39%; by level: easy 65%, medium 47%, hard 52%. The request explains 9% of the variation in ratings, the word pack 6%, the reviewer 4%, the method 0%: the 49% of the 15 November file came from having only ten requests. The greeting words are still the worst pack, but not by the margin it looked.
- **The cascade is the first method that clearly moves the verdicts, on four requests.** Baseline: 0 of 4 stories passed by both reviewers, 7 of 8 reviews failed, mean ratings gpt 2.2 and qwen 2.0, 3.8 findings per story. Cascade: 4 of 4 passed, 0 of 8 failed, ratings 4.0 and 3.0, no findings. Cascade with a proofreading call instead of the repair: 4 of 4, ratings 3.2 and 3.0. The plan alone (+0.4) and mixed candidates with free gates (+0.6, no model review) are inside the noise. Both reviewers see the gain (gpt +1.8, qwen +1.0), so it is not only gpt rating the work of its own model. Four requests are too few to call it clear: with 4 pairs the sign test cannot go below p 0.12. It costs 12 model calls and 13 seconds in the model per story against 1.8 calls and 3.6 seconds (93 seconds against 5 on the free tier, with the waiting). And part of the gain is a story that does not force every word in: the cascade used 5.8 of the 12 learner words, baseline 7.2, at the same length (en-1 became a diary letter with five of the twelve food words). The free score sees none of this (99 for both); the report now shows "learner words used" beside the verdicts.
- **How steady is a rating? (the rating lab)**

  | | gpt, prompt v1 | qwen, prompt v1 | gpt, prompt v2 | qwen, prompt v2 |
  |---|---|---|---|---|
  | values used (of 180) | 2 x71, 3 x69, 4 x40 | 1 x2, 2 x96, 3 x75, 4 x7 | 2 x3, 3 x92, 4 x59, 5 x25 | 1 x6, 2 x43, 3 x64, 4 x54, 5 x13 |
  | fail (2 or less) | 39% | 54% | 2% | 27% |
  | repeats all identical | 67% | 65% | 58% | 45% |
  | repeats on both sides of the pass line | 22% | 30% | 7% | 25% |
  | between-story share of variation (ICC) | 0.81 | 0.47 | 0.72 | 0.67 |

  The same reviewer rating the same text again gives the same number about two times in three and is within one point nearly always, but the verdict flips for a fifth to a third of the stories. A single qwen rating is mostly noise (ICC 0.47; the median of three would give about 0.73 by the Spearman-Brown formula). The two reviewers disagree on pass or fail for 34% of ratings, qwen rates 0.34 lower, and their story means agree with a rank correlation of 0.47. Of the 60 stories, 23 are solid passes (0 or 1 of their 6 v1 ratings fail), 16 solid fails (5 or 6) and 21 sit in the middle, where the verdict is whoever and whenever asked.
- **Prompt v2 is not a clear win, and stays off.** It moves every rating up by about 0.7 and changes the verdict on 36 to 37% of ratings. gpt almost never fails under it (2%), so its pass line never triggers; qwen's ICC rises (0.47 to 0.67) while gpt's falls (0.81 to 0.72); the reviewers' agreement on the ranking hardly moves (0.47 to 0.50); the pass/fail disagreement falls (34% to 26%) mostly because gpt stopped failing anything. The hypothesis v2 was built for, that easy stories are marked down for short sentences, is not in the data: under v1 easy stories fail no more than hard ones (gpt 37% against 40%, qwen 55% against 65%). The default does not change.
- **What the data says to do about the noise: ask more, not differently.** Patch 0090 adds `--rating-repeats N` (each reviewer rates each story N times and the median counts, default 1) and asks a review once more when it failed for a timeout or a non-JSON answer (3 of the 60 qwen reviews of the writer run, and one rating of the cascade run, were lost that way). Median of three costs 4 more short calls per story and reviewer.
- **Idea 7 (greeting words in quoted speech) is demoted.** It is a prompt rule like the ones that just measured as no effect; the cascade's gain is larger and comes from choosing and repairing, not from instructions.

Next round, for the decision "is the cascade worth 7 times the calls" (both ran on 17 November, see below; the next cell is in patch 0092): `--variants baseline,=cascade` on the 30 English requests with `--rating-repeats 3` (60 stories, about 830 calls), then the five cascade methods on all 20 fixed requests (100 stories, about 1,470 calls). `cascade` is both the name of a group of five methods and of one method, so `baseline,cascade` means five; a leading `=` names the single method (`baseline,=cascade`). The size estimate printed before a run now counts the reviewers and the rating repeats (it left them out before, so it said about 870 calls for a run that makes about 1,470).

### Human labels, and what the first round showed (patch 0091)

Everything above was measured with model reviewers, and a model reviewer had never been checked against a reader. `scripts/label_stories.py` does that, with no model calls:

    python scripts/label_stories.py build --from writer_kaggle_30.json,overnight_kaggle.json --out labeling_round1 [--languages fr,de]
    python scripts/label_stories.py analyze --key labeling_round1/label_key_PRIVATE.csv --labels returned_folder [--humans-only] [--out joined.csv]

`build` takes, for each language, `--method-requests` requests (4) with every method that wrote them, so people compare the methods on the same request, and `--per-verdict` stories (6) for each model verdict (passed, split, failed by every reviewer) from other requests, one story a request, spread over levels and word packs. It writes one spreadsheet per language and a README in `story_labeling_set.zip`, and a separate `label_key_PRIVATE.csv`. The sheets are blind: no method, score or verdict, the texts shuffled, ids like EN07. Each text gets three answers: would you give it to a learner as it is (Yes / Small fix first / No: pass, split, fail), how natural it reads 1 to 5 (the reviewers' scale), and the main problem, plus a comment. People are asked to work alone and without AI tools. `analyze` reads the filled sheets (a folder is fine; a person's English and Spanish files are merged by the name in the sheet's "About you" cell, else by the file name) and prints the agreement between labelers, the reviewers and the free score against them, what labelers said where the reviewers agreed, and the methods side by side. `--humans-only` leaves out a sheet whose own cell says it is a model.

**First round (16 to 17 November): 38 texts (28 English, 10 Spanish), three files back.** "SY" calls themselves a native reader of English and Spanish; nothing in the file can verify that. The other two say in their About-you cell that they are models: "AI-assisted benchmark (ChatGPT)" ("not an independent human reader") and "Claude (AI model, not a human reader)", which was run with a fresh context. So this round is one reader of unverified independence and two extra model reviewers, not three humans; every number is also given for SY alone, and `--humans-only` does the same cut.

| | all three files | SY alone |
|---|---|---|
| labelers' own agreement (rank correlation of the 1 to 5 ratings) | 0.76 (ChatGPT, Claude), 0.87 (ChatGPT, SY), 0.81 (Claude, SY) | |
| free score against the labelers' mean rating | -0.13 | -0.16 |
| gpt rating (one rating per story) | 0.81 | 0.79 |
| qwen rating | 0.72 | 0.75 |
| reviewed score (0 to 100) | 0.74 | 0.69 |
| same pass/fail as gpt, as qwen (rating 2 or less fails) | 82 to 84%, 81 to 89% | 84%, 89% |
| cascade against baseline, mean rating (4 requests) | 4.33 against 2.08 | 4.50 against 2.25 |
| "Yes" to the cascade, to the baseline | 10 of 12, 0 of 12 | 3 of 4, 0 of 4 |

- **The free score says nothing about what a reader thinks**, as the rest of this document found with models. It spans 51 to 100 over these texts and does not rank them.
- **The model reviewers do track the labelers.** A single rating correlates 0.72 to 0.81, and they agree on pass or fail on 81 to 89% of texts.
- **A verdict every reviewer agreed on was never contradicted.** Of 15 texts both reviewers passed, no labeler said "No" (45 answers: 22 Yes, 23 Small fix first); of 13 both failed, none said "Yes" (39 answers: 32 No, 7 Small fix). The labelers differ from the reviewers only on the 10 texts the reviewers split on (30 answers: 16 Small fix, 14 No), where a single rating is the noisiest. This is why the report leads with "passed / failed by every reviewer" and treats "split" as undecided.
- **The cascade is the method the labelers prefer on every one of the four requests**, by 1.3 to 2.7 points: the proofreading variant 3.67, the plan 2.50, the mixed candidates with free checks 2.25, the baseline 2.08. But four requests were a lucky draw for the size of the gap: rewritten on 17 November the same four baseline stories passed 2 of 4 (see the next section), and the 30-request result is the better estimate.
- **Limits.** 38 texts, four requests for the method comparison, one reader whose independence is unknown and two declared models. Ask two or three people per language, who did it without AI tools, before using the numbers for more than a direction.

### What the 17 November round showed (patch 0092)

Two Kaggle runs on 17 November: `cascade_30` (baseline against the cascade, the same 30 English requests, both reviewers, each rating asked three times and the median kept; 60 of 60 reviews worked, so the retry of patch 0090 did its job) and `cascade_set` (the five cascade methods on all 20 requests, stopped at 43 of 100 stories by the daily token limit of gpt-oss-120b, 200,000 tokens).

- **The cascade passes about twice as many stories.** Passed by both reviewers: cascade 22 of 30 (56 to 86%) against baseline 11 of 30 (22 to 54%); split 5 against 11; failed by both 3 against 8; failed reviews 11 of 60 against 27 of 60. Request by request (pass 1, split 0.5, fail 0): better 15, worse 3, the same 12, mean +0.27 (+0.11 to +0.43), sign test p 0.0075: a clear gain by the report's rule (a range that excludes 0 and p below 0.05).
- **It removes failures more than it raises quality.** The mean rating moves +0.30 (+0.06 to +0.54): gpt 3.03 to 3.40, qwen 2.67 to 2.90, and on the ratings alone the sign test is not clear (better 16, worse 8, the same 6, p 0.15). The findings per story fall from 2.0 to 1.2.
- **Where.** Medium stories passed by both reviewers 3 of 10 to 7 of 10 and hard ones 2 to 6, easy ones 6 to 9 (their mean rating did not move: 3.20 and 3.20). By word pack, basics 1 of 8 to 5 of 8, food 2 to 5, numbers 4 to 6, people 4 to 6.
- **What it costs.** 12.6 model calls (10 to 16) and about 59 seconds on the free tier (18 seconds in the model) a story, against 1.7 calls and 4 seconds. It uses 7.0 of the 12 learner words against 8.3, at 123 words against 115. The free tier's gpt-oss-120b allows 200,000 tokens a day, and the five-method run hit it after 43 stories; an extra key only adds to that if it belongs to another Groq account (the limit is per account).
- **The 16 November result of four requests overstated it.** The same four requests rewritten on 17 November: the baseline stories passed 2 of 4 (not 0 of 4) and the cascade 3 of 4. One story per request is a coin toss; read the 30 requests.
- **Its two halves both do something.** Of the 30 cascade stories the repair changed 15 (kept: 9 passed, 4 split, 2 failed), was rejected in 4 and found nothing to fix in 11, and all 11 of those passed. The judge's naturalness rating of the two candidates it compared differed by 0 in 16 cases, by 1 in 10 and by 2 or more in 3, so the choice between two candidates is often a tie.
- **The five methods (8 requests with all five: English, Spanish, French, German).** Passed by both reviewers: baseline 3, plan 3, mixed candidates with free checks 4, cascade 6, cascade with proofreading 5 of 8; failed reviews 8 of 16, 6 of 14, 6 of 16, 2 of 13, 3 of 16. The plan and the free checks alone stay near the baseline, as on 16 November, and the methods with a model review are ahead. Eight requests do not separate the cascade from the proofreading variant (6 against 5), and a single language is two requests: no claim per language. The cascade here cost 11.4 calls and 88 seconds, the proofreading variant 10.6 and 74.
- **A rating repeated three times in this run:** all three identical for 53% of story and reviewer pairs, and on both sides of the pass line for 27%. That is the same noise the rating lab measured (22 to 30%), and the reason the verdict uses the median of three.

**What it means.** The cascade is worth having for the share of stories a reviewer will pass, and its cost is about 7 times the calls. The question for the app is which part of it pays: **`cascade_pick`** (the four candidates and the judge's choice, no repair, about 9 calls) and **`review_repair`** (one draft with the plan, a model review and one repair, about 4 calls) take the two halves apart; `--variants ablation` runs them next to the baseline and the cascade, and `kaggle_ablation.py` runs it on the 30 English requests, then the cascade against the baseline in the other languages. If `review_repair` holds most of the gain, the cascade's candidates are not needed; if `cascade_pick` does, the repair is not. No new variant is on by default.

### What the 18 November ablation showed, and a repair that sees naturalness (patch 0093)

The ablation ran on the same 30 English requests (120 stories; all 240 reviews and ratings worked; ratings the median of 3):

| Method | Passed by both reviewers | Split / failed | Failed reviews | Rating gpt / qwen | Calls, seconds a story |
|---|---|---|---|---|---|
| baseline | 11 of 30 | 11 / 8 | 27 of 60 | 3.03 / 2.67 | 1.7, 4 |
| `review_repair` | 19 of 30 | 10 / 1 | 12 of 60 | 3.30 / 2.83 | 4.4, 10 |
| `cascade_pick` | 21 of 30 | 4 / 5 | 14 of 60 | 3.27 / 2.90 | 10.2, 52 |
| `cascade` | 22 of 30 | 5 / 3 | 11 of 60 | 3.40 / 2.90 | 12.6, 59 |

Request by request (pass 1, split 0.5, fail 0) against the baseline: `review_repair` +0.25 (+0.10 to +0.40, better 13, worse 2, sign test p 0.0074), `cascade_pick` +0.22 (+0.01 to +0.42, p 0.049), `cascade` +0.27 (+0.11 to +0.43, p 0.0075). Between the methods no difference shows: `cascade` against `review_repair` +0.02 (-0.15 to +0.18), against `cascade_pick` +0.05 (-0.13 to +0.23). On the mean rating no method is clearly above the baseline. So each half of the cascade alone gets most of the gain, and the cheapest, one draft with a model review and one repair (the repair was kept in 14 of 30, rejected in 6, not needed in 10), costs a third of the calls. The Spanish, French and German run stopped after 10 of 48 stories on the daily limit of gpt-oss-120b: each key has its own counter of 200,000 tokens a day (about 600,000 with three keys, not shared), and by then the three had spent theirs. It cannot be read.

**What the reviewers still failed.** Of the ratings of 2 or less, 22 were for baseline stories, 10 for `review_repair` and 11 for the cascade, and their reasons are almost all about sense and flow: "events are nonsensical", "repetitive time words", "choppy, list-like sentences", "artificial number sequences". The repair never saw that: it was given grammar mistakes and missed requirements, and compared texts by a score that left naturalness out (only the candidate choice rated it).

**Built in patch 0093, off by default:** `StoryOptions.repair_naturalness` (`STORY_REPAIR_NATURALNESS=1`). With it the judge also rates the text 1 to 5 before the repair and again after each rewrite; a rating of 3 or less becomes a requirement that quotes the reviewer's reason ("A reviewer said: ..."), replacing the generic "rewrite it so it reads naturally"; and a rewrite is kept only when the score, which now includes the rating (weight 35), rises by 0.5. Cost: two short rating calls. Test method `review_repair_nat` (about 6 calls) and the group `--variants naturalness` (baseline, `review_repair`, `review_repair_nat`). `kaggle_naturalness.py` runs it on the 30 English requests (baseline and `review_repair` come from the ablation file, so only 30 stories are new), then the three in Spanish, French and German.

**Caution.** The judge that rates and gives the reason is gpt-oss-20b, the graders are gpt-oss-120b and qwen: different models, but the same kind of reader. A gain here partly means "the story pleases that kind of reviewer"; the human labels (patch 0091) are what checks that, and a second round for the other languages is still open.

**The pre-run check in the cell.** `kaggle_naturalness.py` prints, before any model call, which secrets are set, whether the new code is on the branch, whether `simplemma` is installed, whether each input file was found, the size of each job (from `--dry-run`, counting only what the input file still lacks), and stops with a list if a secret, the code or a model name is missing, or if `GROQ_JUDGE_MODEL` or `GROQ_QWEN_MODEL` differs from the model recorded in the input file (the new rows would not be comparable).

### What the 19 November round showed, and what patch 0094 adds to the tests

**The result (30 English requests, then es, fr, de).** The naturalness-aware repair (`review_repair_nat`) is not an improvement. Stories passed by both reviewers: baseline 11, `cascade` 22, `review_repair` 19, `cascade_pick` 21, `review_repair_nat` 20 of 30. Against plain `review_repair` it moves passed stories by 0 points (-16 to +16) and the reviewers go opposite ways: gpt-oss-120b, which also writes the stories, fails 2 stories instead of 5, qwen, the other model family, fails 10 instead of 7. That is the pattern of a model liking its own kind of writing. It costs 6.6 calls and 23 s a story against 4.4 and 10 s, and its sentence level fits worse (26 of 30 in range against 29). `STORY_REPAIR_NATURALNESS` stays off. Against the baseline every new method is clearly better (+22 to +27 points, both reviewers agree, p 0.007 to 0.049) and none can be told from another, so choose by cost: `review_repair`.

Other languages (89 of 96 stories; the daily limit stopped it, again each key spent its own 200,000 tokens): passed baseline 10 of 23, `review_repair` 15 of 22, `review_repair_nat` 14 of 22, `cascade` 14 of 22. The gain is the same size (+25 points) but within noise at 22 stories. German is weakest for every method (1 to 3 of 6 or 7 passed; baseline 1 of 7).

**Found while building the tests.**
- *The same baseline moves between runs.* The 16 and 17 November runs made the same baseline for the same 30 requests (the story model samples, so the texts differ): 9 and 11 passed, 5 requests better, 22 the same, 3 worse, +8 points (-6 to +22), spread 0.37. Any gap smaller than about 15 points between two methods is inside that.
- *How many requests it takes.* The change of one request spreads by 0.41 to 0.55. At 30 requests a 95% range is about +-15 points; to see a gain of 15 points reliably takes about 60 to 110 requests, and to separate `review_repair` from `cascade` (2 points) thousands. So choose between methods of equal quality by cost, not by more runs.
- *The sentence level.* The level note asks 5 to 8 words (easy), 8 to 12 (medium), 10 to 16 (hard), but STORY_RANGE_PROMPT is off in the app, so the baseline writes the same sentences at every level: in range for 13 of 30 stories (0 of 10 easy). `review_repair` 29 of 30. The free score has one ruler (6 to 12 words) for every level and so cannot see this; the repair also asks for 6 to 12 words at every level, which for the hard level contradicts the note. Not changed: a tier-aware ruler is a score version change (4.1 to 4.2), left for a decision.
- *What the prompt alone buys is not measured.* An earlier claim that the plain prompt passes 9 of 16 against 3 of 16 compared the stories a repair left alone, which are the ones with nothing found, so it was biased and is withdrawn. On the two earlier multi-language runs (13 requests) `plan` alone passed no more stories than the baseline (3 better, 10 the same, 0 worse) but was in the asked sentence range for 13 of 13 against 6 of 13. The 30-request controls below settle it.
- *A flaw in the 0093 repair, fixed.* When the judge's re-rating of a rewrite could not be read, the score had no naturalness part, so no penalty, and the rewrite went from 44.9 to 100.0 and was kept on no evidence. A rewrite is now compared like for like: rated when the old text was, rejected when the new rating is missing, unrated on both sides when the first rating failed.
- *Three options never reached the containers.* `STORY_REFINE`, `STORY_WRITER_RULES` and `STORY_REPAIR_NATURALNESS` were read by the code but not passed by `docker-compose.yml`, so setting them in `.env` did nothing. They are passed now, documented, and a test checks every `STORY_` option the code reads.
- *The own-model note never showed.* Stories written by the default model are recorded as "default", so the report could not tell that gpt-oss-120b both writes and reviews. It now reads the run's story model, and marks the reviewer "(also the writer)".

**New in the tests (patch 0094).**
- The report has: **passed stories, each method against the first** (a pass is 1, a split 0.5, a fail 0, in points, with each reviewer alone, the sign test and how many requests it would take to see 15 points), **does the story fit its level** (from the free measurement, ranges read from the level note itself), **each reviewer on its own**, **failed reviews by story type**, and a note that states how much a repeated method moved.
- Methods: `baseline_b` (the baseline made again for the same requests; its gap to the baseline is the noise) and the group `--variants controls`: baseline, baseline_b, `range` (range prompt only), `plan` (range prompt and plan), `review_repair`, `review_repair_nat`. With `--resume cascade_nat.json` only `baseline_b`, `range` and `plan` are made (90 stories; the runner's dry run: about 913,000 tokens over all models, roughly 550,000 on gpt-oss-120b, about a day of three keys; the es/fr/de continuation about 810,000 tokens).
- `python scripts/compare_story_runs.py a.json b.json [--a METHOD --b METHOD]`: two saved runs on the requests that are the same in both, with the settings that differ (reviewer models, score version, rating repeats) printed under it. No key, no model.
- The cell `kaggle_controls.py`, with the same pre-run check as before.

### Why the score misleads, and what patch 0089 changed in the report

Looking again at the 15 November files (`--rescore` with no model calls) the headline numbers misled in four ways:

1. **The free score cannot tell a good story from a bad one.** It checks the brief (words, length, level, built-in grammar rules). In `writer_kaggle` it was 54 to 100 on the 7 stories both reviewers failed and 95 to 100 on the 7 both passed; the "Mean score", "vs first" and "Pass rate" columns and the big number on each card all used it.
2. **The reviewed score has a cliff.** A failed review multiplies the score by 0.6, ratings take only 2, 3 and 4 (19, 15 and 6 of 40 ratings in that file), and the pass line is between 2 and 3, so one point of reviewer noise moves a story by about 40 points. The mean of such numbers mostly counts failures.
3. **Ten requests are few.** In the ten-request file the request explained about half of the variation in ratings (52%) and the method none, so a gap between two methods looked like which requests were drawn; with 30 requests the request explains 9% (see the 16 November section), so even that reading was too strong. Either way the old page showed gaps with no range.
4. **The reviewers do not agree.** They judged pass or fail the same way on 14 of 20 stories, and gpt-oss-120b is both the writer and one of the reviewers.

What the page does now when the file has reviews (`story_eval/verdicts.py` computes, `report.py` draws):

- It leads with **what the reviewers decided**: stories passed by every reviewer (with the 95% range, 3 of 10 is 11 to 60%), split, failed by every reviewer, failed reviews, each reviewer's mean rating. The free score moves to "Brief fit and cost" with a line saying what it cannot see; the per-language table and the cards use the reviewed score, and the card shows "passed by both reviewers" or "failed by gpt; passed by qwen" with the free score in small type.
- **Each method against the first, request by request**: mean rating change with its 95% range, better, same and worse counts, the sign test, each reviewer's own change, and a reading: *clear gain* or *clear loss* only when the range leaves zero, the sign test agrees and no reviewer goes the other way; *reviewers disagree*; *too few requests* (under 6 pairs the sign test can never reach p 0.05); else *within noise*. On `writer_kaggle` the writer rules read "+0.1 (-0.2 to +0.3), within noise".
- **Failed reviews by word pack and by level**, and a grid of every request's ratings per method (✓ passed, ~ split, ✗ failed), so a request that fails in every column shows as the request's doing.
- **How far to trust this**: the ratings given, the share of the variation each factor explains, how often the reviewers agreed, and a warning when a reviewer's model also wrote the stories.
- A file with **no review** says so in a red box and calls its score "free checks only, not a measure of quality". The runner's log line shows `free 100 reviewed 63.9 (gpt 2 FAIL, qwen 3 ok)` instead of one unlabelled score.

**The rating lab (not yet run).** The report cannot fix the instrument. `scripts/rate_texts.py --from FILE.json` re-rates saved stories several times with each reviewer and each rating prompt and prints how steady a rating is: the share of stories whose repeats are all the same, the share whose repeats fall on both sides of the pass line (flips), the intraclass correlation (how much of the variation lies between stories), and how often two reviewers, or two prompts, disagree on pass or fail. 40 stories x 2 reviewers x 2 prompts x 3 repeats is 480 short calls; `--limit`, `--max-minutes`, `--resume` and extra keys spread them over days. The Kaggle cell runs it after the two tests.

**Rating prompt v2 (opt-in, the default is unchanged).** `naturalness.rate(..., prompt="v2", level=...)` asks two small questions, SENSE and WORDING, each 1 to 3, and says that short simple sentences are expected at the level. The first prompt lists "choppy sentences" as a level-3 defect although the brief asks for short sentences: 33 of the 49 passing ratings of the 15 November runs cite "choppy". The rating is sense + wording - 1, and 2 at most when either is 1, so a story fails exactly when it makes no sense or is often unnatural. This is a hypothesis: v2 is better only if the lab shows fewer flips and more agreement with several values still in use. Nothing in the score, the refine loop or the app uses it until then.

### Ideas not built yet, with the evidence

1. **Tell the writer what the reviewers punish** (built as patch 0086, first measurement above). Of 25 findings on the ten refine first drafts, 10 were a missing article or possessive ("to kitchen", "in house", "opened drawer", "friend on the phone"), 4 an unneeded word or phrase ("please", "thank you", "goodbye today", "to me"), 4 an adverb in the wrong form or place ("bright", "gone still", "tired slowly"); my grouping, by the wording of each finding. The classic writer prompt asks for short sentences (5 to 10 words) and only says articles "may" be added; it never asks to keep them or not to pad (the story-type prompts were not re-read for this). One added rule per language family (keep every article, possessive and particle even in short sentences; leave a learner word out rather than tack it on; no "today", "now", "still" at the end of lines) targets 18 of the 25 findings at no extra call. Measure with `--variants baseline` before and after.
2. **Write again instead of repairing when the draft reads unnatural.** Sentence repair cannot fix a rating of 2. About one baseline review in three (6 of 18, leaving out the stuffed story) rates the draft 2 or less. Whether a second draft of the same request would pass is not measured yet: write each of the ten requests three times with the plain pipeline and rate each draft (30 stories) before building this. One new draft chosen by the same rating, only when the rating of the first is 2 or less or a free gate fails, costs 3 calls on a third of the stories.
3. **Fit the word target to the list.** Hard asks for at least 8 of the learner's words in 200 words. With a list of 12 greetings and interjections ("please", "yes", "no", "sorry", "excuse me") the hard stories used 10 to 12 of them, and in each of the three pairs the version that used more words was rated lower. Try a hard minimum of 6, or a minimum that scales with how many of the words are nouns and verbs.
4. **A softer cliff** (measure the rating first: the rating lab above). Today a single 2 fails the story and halves the score. With one reviewer that is a coin flip near the boundary. Options: rate twice and take the mean; count 2 as a warning and fail only at 1.5 or below; or ask for a 1 to 10 scale.
5. **Free gates cannot see naturalness.** On the 20 texts a reviewer failed 10; the free gates failed 3 of those (the "stuffed" ones). Simple offline detectors (share of lines ending in "today", "now", "again") did not separate failed from passed texts on this sample, so the model rating stays the judge; a better offline signal is a question for `eval_signals.py` with LanguageTool and perplexity on the hand grades.
6. **Cost.** Refine is 8 calls and about 90 to 100 seconds per story on the free tier (15 November; 5 calls and 50 seconds before the rating was added). It removes mistakes (2.5 to 0.9 findings per story) but not the unnatural verdict, so it is worth its cost only where the first draft has mistakes and reads naturally.
7. **Put greeting and polite words in quoted speech** (evidence: the 15 November run, above; demoted on 16 November: a prompt rule, and the writer rules measured as no effect on 30 requests). "Hello", "thank you", "sorry", "excuse me" and "how are you" are things people say. One more writer rule, "use them inside quoted speech between two people, never as narration" ("'Good morning,' says Ana", not "I say good morning to the sun"), targets the pack behind half of the failed reviews. Not built. Measure on the basics requests (`--count 30` has 8 of the 30 from that pack), and watch the free gates (quotation marks, the count of the learner's words) and the "own words used" column.


## What is left on each key (patch 0075)

`scripts/key_status.py` makes one 1-token call per key and model and prints and saves Groq's counters (`key_status.json`, names only). Each call uses one request of the day. A key that is already refused reports which limit it hit (per-minute or per-day tokens) and how much it used. The run JSON's `meta["key events"]` lists every refusal a story test saw, with the same fields.

## Story Test Desk (patch 0076)

A local page for watching tests while they run. Start it with `test-desk.bat` (port 8090; `--port` to change). It reads `test-reports\overnight-*\SUMMARY.txt`, the step logs, and `scripts\overnight_*.json` / `refine_*.json`, and refreshes every 10 seconds. A run counts as running when it has no Finished line, no exit code, and a log written within 15 minutes. `run-overnight.bat` starts the desk itself. The refine step is shown as its own run with the phase-by-phase trace for each story. "Check keys now" runs `key_status.py` inside the Langflow container.

## Writer v2, the directive repair and the stiffness signal (patch 0095, 20 November 2026)

**Why.** After review and repair, what the reviewers still fail is how the story reads. The naturalness plan of 19 November (writer v2 prompt, a repair that gets concrete edits, ten other ideas) was checked against the 150 English stories of the 19 November round with its own code before anything was built.

**What the check found (correlations, 30 requests).** Mean reviewer rating by number of free findings (flat rhythm, repeated opener, filler time words, one sentence per line): 0 findings 3.42 (13 stories), 1 finding 3.38 (25), 2 findings 3.04 (52), 3 or more 2.82 (60; 12 of them failed by a reviewer). Each finding alone: filler 2.77 with against 3.18 without, repeated opener 2.87 / 3.16, flat rhythm 2.96 / 3.15, one sentence per line 2.98 / 3.33. Within one request the sentence-length SD goes with the rating (r 0.49, +0.26 rating per SD). "today" is in 77 of 150 stories and "Maya" in 22. **The layout finding is in 124 of 150 stories and tells them apart least, so it does not count towards the repair trigger**: without it, 2 or more findings fire in 13 of 30 baseline stories and 17 of 30 `review_repair` stories (with it, 25 and 26 of 30). Findings a story by method: baseline 1.57, `review_repair` 1.53, cascade 1.17, `cascade_pick` 1.17, `review_repair_nat` 1.30; the sentence-length SD is 0.83, 1.00, 1.35, 1.80 and 1.36.

**What is built (off by default).**
- `story_diagnose.py`: the free checks and the edit sentences (in the language's own connectors and filler words). A learner's own word is never filler. Texts under 6 sentences and Chinese and Japanese are not judged.
- `story_seed.py` and `STORY_WRITER_V2=1`: a prompt block before the final instruction. A scene decided before writing (the model's reasoning does it; no `<plan>` is written out because a leaked plan is gated to 0), words placed where an event needs them, short sentences (3 to 5 words) mixed with longer ones, no more than two openers in a row alike, no filler time word at the end, one or two paragraphs (not for a dialogue), nothing over 20 words. Name, place and time come from code, drawn from the same `rng` as the word sample; names exist for en/es/fr/de only, and a diary or letter gets no name. The level stays set by the level note's sentence range (it fits 29 of 30 stories); the block adds spread, not a longer average. The plan's idea of setting the level by vocabulary instead of sentence length was not taken: the measured fit is the evidence we have.
- `STORY_REPAIR_DIRECTIVES=1`: see the changelog for the keep rule. It is a different keep rule from the ordinary repair because the free score uses one ruler (6 to 12 words a sentence) and does not value rhythm, so a rewrite that joins sentences cannot be asked to raise it.

**What is measured next (`kaggle_v2.py`, the same 30 English requests).** `v2` against `plan` (the block alone), `v2_directive` against `plan`, `rr_directive` against `review_repair` (the edits alone), and each against the baseline. The pass rate with both reviewers is the measure; the stiffness table is a signal. At 30 requests a 95% range is about 15 points wide on each side, so only a gain of that size will show. Not built until these show something: the plan call for different candidates, usage cards per word, exemplars, the richer reviewer (sub-scores plus edits), a different writer for fr and de.

### What round 6 showed (20 November 2026, patch 0096)

30 English requests, the 19 Nov reviewers, 256 of 270 stories before the daily limit stopped the run (`plan` 27, `v2` 27, `v2_directive` 26, `rr_directive` 26 requests; the paired numbers use only the requests a pair shares).

| Method | Calls | Passed / split / failed | In the level's range |
| --- | --- | --- | --- |
| baseline | 1.7 | 11 / 11 / 8 | 13 of 30 |
| plan | 1.9 | 8 / 10 / 9 (of 27) | 27 of 27 |
| v2 | 2.1 | 19 / 7 / 1 (of 27) | 24 of 27 |
| v2_directive | 2.5 | 13 / 9 / 4 (of 26) | 21 of 26 |
| review_repair | 4.4 | 19 / 10 / 1 | 29 of 30 |
| rr_directive | 4.9 | 20 / 4 / 2 (of 26) | 19 of 26 |
| cascade | 12.6 | 22 / 5 / 3 | 26 of 30 |

- **`v2` against `plan`: +35 points (+20 to +51), 16 better, 10 same, 1 worse; both reviewers agree (gpt +42, Qwen +30).** That is the block alone. Against the baseline +28 (+8 to +48, p 0.049), Qwen and gpt both about +27 to +30. Against `review_repair`, `cascade_pick` and `cascade` it is +2 points each (within noise): a one-call prompt change reaches the passed-story rate of the expensive methods, at about a third to a sixth of the calls.
- **Careful with the +35.** `plan` passed fewer stories than the baseline this time (8 against 11, -7 points, within noise), so part of the gap to `plan` is a weak control. The gap to the baseline is the sturdier one, and it is only just clear.
- **What the reviewers saw.** Mean naturalness `plan` 2.65, baseline 2.85, `review_repair` 3.07, `v2` 3.13. Remarks about repetition: `plan` 30%, `v2` 9%. Remarks about choppy or very short sentences: `plan` 39%, `v2` 45%, `review_repair` 62%: the block did not fix those. Grammar findings a review: `v2` 1.55, `review_repair` 0.90, `plan` 2.15. By level `v2` passed 5 of 9 easy, 9 of 9 medium, 5 of 9 hard stories.
- **Free checks.** Findings a story (rhythm, opener, filler): baseline 1.57, `plan` 1.74, `v2` 1.00; stories with "today": baseline 21 of 30, `plan` 16 of 27, `v2` 10 of 27. No "Setting:" or plan text leaked into a story. The stories are in 4.7 lines against about 10.
- **Directive repair: no gain.** `v2_directive` against `v2`: -15 points (-33 to +2; gpt -8, Qwen -23); `rr_directive` against `review_repair` +4 (-11 to +19). The edits make the free findings fall (0.77 and 0.81 a story) and the reviewers do not like the result. `STORY_REPAIR_DIRECTIVES` stays off.
- **Not known.** Which part of the block does the work: the paragraph layout (a one-sentence-per-line text was the baseline's shape), the mixed rhythm, the seeded name and place, or the instruction to plan a scene. The block is one bundle, so this round cannot say. Also the noise floor: `baseline_b` made 1 of 30 stories and `range` none before the limit.
- **Next (`kaggle_round7.py`).** `v2_rr` (the block with review and repair: the repetition fixed by the block and the grammar by the repair), after finishing the 14 missing stories; then the controls. If `v2_rr` is above `v2` by more than the noise, it is the candidate; if not, `v2` at 2.1 calls is.

### Summary first, and sentence by sentence (patch 0097, 20 November 2026)

**The question.** Would it help to write a summary of the story first, with the vocabulary assigned to its parts, and then write grammatical, natural sentences one at a time?

**What we know before the test.**
- The scene-first half has some support: the writer v2 block asks the model to decide a scene before writing (silently) and it raised passed stories from 8 to 19 of 27 (round 6). So an explicit outline can only add the part the model did not already do. The cascade's two-pass candidates (draft with no word list, then adapt) are a related idea and showed no clear advantage in the data we have.
- The sentence-by-sentence half runs against the reviewers' commonest remark: "choppy" or list-like text, in 45% of the naturalness remarks for `v2` and 62% for `review_repair`. A sentence written alone, one call at a time, has no pull towards joining its neighbours and tends to start like the last one; the v2 gain came from asking for connected paragraphs. Sentence-level fixing has been tried: `refine` (rewrite only the flagged sentences) tied with the baseline (13 Nov).
- Cost: 5 events means 6 calls before any retry, against 2.1 for `v2`, which already passes as many stories as methods of 4 to 13 calls. On the free keys (200,000 tokens a day for each) that is a real limit.

**What is built (off by default).** `story_outline.py`; `StoryOptions.outline` / `STORY_OUTLINE` = `whole` or `beats`. `whole`: one outline call, then one call writes the text from the outline, as connected prose, not one sentence a line. `beats`: one call per event, each given the base prompt (level, words, rules, name and place), the outline, the text so far and the instruction to start differently from the last sentence and join with a connector where it reads better; a dialogue gets one or two lines a beat. An outline with fewer than 3 events, a failed outline call or a failed beat gives back the normal one-call story, with a note.

**What is measured next.** On the same 30 English requests: `outline` and `beats` against `v2` (gap = the outline; gap between them = writing in pieces), and each against `review_repair`. The measure is the passed stories of both reviewers; the stiffness table shows rhythm, openers and filler beside it. If `outline` is level with `v2` the extra call is not worth it; if `beats` is below `outline`, writing in pieces hurts, which is the expectation.

### Spread the words (patch 0098, 20 November 2026)

**Where it came from.** A prompt template for "literary fiction with a vocabulary list" was suggested. Most of it does not fit learner text: "short, sharp fragments" runs against the grammar checks (fragments count against a story) and the reviewers' "choppy" remark; "show, don't tell", subtext and messy, interrupted speech are harder to read at A1 and A2; the list of banned words (tapestry, delve, beacon) names a problem simple text does not have; and it sets neither a level nor a length. Two lines fit: write with a natural cadence (writer v2 already asks for it) and **spread the words across the whole text**, which v2 does not.

**The check.** Position of each learner word in the 19 November stories, as the share that falls in the first third of the text (an even spread is 33%): baseline 41%, `plan` 43%, `v2` 45%, `review_repair` 40%, `cascade` 43%; the last third holds 20 to 23%. Part of this is natural (a greeting word belongs at the start of a greetings story), so the pull is small, about ten points, and not the main fault.

**What is built.** `StoryOptions.spread` (`STORY_SPREAD_WORDS=1`): one sentence before the final instruction, "Spread the listed words across the whole text, not only the first sentences: some in the middle and some near the end, each where its event needs it." Method `v2_spread` = `v2` plus the sentence. The report's stiffness table now has a column for it ("learner words first used in the first third of the text", the first use of each word, stories with at least 3 of the words found, mean over stories; free, no model), and it reproduces the numbers above. Next: `v2_spread` against `v2` on the same 30 English requests, with two readings: did the placement move (the column), and did the passed stories move (the reviewers). One hint that placement alone is not what the reviewers reward: the two directive methods of round 6 spread the words more evenly (37% and 36% in the first third, against 45% for `v2`) and passed no more stories than `v2` (13 and 20 of 26 against 19 of 27). That is suggestive and not a test, since those methods changed much else. If the passed stories do not move, the sentence is not worth keeping, which is the likely result for a shift of about ten points.

**A fix found on the way.** `--resume` finishes every method the file has; `--dry-run` counted only the methods named in `--variants`. It now counts all of them, and `--skip` leaves methods out.

### What round 8 showed, and the second v2 run (patch 0100, 21 November 2026)

**What ran.** The same 30 English requests, reviewers gpt-oss-120b and qwen, three ratings each. Job 1 made `v2_rr` and `v2_spread` (30 each) and the last three `v2` stories; job 2 made `outline` (14) and `beats` (13); job 3 got one story each of `baseline_b` and `range`. The Groq daily limit (200,000 tokens a key on gpt-oss-120b; 199,446, 199,978 and 199,993 used) stopped the work after about 90 new stories, so **the controls are still not measured**.

| Method | Stories | Calls a story | Passed / split / failed | That method minus `v2`, in points (range) |
|---|---|---|---|---|
| `baseline` | 30 | 1.7 | 11 / 11 / 8 | −28 (−46 to −10) |
| `review_repair` | 30 | 4.4 | 19 / 10 / 1 | −3 (−14 to +8) |
| `cascade` | 30 | 12.6 | 22 / 5 / 3 | −2 (−18 to +14) |
| **`v2`** | 30 | 2.1 | 21 / 8 / 1 | |
| `v2_rr` | 30 | 4.4 | 20 / 6 / 4 | −7 (−22 to +9) |
| `v2_spread` | 30 | 2.1 | 19 / 5 / 6 | −12 (−26 to +3) |
| `v2_directive` | 26 | 2.5 | 13 / 9 / 4 | −15 (−33 to +2) |
| `outline` | 14 | 2.9 | 8 / 3 / 3 | −18 (−45 to +9) |
| `beats` | 13 | 6.6 | 6 / 3 / 4 | −27 (−47 to −7), p 0.031 |

**What it shows.**

1. **`v2` is the one clear result.** 21 passed, 8 split, 1 failed at 2.1 calls a story. Against the baseline it is +28 points (+10 to +46, p 0.019) and both reviewers agree (gpt +31, qwen +27). It is level with `review_repair` (+3, −8 to +14) and `cascade` (+2, −14 to +18) at 48% and 17% of their calls. Round 6 had the same picture on 27 stories (19 passed).
2. **Nothing added on top of `v2` helped.** Every method built on it is below it: review and repair on top (`v2_rr`) −7, `v2_spread` −12, `v2_directive` −15, `outline` −18, `beats` −27. Only `beats` is outside its range, and p 0.031 is the one value under 0.05 among the 19 comparisons of the round, so it reads as "probably not better", not as proven worse. `v2_spread` did what it was built for (learner words first used in the first third of the text: 45% for `v2`, 29%) and the reviewers passed fewer, so placement is not what they reward. Review and repair on top of `v2` left 23 of 30 stories in the level's sentence range against 27 (five became too short).
3. **The free stiffness checks are diagnostics, not levers.** The methods built to lower them did (findings a story: `beats` 0.56, `v2_directive` 0.77, `rr_directive` 0.81, `outline` 0.93, `v2` 1.10, `baseline` 1.57) and passed fewer (13 of 26, 6 of 13, 8 of 14). Only `rr_directive` kept pace (20 of 26, +4 points on `review_repair`, inside noise).
4. **The request matters more than the method.** Across the seven methods that pass about two thirds of their stories, 6 requests are passed by all seven and 5 by two or fewer; if the request did not matter (pass rate 0.68) that would be about 2 and 1. Every request was passed by at least one method, which is what seven draws at that rate give and says nothing about a ceiling.
5. **The ruler is the limit.** A reviewer's three ratings of one story fell on both sides of the pass line (2 or less fails) for 145 of 348 qwen stories (42%) and 53 of 344 gpt stories (15%). qwen's mean rating is 2.7 to 2.9 for every method that passes about two thirds of its stories (gpt 3.3 to 3.5), so the line cuts through the middle of its ratings and a story's verdict is often the median of a coin flip. Rating the same 30 stories again would move a method's passed count by one standard deviation of 1.0 to 1.7 stories (about ±3 at 95%), before any change in the writer's own story. So 19, 20, 21 and 22 passes are one plateau, and with 30 requests a gap under about 4 stories (13 points) is not a difference. The counts of the best methods are also the high end of what their own ratings give: `v2` 21 reported, 18.8 expected on a new set of ratings; `cascade` 22 and 20.0; `v2_spread` 19 and 17.3. `verdicts.crossing` and `verdicts.rerating` compute this, and "How far to trust this" in the report now says it every round.

**What it does not settle.** `v2` was picked because it did well, and all five methods built on it landing below it is also what a lucky `v2` looks like. Only a second draw of `v2` tells the two apart, and its gap to the first is the run-to-run noise of the method that matters.

**What is built.** Method `v2_b` (`v2` made again, `replicate_of: v2`), and `kaggle_round9.py`: job 1 `v2_b` on the 30 requests of round 8's `v2_en.json`, job 2 the 29 missing `baseline_b` stories of `controls_en.json`; the cell stops before spending anything when the `v2_en.json` it is given is not round 8's. About 60 stories, 0.64 million tokens in all (the runner's estimate), about 0.4 million of them on gpt-oss-120b: one day on three keys. Not made again: `plan`, `v2_directive`, `rr_directive`, `range`, `outline`, `beats`, and the cell leaves `v2_rr` and `v2_spread` as they are.

**How to read round 9.** If `v2_b` lands within about 4 stories of `v2` (17 to 25 passes), the add-ons of round 8 were noise and `v2` stays the candidate at 2.1 calls. If it falls to 18 or 19, `v2` is level with the repair methods, not above them, and still the cheapest. The gap between `baseline_b` and `baseline` is the same noise for the plain method. **The app default is not changed:** `STORY_WRITER_V2` stays off until `v2_b` is in (so far: +28 points over the baseline with both reviewers agreeing, +0.4 calls, English only; es, fr, de, it, pt, zh, ja and ko are not measured with it).

### What round 9 showed (patch 0101, 22 November 2026)

Round 9 made `v2` again (`v2_b`) and the baseline again (`baseline_b`) for the same 30 English requests, with both reviewers and three ratings each. Both runs stopped at the Groq daily limit after their last story; nothing was left unmade, and `plan`, `v2_directive` and `rr_directive` were not made again on purpose.

| Method | Stories | Calls a story | Passed / split / failed | Points of 30 |
|---|---|---|---|---|
| `baseline` | 30 | 1.7 | 11 / 11 / 8 | 16.5 |
| `baseline_b` (the baseline again) | 30 | 1.7 | 10 / 9 / 11 | 14.5 |
| `review_repair` | 30 | 4.4 | 19 / 10 / 1 | 24.0 |
| `cascade` | 30 | 12.6 | 22 / 5 / 3 | 24.5 |
| **`v2`** | 30 | 2.1 | 21 / 7 / 2 | 24.5 |
| **`v2_b`** (`v2` again) | 30 | 2.1 | 19 / 7 / 4 | 22.5 |

1. **The noise of one run is now measured, and it is the same size for both methods.** `v2_b` is 7 points below `v2` (−23 to +10, p 0.61) and `baseline_b` is 7 points below `baseline` (−24 to +11, p 0.63): one story fewer passed and one more failed, each. Two draws of the same method differ by about 2 stories of 30, inside the ±3 that rating the same stories again would give (`v2_b`: 19 reported, 18.4 expected; `v2`: 21 and 18.5).
2. **`v2` beats the baseline, and the second draw confirms it.** `v2` is +27 points over `baseline` (+8 to +45, p 0.031) and `v2_b` is +27 over `baseline_b` (+7 to +47, p 0.031); crossed, +20 and +33. Pooling both draws of each (60 stories against 60): `v2` 78% of the points, baseline 52%, +27 points a request (about +12 to +41). Both reviewers agree (gpt +23 to +32, qwen +17 to +33).
3. **`v2` is level with the repair methods, not above them, and the cheapest.** `v2_b` against `review_repair` −5 (−21 to +11), against `cascade` −7 (−26 to +13); both inside noise. At 2.1 calls it is 48% of `review_repair` and 17% of `cascade`. This is the pre-registered "18 or 19 passes" reading of round 8's write-up: level, still the cheapest.
4. **The free stiffness checks reproduce.** Findings a story 0.97 and 0.93 for `v2` and `v2_b` against 1.57 and 1.60 for the two baselines; stories with two or more findings 6 and 6 against 13 and 16. Sentences inside the level's range: 27 and 28 of 30 against 13 and 11.

**Things to know about these numbers.** The `v2_en.json` the run started from has three `v2` stories (en-27, en-28, en-29) that differ from round 8's copy (the verdicts moved from 21 / 8 / 1 to 21 / 7 / 2, en-29 from split to fail); the numbers above are the ones in the file the run produced. Two stories were reviewed by one reviewer only because gpt hit its daily limit on that call (`v2` en-26, `baseline_b` en-0), so each can only be 0.5 point off. Round 8's reading that the add-ons are noise stands, and nothing here suggests `v2` has a ceiling: with 30 requests a gap under about 4 stories is not a difference.

**What it settles and what it does not.** In English `v2` is a real gain over the baseline at +0.4 calls, and as good as methods that cost 2 to 6 times as many. It was never measured outside English (es, fr, de, it, pt, zh, ja and ko), and `STORY_WRITER_V2` is still off in the app; that is your decision, and the evidence for English is now what it will be.

**What is built.** `kaggle_round10.py`: `baseline` and `v2` on 30 requests in Spanish, French and German, each its own job (60 stories, about 0.65 million tokens, one day of three keys each; 1.95 million in all), starting from nothing, each continuing from its own file on the next day.

### What rounds 10 and 11 showed (patch 0104, 23 November 2026)

Round 10 was baseline against `v2` on 30 requests each in Spanish, French and German; round 11 the same in Italian, Portuguese, Chinese, Japanese and Korean. Only part of it ran, and the reason is the daily limit, not a fault.

| Language | Stories made (of 60) | Stories judged by both reviewers | Passed / split / failed, baseline | the same, `v2` | `v2` against baseline |
|---|---|---|---|---|---|
| Spanish | 60 | 60 | 11 / 2 / 17 | 15 / 10 / 5 | **+27 (+4 to +49), p 0.041** |
| French | 60 | 58 | 13 / 6 / 11 | 11 / 9 / 10 | −2 (−23 to +20), p 0.82 |
| German | 30 | 6 | 4 / 1 / 10 (15 requests) | 6 / 3 / 6 | +20 (−17 to +57), p 0.75, mostly gpt alone |
| Italian | 41 | 34 | 6 / 5 / 10 (21 stories) | 9 / 5 / 6 (20) | +20 (−1 to +41), p 0.18 |
| Portuguese, Chinese, Japanese, Korean | 0 (Chinese 1) | | | | not measured |

1. **Why most of round 11 did not run.** Groq allows 200,000 tokens a day for gpt-oss-120b and for qwen, counted over a rolling 24 hours. One language is about 0.65 million tokens (about 0.4 million of them on gpt-oss-120b), so a day holds about two languages. Round 10 spent the limit between 06:10 and 08:29 UTC; round 11 started at 15:08 UTC the same day, so Italian got 41 stories and the other four got 0 or 1.
2. **A gap in the test code, found here.** When qwen reached its daily limit the story was still saved, with gpt's verdict only (German 24 of 30 stories, Italian 7 of 41), and a plain `--resume` makes only the stories that are missing, so those stayed one-reviewer verdicts. Patch 0104 adds `--fill-reviews`: on a resumed run it first asks again the reviewers that have no working review of a saved story (no story is written again, and a new answer replaces an old one only when more of it worked), then makes the missing stories. The round 12 cell uses it.
3. **`v2` does what it was built to do in every language measured.** Findings a story fell from 3.4 to 2.6 (Spanish), 3.2 to 2.3 (French), 3.4 to 2.7 (German) and 3.4 to 2.8 (Italian); sentences inside the level's range went from 10, 10, 5 and 7 stories to 29, 30, 14 and 20 (of 30, 30, 15 and 20 to 21). Agreement slips fell in Spanish, French and Italian (30 to 10, 24 to 4, 29 to 16 findings).
4. **Passes: a gain in three languages, none in French, and the pooled figure is smaller than English.** Counting only the 76 requests where both reviewers judged both stories (Spanish 30, French 29, Italian 17): +14 points a request (about +1 to +26), 30 requests better and 14 worse. English was +27. Spanish alone reaches significance; Italian and German point the same way; French is flat (its baseline already passes 13 of 30, against 11 in Spanish and 4 of 15 in German).
5. **What French showed.** The free checks fit (30 of 30 in the level's range) but the reviewers' remarks moved: fewer agreement and preposition findings, but adjective and adverb placement stayed or grew (French 14 findings for the baseline, 18 for `v2`; German 12 and 17): "quatre arbres grands", "le jardin petit", "J'écoute la radio souvent", "gesungen leise", "fiel ein roter Apfel vom Baum plötzlich". These are a few remarks in 30 stories, so a language-specific word-order sentence for the writer is a hypothesis, not a result; it is not built, and the next round does not test it.

**What it settles and what it does not.** `v2` is not worse in any language measured, costs the same one call as the baseline, and is clearly better on the free checks everywhere; on the reviewers' pass rate it is clearly better in English and Spanish and not distinguishable from the baseline in French. German and Italian need their remaining stories and the missing qwen verdicts before they can be read. Portuguese, Chinese, Japanese and Korean are unmeasured. `STORY_WRITER_V2` stays off in the app; the evidence is now English plus three languages, and the decision is yours.

**What is built.** `kaggle_round12.py`: three days, each a `DAY` number in the cell: day 1 continues German (28 reviews to fill, 30 stories to make) and Italian (7 reviews, 19 stories); day 2 Portuguese and Chinese; day 3 Japanese and Korean. Each starts at least 24 hours after the last stop of the day before.
