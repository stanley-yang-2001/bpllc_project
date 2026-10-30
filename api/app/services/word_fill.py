"""The words that still lack something the tutor can write (a meaning, a part of speech), and putting what it wrote in.

Both never replace what the learner wrote: a value is set only where the word still has none and belongs to this learner."""
from __future__ import annotations

from ..db import cursor
from . import word_sets


def _missing(conn, user_id: int, language: str, ids, set_filter, limit: int, lacks: str) -> dict:
    """{"items": [{"id", "word"}] (at most `limit`), "remaining": how many in all} for this learner's words where `lacks` (a SQL condition) holds.
    `ids` limits it to those words (only the learner's own ever match); otherwise the set choice works as on the vocabulary page."""
    where, params = f"user_id = %s AND language = %s AND ({lacks})", [user_id, language]
    if ids is not None:
        where += " AND id = ANY(%s)"
        params.append(list(ids))
    else:
        extra, extra_params = word_sets.filter_clause(set_filter)
        where, params = where + extra, params + extra_params
    with cursor(conn) as cur:
        cur.execute(f"SELECT id, word FROM words WHERE {where} ORDER BY id LIMIT %s", [*params, limit])
        items = cur.fetchall()
        cur.execute(f"SELECT count(*) AS n FROM words WHERE {where}", params)
        return {"items": items, "remaining": cur.fetchone()["n"]}


def words_without_meaning(conn, user_id: int, language: str, ids, set_filter, limit: int) -> dict:
    """The learner's own words that have no meaning yet."""
    return _missing(conn, user_id, language, ids, set_filter, limit, "meaning IS NULL OR btrim(meaning) = ''")


def words_without_pos(conn, user_id: int, language: str, ids, set_filter, limit: int) -> dict:
    """The learner's own words that have no part of speech yet."""
    return _missing(conn, user_id, language, ids, set_filter, limit, "pos IS NULL")


def fill_meanings(conn, user_id: int, pairs) -> int:
    """Sets each meaning only where the word still has none and belongs to this learner; returns how many were set."""
    done = 0
    with cursor(conn) as cur:
        for word_id, meaning in pairs:
            cur.execute("UPDATE words SET meaning = %s WHERE id = %s AND user_id = %s AND (meaning IS NULL OR btrim(meaning) = '')",
                        (meaning, word_id, user_id))
            done += cur.rowcount
    return done


def fill_pos(conn, user_id: int, pairs) -> int:
    """Sets each label only where the word still has none and belongs to this learner; returns how many were set."""
    done = 0
    with cursor(conn) as cur:
        for word_id, code in pairs:
            cur.execute("UPDATE words SET pos = %s WHERE id = %s AND user_id = %s AND pos IS NULL", (code, word_id, user_id))
            done += cur.rowcount
    return done
