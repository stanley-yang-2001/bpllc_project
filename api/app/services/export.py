"""Everything we hold about one person, for "Download my data".

Keys are the table names (the profile is the `users` table). A test fails if a table with a user_id column
exists that is missing from this export, so new features cannot silently leave data out."""
from __future__ import annotations

from datetime import datetime, timezone

from ..db import cursor
from ..policy import POLICY_VERSION


def build(conn, user_id: int) -> dict:
    out: dict = {"exported_at": datetime.now(timezone.utc), "policy_version": POLICY_VERSION}
    with cursor(conn) as cur:
        cur.execute("SELECT email, display_name, native_language, created_at, privacy_accepted_at, privacy_version "
                    "FROM users WHERE id = %s", (user_id,))
        out["profile"] = cur.fetchone()
        cur.execute("SELECT language, created_at FROM user_languages WHERE user_id = %s ORDER BY created_at, language", (user_id,))
        out["user_languages"] = cur.fetchall()
        cur.execute("SELECT w.language, w.word, w.meaning, s.name AS set_name, w.created_at FROM words w "
                    "LEFT JOIN word_sets s ON s.id = w.set_id WHERE w.user_id = %s ORDER BY w.language, w.word", (user_id,))
        out["words"] = cur.fetchall()           # set_name null = the General set
        cur.execute("SELECT language, name, created_at FROM word_sets WHERE user_id = %s ORDER BY language, name", (user_id,))
        out["word_sets"] = cur.fetchall()
        cur.execute("SELECT active_language, ui_follows_study_language, chat_in_study_language, theme, custom_colors, updated_at "
                    "FROM user_preferences WHERE user_id = %s", (user_id,))
        out["user_preferences"] = cur.fetchone()          # null when never saved
        cur.execute("SELECT id, language, story_type, topic, body, passed, report, created_at FROM stories "
                    "WHERE user_id = %s ORDER BY id", (user_id,))
        out["stories"] = cur.fetchall()
        # your own model: the settings you entered, never the key (only its last four characters)
        cur.execute("SELECT model, base_url, key_last4, updated_at FROM user_models WHERE user_id = %s", (user_id,))
        out["user_models"] = cur.fetchone()               # null when you have none
        # login records: when, not the secret ids
        cur.execute("SELECT created_at, expires_at FROM sessions WHERE user_id = %s ORDER BY created_at", (user_id,))
        out["sessions"] = cur.fetchall()
        # which chat sessions we hold for you; the messages themselves live in the tutor service
        cur.execute("SELECT session_id, created_at FROM chat_sessions WHERE user_id = %s ORDER BY created_at, session_id", (user_id,))
        out["chat_sessions"] = cur.fetchall()
    return out
