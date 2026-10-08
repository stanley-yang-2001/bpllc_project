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
        cur.execute("SELECT language, word, meaning, created_at FROM words WHERE user_id = %s ORDER BY language, word", (user_id,))
        out["words"] = cur.fetchall()
        # login records: when, not the secret ids
        cur.execute("SELECT created_at, expires_at FROM sessions WHERE user_id = %s ORDER BY created_at", (user_id,))
        out["sessions"] = cur.fetchall()
    return out
