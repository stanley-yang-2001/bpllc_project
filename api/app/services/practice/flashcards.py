"""Flashcards, dictation and parts-of-speech cards: the learner's own words, picked at random or (Due) by what is due now."""
from __future__ import annotations

from datetime import timedelta

from tutor_core import pos as pos_rules
from tutor_core import srs

from ...db import cursor
from ...errors import validation_error
from .. import progress, word_sets


SCOPES = ("all", "due", "ids")
MAX_IDS = 200


def flashcards(conn, user_id: int, language: str, limit: int | None = None, set_filter=None, due: bool = False,
               scope: str | None = None, ids: list[int] | None = None) -> dict:
    """The learner's words that have a meaning (a card with nothing on its back is no use), from the sets they chose. No size limit:
    `limit` only shortens a round when the learner asks for that.
    scope "all": every word shuffled (practice ahead of time); "due": what the schedule asks for now (words in learning or relearning
    first, then reviews that are due, then words never practised); "ids": exactly these words (e.g. the hardest ones).
    due=True is the old way of saying scope "due". Each card carries its schedule state and what each answer would do to it."""
    scope = scope or ("due" if due else "all")
    if scope not in SCOPES:
        raise validation_error("Unknown flashcard scope.")
    if scope == "ids":
        ids = sorted({int(i) for i in ids or []})[:MAX_IDS]
        if not ids:
            raise validation_error("Choose the words to practise.")
    extra, params = word_sets.filter_clause(set_filter, "w.set_id")
    with cursor(conn) as cur:
        cur.execute("SELECT now() AS now")
        now = cur.fetchone()["now"]
        cur.execute("SELECT w.id, w.word, w.meaning, p.word_id IS NULL AS is_new, p.phase, p.step, p.ease, p.interval_days, p.lapses, "
                    "COALESCE(p.right_count + p.wrong_count, 0) AS reps, p.due_at FROM tutor.words w "
                    "LEFT JOIN tutor.word_progress p ON p.word_id = w.id "
                    "WHERE w.user_id = %s AND w.language = %s AND w.meaning IS NOT NULL AND btrim(w.meaning) <> ''" + extra
                    + " ORDER BY random()", [user_id, language, *params])
        rows = cur.fetchall()
    cards = [(r, _card(r)) for r in rows]
    due_now = [(r, c) for r, c in cards if _asked_for(r, c, now)]
    counts = {"selection": len(rows), "due": sum(1 for r, c in cards if not r["is_new"] and _asked_for(r, c, now)),
              "new": sum(1 for r in rows if r["is_new"])}
    if scope == "due":
        picked = sorted(due_now, key=lambda rc: _queue_rank(rc[0], rc[1]))
    elif scope == "ids":
        picked = [(r, c) for r, c in cards if r["id"] in ids]
    else:
        picked = cards
    total = len(picked)
    if limit:
        picked = picked[:limit]
    return {"items": [_out(r, c, now) for r, c in picked], "total": total, **counts}


def _card(row: dict) -> srs.Card:
    if row["is_new"]:
        return srs.Card()
    return srs.Card(phase=row["phase"], step=row["step"], ease=float(row["ease"]), interval_days=float(row["interval_days"]),
                    reps=row["reps"], lapses=row["lapses"], due_at=row["due_at"])


def _asked_for(row: dict, card: srs.Card, now) -> bool:
    """Due now; a card in a short learning step that comes due within the next 20 minutes is shown now too (the session would otherwise wait)."""
    if row["is_new"]:
        return True
    ahead = srs.LEARN_AHEAD_SECONDS if card.phase != srs.REVIEW else 0
    return card.due_at <= now + timedelta(seconds=ahead)


def _queue_rank(row: dict, card: srs.Card):
    if row["is_new"]:
        return (2, 0.0)
    return (0 if card.phase != srs.REVIEW else 1, card.due_at.timestamp())


def _out(row: dict, card: srs.Card, now) -> dict:
    return {"id": row["id"], "word": row["word"], "meaning": row["meaning"], "status": srs.status_of(card), "ease": card.ease,
            "interval_days": card.interval_days, "lapses": card.lapses, "reps": card.reps, "leech": srs.is_leech(card),
            "due_at": None if row["is_new"] else card.due_at, "preview": progress.preview_of(row["id"], card, now)}


def dictation(conn, user_id: int, language: str, limit: int, set_filter=None, due: bool = False) -> dict:
    """Words to hear and type. Any word will do (a meaning is not needed), so words with no meaning are included; a word is returned
    with its meaning when it has one. With due=True: the words that are due now, then words never practised."""
    extra, params = word_sets.filter_clause(set_filter)
    with cursor(conn) as cur:
        if due:
            rows = progress.due_rows(cur, user_id, language, *word_sets.filter_clause(set_filter, "w.set_id"), need_meaning=False)
            return {"items": rows[:limit], "total": len(rows)}
        cur.execute("SELECT id, word, NULLIF(btrim(meaning), '') AS meaning FROM tutor.words WHERE user_id = %s AND language = %s" + extra
                    + " ORDER BY random() LIMIT %s", [user_id, language, *params, limit])
        items = cur.fetchall()
        cur.execute("SELECT count(*) AS n FROM tutor.words WHERE user_id = %s AND language = %s" + extra, [user_id, language, *params])
        return {"items": items, "total": cur.fetchone()["n"]}


def pos_cards(conn, user_id: int, language: str, limit: int, set_filter=None, due: bool = False) -> dict:
    """Which part of speech is this word? Cards from the learner's own words that have a label; the options are the categories of
    the language (each language has its own list). With due=True: the due words first, then words never practised."""
    options = list(pos_rules.categories(language))
    extra, params = word_sets.filter_clause(set_filter)
    with cursor(conn) as cur:
        if due:
            e, p = word_sets.filter_clause(set_filter, "w.set_id")
            rows = progress.due_rows(cur, user_id, language, e + " AND w.pos IS NOT NULL", p, need_meaning=False, with_pos=True)
            items = rows[:limit]
            total = len(rows)
        else:
            cur.execute("SELECT id, word, meaning, pos FROM tutor.words WHERE user_id = %s AND language = %s AND pos IS NOT NULL" + extra
                        + " ORDER BY random() LIMIT %s", [user_id, language, *params, limit])
            items = cur.fetchall()
            cur.execute("SELECT count(*) AS n FROM tutor.words WHERE user_id = %s AND language = %s AND pos IS NOT NULL" + extra, [user_id, language, *params])
            total = cur.fetchone()["n"]
    return {"items": [{"id": r["id"], "word": r["word"], "answer": r["pos"], "options": options, "meaning": (r["meaning"] or "").strip() or None}
                      for r in items if r["pos"] in options], "total": total}
