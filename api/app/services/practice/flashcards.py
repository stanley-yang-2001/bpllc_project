"""Flashcards, dictation and parts-of-speech cards: the learner's own words, picked at random or (Due) by what is due now."""
from __future__ import annotations

from tutor_core import pos as pos_rules

from ...db import cursor
from .. import progress, word_sets


def flashcards(conn, user_id: int, language: str, limit: int, set_filter=None, due: bool = False) -> dict:
    """Shuffled words that have a meaning (a card with nothing on its back is no use), optionally from one set only.
    With due=True: only the words that are due now (oldest first), then words never practised."""
    extra, params = word_sets.filter_clause(set_filter)
    with cursor(conn) as cur:
        if due:
            rows = progress.due_rows(cur, user_id, language, *word_sets.filter_clause(set_filter, "w.set_id"))
            return {"items": rows[:limit], "total": len(rows)}
        cur.execute("SELECT id, word, meaning FROM tutor.words WHERE user_id = %s AND language = %s "
                    "AND meaning IS NOT NULL AND btrim(meaning) <> ''" + extra + " ORDER BY random() LIMIT %s", [user_id, language, *params, limit])
        items = cur.fetchall()
        cur.execute("SELECT count(*) AS n FROM tutor.words WHERE user_id = %s AND language = %s "
                    "AND meaning IS NOT NULL AND btrim(meaning) <> ''" + extra, [user_id, language, *params])
        return {"items": items, "total": cur.fetchone()["n"]}


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
