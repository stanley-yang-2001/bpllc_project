"""Which Langflow chat sessions belong to which learner (ids only; the messages live in Langflow).

Recorded on every chat turn so that deleting an account can delete the stored conversation too."""
from __future__ import annotations

from ..db import cursor


def record(conn, user_id: int, session_id: str) -> None:
    with cursor(conn) as cur:
        cur.execute("INSERT INTO tutor.chat_sessions (user_id, session_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                    (user_id, session_id))


def list_ids(conn, user_id: int) -> list[str]:
    with cursor(conn) as cur:
        cur.execute("SELECT session_id FROM tutor.chat_sessions WHERE user_id = %s ORDER BY created_at, session_id", (user_id,))
        return [row["session_id"] for row in cur.fetchall()]
