"""Migration 0009: stories may have a type of the learner's own, and the downgrade puts the old rule back safely.

This test moves the shared test database down one revision and back up, inside try/finally, so the rest of the suite always
finds it at head."""
import psycopg2
import pytest
from alembic import command
from alembic.config import Config
from psycopg2 import errors

from app.migrate import ROOT
from conftest import DB_URL

BUILT_IN = ("narration", "dialogue", "story", "diary", "letter", "place", "routine", "anecdote")


def cfg():
    c = Config(str(ROOT / "alembic.ini"))
    c.set_main_option("script_location", str(ROOT / "migrations"))
    c.attributes["database_url"] = DB_URL
    return c


def story_types(conn):
    with conn.cursor() as cur:
        cur.execute("SELECT story_type FROM tutor.stories ORDER BY id")
        return [r[0] for r in cur.fetchall()]


def insert(conn, user, story_type):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO tutor.stories (user_id, language, story_type, body, passed, report) "
                    "VALUES (%s, 'en', %s, 'Ana: Hi.', true, '{}')", (user, story_type))
    conn.commit()


def test_a_label_of_one_to_forty_characters_is_accepted_and_nothing_else(conn, make_learner):
    user = make_learner()
    for ok in ("a poem", "x", "x" * 40, "diary", None):
        insert(conn, user, ok)
    for bad in ("", "x" * 41):
        with pytest.raises(errors.CheckViolation):
            insert(conn, user, bad)
        conn.rollback()
    assert story_types(conn) == ["a poem", "x", "x" * 40, "diary", None]


def test_the_downgrade_turns_custom_labels_into_story_and_restores_the_old_rule(conn, make_learner):
    user = make_learner()
    for t in ("a poem", "diary", None, "x" * 40):
        insert(conn, user, t)
    conn.commit()
    conn.close()                                   # the migration needs the table free of this session's locks
    try:
        command.downgrade(cfg(), "0008")
        with psycopg2.connect(DB_URL) as c:
            assert story_types(c) == ["story", "diary", None, "story"]
            with pytest.raises(errors.CheckViolation):
                insert(c, user, "a poem")
            c.rollback()
            for t in BUILT_IN:
                insert(c, user, t)                 # every built-in type still passes the old rule
    finally:
        command.upgrade(cfg(), "head")
    with psycopg2.connect(DB_URL) as c:
        insert(c, user, "a poem")                  # and the new rule is back
        assert story_types(c)[-1] == "a poem"
