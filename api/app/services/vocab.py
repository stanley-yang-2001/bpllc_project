from __future__ import annotations

import psycopg2.errors
from tutor_core import pos as pos_rules, starter
from tutor_core.words import WordError, validate_meaning, validate_word

from ..db import cursor
from ..errors import conflict, not_found, validation_error
from . import word_sets
from .csv_import import bulk_add, parse_csv                                       # noqa: F401  (old import path)
from .word_fill import fill_meanings, fill_pos, words_without_meaning, words_without_pos      # noqa: F401  (old import path)

WORD_COLS = "id, language, word, meaning, pos, set_id, created_at"


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_words(conn, user_id: int, language: str, q: str | None, limit: int, offset: int, set_filter: str | None = None,
               missing_meaning: bool = False) -> dict:
    """set_filter: None or "all" = every word; "general" = words in no set; a number = that set (the learner's own)."""
    where, params = "user_id = %s AND language = %s", [user_id, language]
    extra, extra_params = word_sets.filter_clause(set_filter)
    where, params = where + extra, params + extra_params
    if missing_meaning:
        where += " AND (meaning IS NULL OR btrim(meaning) = '')"
    if q and q.strip():
        like = f"%{_escape_like(q.strip().lower())}%"
        where += " AND (lower(word) LIKE %s OR lower(coalesce(meaning, '')) LIKE %s)"
        params += [like, like]
    with cursor(conn) as cur:
        cur.execute(f"SELECT count(*) AS n FROM words WHERE {where}", params)
        total = cur.fetchone()["n"]
        cur.execute(f"SELECT {WORD_COLS} FROM words WHERE {where} ORDER BY id DESC LIMIT %s OFFSET %s", params + [limit, offset])
        return {"items": cur.fetchall(), "total": total, "limit": limit, "offset": offset}


def _clean(word, meaning, language):
    try:
        return validate_word(word, language), validate_meaning(meaning)
    except WordError as e:
        raise validation_error(str(e))


def _clean_pos(language: str, code):
    """None or "" = no label; otherwise a code from this language's own list."""
    if code is None or code == "":
        return None
    if not pos_rules.valid(language, code):
        raise validation_error("Choose a part of speech from the list for this language.")
    return code


def add_word(conn, user_id: int, language: str, word: str, meaning, set_id: int | None = None, pos: str | None = None) -> dict:
    word, meaning = _clean(word, meaning, language)
    pos = _clean_pos(language, pos)
    if set_id is not None:
        word_sets.owned(conn, user_id, set_id, language)          # a set that is not this learner's, or another language's: not found
    with cursor(conn) as cur:
        try:
            cur.execute(f"INSERT INTO words (user_id, language, word, meaning, set_id, pos) VALUES (%s, %s, %s, %s, %s, %s) RETURNING {WORD_COLS}",
                        (user_id, language, word, meaning, set_id, pos))
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            raise conflict(f"'{word}' is already in your list.")
        row = cur.fetchone()
        cur.execute("INSERT INTO user_languages (user_id, language) VALUES (%s, %s) ON CONFLICT DO NOTHING", (user_id, language))
    return row


def update_word(conn, user_id: int, word_id: int, fields: dict) -> dict:
    with cursor(conn) as cur:
        cur.execute(f"SELECT {WORD_COLS} FROM words WHERE id = %s AND user_id = %s", (word_id, user_id))
        current = cur.fetchone()
        if not current:
            raise not_found("Word not found.")
        new_word = fields.get("word", current["word"])
        new_meaning = fields["meaning"] if "meaning" in fields else current["meaning"]
        new_word, new_meaning = _clean(new_word, new_meaning, current["language"])
        new_pos = _clean_pos(current["language"], fields["pos"]) if "pos" in fields else current["pos"]
        try:
            cur.execute(f"UPDATE words SET word = %s, meaning = %s, pos = %s WHERE id = %s AND user_id = %s RETURNING {WORD_COLS}",
                        (new_word, new_meaning, new_pos, word_id, user_id))
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            raise conflict(f"'{new_word}' is already in your list.")
        return cur.fetchone()


def delete_words(conn, user_id: int, ids: list[int]) -> int:
    with cursor(conn) as cur:
        cur.execute("DELETE FROM words WHERE user_id = %s AND id = ANY(%s)", (user_id, ids))
        return cur.rowcount


def starter_packs(conn, user_id: int, language: str) -> list[dict]:
    """The ready-made packs for this language and how many of their words the learner does not have yet."""
    if not starter.has_packs(language):
        return []
    with cursor(conn) as cur:
        cur.execute("SELECT word FROM words WHERE user_id = %s AND language = %s", (user_id, language))
        have = {r["word"] for r in cur.fetchall()}
    out = []
    for pack in starter.pack_ids():
        words = [w for w, _ in starter.pack_words(pack, language)]
        out.append({"id": pack, "total": len(words), "remaining": sum(1 for w in words if validate_word(w, language) not in have)})
    return out


def add_starter_pack(conn, user_id: int, language: str, pack: str, with_gloss: bool) -> dict:
    """Adds a pack's words that the learner does not have (existing words are never touched). With `with_gloss` the short English
    gloss is stored as the meaning, free and ready for practice; without it the words have no meaning yet, to be written by the tutor."""
    pairs = starter.pack_words(pack, language)
    if not pairs:
        raise not_found("That pack isn't available for this language.")
    rows = [(i + 1, w, (g or "") if with_gloss else "") for i, (w, g) in enumerate(pairs)]
    result = bulk_add(conn, user_id, language, rows)
    return {"added": result["added"], "duplicates": result["duplicates"], "with_meaning": bool(with_gloss and language != "en")}


