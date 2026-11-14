"""What a learner got right and wrong in practice, remembered so each word comes back when it is due (spaced repetition).

The schedule itself is tutor_core.srs (pure, tested on its own); this file keeps it in the database. Every answer is a grade from 1
(Again) to 4 (Easy); the modes that only know right or wrong send Good or Again. Each answer is also written to review_log with how
long the learner took (`think_ms`: until they checked or chose the answer; `rate_ms`: from seeing the answer to grading it), which is
what "your hardest words" and the study statistics are made from. The database clock is the only clock (now() is read once per
request). Days are UTC days. Everything is the learner's own: it is in "Download my data" and goes with the account."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from tutor_core import srs

from ..db import cursor
from ..errors import not_found, validation_error
from . import word_sets

KNOWN_BOX = 4                  # box 4 and 5 (a rest of 7+ days) count as "known"
MAX_ANSWERS = 50
MAX_MS = 120_000               # an answer left open longer than this was not a slow answer, so it is recorded as this long
MODES = ("flashcards", "choices", "dictation", "pos", "cloze")
DIRECTIONS = ("word", "meaning")
_HAS_MEANING = "w.meaning IS NOT NULL AND btrim(w.meaning) <> ''"
_TODAY = "(now() AT TIME ZONE 'UTC')::date"


@dataclass(frozen=True)
class Review:
    word_id: int
    grade: int
    think_ms: int | None = None
    rate_ms: int | None = None
    mode: str = "flashcards"
    direction: str | None = None


def card_from_row(row: dict | None) -> srs.Card:
    """A word_progress row (None: never practised) as the scheduler's card."""
    if not row:
        return srs.Card()
    return srs.Card(phase=row["phase"], step=row["step"], ease=float(row["ease"]), interval_days=float(row["interval_days"]),
                    reps=row["right_count"] + row["wrong_count"], lapses=row["lapses"], due_at=row["due_at"])


def seed_of(word_id: int, reps: int) -> int:
    return word_id * 31 + reps


def _ms(value) -> int | None:
    return None if value is None else min(MAX_MS, max(0, int(value)))


def preview_of(word_id: int, card: srs.Card, now) -> dict:
    """What each of the four answers would schedule next, in seconds (the same spread as the answer itself will use)."""
    p = srs.preview(card, now, srs.fuzz_factor(seed_of(word_id, card.reps)))
    return {"again": int(p[srs.AGAIN]), "hard": int(p[srs.HARD]), "good": int(p[srs.GOOD]), "easy": int(p[srs.EASY])}


def _result(word_id: int, card: srs.Card, out: srs.Outcome, now) -> dict:
    return {"preview": preview_of(word_id, card, now), "word_id": word_id, "delay_seconds": int(out.delay_seconds), "status": srs.status_of(card), "counted": out.counted, "correct": out.correct,
            "box": srs.box_of(card), "ease": card.ease, "interval_days": card.interval_days, "lapses": card.lapses}


def record_reviews(conn, user_id: int, reviews: list[Review]) -> list[dict]:
    """Remember a round of graded answers. Every word must be this learner's own. Returns, for each answer, when the word is due again."""
    if not reviews:
        return []
    if len(reviews) > MAX_ANSWERS:
        raise validation_error(f"At most {MAX_ANSWERS} answers at a time.")
    for r in reviews:
        if r.grade not in srs.GRADES:
            raise validation_error("An answer's grade is 1 (again) to 4 (easy).")
        if r.mode not in MODES or (r.direction is not None and r.direction not in DIRECTIONS):
            raise validation_error("Unknown practice mode.")
    ids = sorted({r.word_id for r in reviews})
    results: list[dict] = []
    with cursor(conn) as cur:
        cur.execute("SELECT id FROM tutor.words WHERE user_id = %s AND id = ANY(%s)", (user_id, ids))
        if len(cur.fetchall()) != len(ids):
            raise not_found("One of those words isn't in your list.")
        cur.execute("SELECT now() AS now")
        now = cur.fetchone()["now"]
        cur.execute("SELECT * FROM tutor.word_progress WHERE user_id = %s AND word_id = ANY(%s) FOR UPDATE", (user_id, ids))
        cards = {r["word_id"]: card_from_row(r) for r in cur.fetchall()}
        for r in reviews:
            card = cards.get(r.word_id, srs.Card())
            out = srs.review(card, r.grade, now, srs.fuzz_factor(seed_of(r.word_id, card.reps)))
            new = out.card
            cur.execute(
                "INSERT INTO tutor.word_progress (word_id, user_id, box, due_at, right_count, wrong_count, last_answered_at, "
                "phase, step, ease, interval_days, lapses, last_grade, known_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (word_id) DO UPDATE SET box = EXCLUDED.box, due_at = EXCLUDED.due_at, "
                "right_count = tutor.word_progress.right_count + EXCLUDED.right_count, "
                "wrong_count = tutor.word_progress.wrong_count + EXCLUDED.wrong_count, last_answered_at = EXCLUDED.last_answered_at, "
                "phase = EXCLUDED.phase, step = EXCLUDED.step, ease = EXCLUDED.ease, interval_days = EXCLUDED.interval_days, "
                "lapses = EXCLUDED.lapses, last_grade = EXCLUDED.last_grade, "
                "known_at = CASE WHEN EXCLUDED.box >= %s THEN COALESCE(tutor.word_progress.known_at, EXCLUDED.known_at) ELSE NULL END",
                (r.word_id, user_id, srs.box_of(new), new.due_at, int(out.correct), int(not out.correct), now,
                 new.phase, new.step, new.ease, new.interval_days, new.lapses, r.grade, now if srs.box_of(new) >= KNOWN_BOX else None, KNOWN_BOX))
            cur.execute(
                "INSERT INTO tutor.review_log (user_id, word_id, reviewed_at, mode, direction, grade, think_ms, rate_ms, phase_before, "
                "was_due, counted, ease_after, delay_seconds) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (user_id, r.word_id, now, r.mode, r.direction, r.grade, _ms(r.think_ms), _ms(r.rate_ms), card.phase, out.was_due,
                 out.counted, new.ease, int(out.delay_seconds)))
            cards[r.word_id] = new                                  # a repeat in the same request starts from the new state
            results.append(_result(r.word_id, new, out, now))
        cur.execute(f"INSERT INTO tutor.practice_days (user_id, day, answers) VALUES (%s, {_TODAY}, %s) "
                    "ON CONFLICT (user_id, day) DO UPDATE SET answers = tutor.practice_days.answers + EXCLUDED.answers",
                    (user_id, len(reviews)))
    return results


def record(conn, user_id: int, answers: list[tuple[int, bool]], mode: str = "flashcards") -> list[dict]:
    """Right/wrong answers from the modes that have no grade buttons: right is Good, wrong is Again."""
    return record_reviews(conn, user_id, [Review(i, srs.GOOD if right else srs.AGAIN, mode=mode) for i, right in answers])


def due_rows(cur, user_id: int, language: str, extra: str = "", params: list | None = None, need_meaning: bool = True, with_pos: bool = False) -> list[dict]:
    """Words with a meaning (any word when need_meaning is False) that are due now (oldest first), then words never practised (shuffled)."""
    cur.execute(f"SELECT w.id, w.word, w.meaning{', w.pos' if with_pos else ''} FROM tutor.words w LEFT JOIN tutor.word_progress p ON p.word_id = w.id "
                f"WHERE w.user_id = %s AND w.language = %s{f' AND {_HAS_MEANING}' if need_meaning else ''}{extra} AND (p.word_id IS NULL OR p.due_at <= now()) "
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


def summary(conn, user_id: int, language: str, set_filter=None) -> dict:
    extra, params = word_sets.filter_clause(set_filter, "w.set_id")
    with cursor(conn) as cur:
        cur.execute(
            "SELECT count(*) FILTER (WHERE p.word_id IS NULL) AS new, "
            "count(*) FILTER (WHERE p.box < %s) AS learning, count(*) FILTER (WHERE p.box >= %s) AS known, "
            "count(*) FILTER (WHERE p.due_at <= now()) AS due "
            f"FROM tutor.words w LEFT JOIN tutor.word_progress p ON p.word_id = w.id "
            f"WHERE w.user_id = %s AND w.language = %s AND {_HAS_MEANING}{extra}", [KNOWN_BOX, KNOWN_BOX, user_id, language, *params])
        out = dict(cur.fetchone())
        cur.execute("SELECT day FROM tutor.practice_days WHERE user_id = %s ORDER BY day DESC LIMIT 400", (user_id,))
        days = [r["day"] for r in cur.fetchall()]
        cur.execute(f"SELECT {_TODAY} AS today")
        today = cur.fetchone()["today"]
    out["streak"] = streak(days, today)
    out["practised_today"] = bool(days) and days[0] == today
    out["language"] = language
    return out
