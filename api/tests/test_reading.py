"""The reader (0099): where the learner's own words stand in a story, with their meanings. Nothing is stored and no model is called."""
from conftest import HEADERS
from fastapi.testclient import TestClient

from app.services import reading


def add(c, word, meaning=None, language="en"):
    body = {"language": language, "word": word}
    if meaning:
        body["meaning"] = meaning
    r = c.post("/api/words", json=body)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def gloss(c, text, language="en"):
    return c.post("/api/reading/gloss", json={"language": language, "text": text})


def test_needs_a_signed_in_learner(app):
    r = TestClient(app, headers=HEADERS).post("/api/reading/gloss", json={"language": "en", "text": "A dog."})
    assert r.status_code == 401


def test_unknown_language_is_refused(make_user):
    c = make_user()
    assert gloss(c, "A dog.", "xx").status_code == 422


def test_the_text_has_a_limit(make_user):
    c = make_user()
    assert gloss(c, "a" * 8001).status_code == 422
    assert gloss(c, "a" * 8000).status_code == 200


def test_spans_slice_the_text_and_words_come_with_their_meanings(make_user):
    c = make_user()
    dog = add(c, "dog", "a pet")
    run = add(c, "run")                                  # a word with no meaning yet
    add(c, "cat", "another pet")                         # not in the text: not in the answer
    text = "The dogs were running.\nBen: A dog!"
    body = gloss(c, text).json()
    assert [(text[s["start"]:s["end"]], s["word_id"]) for s in body["spans"]] == [("dogs", dog), ("running", run), ("dog", dog)]
    assert body["words"] == [{"id": dog, "word": "dog", "meaning": "a pet", "pos": None, "picture": None},
                             {"id": run, "word": "run", "meaning": None, "pos": None, "picture": None}]


def test_no_words_no_spans(make_user):
    c = make_user()
    assert gloss(c, "A dog ran.").json() == {"spans": [], "words": []}
    add(c, "cat", "a pet")
    assert gloss(c, "").json() == {"spans": [], "words": []}


def test_only_the_learners_own_words_of_that_language(make_user):
    alice, bob = make_user("alice"), make_user("bob")
    add(alice, "dog", "a pet")
    add(bob, "ran", "moved fast")
    spanish = add(alice, "perro", "dog", language="es")
    text = "The dog ran. El perro corre."
    assert [w["word"] for w in gloss(alice, text, "en").json()["words"]] == ["dog"]          # not Bob's "ran", not the Spanish word
    assert [w["word"] for w in gloss(bob, text, "en").json()["words"]] == ["ran"]
    assert [(w["id"], w["word"]) for w in gloss(alice, text, "es").json()["words"]] == [(spanish, "perro")]


def test_positions_count_the_way_javascript_does_after_an_emoji(make_user):
    c = make_user()
    add(c, "dog", "a pet")
    text = "😀 The dog ran."                             # the emoji is one character in Python and two units in a JavaScript string
    span = gloss(c, text).json()["spans"][0]
    assert (span["start"], span["end"]) == (7, 10)
    assert text.encode("utf-16-le")[span["start"] * 2:span["end"] * 2].decode("utf-16-le") == "dog"


def test_utf16_positions_helper():
    assert reading.utf16_positions("plain text") is None
    assert reading.utf16_positions("a😀b") == [0, 1, 3, 4]
