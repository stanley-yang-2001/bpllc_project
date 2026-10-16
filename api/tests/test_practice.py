"""Practice (M7): flashcards and fill-in-the-blank from a saved story. Nothing is stored; everything is the learner's own."""
import re

import pytest
from fastapi.testclient import TestClient

from app.routes import practice as routes
from conftest import HEADERS

WORDS = {"hello": "greeting", "water": "a drink", "friend": "someone you like", "bread": "baked food", "house": "a home",
         "goodbye": "parting words"}
STORY = ("Ana: Hello, my friend.\nBen: Hello, I want water.\nAna: Here is some bread.\n"
         "Ben: Thank you, goodbye.")


def learner(make_user, name="alice", words=WORDS, language="en"):
    c = make_user(name)
    for w, m in words.items():
        assert c.post("/api/words", json={"language": language, "word": w, "meaning": m}).status_code == 201
    return c


def saved(c, body=STORY, language="en"):
    r = c.post("/api/stories", json={"language": language, "body": body, "story_type": "dialogue"})
    assert r.status_code == 201, r.text
    return r.json()["id"]


def cloze(c, story_id):
    return c.get(f"/api/practice/cloze?story_id={story_id}")


# --- access ---------------------------------------------------------------------------------------------------

def test_practice_needs_login(app):
    anon = TestClient(app, headers=HEADERS)
    assert anon.get("/api/practice/flashcards?language=en").status_code == 401
    assert anon.get("/api/practice/cloze?story_id=1").status_code == 401


# --- flashcards -----------------------------------------------------------------------------------------------

def test_flashcards_are_this_learners_words_with_meanings_in_this_language(make_user):
    alice = learner(make_user)
    alice.post("/api/words", json={"language": "es", "word": "hola", "meaning": "hello"})
    alice.post("/api/words", json={"language": "en", "word": "nomeaning"})
    learner(make_user, "bob", {"secret": "bobs word"})
    body = alice.get("/api/practice/flashcards?language=en&limit=50").json()
    assert sorted(c["word"] for c in body["items"]) == sorted(WORDS) and body["total"] == len(WORDS)
    assert {c["word"]: c["meaning"] for c in body["items"]} == WORDS
    assert set(body["items"][0]) == {"id", "word", "meaning"}


def test_flashcards_are_shuffled_and_limited(make_user):
    many = {f"word{chr(97 + i)}": f"meaning {i}" for i in range(20)}
    c = learner(make_user, words=many)
    orders = {tuple(x["word"] for x in c.get("/api/practice/flashcards?language=en&limit=50").json()["items"]) for _ in range(6)}
    assert len(orders) > 1                                              # not the stored order every time
    body = c.get("/api/practice/flashcards?language=en&limit=5").json()
    assert len(body["items"]) == 5 and body["total"] == 20


def test_flashcards_with_nothing_to_show_are_an_empty_set(make_user):
    assert make_user("alice").get("/api/practice/flashcards?language=en").json() == {"items": [], "total": 0}


@pytest.mark.parametrize("query", ["language=xx", "language=en&limit=0", "language=en&limit=51", ""])
def test_bad_flashcard_requests_are_validation_errors(make_user, query):
    r = make_user("alice").get(f"/api/practice/flashcards?{query}")
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"


# --- cloze ----------------------------------------------------------------------------------------------------

def test_a_blank_replaces_exactly_one_of_the_learners_words_in_the_story(make_user):
    c = learner(make_user)
    body = cloze(c, saved(c)).json()
    assert body["language"] == "en" and body["items"]
    for item in body["items"]:
        assert item["answer"].lower() in WORDS
        assert item["answer"] in STORY and item["answer"] not in (item["before"] + item["after"]).split()
        assert (item["before"] + item["answer"] + item["after"]) in STORY.replace("\n", " ") or \
            any((item["before"] + item["answer"] + item["after"]) in line for line in STORY.split("\n"))
        assert item["hint"] == WORDS[item["answer"].lower()]


def test_every_item_offers_the_answer_among_choices_from_the_learners_own_list(make_user):
    c = learner(make_user)
    for item in cloze(c, saved(c)).json()["items"]:
        assert item["answer"].lower() in [x.lower() for x in item["choices"]]
        assert len(set(item["choices"])) == len(item["choices"]) and 2 <= len(item["choices"]) <= 4
        assert all(x.lower() in WORDS for x in item["choices"])


def test_the_same_answer_is_not_asked_twice(make_user):
    c = learner(make_user)
    answers = [i["answer"].lower() for i in cloze(c, saved(c, "Ana: Hello my friend.\nBen: Hello my friend.\nAna: Hello some water.\nBen: Hello some bread.")).json()["items"]]
    assert len(answers) == len(set(answers))


def test_the_speaker_label_is_never_blanked(make_user):
    c = learner(make_user, words={"ana": "a name", "water": "a drink", "bread": "food", "hello": "hi", "friend": "pal"})
    for item in cloze(c, saved(c, "Ana: Hello, my friend.\nBen: Hello, I want water.\nAna: Here is some bread.")).json()["items"]:
        assert item["answer"].lower() != "ana"


def test_an_inflected_form_in_the_story_is_matched_to_the_base_word(make_user):
    c = learner(make_user, words={"friend": "pal", "water": "a drink", "bread": "food", "house": "home", "hello": "hi"})
    items = cloze(c, saved(c, "Ana: Look at my friends.\nBen: I want some waters.\nAna: Here is some bread.")).json()["items"]
    hits = {i["answer"]: i["hint"] for i in items}
    assert hits.get("friends") == "pal"


def test_at_most_eight_items(make_user):
    words = {f"word{chr(97 + i)}": f"m{i}" for i in range(12)}
    c = learner(make_user, words=words)
    story = "\n".join(f"Ana: I see {w} now." for w in words)
    assert len(cloze(c, saved(c, story)).json()["items"]) == routes.MAX_ITEMS == 8


def test_a_story_with_none_of_the_learners_words_has_nothing_to_practise(make_user):
    c = learner(make_user, words={"zebra": "an animal", "quantum": "tiny", "xylophone": "an instrument", "yacht": "a boat", "walrus": "an animal"})
    r = cloze(c, saved(c))
    assert r.status_code == 422 and r.json()["error"]["code"] == "no_blanks"


def test_another_learners_story_is_not_found(make_user):
    alice, bob = learner(make_user), learner(make_user, "bob")
    assert cloze(bob, saved(alice)).status_code == 404 and cloze(alice, 9999).status_code == 404


def test_a_language_without_a_word_tokeniser_says_so(make_user):
    c = make_user("alice")
    for w in ("こんにちは", "ありがとう", "水", "パン", "家"):
        c.post("/api/words", json={"language": "ja", "word": w, "meaning": "x"})
    sid = c.post("/api/stories", json={"language": "ja", "body": "アナ：こんにちは。水をください。\nベン：はい、どうぞ。", "story_type": "dialogue"}).json()["id"]
    r = cloze(c, sid)
    assert r.status_code == 422 and r.json()["error"]["code"] == "language_unavailable"
    assert "Japanese" in r.json()["error"]["message"]


def test_cloze_for_spanish_uses_exact_words_and_the_learners_spanish_list(make_user):
    c = learner(make_user, words={"hola": "hello", "agua": "water", "amigo": "friend", "casa": "house", "pan": "bread"}, language="es")
    c.post("/api/words", json={"language": "en", "word": "water", "meaning": "english only"})
    items = cloze(c, saved(c, "Ana: Hola, amigo.\nLuis: Hola, tengo agua.\nAna: Gracias por el pan.", "es")).json()["items"]
    assert {i["answer"].lower() for i in items} <= {"hola", "agua", "amigo", "pan"} and items
    assert all(x.lower() in {"hola", "agua", "amigo", "casa", "pan"} for i in items for x in i["choices"])


def test_nothing_is_stored_by_practising(make_user, conn):
    c = learner(make_user)
    sid = saved(c)
    cloze(c, sid)
    c.get("/api/practice/flashcards?language=en")
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM tutor.stories")
        assert cur.fetchone()[0] == 1
        cur.execute("SELECT count(*) FROM tutor.words")
        assert cur.fetchone()[0] == len(WORDS)


def test_practice_makes_no_ai_call_and_costs_no_tokens(make_user, app):
    c = learner(make_user)
    before = app.state.ai_gate.tokens_used
    cloze(c, saved(c))
    c.get("/api/practice/flashcards?language=en")
    assert app.state.ai_gate.tokens_used == before


def test_a_very_short_sentence_is_not_turned_into_a_blank(make_user):
    c = learner(make_user)
    items = cloze(c, saved(c, "Ana: Hello.\nBen: Water.\nAna: Here is some bread.")).json()["items"]
    assert [i["answer"] for i in items] == ["bread"]


def test_a_phrase_in_the_list_is_never_a_blank_or_a_wrong_choice(make_user):
    c = learner(make_user, words={**WORDS, "thank you": "gratitude"})
    for item in cloze(c, saved(c, "Ana: Thank you for the bread.\nBen: Here is some water.\nAna: I like my house.")).json()["items"]:
        assert " " not in item["answer"] and all(" " not in x for x in item["choices"])
