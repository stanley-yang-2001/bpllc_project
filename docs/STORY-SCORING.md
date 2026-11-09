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
