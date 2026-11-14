# Rewards and progress — design

Written for patch 0079. Built and tested here (API, tutor_core, web unit tests); not run end to end on your machine.

## Goal
Give a learner a visible reason to come back tomorrow, without comparing them with other people and without anything they cannot switch off.

## What the learner sees
- **Home:** a card at the top with a daily-goal ring (answers today / goal), the streak (with best streak and a rest-day hint), a "Practise now" button, this week's numbers (days practised, words learned, stories saved, ready to review), the next badge with a progress bar, and a link to Progress.
- **Top bar (every page):** a flame chip with the streak and today's goal ("5 · 4/10"), linking to Progress.
- **Progress page (`/progress`):** the same summary plus the badge grid (earned and in-progress).
- **Toast:** "New badge: ..." once per new badge. The first visit on a device is silent, so existing learners are not flooded.
- **Settings:** daily goal (5, 10, 15, 20, 30, 50, 100) and "Show my streak, goal and badges". Off hides everything above.

## Rules
- **Streak:** consecutive practice days. One missed day ("rest day") per rolling 7 days does not break it (`REST_GAP_DAYS = 7`). A streak is alive if today or yesterday (or the rest-day gap) is covered.
- **Goal:** answers in Practice today, 5 to 100, default 10.
- **Known:** a word at box >= 4 (`KNOWN_BOX`). `known_at` is set when it reaches that box and cleared if it falls back.
- **Badges (12, derived, not stored):** first answer; 10, 50, 100, 250 known words; 3, 7, 30 day streak; first story saved; 5 stories; first dictation; a second language. "New" is tracked per browser in localStorage (`tutor:badges-seen:<userId>`).

## Data
Migration `0018_rewards`: `tutor.word_progress.known_at` (backfilled from `last_answered_at` for box >= 4), `tutor.user_preferences.daily_goal` (5..100, default 10), `show_rewards` (default true). Both new preference fields and `known_at` are in "Download my data".

## API
- `GET /practice/rewards?language=xx` returns show_rewards, streak (days, best, alive, practised_today, rest_available, rest_used_on), goal, week, known_words, badges, next_badge.
- `PATCH /me/preferences` accepts `daily_goal` and `show_rewards`.
- Logic lives in `tutor_core/rewards.py` (pure functions) and `api/app/services/rewards.py` (queries).

## Privacy
Nothing is shared or ranked. Stored: practice results (already), `known_at`, goal and the on/off setting. The privacy policy needs a sentence covering these (item 20 on the by-hand list).

## Tests
`tutor_core/tests/test_rewards.py`, `api/tests/test_rewards.py`, `web/src/rewards/rewards.test.tsx`; two older API tests gained the new fields.

## Not built
Word-used-in-stories tracker, story unlocks, personal records, XP and leaderboards (postponed on purpose). Nine-language text has had no native-speaker review.
