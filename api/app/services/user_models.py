"""The saved model of one learner (table tutor.user_models). Every query filters by the learner's id."""
from __future__ import annotations

from ..db import cursor


def enabled(conn, user_id: int) -> bool:
    with cursor(conn) as cur:
        cur.execute("SELECT custom_model_enabled FROM tutor.users WHERE id = %s", (user_id,))
        row = cur.fetchone()
        return bool(row and row["custom_model_enabled"])


def get(conn, user_id: int):
    with cursor(conn) as cur:
        cur.execute("SELECT model, base_url, api_key_encrypted, key_last4, updated_at FROM tutor.user_models WHERE user_id = %s", (user_id,))
        return cur.fetchone()


def save(conn, user_id: int, model: str, base_url: str, api_key_encrypted: str, key_last4: str) -> None:
    with cursor(conn) as cur:
        cur.execute("""INSERT INTO tutor.user_models (user_id, model, base_url, api_key_encrypted, key_last4)
                       VALUES (%s, %s, %s, %s, %s)
                       ON CONFLICT (user_id) DO UPDATE SET model = EXCLUDED.model, base_url = EXCLUDED.base_url,
                           api_key_encrypted = EXCLUDED.api_key_encrypted, key_last4 = EXCLUDED.key_last4, updated_at = now()""",
                    (user_id, model, base_url, api_key_encrypted, key_last4))


def delete(conn, user_id: int) -> bool:
    with cursor(conn) as cur:
        cur.execute("DELETE FROM tutor.user_models WHERE user_id = %s", (user_id,))
        return cur.rowcount == 1
