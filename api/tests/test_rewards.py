"""Streak, daily goal, week and badges from a learner's own records (the rules are tested in tutor_core/tests/test_rewards.py)."""
import psycopg2

from conftest import DB_URL, HEADERS


def add_words(client, n=4, language="es"):
    for i in range(n):
        r = client.post("/api/words", json={"language": language, "word": "palabra" + "abcdefgh"[i], "meaning": "a word"})
        assert r.status_code in (200, 201), r.text


def word_ids(client, language="es"):
    return [w["id"] for w in client.get("/api/words", params={"language": language, "limit": 50}).json()["items"]]


def answer(client, ids, grade=3, mode="flashcards"):
    r = client.post("/api/practice/reviews", json={"reviews": [{"word_id": i, "grade": grade, "mode": mode} for i in ids]})
    assert r.status_code == 200, r.text


def rewards(client, language="es"):
    r = client.get("/api/practice/rewards", params={"language": language})
    assert r.status_code == 200, r.text
    return r.json()


def sql(statement, params=()):
    with psycopg2.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute(statement, params)


def test_a_new_learner_has_a_goal_and_no_badges(client, make_user):
    c = make_user("rita")
    r = rewards(c)
    assert r["show_rewards"] is True and r["streak"]["days"] == 0 and r["goal"] == {"target": 10, "done": 0, "reached": False, "left": 10}
    assert not any(b["earned"] for b in r["badges"]) and r["next_badge"] is not None and r["known_words"] == 0


def test_answers_count_toward_the_goal_the_streak_and_the_first_badge(client, make_user):
    c = make_user("rita")
    add_words(c, 3)
    answer(c, word_ids(c)[:3])
    r = rewards(c)
    assert r["goal"]["done"] == 3 and r["streak"]["days"] == 1 and r["streak"]["practised_today"] and r["week"]["days_practised"] == 1
    assert {b["id"]: b["earned"] for b in r["badges"]}["first_answer"] is True and r["week"]["answers"] == 3


def test_the_daily_goal_is_a_setting_and_is_kept_in_range(client, make_user):
    c = make_user("rita")
    assert c.patch("/api/me/preferences", json={"daily_goal": 20}).json()["daily_goal"] == 20
    assert rewards(c)["goal"]["target"] == 20
    assert c.patch("/api/me/preferences", json={"daily_goal": 2}).status_code == 422
    assert c.patch("/api/me/preferences", json={"daily_goal": None}).status_code == 422
    r = c.patch("/api/me/preferences", json={"show_rewards": False}).json()
    assert r["show_rewards"] is False and rewards(c)["show_rewards"] is False


def test_a_word_becoming_known_counts_as_learned_this_week(client, make_user):
    c = make_user("rita")
    add_words(c, 2)
    ids = word_ids(c)
    sql("INSERT INTO tutor.word_progress (word_id, user_id, box, due_at, last_answered_at) SELECT id, user_id, 4, now() + interval '5 days', now() FROM tutor.words WHERE id = %s", (ids[0],))
    sql("UPDATE tutor.word_progress SET known_at = now() - interval '10 days'")
    assert rewards(c)["known_words"] == 1 and rewards(c)["week"]["words_learned"] == 0         # known, but not this week
    sql("UPDATE tutor.word_progress SET known_at = now()")
    assert rewards(c)["week"]["words_learned"] == 1


def test_known_at_is_set_when_a_word_reaches_known_and_cleared_when_it_falls_back(client, make_user):
    c = make_user("rita")
    add_words(c, 1)
    wid = word_ids(c)[0]
    sql("INSERT INTO tutor.word_progress (word_id, user_id, box, due_at, phase, interval_days, last_answered_at) SELECT id, user_id, 4, now() - interval '1 day', 'review', 7, now() - interval '9 days' FROM tutor.words WHERE id = %s", (wid,))
    answer(c, [wid], grade=3)
    with psycopg2.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT box, known_at IS NOT NULL FROM tutor.word_progress WHERE word_id = %s", (wid,))
        box, has = cur.fetchone()
    assert box >= 4 and has
    answer(c, [wid], grade=1)                                   # forgotten: back to learning
    with psycopg2.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute("SELECT box, known_at IS NULL FROM tutor.word_progress WHERE word_id = %s", (wid,))
        box, cleared = cur.fetchone()
    assert box < 4 and cleared


def test_a_saved_story_a_dictation_and_a_second_language_earn_badges(client, make_user):
    c = make_user("rita")
    add_words(c, 1, "es")
    add_words(c, 1, "fr")
    wid = word_ids(c, "es")[0]
    answer(c, [wid], mode="dictation")
    sql("INSERT INTO tutor.stories (user_id, language, story_type, topic, body, passed, report) SELECT id, 'es', 'story', 'x', 'Hola.', true, '{}'::jsonb FROM tutor.users LIMIT 1")
    got = {b["id"]: b["earned"] for b in rewards(c)["badges"]}
    assert got["first_dictation"] and got["first_story"] and got["second_language"] and not got["stories_5"]


def test_a_missed_day_is_forgiven_once_and_the_streak_shows_it(client, make_user):
    c = make_user("rita")
    add_words(c, 1)
    answer(c, word_ids(c)[:1])
    sql("INSERT INTO tutor.practice_days (user_id, day, answers) SELECT id, (now() AT TIME ZONE 'UTC')::date - 1, 5 FROM tutor.users")
    sql("INSERT INTO tutor.practice_days (user_id, day, answers) SELECT id, (now() AT TIME ZONE 'UTC')::date - 3, 5 FROM tutor.users")
    s = rewards(c)["streak"]
    assert s["days"] == 3 and s["rest_available"] is False and s["best"] == 3          # today, yesterday and 3 days ago; day 2 was the rest day


def test_rewards_are_private_and_need_a_known_language(client, make_user):
    assert client.get("/api/practice/rewards", params={"language": "es"}).status_code == 401
    c = make_user("rita")
    assert c.get("/api/practice/rewards", params={"language": "xx"}).status_code == 422
    other = make_user("bob")
    add_words(c, 2)
    answer(c, word_ids(c)[:2])
    assert rewards(other)["goal"]["done"] == 0                                    # bob sees none of rita's answers


def test_the_download_includes_the_new_fields(client, make_user):
    c = make_user("rita")
    c.patch("/api/me/preferences", json={"daily_goal": 15})
    add_words(c, 1)
    answer(c, word_ids(c)[:1])
    r = c.get("/api/me/export")
    assert r.status_code == 200
    data = r.json()
    assert data["user_preferences"]["daily_goal"] == 15 and data["user_preferences"]["show_rewards"] is True and "known_at" in data["word_progress"][0]


def test_records_start_empty_and_grow_with_practice(client, make_user):
    c = make_user("rita")
    r = rewards(c)["records"]
    assert r == {"best_day": None, "longest_run": 0, "fastest_ms": None, "best_week_learned": 0}
    add_words(c, 3)
    ids = word_ids(c)
    answer(c, ids[:2], grade=3)
    answer(c, ids[2:3], grade=1)
    answer(c, ids[:3], grade=4)
    r = rewards(c)["records"]
    assert r["best_day"]["value"] == 6 and r["longest_run"] == 3          # good, good, again, then easy x3: the longest run is the last three


def test_a_slow_day_does_not_count_as_fastest_without_ten_answers(client, make_user):
    c = make_user("rita")
    add_words(c, 4)
    ids = word_ids(c)
    c.post("/api/practice/reviews", json={"reviews": [{"word_id": i, "grade": 3, "mode": "flashcards", "think_ms": 1500} for i in ids]})
    assert rewards(c)["records"]["fastest_ms"] is None
    for _ in range(2):
        c.post("/api/practice/reviews", json={"reviews": [{"word_id": i, "grade": 3, "mode": "flashcards", "think_ms": 1500} for i in ids]})
    assert rewards(c)["records"]["fastest_ms"] == 1500


def test_words_that_appear_in_a_saved_story_are_counted(client, make_user):
    c = make_user("rita")
    add_words(c, 3)                      # palabraa, palabrab, palabrac
    sql("INSERT INTO tutor.stories (user_id, language, story_type, topic, body, passed, report) SELECT id, 'es', 'story', 'x', 'Hoy Palabraa y palabrac; no palabrabb.', true, '{}'::jsonb FROM tutor.users LIMIT 1")
    assert rewards(c)["story_words"] == {"used": 2, "total": 3}


def test_a_learner_back_after_a_break_is_told_and_then_marked_returned(client, make_user):
    c = make_user("rita")
    add_words(c, 1)
    assert rewards(c)["comeback"] is None
    sql("INSERT INTO tutor.practice_days (user_id, day, answers) SELECT id, (now() AT TIME ZONE 'UTC')::date - 5, 5 FROM tutor.users")
    assert rewards(c)["comeback"] == {"days_away": 5, "returned": False}
    answer(c, word_ids(c)[:1])
    assert rewards(c)["comeback"] == {"days_away": 5, "returned": True}
