"""Saved stories (the library). Every query filters by the learner's id; another learner's row is simply 'not found'."""
from __future__ import annotations

from psycopg2.extras import Json

from ..db import cursor

CARD_COLS = "id, language, story_type, topic, body, passed, created_at"
FULL_COLS = CARD_COLS + ", report"


def create(conn, user_id: int, language: str, story_type, topic, body: str, report: dict) -> dict:
    """`passed` always comes from the report (which the server computed), never from the caller."""
    passed = report.get("status") == "pass"
    with cursor(conn) as cur:
        cur.execute(f"INSERT INTO tutor.stories (user_id, language, story_type, topic, body, passed, report) "
                    f"VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING {FULL_COLS}",
                    (user_id, language, story_type, topic, body, passed, Json(report)))
        return cur.fetchone()


def get(conn, user_id: int, story_id: int):
    with cursor(conn) as cur:
        cur.execute(f"SELECT {FULL_COLS} FROM tutor.stories WHERE id = %s AND user_id = %s", (story_id, user_id))
        return cur.fetchone()


def list_for_user(conn, user_id: int, language: str | None, limit: int, offset: int) -> dict:
    where, params = "user_id = %s", [user_id]
    if language:
        where += " AND language = %s"
        params.append(language)
    with cursor(conn) as cur:
        cur.execute(f"SELECT count(*) AS n FROM tutor.stories WHERE {where}", params)
        total = cur.fetchone()["n"]
        cur.execute(f"SELECT {CARD_COLS} FROM tutor.stories WHERE {where} ORDER BY id DESC LIMIT %s OFFSET %s", params + [limit, offset])
        return {"items": cur.fetchall(), "total": total, "limit": limit, "offset": offset}


def delete(conn, user_id: int, story_id: int) -> bool:
    with cursor(conn) as cur:
        cur.execute("DELETE FROM tutor.stories WHERE id = %s AND user_id = %s", (story_id, user_id))
        return cur.rowcount == 1
