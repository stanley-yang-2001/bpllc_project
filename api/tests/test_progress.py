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


def review(c, *items):
    """Graded answers (word id, grade 1-4[, think_ms, rate_ms])."""
    body = [{"word_id": i[0], "grade": i[1], **({"think_ms": i[2]} if len(i) > 2 else {}), **({"rate_ms": i[3]} if len(i) > 3 else {})} for i in items]
    r = c.post("/api/practice/reviews", json={"reviews": body})
    assert r.status_code == 200, r.text
    return r.json()["results"]


def graduate(c, word_id):
    """Two Good answers: a new word leaves learning and rests one day."""
    answer(c, (word_id, True))
    make_due(word_id)
    answer(c, (word_id, True))


def state(word_id):
    return rows("SELECT phase, step, ease, interval_days, lapses, box, right_count, wrong_count, "
                "extract(epoch FROM due_at - now()) FROM tutor.word_progress WHERE word_id = %s", word_id)[0]


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


def test_a_right_answer_on_a_new_word_starts_its_learning_steps(make_user):
    c, ids = learner(make_user)
    answer(c, (ids["hello"], True))
    phase, step, ease, interval, lapses, box, right, wrong, secs = state(ids["hello"])
    assert (phase, step, box, right, wrong) == ("learning", 1, 1, 1, 0) and 590 < float(secs) <= 600       # a second step, 10 minutes
    p = prog(c)
    assert (p["new"], p["learning"], p["due"], p["practised_today"], p["streak"]) == (3, 1, 0, True, 1)


def test_the_second_right_answer_graduates_the_word_to_a_day(make_user):
    c, ids = learner(make_user)
    graduate(c, ids["hello"])
    phase, step, ease, interval, lapses, box, right, wrong, secs = state(ids["hello"])
    assert (phase, float(interval), box, right) == ("review", 1.0, 2, 2) and 0.99 < float(secs) / 86400 < 1.01


def test_a_wrong_answer_on_a_known_word_is_a_lapse_and_returns_in_minutes(make_user):
    c, ids = learner(make_user)
    graduate(c, ids["hello"])
    make_due(ids["hello"])
    answer(c, (ids["hello"], False))
    phase, step, ease, interval, lapses, box, right, wrong, secs = state(ids["hello"])
    assert (phase, lapses, box, right, wrong) == ("relearning", 1, 1, 2, 1) and round(float(ease), 2) == 2.3 and 590 < float(secs) <= 600


def test_intervals_grow_with_each_right_answer_and_known_is_a_week_or_more(make_user):
    c, ids = learner(make_user)
    answer(c, (ids["hello"], True))
    make_due(ids["hello"])
    answer(c, (ids["hello"], True))
    seen = [float(state(ids["hello"])[3])]
    for _ in range(5):
        make_due(ids["hello"])
        answer(c, (ids["hello"], True))
        seen.append(float(state(ids["hello"])[3]))
    assert seen == sorted(seen) and seen[0] == 1 and seen[-1] >= 21 and len(set(seen)) == len(seen)
    assert rows("SELECT box FROM tutor.word_progress")[0][0] == 5
    p = prog(c)
    assert (p["known"], p["learning"]) == (1, 0)


def test_an_early_right_answer_counts_but_does_not_move_the_schedule(make_user):
    c, ids = learner(make_user)
    graduate(c, ids["hello"])
    before = rows("SELECT box, due_at, interval_days, ease FROM tutor.word_progress")[0]
    review(c, (ids["hello"], 4))
    after = rows("SELECT box, due_at, right_count, interval_days, ease FROM tutor.word_progress")[0]
    assert after[0] == before[0] and after[1] == before[1] and after[3] == before[2] and after[4] == before[3] and after[2] == 3
    log = rows("SELECT was_due, counted FROM tutor.review_log ORDER BY id DESC LIMIT 1")[0]
    assert log == (False, False)


def test_the_same_word_twice_in_one_request_moves_through_the_steps_in_order(make_user):
    c, ids = learner(make_user)
    answer(c, (ids["hello"], True), (ids["hello"], True))
    assert rows("SELECT phase, right_count FROM tutor.word_progress")[0] == ("review", 2)


def test_due_flashcards_are_what_is_learning_or_due_first_then_new_words(make_user):
    c, ids = learner(make_user)
    graduate(c, ids["hello"])
    graduate(c, ids["water"])
    assert sorted(due_words(c)) == ["bread", "friend"]                       # practised words rest; new ones are offered
    make_due(ids["water"])
    make_due(ids["hello"])
    rows("UPDATE tutor.word_progress SET due_at = now() - interval '3 days' WHERE word_id = %s", ids["water"])
    got = due_words(c)
    assert got[:2] == ["water", "hello"] and sorted(got[2:]) == ["bread", "friend"]       # the most overdue first
    body = c.get("/api/practice/flashcards?language=en&limit=1&due=true").json()
    assert len(body["items"]) == 1 and body["total"] == 4


def test_a_word_in_a_short_learning_step_is_offered_again_in_the_same_session_first(make_user):
    c, ids = learner(make_user)
    graduate(c, ids["hello"])
    answer(c, (ids["water"], True))                                          # 10 minutes: within the 20 minute look-ahead
    assert due_words(c)[0] == "water" and sorted(due_words(c)[1:]) == ["bread", "friend"]


def test_due_flashcards_respect_the_set_filter(make_user):
    c, ids = learner(make_user)
    s = c.post("/api/sets", json={"language": "en", "name": "food"}).json()["id"]
    c.post("/api/words/move", json={"ids": [ids["bread"]], "set_id": s})
    assert due_words(c, set=s) == ["bread"]
    assert "bread" not in due_words(c, set="general")


def test_due_choices_ask_about_due_words_but_offer_the_whole_list(make_user):
    c, ids = learner(make_user)
    for w in ("hello", "water", "friend"):
        graduate(c, ids[w])
    body = c.get("/api/practice/choices?language=en&limit=10&due=true").json()
    assert [x["prompt"] for x in body["items"]] == ["bread"] and body["total"] == 1
    assert len(body["items"][0]["choices"]) == 4


def test_nothing_due_when_everything_rests(make_user):
    c, ids = learner(make_user)
    for w in WORDS:
        graduate(c, ids[w])
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
    graduate(c, ids["hello"])
    review(c, (ids["water"], 1, 4200, 900))
    data = c.get("/api/me/export").json()
    assert {(p["word"], p["box"], p["phase"], p["right_count"], p["wrong_count"]) for p in data["word_progress"]} == {("hello", 2, "review", 2, 0), ("water", 1, "learning", 0, 1)}
    assert set(data["word_progress"][0]) == {"language", "word", "box", "phase", "ease", "interval_days", "lapses", "last_grade", "due_at", "right_count",
                                             "wrong_count", "last_answered_at"}
    assert len(data["practice_days"]) == 1 and data["practice_days"][0]["answers"] == 3
    log = [l for l in data["review_log"] if l["word"] == "water"]
    assert len(log) == 1 and (log[0]["grade"], log[0]["think_ms"], log[0]["rate_ms"], log[0]["mode"]) == (1, 4200, 900, "flashcards")
    assert len(data["review_log"]) == 3


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


# --- dictation: any word, with or without a meaning -------------------------------------------------------------

def test_dictation_offers_words_with_and_without_meanings(make_user):
    c, ids = learner(make_user)
    c.post("/api/words", json={"language": "en", "word": "nomeaning"})
    body = c.get("/api/practice/dictation?language=en&limit=50").json()
    got = {x["word"]: x["meaning"] for x in body["items"]}
    assert got == {**WORDS, "nomeaning": None} and body["total"] == 5
    assert set(body["items"][0]) == {"id", "word", "meaning"}


def test_dictation_is_this_learners_words_in_this_language_and_limited(make_user):
    c, _ = learner(make_user)
    c.post("/api/words", json={"language": "es", "word": "hola"})
    learner(make_user, "bob", {"secret": "x"})
    body = c.get("/api/practice/dictation?language=en&limit=2").json()
    assert len(body["items"]) == 2 and body["total"] == 4
    assert all(x["word"] in WORDS for x in body["items"])


def test_dictation_due_mode_skips_words_that_are_resting(make_user):
    c, ids = learner(make_user)
    c.post("/api/words", json={"language": "en", "word": "nomeaning"})
    answer(c, (ids["hello"], True))
    got = [x["word"] for x in c.get("/api/practice/dictation?language=en&limit=50&due=true").json()["items"]]
    assert "hello" not in got and "nomeaning" in got and len(got) == 4


def test_dictation_respects_the_set_filter_and_needs_login(app, make_user):
    c, ids = learner(make_user)
    s = c.post("/api/sets", json={"language": "en", "name": "food"}).json()["id"]
    c.post("/api/words/move", json={"ids": [ids["bread"]], "set_id": s})
    assert [x["word"] for x in c.get(f"/api/practice/dictation?language=en&set={s}").json()["items"]] == ["bread"]
    assert c.get("/api/practice/dictation?language=en&set=oops").status_code == 422
    assert TestClient(app, headers=HEADERS).get("/api/practice/dictation?language=en").status_code == 401


# --- the study queue: no card limit, several sets, exact words, and what every answer would do -----------------------

def cards(c, **params):
    r = c.get("/api/practice/flashcards", params={"language": "en", **params})
    assert r.status_code == 200, r.text
    return r.json()


def test_flashcards_have_no_limit_unless_one_is_asked_for(make_user):
    many = {f"word{chr(97 + i // 26)}{chr(97 + i % 26)}": f"meaning {i}" for i in range(120)}
    c, _ = learner(make_user, words=many)
    body = cards(c)
    assert len(body["items"]) == 120 and body["total"] == 120 and body["selection"] == 120
    assert len(cards(c, limit=7)["items"]) == 7 and cards(c, limit=7)["total"] == 120


def test_several_sets_can_be_studied_together(make_user):
    c, ids = learner(make_user)
    food = c.post("/api/sets", json={"language": "en", "name": "food"}).json()["id"]
    talk = c.post("/api/sets", json={"language": "en", "name": "talk"}).json()["id"]
    c.post("/api/words/move", json={"ids": [ids["bread"], ids["water"]], "set_id": food})
    c.post("/api/words/move", json={"ids": [ids["hello"]], "set_id": talk})
    assert sorted(x["word"] for x in cards(c, set=f"{food},{talk}")["items"]) == ["bread", "hello", "water"]
    assert sorted(x["word"] for x in cards(c, set=f"{talk},general")["items"]) == ["friend", "hello"]
    assert cards(c, set=f"{food},{talk}")["selection"] == 3
    assert c.get("/api/practice/flashcards?language=en&set=1,x").status_code == 422
    assert prog(c, "en")["new"] == 4
    assert c.get(f"/api/practice/progress?language=en&set={food},{talk}").json()["new"] == 3


def test_a_card_says_what_each_answer_would_schedule(make_user):
    c, ids = learner(make_user)
    new = next(x for x in cards(c)["items"] if x["word"] == "hello")
    assert new["status"] == "new" and new["preview"] == {"again": 60, "hard": 90, "good": 600, "easy": 4 * 86400}
    graduate(c, ids["hello"])
    make_due(ids["hello"])
    got = next(x for x in cards(c, scope="due")["items"] if x["word"] == "hello")
    assert got["status"] == "young" and got["preview"]["again"] == 600 and got["preview"]["hard"] < got["preview"]["good"] < got["preview"]["easy"]
    # what it said is what happens (the same spread of the interval is used for the preview and the answer)
    res = review(c, (ids["hello"], 3))[0]
    assert res["delay_seconds"] == got["preview"]["good"] and res["counted"] is True
    assert set(res["preview"]) == {"again", "hard", "good", "easy"} and res["preview"]["again"] == 600


def test_exact_words_can_be_asked_for_and_must_be_this_learners(make_user):
    c, ids = learner(make_user)
    learner(make_user, "bob", {"secret": "bobs"})
    ask = f"{ids['hello']},{ids['bread']}"
    assert sorted(x["word"] for x in cards(c, scope="ids", ids=ask)["items"]) == ["bread", "hello"]
    assert c.get("/api/practice/flashcards?language=en&scope=ids").status_code == 422
    assert c.get("/api/practice/flashcards?language=en&scope=ids&ids=a,b").status_code == 422
    assert c.get("/api/practice/flashcards?language=en&scope=nope").status_code == 422
    assert cards(c, scope="ids", ids="999999")["items"] == []


def test_review_endpoint_records_grades_timings_and_returns_the_next_due(make_user):
    c, ids = learner(make_user)
    res = review(c, (ids["hello"], 3, 2500, 700), (ids["water"], 1, 9000, 1200), (ids["bread"], 4, 800, 300))
    assert [(r["word_id"], r["status"]) for r in res] == [(ids["hello"], "learning"), (ids["water"], "learning"), (ids["bread"], "young")]
    assert res[0]["delay_seconds"] == 600 and res[1]["delay_seconds"] == 60 and res[2]["delay_seconds"] == 4 * 86400
    log = rows("SELECT w.word, l.grade, l.think_ms, l.rate_ms, l.phase_before, l.was_due, l.counted, l.mode FROM tutor.review_log l JOIN tutor.words w ON w.id = l.word_id ORDER BY l.id")
    assert log == [("hello", 3, 2500, 700, "learning", True, True, "flashcards"), ("water", 1, 9000, 1200, "learning", True, True, "flashcards"),
                   ("bread", 4, 800, 300, "learning", True, True, "flashcards")]
    assert prog(c)["practised_today"] is True


def test_review_validation_and_ownership(make_user):
    c, ids = learner(make_user)
    bob, b_ids = learner(make_user, "bob", {"secret": "bobs"})
    for bad in ({"word_id": ids["hello"], "grade": 0}, {"word_id": ids["hello"], "grade": 5}, {"word_id": ids["hello"], "grade": 3, "think_ms": -1},
                {"word_id": ids["hello"], "grade": 3, "mode": "x" * 20}):
        assert c.post("/api/practice/reviews", json={"reviews": [bad]}).status_code == 422
    assert c.post("/api/practice/reviews", json={"reviews": [{"word_id": ids["hello"], "grade": 3, "mode": "karaoke"}]}).status_code == 422
    assert c.post("/api/practice/reviews", json={"reviews": [{"word_id": b_ids["secret"], "grade": 3}]}).status_code == 404
    assert rows("SELECT count(*) FROM tutor.review_log")[0][0] == 0
    assert c.post("/api/practice/reviews", json={"reviews": []}).json() == {"results": []}


def test_a_time_left_open_is_recorded_as_at_most_two_minutes(make_user):
    c, ids = learner(make_user)
    review(c, (ids["hello"], 3, 3_000_000, 90_000_000 // 100))
    assert rows("SELECT think_ms, rate_ms FROM tutor.review_log")[0] == (progress.MAX_MS, progress.MAX_MS)


def test_answers_from_other_modes_carry_timing_and_mode(make_user):
    c, ids = learner(make_user)
    r = c.post("/api/practice/answers", json={"answers": [{"word_id": ids["hello"], "correct": False, "think_ms": 4000, "mode": "choices", "direction": "meaning"}]})
    assert r.status_code == 204
    assert rows("SELECT grade, think_ms, mode, direction FROM tutor.review_log")[0] == (1, 4000, "choices", "meaning")


def test_stats_count_words_by_stage_retention_and_time(make_user):
    c, ids = learner(make_user)
    graduate(c, ids["hello"])
    make_due(ids["hello"])
    review(c, (ids["hello"], 3, 2000, 500))                      # a due review remembered
    make_due(ids["hello"])
    review(c, (ids["hello"], 1, 6000, 500))                      # a due review forgotten
    s = c.get("/api/practice/stats?language=en").json()
    assert (s["words"], s["new"], s["relearning"], s["leeches"]) == (4, 3, 1, 0)
    assert s["reviews_30d"] == 4 and s["today_reviews"] == 4
    assert s["retention_30d"] == 0.5 and s["accuracy_30d"] == 0.75
    assert s["avg_think_ms"] == 4000 and s["avg_rate_ms"] == 500 and s["median_think_ms"] == 4000
    assert len(s["forecast"]) == 7 and s["forecast"][0]["due"] >= 1 and len(s["days"]) == 1 and s["days"][0]["reviews"] == 4
    # the running total over everything ever answered (here the same four answers on one word, one day)
    assert (s["total_reviews"], s["total_words_practised"], s["total_days"], s["total_accuracy"], s["total_retention"], s["total_avg_think_ms"]) == (4, 1, 1, 0.75, 0.5, 4000)
    old = rows("UPDATE tutor.review_log SET reviewed_at = now() - interval '60 days' WHERE id = (SELECT min(id) FROM tutor.review_log)")
    s = c.get("/api/practice/stats?language=en").json()
    assert s["reviews_30d"] == 3 and s["total_reviews"] == 4 and s["total_days"] == 2


def test_stats_follow_the_chosen_sets_and_belong_to_the_learner(make_user):
    c, ids = learner(make_user)
    food = c.post("/api/sets", json={"language": "en", "name": "food"}).json()["id"]
    c.post("/api/words/move", json={"ids": [ids["bread"]], "set_id": food})
    review(c, (ids["bread"], 3, 1000, 100))
    review(c, (ids["hello"], 3, 1000, 100))
    assert c.get(f"/api/practice/stats?language=en&set={food}").json()["reviews_30d"] == 1
    assert c.get("/api/practice/stats?language=en&set=general").json()["words"] == 3
    bob, _ = learner(make_user, "bob", {"secret": "bobs"})
    assert bob.get("/api/practice/stats?language=en").json()["reviews_30d"] == 0


def test_hardest_words_are_the_missed_slow_ones_with_reasons(make_user):
    c, ids = learner(make_user)
    for _ in range(4):                                                        # water: missed again and again, slowly
        review(c, (ids["water"], 1, 9000, 800))
    for _ in range(4):                                                        # hello: right and quick
        review(c, (ids["hello"], 3, 1500, 300))
    review(c, (ids["bread"], 1, 1500, 300))                                   # bread: one try only: not enough to call it hard
    body = c.get("/api/practice/hardest?language=en").json()
    assert [w["word"] for w in body["items"]][:1] == ["water"] and "bread" not in [w["word"] for w in body["items"]]
    water = body["items"][0]
    assert water["miss_rate"] == 1.0 and "often_missed" in water["reasons"] and water["reviews"] == 4 and water["avg_think_ms"] == 9000
    assert body["typical_think_ms"] == 1500 and "slow" in water["reasons"]
    assert all(w["word"] != "hello" for w in body["items"])
    assert c.get("/api/practice/hardest?language=en&limit=0").status_code == 422


def test_old_progress_is_kept_when_the_spaced_repetition_columns_arrive(make_user):
    """Words already in a box when the migration ran keep resting: box 3 is a rest of 3 days, box 1 is still learning."""
    c, ids = learner(make_user)
    rows("INSERT INTO tutor.word_progress (word_id, user_id, box, due_at, right_count, wrong_count) VALUES (%s, (SELECT user_id FROM tutor.words WHERE id = %s), 3, now(), 4, 1)",
         ids["hello"], ids["hello"])
    rows("UPDATE tutor.word_progress SET phase = 'review', interval_days = 3 WHERE word_id = %s", ids["hello"])
    s = c.get("/api/practice/stats?language=en").json()
    assert s["young"] == 1 and s["due_now"] == 1
    res = review(c, (ids["hello"], 3))[0]
    assert res["status"] == "young" and res["delay_seconds"] >= 7 * 86400 and res["box"] >= 4
