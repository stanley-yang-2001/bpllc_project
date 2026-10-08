"""Server-side sessions. A token is only honoured while its session row exists, so logout, "log out
everywhere" and deleting a user all take effect immediately, not when the JWT expires."""
from __future__ import annotations

from ..db import cursor
from ..security import new_session_id


def create(conn, user_id: int, hours: int) -> str:
    sid = new_session_id()
    with cursor(conn) as cur:
        cur.execute("DELETE FROM sessions WHERE expires_at < now()")          # tidy up expired rows
        cur.execute("INSERT INTO sessions (id, user_id, expires_at) VALUES (%s, %s, now() + make_interval(hours => %s))",
                    (sid, user_id, hours))
    return sid


def user_for(conn, session_id: str, user_id: int):
    """The user behind a live session, or None. The user id must match the one signed into the token."""
    with cursor(conn) as cur:
        cur.execute("SELECT u.id, u.email, u.display_name, u.native_language, u.created_at FROM sessions s "
                    "JOIN users u ON u.id = s.user_id WHERE s.id = %s AND s.user_id = %s AND s.expires_at > now()",
                    (session_id, user_id))
        return cur.fetchone()


def revoke(conn, session_id: str) -> None:
    with cursor(conn) as cur:
        cur.execute("DELETE FROM sessions WHERE id = %s", (session_id,))


def revoke_others(conn, user_id: int, keep_session_id: str) -> int:
    """End every session of the user except the one making the request (used after a password change)."""
    with cursor(conn) as cur:
        cur.execute("DELETE FROM sessions WHERE user_id = %s AND id <> %s", (user_id, keep_session_id))
        return cur.rowcount


def revoke_all(conn, user_id: int) -> int:
    with cursor(conn) as cur:
        cur.execute("DELETE FROM sessions WHERE user_id = %s", (user_id,))
        return cur.rowcount
