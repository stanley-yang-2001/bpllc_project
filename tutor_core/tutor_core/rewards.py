"""Progress and rewards (13 Nov 2026): a streak that forgives one rest day a week, a daily goal, and a small set of badges.

Pure functions: the API reads the numbers from the database and hands them here. Nothing is a rank or a score against other people.
Rewards follow learning (words that became known, days practised, stories kept), never raw clicks alone."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Iterable, Sequence

REST_GAP_DAYS = 7              # after a rest day, six practised days must follow before the next rest day is forgiven
GOAL_MIN, GOAL_MAX, GOAL_DEFAULT = 5, 100, 10


def streak_of(days: Iterable[date], today: date) -> dict:
    """The day streak, forgiving one missed day (a "rest day") per week.

    A streak is the number of practised days in a row, where a single missed day between two practised days is forgiven when no other
    rest day was used in the 7 days before it. Two missed days in a row end the streak. Today is still open: if the last practised day was
    two days ago, yesterday counts as a rest day and the streak is alive until today ends.
    Returns {"days": n, "alive": bool, "practised_today": bool, "rest_available": bool, "rest_used_on": date | None}:
    `rest_available` is true when a missed day would be forgiven right now."""
    have = sorted({d for d in days if d <= today}, reverse=True)
    out = {"days": 0, "alive": False, "practised_today": False, "rest_available": True, "rest_used_on": None}
    if not have:
        return out
    last = have[0]
    out["practised_today"] = last == today
    rests: list[date] = []                                  # missed days forgiven so far, newest first
    if last == today - timedelta(days=2):
        rests.append(today - timedelta(days=1))
    elif last < today - timedelta(days=1):
        return out
    count, prev = 1, last
    for d in have[1:]:
        gap = (prev - d).days
        if gap == 1:
            count += 1
        elif gap == 2:
            missed = prev - timedelta(days=1)
            if rests and (rests[-1] - missed).days < REST_GAP_DAYS:
                break
            rests.append(missed)
            count += 1
        else:
            break
        prev = d
    out.update(days=count, alive=True, rest_used_on=rests[0] if rests else None)
    out["rest_available"] = not rests or (today - rests[0]).days >= REST_GAP_DAYS
    return out


def best_streak(days: Iterable[date]) -> int:
    """The longest streak ever, by the same rule (a rest day is forgiven)."""
    have = sorted(set(days))
    return max((streak_of([d for d in have if d <= end], end)["days"] for end in have), default=0)


def clamp_goal(value) -> int:
    return min(GOAL_MAX, max(GOAL_MIN, int(value)))


def goal_state(target: int, done_today: int) -> dict:
    return {"target": target, "done": done_today, "reached": done_today >= target, "left": max(0, target - done_today)}


# (id, what is counted, how many). The numbers count what the learner has, in every language.
BADGES: Sequence[tuple[str, str, int]] = (
    ("first_answer", "answers", 1),
    ("known_10", "known_words", 10),
    ("known_50", "known_words", 50),
    ("known_100", "known_words", 100),
    ("known_250", "known_words", 250),
    ("streak_3", "best_streak", 3),
    ("streak_7", "best_streak", 7),
    ("streak_30", "best_streak", 30),
    ("first_story", "stories", 1),
    ("stories_5", "stories", 5),
    ("first_dictation", "dictations", 1),
    ("second_language", "languages", 2),
)


def badges(counts: dict) -> list[dict]:
    """Every badge with whether it is earned and how far along: [{id, earned, have, target}]. `counts` holds answers, known_words,
    best_streak, stories, dictations, languages (missing ones count as 0)."""
    out = []
    for badge_id, what, target in BADGES:
        have = int(counts.get(what, 0))
        out.append({"id": badge_id, "earned": have >= target, "have": min(have, target), "target": target})
    return out


def next_badge(items: list[dict]) -> dict | None:
    """The unearned badge that is closest to done (largest share), so the learner always sees one thing to aim at."""
    todo = [b for b in items if not b["earned"]]
    return max(todo, key=lambda b: (b["have"] / b["target"], -b["target"])) if todo else None


COMEBACK_GAP_DAYS = 3


def comeback(days: Iterable[date], today: date) -> dict | None:
    """A learner coming back after a break of at least COMEBACK_GAP_DAYS days: {"days_away": n, "returned": bool}.
    `returned` is true once they have practised today. Nothing for a new learner or one who never left."""
    have = sorted({d for d in days if d <= today}, reverse=True)
    if not have:
        return None
    if have[0] == today:
        away = (today - have[1]).days if len(have) > 1 else 0
        return {"days_away": away, "returned": True} if away >= COMEBACK_GAP_DAYS else None
    away = (today - have[0]).days
    return {"days_away": away, "returned": False} if away >= COMEBACK_GAP_DAYS else None


def longest_run(grades: Iterable[int]) -> int:
    """The longest run of answers in a row that were not "Again" (grade 1), in the order given."""
    best = run = 0
    for g in grades:
        run = run + 1 if g >= 2 else 0
        best = max(best, run)
    return best


def _has_cjk(text: str) -> bool:
    return any(0x2E80 <= ord(c) <= 0x9FFF or 0xAC00 <= ord(c) <= 0xD7AF for c in text)


def words_in_stories(words: Iterable[str], stories: Iterable[str]) -> int:
    """How many of the words appear in at least one of the stories. Whole words, ignoring case; for Chinese, Japanese and Korean (no
    spaces between words) a plain substring match."""
    import re
    texts = [s.casefold() for s in stories]
    joined = "\n".join(texts)
    found = 0
    for w in {x.strip().casefold() for x in words if x and x.strip()}:
        if _has_cjk(w):
            hit = w in joined
        else:
            hit = re.search(rf"(?<!\w){re.escape(w)}(?!\w)", joined) is not None
        found += hit
    return found
