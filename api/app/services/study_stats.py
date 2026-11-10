"""What the review log says about how a learner is doing: totals, retention, how long answers take, a seven day forecast and the words
that are hardest for this learner. Everything is read from the learner's own rows (progress + review_log) for the sets they chose.
The difficulty score itself is tutor_core.srs.difficulty (pure, tested on its own)."""
from __future__ import annotations

from datetime import timedelta

from tutor_core import srs

from ..db import cursor
from . import word_sets

WINDOW_DAYS = 30
HARDEST_MAX = 50
MIN_REVIEWS_FOR_HARD = 2
_HAS_MEANING = "w.meaning IS NOT NULL AND btrim(w.meaning) <> ''"
_UTC_DAY = "(now() AT TIME ZONE 'UTC')::date"


def _typical_think_ms(cur, user_id: int, language: str) -> int | None:
    """The learner's own median time to answer, over the last 30 days: slowness is judged against it, not against a fixed number."""
    cur.execute("SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY l.think_ms) AS m FROM tutor.review_log l JOIN tutor.words w ON w.id = l.word_id "
                "WHERE l.user_id = %s AND w.language = %s AND l.think_ms IS NOT NULL AND l.reviewed_at > now() - interval '30 days'", (user_id, language))
    value = cur.fetchone()["m"]
    return None if value is None else int(round(value))


def hardest(conn, user_id: int, language: str, set_filter=None, limit: int = 10) -> dict:
    """The words this learner finds hardest, hardest first. A word needs two answers before it can be called hard."""
    limit = max(1, min(HARDEST_MAX, limit))
    extra, params = word_sets.filter_clause(set_filter, "w.set_id")
    with cursor(conn) as cur:
        typical = _typical_think_ms(cur, user_id, language)
        cur.execute(
            "SELECT w.id, w.word, w.meaning, p.phase, p.step, p.ease, p.interval_days, p.lapses, p.right_count, p.wrong_count, p.due_at, "
            "(SELECT avg(l.think_ms) FROM tutor.review_log l WHERE l.word_id = w.id AND l.think_ms IS NOT NULL) AS avg_think "
            "FROM tutor.words w JOIN tutor.word_progress p ON p.word_id = w.id "
            "WHERE w.user_id = %s AND w.language = %s AND p.right_count + p.wrong_count >= %s" + extra,
            [user_id, language, MIN_REVIEWS_FOR_HARD, *params])
        rows = cur.fetchall()
    items = []
    for r in rows:
        reviews = r["right_count"] + r["wrong_count"]
        avg = None if r["avg_think"] is None else int(round(r["avg_think"]))
        d = srs.difficulty(reviews, r["wrong_count"], r["lapses"], float(r["ease"]), avg, typical)
        card = srs.Card(phase=r["phase"], step=r["step"], ease=float(r["ease"]), interval_days=float(r["interval_days"]), reps=reviews,
                        lapses=r["lapses"], due_at=r["due_at"])
        items.append({"id": r["id"], "word": r["word"], "meaning": (r["meaning"] or "").strip() or None, "score": d["score"], "reasons": d["reasons"],
                      "reviews": reviews, "miss_rate": d["miss_rate"], "avg_think_ms": avg, "lapses": r["lapses"], "ease": float(r["ease"]),
                      "status": srs.status_of(card), "due_at": r["due_at"]})
    items = [i for i in items if i["score"] > 0 and (i["reasons"] or i["score"] >= 30)]
    items.sort(key=lambda i: (-i["score"], -i["reviews"], i["word"]))
    return {"items": items[:limit], "typical_think_ms": typical}


def stats(conn, user_id: int, language: str, set_filter=None) -> dict:
    extra, params = word_sets.filter_clause(set_filter, "w.set_id")
    base = [user_id, language, *params]
    with cursor(conn) as cur:
        # how the words stand
        cur.execute(
            "SELECT count(*) AS words, count(*) FILTER (WHERE p.word_id IS NULL) AS new, "
            "count(*) FILTER (WHERE p.phase = 'learning') AS learning, count(*) FILTER (WHERE p.phase = 'relearning') AS relearning, "
            "count(*) FILTER (WHERE p.phase = 'review' AND p.interval_days < 21) AS young, "
            "count(*) FILTER (WHERE p.phase = 'review' AND p.interval_days >= 21) AS mature, "
            "count(*) FILTER (WHERE p.due_at <= now() OR (p.phase <> 'review' AND p.due_at <= now() + make_interval(secs => %s))) AS due_now, "
            "count(*) FILTER (WHERE p.lapses >= %s) AS leeches "
            f"FROM tutor.words w LEFT JOIN tutor.word_progress p ON p.word_id = w.id WHERE w.user_id = %s AND w.language = %s AND {_HAS_MEANING}{extra}",
            [srs.LEARN_AHEAD_SECONDS, srs.LEECH_LAPSES, *base])
        out = dict(cur.fetchone())
        # the last 30 days of answers (only answers that counted toward the schedule are retention; all answers are accuracy)
        cur.execute(
            "SELECT count(*) AS n, count(*) FILTER (WHERE l.grade >= 2) AS ok, "
            "count(*) FILTER (WHERE l.was_due AND l.phase_before = 'review') AS due_reviews, "
            "count(*) FILTER (WHERE l.was_due AND l.phase_before = 'review' AND l.grade >= 2) AS due_ok, "
            "avg(l.think_ms) AS think, percentile_cont(0.5) WITHIN GROUP (ORDER BY l.think_ms) AS think_med, avg(l.rate_ms) AS rate, "
            "COALESCE(sum(COALESCE(l.think_ms, 0) + COALESCE(l.rate_ms, 0)), 0) AS ms, "
            "count(*) FILTER (WHERE (l.reviewed_at AT TIME ZONE 'UTC')::date = " + _UTC_DAY + ") AS today "
            f"FROM tutor.review_log l JOIN tutor.words w ON w.id = l.word_id WHERE w.user_id = %s AND w.language = %s{extra} "
            "AND l.reviewed_at > now() - make_interval(days => %s)", [*base, WINDOW_DAYS])
        a = cur.fetchone()
        # everything ever answered in the chosen sets (the running total shown under each session summary)
        cur.execute(
            "SELECT count(*) AS n, count(*) FILTER (WHERE l.grade >= 2) AS ok, count(DISTINCT l.word_id) AS words, "
            "count(DISTINCT (l.reviewed_at AT TIME ZONE 'UTC')::date) AS days, avg(l.think_ms) AS think, "
            "count(*) FILTER (WHERE l.was_due AND l.phase_before = 'review') AS due_reviews, "
            "count(*) FILTER (WHERE l.was_due AND l.phase_before = 'review' AND l.grade >= 2) AS due_ok, "
            "COALESCE(sum(COALESCE(l.think_ms, 0) + COALESCE(l.rate_ms, 0)), 0) AS ms "
            f"FROM tutor.review_log l JOIN tutor.words w ON w.id = l.word_id WHERE w.user_id = %s AND w.language = %s{extra}", base)
        t = cur.fetchone()
        cur.execute(
            f"SELECT (l.reviewed_at AT TIME ZONE 'UTC')::date AS day, count(*) AS reviews, count(*) FILTER (WHERE l.grade >= 2) AS correct, "
            "avg(l.think_ms) AS think FROM tutor.review_log l JOIN tutor.words w ON w.id = l.word_id "
            f"WHERE w.user_id = %s AND w.language = %s{extra} AND l.reviewed_at > now() - interval '14 days' GROUP BY 1 ORDER BY 1", base)
        days = [{"day": r["day"], "reviews": r["reviews"], "correct": r["correct"],
                 "avg_think_ms": None if r["think"] is None else int(round(r["think"]))} for r in cur.fetchall()]
        # what is coming: due now (overdue ones count as today), then each of the next six days
        cur.execute(
            f"SELECT GREATEST((p.due_at AT TIME ZONE 'UTC')::date, {_UTC_DAY}) AS day, count(*) AS due FROM tutor.word_progress p "
            f"JOIN tutor.words w ON w.id = p.word_id WHERE w.user_id = %s AND w.language = %s AND {_HAS_MEANING}{extra} "
            f"AND (p.due_at AT TIME ZONE 'UTC')::date < {_UTC_DAY} + 7 GROUP BY 1 ORDER BY 1", base)
        forecast_rows = {r["day"]: r["due"] for r in cur.fetchall()}
        cur.execute(f"SELECT {_UTC_DAY} AS today")
        today = cur.fetchone()["today"]
    forecast = [{"day": today + timedelta(days=i), "due": forecast_rows.get(today + timedelta(days=i), 0)} for i in range(7)]
    n = a["n"]
    out.update({
        "language": language, "reviews_30d": n,
        "accuracy_30d": round(a["ok"] / n, 3) if n else None,
        "retention_30d": round(a["due_ok"] / a["due_reviews"], 3) if a["due_reviews"] else None,
        "avg_think_ms": None if a["think"] is None else int(round(a["think"])),
        "median_think_ms": None if a["think_med"] is None else int(round(a["think_med"])),
        "avg_rate_ms": None if a["rate"] is None else int(round(a["rate"])),
        "studied_seconds_30d": int(a["ms"] // 1000), "today_reviews": a["today"], "days": days, "forecast": forecast,
        "total_reviews": t["n"], "total_words_practised": t["words"], "total_days": t["days"],
        "total_accuracy": round(t["ok"] / t["n"], 3) if t["n"] else None,
        "total_retention": round(t["due_ok"] / t["due_reviews"], 3) if t["due_reviews"] else None,
        "total_avg_think_ms": None if t["think"] is None else int(round(t["think"])), "total_studied_seconds": int(t["ms"] // 1000)})
    return out
