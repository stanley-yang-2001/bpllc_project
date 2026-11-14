"""What the learner sees as progress and rewards: the streak (one rest day a week is forgiven), the daily goal, the week so far and badges.

Everything is worked out from what is already stored (practice days, word progress, review log, stories) plus two settings on the account
(the daily goal and whether to show rewards). The rules are in tutor_core.rewards. Days are UTC days, like the rest of practice."""
from __future__ import annotations

from datetime import timedelta

from tutor_core import rewards

from ..db import cursor
from . import progress, preferences

_TODAY = progress._TODAY


def _utc_today(cur):
    cur.execute(f"SELECT {_TODAY} AS today")
    return cur.fetchone()["today"]


def _activity(cur, user_id: int) -> list:
    """The learner's practice days, newest first: day and how many answers."""
    cur.execute("SELECT day, answers FROM tutor.practice_days WHERE user_id = %s ORDER BY day DESC LIMIT 800", (user_id,))
    return cur.fetchall()


def _totals(cur, user_id: int) -> dict:
    """Counts across every language that the badges and the week summary use."""
    cur.execute("SELECT count(*) FILTER (WHERE box >= %s) AS known, count(*) FILTER (WHERE known_at >= now() - interval '7 days') AS learned_week "
                "FROM tutor.word_progress WHERE user_id = %s", (progress.KNOWN_BOX, user_id))
    words = cur.fetchone()
    cur.execute("SELECT count(*) AS total, count(*) FILTER (WHERE created_at >= now() - interval '7 days') AS week FROM tutor.stories WHERE user_id = %s", (user_id,))
    stories = cur.fetchone()
    cur.execute("SELECT count(*) AS n FROM tutor.review_log WHERE user_id = %s AND mode = 'dictation'", (user_id,))
    dictations = cur.fetchone()["n"]
    cur.execute("SELECT count(DISTINCT language) AS n FROM tutor.words WHERE user_id = %s", (user_id,))
    return {"known": words["known"], "learned_week": words["learned_week"], "stories_total": stories["total"], "stories_week": stories["week"],
            "dictations": dictations, "languages": cur.fetchone()["n"]}


def _records(cur, user_id: int, answers: dict) -> dict:
    """Personal bests, only ever against the learner's own past."""
    cur.execute("SELECT grade FROM (SELECT grade, reviewed_at FROM tutor.review_log WHERE user_id = %s ORDER BY reviewed_at DESC LIMIT 5000) x "
                "ORDER BY reviewed_at", (user_id,))
    run = rewards.longest_run(r["grade"] for r in cur.fetchall())
    cur.execute("SELECT min(a) AS ms FROM (SELECT avg(think_ms) AS a FROM tutor.review_log WHERE user_id = %s AND think_ms IS NOT NULL "
                "GROUP BY (reviewed_at AT TIME ZONE 'UTC')::date HAVING count(think_ms) >= 10) d", (user_id,))
    fastest = cur.fetchone()["ms"]
    cur.execute("SELECT max(c) AS n FROM (SELECT count(*) AS c FROM tutor.word_progress WHERE user_id = %s AND known_at IS NOT NULL "
                "GROUP BY date_trunc('week', known_at)) w", (user_id,))
    best_week = cur.fetchone()["n"] or 0
    best_day = max(((n, d) for d, n in answers.items()), default=None)
    return {"best_day": {"value": best_day[0], "day": best_day[1]} if best_day else None, "longest_run": run,
            "fastest_ms": int(fastest) if fastest is not None else None, "best_week_learned": int(best_week)}


def _challenge(cur, user_id: int, today, answers: dict) -> dict:
    """This calendar week's challenge (Monday to Sunday, UTC) with how far along the learner is."""
    monday = today - timedelta(days=today.weekday())
    cur.execute("SELECT count(*) AS n FROM tutor.word_progress WHERE user_id = %s AND (known_at AT TIME ZONE 'UTC')::date >= %s", (user_id, monday))
    learned = cur.fetchone()["n"]
    cur.execute("SELECT count(*) AS n FROM tutor.stories WHERE user_id = %s AND (created_at AT TIME ZONE 'UTC')::date >= %s", (user_id, monday))
    stories = cur.fetchone()["n"]
    this_week = [d for d in answers if d >= monday]
    return rewards.weekly_challenge(today, {"words_learned": learned, "days": len(this_week), "answers": sum(answers[d] for d in this_week), "stories": stories})


def _story_words(cur, user_id: int, language: str) -> dict:
    """How many of this language's words appear in one of the learner's saved stories."""
    cur.execute("SELECT word FROM tutor.words WHERE user_id = %s AND language = %s", (user_id, language))
    vocab = [r["word"] for r in cur.fetchall()]
    cur.execute("SELECT body FROM tutor.stories WHERE user_id = %s AND language = %s ORDER BY created_at DESC LIMIT 200", (user_id, language))
    bodies = [r["body"] for r in cur.fetchall()]
    return {"used": rewards.words_in_stories(vocab, bodies), "total": len(set(w.strip().casefold() for w in vocab if w.strip()))}


def overview(conn, user_id: int, language: str) -> dict:
    """Everything the rewards screens show, assembled from the pieces above."""
    prefs = preferences.get(conn, user_id) or {}
    with cursor(conn) as cur:
        today = _utc_today(cur)
        rows = _activity(cur, user_id)
        answers = {r["day"]: r["answers"] for r in rows}
        totals = _totals(cur, user_id)
        records = _records(cur, user_id, answers)
        challenge = _challenge(cur, user_id, today, answers)
        story_words = _story_words(cur, user_id, language)
    days = [r["day"] for r in rows]
    streak = rewards.streak_of(days, today)
    best = max(rewards.best_streak(days), streak["days"])
    week_days = [d for d in answers if 0 <= (today - d).days < 7]
    items = rewards.badges({"answers": sum(answers.values()), "known_words": totals["known"], "best_streak": best, "stories": totals["stories_total"],
                            "dictations": totals["dictations"], "languages": totals["languages"]})
    summary = progress.summary(conn, user_id, language)
    return {
        "show_rewards": bool(prefs.get("show_rewards", True)),
        "streak": {**streak, "best": best},
        "goal": rewards.goal_state(rewards.clamp_goal(prefs.get("daily_goal", rewards.GOAL_DEFAULT)), answers.get(today, 0)),
        "week": {"days_practised": len(week_days), "answers": sum(answers[d] for d in week_days), "words_learned": totals["learned_week"],
                 "stories_saved": totals["stories_week"], "due_now": summary["due"], "new_words": summary["new"]},
        "known_words": totals["known"],
        "comeback": rewards.comeback(days, today),
        "challenge": challenge,
        "garden": {"seeds": summary["new"], "sprouts": summary["learning"], "trees": summary["known"]},
        "records": records,
        "story_words": story_words,
        "badges": items,
        "next_badge": rewards.next_badge(items),
    }
