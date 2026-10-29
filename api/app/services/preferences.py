"""Preferences kept on the account (design 3H): the theme, the five custom colours, whether the site follows
the study language, the language of tutor-written meanings, and the language being studied now. No row means defaults."""
from __future__ import annotations

from psycopg2.extras import Json

from ..db import cursor

COLUMNS = "active_language, ui_follows_study_language, chat_in_study_language, meaning_mode, theme, custom_colors"
_WRITABLE = ("active_language", "ui_follows_study_language", "chat_in_study_language", "meaning_mode", "theme", "custom_colors")


def get(conn, user_id: int) -> dict | None:
    """The saved preferences, or None when this person never saved any (the app then uses its defaults)."""
    with cursor(conn) as cur:
        cur.execute(f"SELECT {COLUMNS} FROM user_preferences WHERE user_id = %s", (user_id,))
        return cur.fetchone()


def save(conn, user_id: int, changes: dict) -> dict:
    """Changes any subset of the fields and leaves the rest as they were. `changes` holds only the fields the caller
    sent; a value of None clears active_language or custom_colors."""
    unknown = set(changes) - set(_WRITABLE)
    if unknown:                                      # a programming error, never user input (the route rejects extras)
        raise ValueError(f"unknown preference fields: {sorted(unknown)}")
    with cursor(conn) as cur:
        cur.execute("INSERT INTO user_preferences (user_id) VALUES (%s) ON CONFLICT (user_id) DO NOTHING", (user_id,))
        if changes:
            sets = ", ".join(f"{name} = %s" for name in changes) + ", updated_at = now()"
            values = [Json(v) if name == "custom_colors" and v is not None else v for name, v in changes.items()]
            cur.execute(f"UPDATE user_preferences SET {sets} WHERE user_id = %s", (*values, user_id))
    return get(conn, user_id)


_NOT_NULLABLE = {"theme": "theme: cannot be empty", "ui_follows_study_language": "ui_follows_study_language: must be true or false",
                 "chat_in_study_language": "chat_in_study_language: must be true or false",
                 "meaning_mode": "meaning_mode: must be native, study or both"}


def changes_from(sent: dict) -> dict:
    """The columns to write for the fields a request actually sent. A field that may not be cleared refuses None; the colours may."""
    from ..errors import validation_error
    changes = {}
    for key in _WRITABLE:
        if key not in sent:
            continue
        if sent[key] is None and key in _NOT_NULLABLE:
            raise validation_error(_NOT_NULLABLE[key])
        changes[key] = sent[key]
    return changes
