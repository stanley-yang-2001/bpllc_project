"""Spaced repetition: answers are remembered per word, due words come back, and it all belongs to the learner."""
from datetime import date, timedelta

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.services import progress
from conftest import DB_URL, HEADERS

WORDS = {"hello": "greeting", "water": "a drink", "friend": "someone you like", "bread": "baked food"}


def learner(make_user, name="alice", words=WORDS, language="en"):
    c = make_user(name)
    ids = {}
    for w, m in words.items():
        r = c.post("/api/words", json={"language": language, "word": w, "meaning": m})
        assert r.status_code == 201
        ids[w] = r.json()["id"]
    return c, ids


def answer(c, *pairs):
    r = c.post("/api/practice/answers", json={"answers": [{"word_id": i, "correct": ok} for i, ok in pairs]})
    assert r.status_code == 204, r.text


def rows(sql, *args):
    with psycopg2.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall() if cur.description else []


def make_due(word_id):
    rows("UPDATE tutor.word_progress SET due_at = now() - interval '1 minute' WHERE word_id = %s", word_id)


def prog(c, language="en"):
    return c.get(f"/api/practice/progress?language={language}").json()


def due_words(c, **extra):
    r = c.get("/api/practice/flashcards", params={"language": "en", "limit": 50, "due": "true", **extra})
    return [x["word"] for x in r.json()["items"]]


def test_needs_login(app):
    anon = TestClient(app, headers=HEADERS)
    assert anon.post("/api/practice/answers", json={"answers": []}).status_code == 401
    assert anon.get("/api/practice/progress?language=en").status_code == 401


def test_fresh_learner_has_only_new_words(make_user):
    c, _ = learner(make_user)
    assert prog(c) == {"language": "en", "new": 4, "learning": 0, "known": 0, "due": 0, "streak": 0, "practised_today": False}


def test_words_without_a_meaning_are_not_counted(make_user):
    c, _ = learner(make_user)
    c.post("/api/words", json={"language": "en", "word": "nomeaning"})
    assert prog(c)["new"] == 4


def test_a_right_answer_moves_up_a_box_and_rests_a_day(make_user):
    c, ids = learner(make_user)
    answer(c, (ids["hello"], True))
    box, days, right, wrong = rows("SELECT box, extract(epoch FROM due_at - now()) / 86400, right_count, wrong_count FROM tutor.word_progress")[0]
    assert box == 2 and 0.99 < float(days) < 1.01 and (right, wrong) == (1, 0)
    p = prog(c)
    assert (p["new"], p["learning"], p["due"], p["practised_today"], p["streak"]) == (3, 1, 0, True, 1)


def test_a_wrong_answer_goes_back_to_box_one_and_returns_in_minutes(make_user):
    c, ids = learner(make_user)
    answer(c, (ids["hello"], True))
    make_due(ids["hello"])
    answer(c, (ids["hello"], False))
    box, minutes, right, wrong = rows("SELECT box, extract(epoch FROM due_at - now()) / 60, right_count, wrong_count FROM tutor.word_progress")[0]
    assert box == 1 and 9 < float(minutes) <= 10 and (right, wrong) == (1, 1)


def test_boxes_stop_at_five_and_known_is_box_four_up(make_user):
    c, ids = learner(make_user)
    for _ in range(6):
        answer(c, (ids["hello"], True))
        make_due(ids["hello"])
    assert rows("SELECT box FROM tutor.word_progress")[0][0] == 5
    p = prog(c)
    assert (p["known"], p["learning"], p["due"]) == (1, 0, 1)


def test_an_early_right_answer_counts_but_does_not_move_the_box_or_the_date(make_user):
    c, ids = learner(make_user)
    answer(c, (ids["hello"], True))
    before = rows("SELECT box, due_at FROM tutor.word_progress")[0]
    answer(c, (ids["hello"], True))
    after = rows("SELECT box, due_at, right_count FROM tutor.word_progress")[0]
    assert after[0] == before[0] == 2 and after[1] == before[1] and after[2] == 2


def test_the_same_word_twice_in_one_request_moves_up_once(make_user):
    c, ids = learner(make_user)
    answer(c, (ids["hello"], True), (ids["hello"], True))
    assert rows("SELECT box, right_count FROM tutor.word_progress")[0] == (2, 2)


def test_due_flashcards_are_due_words_first_then_new_words(make_user):
    c, ids = learner(make_user)
    answer(c, (ids["hello"], True), (ids["water"], True))
    assert sorted(due_words(c)) == ["bread", "friend"]                       # practised words rest; new ones are offered
    make_due(ids["water"])
    make_due(ids["hello"])
    rows("UPDATE tutor.word_progress SET due_at = now() - interval '3 days' WHERE word_id = %s", ids["water"])
    got = due_words(c)
    assert got[:2] == ["water", "hello"] and sorted(got[2:]) == ["bread", "friend"]       # the most overdue first
    body = c.get("/api/practice/flashcards?language=en&limit=1&due=true").json()
    assert len(body["items"]) == 1 and body["total"] == 4


def test_due_flashcards_respect_the_set_filter(make_user):
    c, ids = learner(make_user)
    s = c.post("/api/sets", json={"language": "en", "name": "food"}).json()["id"]
    c.post("/api/words/move", json={"ids": [ids["bread"]], "set_id": s})
    assert due_words(c, set=s) == ["bread"]
    assert "bread" not in due_words(c, set="general")


def test_due_choices_ask_about_due_words_but_offer_the_whole_list(make_user):
    c, ids = learner(make_user)
    answer(c, *[(ids[w], True) for w in ("hello", "water", "friend")])
    body = c.get("/api/practice/choices?language=en&limit=10&due=true").json()
    assert [x["prompt"] for x in body["items"]] == ["bread"] and body["total"] == 1
    assert len(body["items"][0]["choices"]) == 4


def test_nothing_due_when_everything_rests(make_user):
    c, ids = learner(make_user)
    answer(c, *[(ids[w], True) for w in WORDS])
    assert due_words(c) == []
    assert c.get("/api/practice/choices?language=en&due=true").json() == {"items": [], "total": 0}


def test_other_peoples_words_are_refused_and_nothing_is_saved(make_user):
    alice, a_ids = learner(make_user)
    bob, b_ids = learner(make_user, "bob", {"secret": "bobs"})
    r = alice.post("/api/practice/answers", json={"answers": [{"word_id": a_ids["hello"], "correct": True}, {"word_id": b_ids["secret"], "correct": True}]})
    assert r.status_code == 404
    assert rows("SELECT count(*) FROM tutor.word_progress")[0][0] == 0
    assert prog(bob)["practised_today"] is False


def test_answers_are_validated(make_user):
    c, ids = learner(make_user)
    assert c.post("/api/practice/answers", json={"answers": [{"word_id": ids["hello"]}]}).status_code == 422
    too_many = [{"word_id": ids["hello"], "correct": True}] * 51
    assert c.post("/api/practice/answers", json={"answers": too_many}).status_code == 422
    assert c.post("/api/practice/answers", json={"answers": []}).status_code == 204


def test_progress_is_per_language(make_user):
    c, ids = learner(make_user)
    c.post("/api/words", json={"language": "es", "word": "hola", "meaning": "hello"})
    answer(c, (ids["hello"], True))
    assert prog(c, "es")["new"] == 1 and prog(c, "es")["learning"] == 0
    assert c.get("/api/practice/progress?language=zz").status_code in (400, 404, 422)


def test_cloze_items_carry_the_word_id(make_user):
    c, ids = learner(make_user)
    story = c.post("/api/stories", json={"language": "en", "body": "Ana: Hello, my friend.\nBen: I want water.", "story_type": "dialogue"}).json()["id"]
    items = c.get(f"/api/practice/cloze?story_id={story}").json()["items"]
    assert items and all(i["word_id"] == ids[i["answer"].lower()] for i in items)


def test_deleting_a_word_removes_its_progress(make_user):
    c, ids = learner(make_user)
    answer(c, (ids["hello"], True))
    assert c.post("/api/words/delete", json={"ids": [ids["hello"]]}).json() == {"deleted": 1}
    assert rows("SELECT count(*) FROM tutor.word_progress")[0][0] == 0
    assert prog(c)["practised_today"] is True                                   # the day still counted


def test_export_includes_progress_and_days(make_user):
    c, ids = learner(make_user)
    answer(c, (ids["hello"], True), (ids["water"], False))
    data = c.get("/api/me/export").json()
    assert {(p["word"], p["box"], p["right_count"], p["wrong_count"]) for p in data["word_progress"]} == {("hello", 2, 1, 0), ("water", 1, 0, 1)}
    assert set(data["word_progress"][0]) == {"language", "word", "box", "due_at", "right_count", "wrong_count", "last_answered_at"}
    assert len(data["practice_days"]) == 1 and data["practice_days"][0]["answers"] == 2


# --- streak, without the database -------------------------------------------------------------------------------

TODAY = date(2026, 10, 29)


@pytest.mark.parametrize("days,expected", [
    ([], 0),
    ([TODAY], 1),
    ([TODAY, TODAY - timedelta(1), TODAY - timedelta(2)], 3),
    ([TODAY - timedelta(1), TODAY - timedelta(2)], 2),                    # not lost until a whole day is missed
    ([TODAY - timedelta(2)], 0),
    ([TODAY, TODAY - timedelta(2)], 1),                                   # a gap ends the run
    ([TODAY - timedelta(1), TODAY, TODAY], 2),                            # order and repeats do not matter
])
def test_streak(days, expected):
    assert progress.streak(days, TODAY) == expected
