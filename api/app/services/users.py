from __future__ import annotations

import psycopg2.errors

from ..db import cursor
from ..errors import conflict, unauthorized

USER_COLS = "id, email, display_name, native_language, created_at"


def create_user(conn, email: str, password_hash: str, display_name: str, language: str, policy_version: str) -> dict:
    with cursor(conn) as cur:
        try:
            cur.execute(
                "INSERT INTO users (email, password_hash, display_name, privacy_accepted_at, privacy_version) "
                f"VALUES (%s, %s, %s, now(), %s) RETURNING {USER_COLS}", (email, password_hash, display_name, policy_version))
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            raise conflict("An account with that email already exists.")
        user = cur.fetchone()
        cur.execute("INSERT INTO user_languages (user_id, language) VALUES (%s, %s)", (user["id"], language))
    return user


def get_by_email(conn, email: str):
    with cursor(conn) as cur:
        cur.execute(f"SELECT {USER_COLS}, password_hash FROM users WHERE email = %s", (email,))
        return cur.fetchone()


def get_by_id(conn, user_id: int):
    with cursor(conn) as cur:
        cur.execute(f"SELECT {USER_COLS} FROM users WHERE id = %s", (user_id,))
        return cur.fetchone()


def languages_of(conn, user_id: int) -> list[str]:
    with cursor(conn) as cur:
        cur.execute("SELECT language FROM user_languages WHERE user_id = %s ORDER BY created_at, language", (user_id,))
        return [r["language"] for r in cur.fetchall()]


def add_language(conn, user_id: int, language: str) -> None:
    with cursor(conn) as cur:
        cur.execute("INSERT INTO user_languages (user_id, language) VALUES (%s, %s) ON CONFLICT DO NOTHING", (user_id, language))


def update_profile(conn, user_id: int, display_name, native_language) -> dict:
    with cursor(conn) as cur:
        cur.execute(
            f"UPDATE users SET display_name = COALESCE(%s, display_name), native_language = COALESCE(%s, native_language) "
            f"WHERE id = %s RETURNING {USER_COLS}", (display_name, native_language, user_id))
        user = cur.fetchone()
    if not user:
        raise unauthorized()
    return user


def update_email(conn, user_id: int, email: str) -> dict:
    with cursor(conn) as cur:
        try:
            cur.execute(f"UPDATE users SET email = %s WHERE id = %s RETURNING {USER_COLS}", (email, user_id))
        except psycopg2.errors.UniqueViolation:
            conn.rollback()
            raise conflict("An account with that email already exists.")
        return cur.fetchone()


def set_password(conn, user_id: int, password_hash: str) -> None:
    with cursor(conn) as cur:
        cur.execute("UPDATE users SET password_hash = %s WHERE id = %s", (password_hash, user_id))


def delete_user(conn, user_id: int) -> None:
    """Hard delete. Every table that references users does so with ON DELETE CASCADE, so words, languages,
    sessions (and later stories) go with the account. A test checks this against the live schema."""
    with cursor(conn) as cur:
        cur.execute("DELETE FROM users WHERE id = %s", (user_id,))


def profile(conn, user: dict) -> dict:
    return {**{k: user[k] for k in ("id", "email", "display_name", "native_language")},
            "languages": languages_of(conn, user["id"])}
