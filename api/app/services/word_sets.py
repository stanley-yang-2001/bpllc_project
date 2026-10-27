"""A learner's vocabulary sets (migration 0012). The words with no set are the General set, which always exists and cannot be
renamed or deleted. A set belongs to one learner and one language; every query here carries the learner id, so a set id that
belongs to someone else behaves exactly like one that does not exist."""
from __future__ import annotations

import re

import psycopg2.errors

from ..db import cursor
from ..errors import conflict, not_found, validation_error

MAX_SETS = 20            # per learner and language
NAME_MAX = 40
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")


def clean_name(name) -> str:
    text = " ".join(_CONTROL.sub(" ", str(name or "")).split())
    if not text:
        raise validation_error("Give the set a name.")
    if len(text) > NAME_MAX:
        raise validation_error(f"A set name is at most {NAME_MAX} characters.")
    if text.casefold() == "general":
        raise validation_error("General is the set your words are in until you move them; choose another name.")
    return text


def list_sets(conn, user_id: int, language: str) -> dict:
    with cursor(conn) as cur:
        cur.execute("SELECT s.id, s.name, s.language, count(w.id) AS count FROM tutor.word_sets s "
                    "LEFT JOIN tutor.words w ON w.set_id = s.id AND w.user_id = s.user_id "
                    "WHERE s.user_id = %s AND s.language = %s GROUP BY s.id ORDER BY lower(s.name)", (user_id, language))
        items = cur.fetchall()
        cur.execute("SELECT count(*) AS n FROM tutor.words WHERE user_id = %s AND language = %s AND set_id IS NULL", (user_id, language))
        general = cur.fetchone()["n"]
    return {"items": items, "general_count": general, "total_count": general + sum(i["count"] for i in items)}


def create(conn, user_id: int, language: str, name) -> dict:
    name = clean_name(name)
    with cursor(conn) as cur:
        cur.execute("SELECT count(*) AS n FROM tutor.word_sets WHERE user_id = %s AND language = %s", (user_id, language))
        if cur.fetchone()["n"] >= MAX_SETS:
            raise validation_error(f"You can have {MAX_SETS} sets in one language. Delete one to make another.")
        try:
            cur.execute("INSERT INTO tutor.word_sets (user_id, language, name) VALUES (%s, %s, %s) RETURNING id, name, language",
                        (user_id, language, name))
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            raise conflict(f"You already have a set called '{name}'.")
        row = cur.fetchone()
    return {**row, "count": 0}


def rename(conn, user_id: int, set_id: int, name) -> dict:
    name = clean_name(name)
    with cursor(conn) as cur:
        try:
            cur.execute("UPDATE tutor.word_sets SET name = %s WHERE id = %s AND user_id = %s RETURNING id, name, language",
                        (name, set_id, user_id))
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            raise conflict(f"You already have a set called '{name}'.")
        row = cur.fetchone()
        if not row:
            raise not_found("That set doesn't exist.")
        cur.execute("SELECT count(*) AS n FROM tutor.words WHERE set_id = %s AND user_id = %s", (set_id, user_id))
        return {**row, "count": cur.fetchone()["n"]}


def delete(conn, user_id: int, set_id: int) -> int:
    """Deletes the set; its words go back to General (the foreign key sets them to NULL). Returns how many words moved back."""
    with cursor(conn) as cur:
        cur.execute("SELECT count(*) AS n FROM tutor.words WHERE set_id = %s AND user_id = %s", (set_id, user_id))
        moved = cur.fetchone()["n"]
        cur.execute("DELETE FROM tutor.word_sets WHERE id = %s AND user_id = %s", (set_id, user_id))
        if cur.rowcount == 0:
            raise not_found("That set doesn't exist.")
    return moved


def owned(conn, user_id: int, set_id: int, language: str | None = None) -> dict:
    """The learner's own set (optionally in that language), or a 'not found'."""
    with cursor(conn) as cur:
        cur.execute("SELECT id, name, language FROM tutor.word_sets WHERE id = %s AND user_id = %s", (set_id, user_id))
        row = cur.fetchone()
    if not row or (language and row["language"] != language):
        raise not_found("That set doesn't exist.")
    return row


def move_words(conn, user_id: int, ids: list[int], set_id: int | None) -> int:
    """Moves words into a set (or back to General when set_id is None). Only this learner's words, and, for a set, only those in
    the set's own language, are moved; the rest are left alone. Returns how many moved."""
    with cursor(conn) as cur:
        if set_id is None:
            cur.execute("UPDATE tutor.words SET set_id = NULL WHERE user_id = %s AND id = ANY(%s)", (user_id, ids))
        else:
            target = owned(conn, user_id, set_id)
            cur.execute("UPDATE tutor.words SET set_id = %s WHERE user_id = %s AND id = ANY(%s) AND language = %s",
                        (set_id, user_id, ids, target["language"]))
        return cur.rowcount
