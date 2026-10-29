"""What a learner got right and wrong in practice, remembered so words come back when they are due (Leitner boxes).

A word starts in box 1. A right answer moves it up one box (up to 5) and it comes back after BOX_DAYS[box] days; a wrong answer
puts it back in box 1 to be tried again in RETRY_MINUTES. A right answer on a word that is not due yet (practising early) is
counted but does not move the box, so repeating a round cannot inflate it. Days are UTC days. Everything is the learner's own:
it is in "Download my data" and goes with the account."""
from __future__ import annotations

from datetime import timedelta

from ..db import cursor
from ..errors import not_found, validation_error

BOX_DAYS = {2: 1, 3: 3, 4: 7, 5: 21}          # how long a word rests after reaching this box
RETRY_MINUTES = 10
KNOWN_BOX = 4                                  # box 4 and 5 count as "known"
MAX_ANSWERS = 50
_HAS_MEANING = "w.meaning IS NOT NULL AND btrim(w.meaning) <> ''"
_TODAY = "(now() AT TIME ZONE 'UTC')::date"


def record(conn, user_id: int, answers: list[tuple[int, bool]]) -> None:
    """Remember a round of answers (word id, was it right). Every word must be this learner's own."""
    if not answers:
        return
    if len(answers) > MAX_ANSWERS:
        raise validation_error(f"At most {MAX_ANSWERS} answers at a time.")
    ids = sorted({i for i, _ in answers})
    with cursor(conn) as cur:
        cur.execute("SELECT id FROM tutor.words WHERE user_id = %s AND id = ANY(%s)", (user_id, ids))
        if len(cur.fetchall()) != len(ids):
            raise not_found("One of those words isn't in your list.")
        cur.execute("SELECT word_id, box, due_at <= now() AS due FROM tutor.word_progress WHERE user_id = %s AND word_id = ANY(%s)", (user_id, ids))
        state = {r["word_id"]: (r["box"], r["due"]) for r in cur.fetchall()}
        for word_id, right in answers:
            box, due = state.get(word_id, (1, True))            # a word never practised is due
            if right:
                new_box = min(box + 1, 5) if due else box
                seconds = BOX_DAYS.get(new_box, BOX_DAYS[5]) * 86400 if due else None
            else:
                new_box, seconds = 1, RETRY_MINUTES * 60
            # an early right answer keeps the old due time; everything else sets a new one
            cur.execute(
                "INSERT INTO tutor.word_progress (word_id, user_id, box, due_at, right_count, wrong_count, last_answered_at) "
                "VALUES (%s, %s, %s, now() + make_interval(secs => COALESCE(%s, 0)), %s, %s, now()) "
                "ON CONFLICT (word_id) DO UPDATE SET box = EXCLUDED.box, "
                "due_at = CASE WHEN %s THEN tutor.word_progress.due_at ELSE EXCLUDED.due_at END, "
                "right_count = tutor.word_progress.right_count + EXCLUDED.right_count, "
                "wrong_count = tutor.word_progress.wrong_count + EXCLUDED.wrong_count, last_answered_at = now()",
                (word_id, user_id, new_box, seconds, int(right), int(not right), seconds is None))
            state[word_id] = (new_box, False)                      # a repeat in the same request is not due again
        cur.execute(f"INSERT INTO tutor.practice_days (user_id, day, answers) VALUES (%s, {_TODAY}, %s) "
                    "ON CONFLICT (user_id, day) DO UPDATE SET answers = tutor.practice_days.answers + EXCLUDED.answers",
                    (user_id, len(answers)))


def due_rows(cur, user_id: int, language: str, extra: str = "", params: list | None = None) -> list[dict]:
    """Words with a meaning that are due now (oldest first), then words never practised (shuffled)."""
    cur.execute(f"SELECT w.id, w.word, w.meaning FROM tutor.words w LEFT JOIN tutor.word_progress p ON p.word_id = w.id "
                f"WHERE w.user_id = %s AND w.language = %s AND {_HAS_MEANING}{extra} AND (p.word_id IS NULL OR p.due_at <= now()) "
                "ORDER BY (p.word_id IS NULL), p.due_at, random()", [user_id, language, *(params or [])])
    return cur.fetchall()


def streak(days: list, today) -> int:
    """Consecutive practised days ending today, or yesterday (a streak is not lost until a whole day is missed)."""
    if not days:
        return 0
    days = sorted(set(days), reverse=True)
    if days[0] < today - timedelta(days=1):
        return 0
    run, expect = 0, days[0]
    for d in days:
        if d != expect:
            break
        run += 1
        expect = d - timedelta(days=1)
    return run


def summary(conn, user_id: int, language: str) -> dict:
    with cursor(conn) as cur:
        cur.execute(
            "SELECT count(*) FILTER (WHERE p.word_id IS NULL) AS new, "
            "count(*) FILTER (WHERE p.box < %s) AS learning, count(*) FILTER (WHERE p.box >= %s) AS known, "
            "count(*) FILTER (WHERE p.due_at <= now()) AS due "
            f"FROM tutor.words w LEFT JOIN tutor.word_progress p ON p.word_id = w.id "
            f"WHERE w.user_id = %s AND w.language = %s AND {_HAS_MEANING}", (KNOWN_BOX, KNOWN_BOX, user_id, language))
        out = dict(cur.fetchone())
        cur.execute("SELECT day FROM tutor.practice_days WHERE user_id = %s ORDER BY day DESC LIMIT 400", (user_id,))
        days = [r["day"] for r in cur.fetchall()]
        cur.execute(f"SELECT {_TODAY} AS today")
        today = cur.fetchone()["today"]
    out["streak"] = streak(days, today)
    out["practised_today"] = bool(days) and days[0] == today
    out["language"] = language
    return out
