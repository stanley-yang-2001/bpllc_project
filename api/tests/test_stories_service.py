"""The stories table and its service (M6): per-learner rows, stored report, deletion with the account, export."""
import psycopg2
import pytest

from app.errors import AppError
from app.services import stories
from conftest import DB_URL, register

REPORT = {"rules_version": 1, "status": "pass"}
BODY = "Ana: Hola.\nLuis: Hola."


def make(conn, uid, language="es", body=BODY, story_type="dialogue", topic="a market day", report=REPORT):
    return stories.create(conn, uid, language, story_type, topic, body, report)


def test_a_saved_story_comes_back_with_its_fields(conn, make_learner):
    uid = make_learner("a")
    saved = make(conn, uid)
    conn.commit()
    got = stories.get(conn, uid, saved["id"])
    assert (got["language"], got["story_type"], got["topic"], got["body"], got["passed"]) == ("es", "dialogue", "a market day", BODY, True)
    assert got["report"] == REPORT and got["created_at"] is not None


def test_passed_is_taken_from_the_report_not_from_the_caller(conn, make_learner):
    uid = make_learner("a")
    assert make(conn, uid, report={"rules_version": 1, "status": "fail"})["passed"] is False
    assert make(conn, uid, report={"rules_version": 1, "status": "pass"})["passed"] is True


def test_a_chat_story_has_no_type_or_topic(conn, make_learner):
    uid = make_learner("a")
    saved = make(conn, uid, story_type=None, topic=None)
    assert saved["story_type"] is None and saved["topic"] is None


def test_the_list_is_newest_first_filtered_by_language_and_paged(conn, make_learner):
    uid = make_learner("a")
    first, second = make(conn, uid, "es"), make(conn, uid, "es")
    other = make(conn, uid, "fr")
    page = stories.list_for_user(conn, uid, "es", limit=10, offset=0)
    assert [s["id"] for s in page["items"]] == [second["id"], first["id"]] and page["total"] == 2
    assert [s["id"] for s in stories.list_for_user(conn, uid, None, 10, 0)["items"]] == [other["id"], second["id"], first["id"]]
    assert [s["id"] for s in stories.list_for_user(conn, uid, "es", 1, 1)["items"]] == [first["id"]]


def test_the_list_leaves_out_the_report_but_keeps_what_the_cards_need(conn, make_learner):
    uid = make_learner("a")
    make(conn, uid)
    item = stories.list_for_user(conn, uid, None, 10, 0)["items"][0]
    assert set(item) == {"id", "language", "story_type", "topic", "body", "passed", "created_at"}


def test_one_learner_cannot_read_list_or_delete_anothers_story(conn, make_learner):
    a, b = make_learner("a"), make_learner("b")
    story = make(conn, a)
    assert stories.get(conn, b, story["id"]) is None
    assert stories.list_for_user(conn, b, None, 10, 0) == {"items": [], "total": 0, "limit": 10, "offset": 0}
    assert stories.delete(conn, b, story["id"]) is False
    assert stories.get(conn, a, story["id"]) is not None


def test_delete_removes_only_that_story(conn, make_learner):
    uid = make_learner("a")
    keep, drop = make(conn, uid), make(conn, uid)
    assert stories.delete(conn, uid, drop["id"]) is True and stories.delete(conn, uid, drop["id"]) is False
    assert [s["id"] for s in stories.list_for_user(conn, uid, None, 10, 0)["items"]] == [keep["id"]]


@pytest.mark.parametrize("kwargs", [{"story_type": "x" * 41}, {"story_type": ""}, {"language": "spanish"}, {"language": "E"}, {"body": "   "},
                                    {"body": "x" * 20001}, {"topic": "t" * 121}])
def test_the_database_refuses_junk_even_if_the_service_were_bypassed(conn, make_learner, kwargs):
    uid = make_learner("a")
    with pytest.raises(psycopg2.errors.CheckViolation):
        make(conn, uid, **kwargs)
    conn.rollback()


def test_deleting_the_user_deletes_their_stories(conn, make_learner):
    a, b = make_learner("a"), make_learner("b")
    make(conn, a), make(conn, b)
    conn.commit()
    with psycopg2.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute("DELETE FROM tutor.users WHERE id = %s", (a,))
    assert [r for r in stories.list_for_user(conn, b, None, 10, 0)["items"]] and stories.list_for_user(conn, a, None, 10, 0)["total"] == 0


def test_the_export_includes_the_learners_stories_and_nobody_elses(make_user, client, conn):
    bob = make_user("bob")
    register(client, "alice")
    with psycopg2.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute("SELECT id, email FROM tutor.users")
        ids = {email: i for i, email in cur.fetchall()}
        for who, text in (("alice@example.com", "alice story"), ("bob@example.com", "bob secret story")):
            cur.execute("INSERT INTO tutor.stories (user_id, language, body, passed, report) VALUES (%s, 'es', %s, true, '{}')",
                        (ids[who], text))
    data = client.get("/api/me/export").json()
    assert [s["body"] for s in data["stories"]] == ["alice story"]
    assert set(data["stories"][0]) == {"id", "language", "story_type", "topic", "body", "passed", "report", "created_at"}
    assert "bob secret story" not in client.get("/api/me/export").text
