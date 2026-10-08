from __future__ import annotations

import csv
import io

import psycopg2.errors
from tutor_core.words import WordError, validate_meaning, validate_word

from ..db import cursor
from ..errors import conflict, not_found, validation_error

WORD_COLS = "id, language, word, meaning, created_at"


def _escape_like(text: str) -> str:
    return text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def list_words(conn, user_id: int, language: str, q: str | None, limit: int, offset: int) -> dict:
    where, params = "user_id = %s AND language = %s", [user_id, language]
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


def add_word(conn, user_id: int, language: str, word: str, meaning) -> dict:
    word, meaning = _clean(word, meaning, language)
    with cursor(conn) as cur:
        try:
            cur.execute(f"INSERT INTO words (user_id, language, word, meaning) VALUES (%s, %s, %s, %s) RETURNING {WORD_COLS}",
                        (user_id, language, word, meaning))
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
        try:
            cur.execute(f"UPDATE words SET word = %s, meaning = %s WHERE id = %s AND user_id = %s RETURNING {WORD_COLS}",
                        (new_word, new_meaning, word_id, user_id))
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            raise conflict(f"'{new_word}' is already in your list.")
        return cur.fetchone()


def delete_words(conn, user_id: int, ids: list[int]) -> int:
    with cursor(conn) as cur:
        cur.execute("DELETE FROM words WHERE user_id = %s AND id = ANY(%s)", (user_id, ids))
        return cur.rowcount


def parse_csv(raw: bytes, max_bytes: int, max_rows: int) -> list[tuple[int, str, str]]:
    """Return [(row_number, word, meaning)]. Row numbers match the file (header is row 1)."""
    if len(raw) > max_bytes:
        raise validation_error(f"File is larger than {max_bytes // 1000} KB.")
    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise validation_error("File must be UTF-8 text.")
    reader = csv.reader(io.StringIO(text))
    header = next(reader, None)
    if not header:
        raise validation_error("File is empty.")
    cols = [c.strip().lower() for c in header]
    if "word" not in cols:
        raise validation_error("The first row must have a 'word' column.")
    wi = cols.index("word")
    mi = next((cols.index(n) for n in ("meaning", "definition") if n in cols), None)
    rows = []
    for n, row in enumerate(reader, start=2):
        if not any(cell.strip() for cell in row):
            continue
        if len(rows) >= max_rows:
            raise validation_error(f"More than {max_rows} rows.")
        word = row[wi] if wi < len(row) else ""
        meaning = row[mi] if mi is not None and mi < len(row) else ""
        rows.append((n, word, meaning))
    return rows


def bulk_add(conn, user_id: int, language: str, rows: list[tuple[int, str, str]]) -> dict:
    added = duplicates = 0
    invalid: list[dict] = []
    with cursor(conn) as cur:
        for n, word, meaning in rows:
            try:
                w, m = validate_word(word, language), validate_meaning(meaning)
            except WordError as e:
                invalid.append({"row": n, "reason": str(e)})
                continue
            cur.execute("INSERT INTO words (user_id, language, word, meaning) VALUES (%s, %s, %s, %s) "
                        "ON CONFLICT (user_id, language, word) DO NOTHING RETURNING id", (user_id, language, w, m))
            if cur.fetchone():
                added += 1
            else:
                duplicates += 1
        if added:
            cur.execute("INSERT INTO user_languages (user_id, language) VALUES (%s, %s) ON CONFLICT DO NOTHING", (user_id, language))
    return {"added": added, "duplicates": duplicates, "invalid_count": len(invalid), "invalid": invalid[:20]}
