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

Next round, for the decision "is the cascade worth 7 times the calls" (both are in the Kaggle cell): `--variants baseline,=cascade` on the 30 English requests with `--rating-repeats 3` (60 stories, about 830 calls), then the five cascade methods on all 20 fixed requests (100 stories, about 1,470 calls). `cascade` is both the name of a group of five methods and of one method, so `baseline,cascade` means five; a leading `=` names the single method (`baseline,=cascade`). The size estimate printed before a run now counts the reviewers and the rating repeats (it left them out before, so it said about 870 calls for a run that makes about 1,470).

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
