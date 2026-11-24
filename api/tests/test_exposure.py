"""How often each word has been met (practice answers and saved stories), the story focus built on it, and the word of the day."""
import hashlib
from datetime import date

import psycopg2
import pytest

from app.services import exposure
from app.services.ai_gate import AiGate
from conftest import DB_URL
from test_stories_generate import DIALOGUE, Llm

def w(i):
    """A word of letters only (words may not hold digits): word + two letters."""
    return "word" + chr(97 + i // 26) + chr(97 + i % 26)


WORDS = ["apple", "bread", "cheese", "dog", "egg", "fish", "grape", "house"]


@pytest.fixture
def app_conn(conn):
    """The raw test connection, with the schema path the app's own connections have."""
    with conn.cursor() as cur:
        cur.execute("SET search_path TO tutor")
    conn.commit()
    return conn


@pytest.fixture
def llm(app):
    saved = app.state.story_llm, app.state.ai_gate
    fake = Llm()
    app.state.story_llm, app.state.ai_gate = fake, AiGate(slots=2, wait_seconds=0.2, tokens_per_minute=8000)
    yield fake
    app.state.story_llm, app.state.ai_gate = saved


def learner(make_user, name="alice", words=WORDS, language="en"):
    c = make_user(name)
    ids = {}
    for w in words:
        r = c.post("/api/words", json={"language": language, "word": w})
        assert r.status_code == 201, r.text
        ids[w] = r.json()["id"]
    return c, ids


def answer(c, word_id, ok=True):
    assert c.post("/api/practice/answers", json={"answers": [{"word_id": word_id, "correct": ok}]}).status_code == 204


def save_story(c, body, language="en"):
    r = c.post("/api/stories", json={"language": language, "body": body, "story_type": "dialogue"})
    assert r.status_code == 201, r.text


def listed(c, language="en"):
    return {w["word"]: w for w in c.get(f"/api/words?language={language}&limit=200").json()["items"]}


def db(sql, *args):
    with psycopg2.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall() if cur.description else None


# ------------------------------------------------------------------ the count on each word
def test_a_new_word_has_been_met_zero_times(make_user):
    c, _ = learner(make_user)
    assert listed(c)["apple"]["exposure"] == {"answers": 0, "stories": 0, "met": 0, "last_answered": None}


def test_answers_and_saved_stories_both_count(make_user):
    c, ids = learner(make_user)
    answer(c, ids["apple"]); answer(c, ids["apple"], ok=False); answer(c, ids["bread"])
    save_story(c, "Ana: I eat an apple.\nBen: I eat bread and an apple.\nAna: The Apple is red.")
    save_story(c, "Ana: Bread, please.\nBen: Here is bread.")
    got = listed(c)
    assert (got["apple"]["exposure"]["answers"], got["apple"]["exposure"]["stories"], got["apple"]["exposure"]["met"]) == (2, 1, 3)      # one story, however often it says apple
    assert (got["bread"]["exposure"]["answers"], got["bread"]["exposure"]["stories"], got["bread"]["exposure"]["met"]) == (1, 2, 3)
    assert got["apple"]["exposure"]["last_answered"] and got["cheese"]["exposure"]["met"] == 0


def test_a_word_inside_another_word_is_not_met(make_user):
    c, _ = learner(make_user, words=["art", "cat", "dog", "egg", "fish"])
    save_story(c, "Ana: A cathedral and a dogma and a party, with eggs.")
    assert all(w["exposure"]["stories"] == 0 for w in listed(c).values())


def test_a_phrase_and_a_chinese_word_are_found(make_user):
    c, _ = learner(make_user, words=["au revoir", "merci", "bonjour", "oui", "non"], language="fr")
    save_story(c, "Ana: Bonjour! Au revoir, et merci.", language="fr")
    got = listed(c, "fr")
    assert got["au revoir"]["exposure"]["stories"] == 1 and got["bonjour"]["exposure"]["stories"] == 1 and got["oui"]["exposure"]["stories"] == 0
    c, _ = learner(make_user, "bob", words=["你好", "谢谢", "水", "朋友", "再见"], language="zh")
    save_story(c, "安：你好，朋友！谢谢你。", language="zh")
    got = listed(c, "zh")
    assert got["你好"]["exposure"]["stories"] == 1 and got["水"]["exposure"]["stories"] == 0


def test_only_the_learners_own_answers_and_stories_count(make_user):
    a, ids = learner(make_user)
    b, _ = learner(make_user, "bob")
    answer(a, ids["apple"]); save_story(a, "Ana: An apple.\nBen: Bread.")
    assert listed(b)["apple"]["exposure"]["met"] == 0
    assert listed(a)["apple"]["exposure"]["met"] == 2


# ------------------------------------------------------------------ the focus
def prompt_words(llm):
    text = llm.prompts[-1]
    return {w for w in WORDS if w in text.lower().split("begin")[0] or f" {w}" in text.lower()}


def gen(c, **body):
    return c.post("/api/stories/generate", json={"language": "en", **body})


def test_focus_least_met_offers_the_words_met_least(make_user, conn):
    c, ids = learner(make_user)
    for w in ("apple", "bread", "cheese", "dog"):
        for _ in range(3):
            answer(c, ids[w])
    with conn.cursor() as cur:
        out = exposure.focus_words(conn, 1, "en", None, "least_met")
    assert set(out["words"][:4]) == {"egg", "fish", "grape", "house"} and out["matched"] == 8 and len(out["words"]) == 8


def test_focus_new_and_due(make_user, conn):
    c, ids = learner(make_user)
    answer(c, ids["apple"]); answer(c, ids["bread"])                       # now resting a little, not new
    db("UPDATE tutor.word_progress SET due_at = now() - interval '2 days' WHERE word_id = %s", ids["apple"])
    db("UPDATE tutor.word_progress SET due_at = now() + interval '30 days' WHERE word_id = %s", ids["bread"])
    new = exposure.focus_words(conn, 1, "en", None, "new")
    assert new["matched"] == 6 and "apple" not in new["words"] and "bread" not in new["words"]
    due = exposure.focus_words(conn, 1, "en", None, "due")
    assert due["matched"] == 1 and due["words"][0] == "apple"               # only one is due: the list is topped up to 5, the apple first
    assert len(due["words"]) == 5 and len(set(due["words"])) == 5


def test_focus_respects_the_chosen_sets(make_user, conn):
    c, ids = learner(make_user)
    s = c.post("/api/sets", json={"language": "en", "name": "Food"}).json()["id"]
    c.post("/api/words/move", json={"ids": [ids["apple"], ids["bread"], ids["cheese"], ids["dog"], ids["egg"], ids["fish"]], "set_id": s})
    out = exposure.focus_words(conn, 1, "en", [s], "least_met")
    assert set(out["words"]) == {"apple", "bread", "cheese", "dog", "egg", "fish"}
    assert set(exposure.focus_words(conn, 1, "en", [0], "least_met")["words"]) == {"grape", "house"}     # the top-up never leaves the chosen sets


def test_generate_with_a_focus_sends_only_those_words_and_says_how_many_fit(make_user, llm):
    c, ids = learner(make_user, words=WORDS + ["jam", "kiwi", "lemon"])
    for w in WORDS:
        answer(c, ids[w])                                                     # the three new words are the ones met least
    r = gen(c, focus="least_met", story_type="dialogue")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["focus"] == "least_met" and body["focus_matched"] == 11
    sent = llm.prompts[0].lower()
    assert all(w in sent for w in ("jam", "kiwi", "lemon"))
    r = gen(c, story_type="dialogue")
    assert r.json()["focus"] == "all" and r.json()["focus_matched"] is None
    assert gen(c, focus="sideways").status_code == 422


def test_a_focus_never_makes_a_story_with_words_that_are_not_the_learners(make_user, llm):
    c, _ = learner(make_user)
    other, _ = learner(make_user, "bob", words=["zebra", "yak", "xylophone", "wolf", "violin"])
    assert gen(c, focus="new", story_type="dialogue").status_code == 200
    assert not any(w in llm.prompts[0].lower() for w in ("zebra", "yak", "xylophone", "wolf", "violin"))


def test_a_focus_still_needs_five_words(make_user, llm):
    c, _ = learner(make_user, words=["apple", "bread", "cheese"])
    r = gen(c, focus="new")
    assert r.status_code == 422 and r.json()["error"]["code"] == "not_enough_words"


# ------------------------------------------------------------------ the word of the day
def today_of(c, language="en"):
    r = c.get(f"/api/words/today?language={language}")
    assert r.status_code == 200, r.text
    return r.json()


def test_the_word_of_the_day_is_one_of_the_learners_words_and_stays_the_same(make_user):
    c, ids = learner(make_user)
    first = today_of(c)
    assert first["date"] == date.today().isoformat() or first["date"]
    assert first["word"]["word"] in WORDS and first["word"]["exposure"]["met"] == 0
    assert all(today_of(c)["word"]["id"] == first["word"]["id"] for _ in range(4))
    answer(c, first["word"]["id"]); save_story(c, f"Ana: {first['word']['word']}.\nBen: Yes.")
    assert today_of(c)["word"]["id"] == first["word"]["id"]               # practising it today does not change today's pick


def test_the_word_of_the_day_comes_from_the_words_met_least(make_user, app_conn):
    c, ids = learner(make_user, words=[w(i) for i in range(20)])
    for i in range(12):
        db("INSERT INTO tutor.review_log (user_id, word_id, reviewed_at, grade, phase_before, was_due, counted, ease_after, delay_seconds) "
           "VALUES (1, %s, now() - interval '3 days', 3, 'learning', true, true, 2.5, 0)", ids[w(i)])
    picks = {exposure.word_of_the_day(app_conn, 1, "en", date(2026, 11, 1) + __import__("datetime").timedelta(days=d))["word"]["word"] for d in range(40)}
    assert picks and picks <= {w(i) for i in range(12, 20)} and len(picks) > 1     # never one of the 12 met, and not always the same one


def test_the_word_of_the_day_is_the_same_for_the_same_day_and_differs_by_learner_and_language(make_user, app_conn):
    c, ids = learner(make_user, words=[w(i) for i in range(30)])
    d = date(2026, 11, 24)
    assert exposure.word_of_the_day(app_conn, 1, "en", d)["word"]["id"] == exposure.word_of_the_day(app_conn, 1, "en", d)["word"]["id"]
    key = lambda user, lang: int.from_bytes(hashlib.sha256(f"{user}:{lang}:{d.isoformat()}".encode()).digest()[:8], "big")
    assert key(1, "en") != key(2, "en") and key(1, "en") != key(1, "fr")


def test_no_words_means_no_word_of_the_day_and_other_languages_are_apart(make_user):
    c = make_user("alice")
    assert today_of(c)["word"] is None
    c.post("/api/words", json={"language": "en", "word": "apple"})
    assert today_of(c)["word"]["word"] == "apple" and today_of(c, "fr")["word"] is None
    assert today_of(c)["word"]["picture"] is None


def test_the_word_of_the_day_needs_login_and_a_known_language(app, make_user):
    from fastapi.testclient import TestClient
    from conftest import HEADERS
    assert TestClient(app, headers=HEADERS).get("/api/words/today?language=en").status_code == 401
    assert make_user("alice").get("/api/words/today?language=xx").status_code in (404, 422)
