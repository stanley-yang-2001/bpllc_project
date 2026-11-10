# Spaced repetition for flashcards (patches 0069 to 0071, 9 November 2026)

Flashcards now follow a schedule instead of a fixed round of ten. This page says what the scheduler does, what is recorded, and where the code is.

## What changed for the learner

- **No card limit.** A session is every word the schedule asks for (or every word of the chosen sets, or exactly the words chosen). An optional `limit` exists in the API; the page does not use it.
- **Several sets at once.** The Practice page has one chip per set (and General); any number can be on. None on = every word. The API takes `set=3,7,general`. The choice also drives the progress card, the statistics and the hardest words, and the other practice modes.
- **Four answers, clicks only (patch 0070).** The word is shown; one click on "Show answer", then one click on Again / Hard / Good / Easy, each saying when the word would come back ("1m", "10m", "1d", "4d"). (Patch 0071 adds the keys 1 to 4 back: grade with a click or a key, whichever you like; the keys work only once the answer is showing.) There is no direction switch (the word is always first; the log still has a `direction` column) and no help text to read.
- **A session lasts as long as the learner chooses (patch 0070):** 2, 5, 10, 20 or 30 minutes, a custom length in minutes and seconds (patch 0071; at least 10 seconds, up to 180 minutes), or no limit (default 10 minutes, remembered in the browser as seconds). A clock counts down; when it reaches zero the card being answered can still be graded, then the summary appears. Words not reached stay due.
- **Study what's due** (learning words first, then reviews that are due, then new words) or **Practise all N words** (ahead of time). Practising early and remembering does not move the schedule; a miss always does.
- **End of session:** grades, share not missed, average time to answer, the slowest words, the missed words, "Practise the N missed", and (patch 0070) an **All time** block under it: answers, words practised and days studied, share not missed, retention, average time to answer and time studied, over everything ever answered in the chosen sets (`total_*` fields of `/practice/stats`).
- **Memory statistics** (Practice page): retention, share not missed, time to answer, time studied (30 days), answers today, where the words stand (new / learning / relearning / young / mature), a 7 day forecast, words that keep being forgotten.
- **Hardest words:** a score of 0 to 100 per word from the learner's own answers, with the reasons (often missed, slow to answer, forgotten again and again, keeps coming back, very hard) and "Practise these".
- Multiple choice, dictation, parts of speech and fill-in-the-blank still record right/wrong (counted as Good or Again) and now also how long the learner took.

## The scheduler (`tutor_core/tutor_core/srs.py`, pure Python, no clock of its own)

SM-2 family, as Anki made familiar.

| Phase | Meaning | Steps |
|---|---|---|
| learning | not remembered yet | 1 min, 10 min; Good on the last step graduates to 1 day, Easy graduates at once to 4 days |
| review | resting for `interval_days` | Good: (interval + half the lateness) x ease; Hard x 1.2; Easy: (interval + lateness) x ease x 1.3 |
| relearning | forgotten in review | 10 min, then back to review at half the old rest (at least a day) |

- Ease starts 2.5; Again -0.20, Hard -0.15, Easy +0.15; kept between 1.3 and 3.5. Intervals have a ceiling of 365 days.
- Good is always at least one day longer than Hard, Easy at least one longer than Good.
- Intervals of 3 days or more get a fixed spread of +-5% (the same for the preview and the answer, seeded by word id and repetition count) so words learnt together do not return together.
- A card in a short learning step that comes back within 20 minutes stays in the session (shown when its time has come, early if nothing else is left); that rule is in `web/src/practice/session.ts`.
- 8 lapses make a word a leech (a note suggests a picture, a rhyme or a sentence of the learner's own).
- The five Leitner boxes of the first version are still stored (`box`, derived from the rest: box 4 and up = a week or more) so the progress card and old exports keep working.

## Hardest words (`srs.difficulty`)

`score = 100 x (0.5 miss rate + 0.2 slowness + 0.2 lapses + 0.1 low ease)`. The miss rate is smoothed ((misses + 0.5) / (answers + 1)) so one miss in one try is not 100%. Slowness is the learner's own average time to answer that word against their own median over 30 days, so a slow reader is not penalised against someone else's speed. A word needs two answers to be listed; a list entry needs a reason or a score of 30.

## What is recorded (migration 0017)

`tutor.word_progress` gains `phase, step, ease, interval_days, lapses, last_grade` (existing rows are carried over from their box: box 2 up become review words resting 1, 3, 7 or 21 days, box 1 stays learning).

New `tutor.review_log`, one row per answer: when, mode (flashcards, choices, dictation, pos, cloze), direction (word or meaning), grade, `think_ms` (card shown until the learner checked or chose the answer), `rate_ms` (answer shown until graded), phase before, whether it was due, whether it counted, ease after and the delay scheduled. A time over 2 minutes is stored as 2 minutes (a card left open is not a slow answer). The database clock is the only clock (`now()` is read once per request).

**Privacy:** the log is new personal data (what was answered and how long it took). It belongs to the learner (`ON DELETE CASCADE`), is in "Download my data" (`review_log`), is never sent to a model or third party, and is read only for the learner's own statistics. Patch 0070 adds this to the approved English policy (new table row "Your practice progress and answer times", the deletion list and the download bullet) and moves `POLICY_VERSION` to `2026-11-09`, as you asked; the only copy is English, so nothing else needs updating.

## API

| Call | What it does |
|---|---|
| `GET /practice/flashcards?language&set&scope=due\|all\|ids&ids=1,2&limit` | Cards with status, ease, interval, lapses, leech flag and what each answer would schedule (`preview`, seconds). `total`, `selection`, `due`, `new` counts. `due=true` still means scope due. |
| `POST /practice/reviews` | Up to 50 graded answers (grade 1 to 4, `think_ms`, `rate_ms`, `mode`, `direction`); returns for each when the word is due again and its new preview. |
| `POST /practice/answers` | Right/wrong from the other modes (Good or Again), now with optional `think_ms`, `mode`, `direction`. |
| `GET /practice/stats?language&set` | The statistics above. |
| `GET /practice/hardest?language&set&limit` | The hardest words. |
| `GET /practice/progress?language&set` | As before, now for the chosen sets. |

Code: `api/app/services/progress.py` (record, preview), `services/practice/flashcards.py` (the queue), `services/study_stats.py`, `routes/practice.py`, `schemas/practice.py`, migration `0017_srs.py`. Web: `practice/Flashcards.tsx`, `session.ts`, `SetPicker.tsx`, `StudyStats.tsx`, `useRecorder.ts`; text in `i18n/catalog/study.ts` (nine languages, not yet reviewed by native speakers).

## Not decided / not done

- No daily limit on new words (you asked for no limit); a "new per day" setting would be a small addition to the queue.
- Parts-of-speech, dictation and choice cards use the same schedule through Good/Again only; they do not show the four buttons.
- Grade weights and steps are the usual Anki defaults, not tuned on your data; the log makes tuning possible later.
