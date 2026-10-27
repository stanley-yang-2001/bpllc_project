"""Practice (M7): flashcards and fill-in-the-blank from a saved story. Nothing is stored; everything is the learner's own."""
import re

import pytest
from fastapi.testclient import TestClient

from app.routes import practice as routes
from app.services import practice as routes_service
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


def test_unspaced_languages_blank_the_learners_own_words(make_user):
    cases = {
        "ja": ({"こんにちは": "hello", "ありがとう": "thanks", "水": "water", "パン": "bread", "家": "house"},
               "アナ：こんにちは。水をください。\nベン：はい、どうぞ。パンもありますよ。"),
        "zh": ({"你好": "hello", "谢谢": "thanks", "水": "water", "面包": "bread", "学校": "school", "学": "study"},
               "安娜：你好，我想要水。\n本：这里有面包。\n安娜：我们去学校吧。"),
        "ko": ({"집": "house", "물": "water", "빵": "bread", "친구": "friend", "학교": "school"},
               "안나: 친구는 집에 있어요.\n벤: 저는 물을 마셔요.\n안나: 학교에서 빵을 먹어요."),
    }
    c = make_user("alice")
    for lang, (words, story) in cases.items():
        for w, m in words.items():
            assert c.post("/api/words", json={"language": lang, "word": w, "meaning": m}).status_code == 201
        sid = c.post("/api/stories", json={"language": lang, "body": story, "story_type": "dialogue"}).json()["id"]
        r = cloze(c, sid)
        assert r.status_code == 200, (lang, r.text)
        items = r.json()["items"]
        assert items and len(items) >= 2, lang
        for item in items:
            assert item["answer"] in words and item["answer"] in item["choices"] and len(set(item["choices"])) == len(item["choices"])
            assert item["hint"] == words[item["answer"]]
            rebuilt = item["before"] + item["answer"] + item["after"]
            assert rebuilt in story, (lang, item)
        assert len({i["answer"] for i in items}) == len(items), "one blank per word"


def test_the_longest_list_word_wins_where_two_overlap():
    items = routes_service.make_cloze("安娜：我们去学校吧。", "zh", {"学": "study", "学校": "school", "我们": "we"})
    assert items and items[0]["answer"] == "我们"      # earliest
    items = routes_service.make_cloze("安娜：去学校吧，好吗。", "zh", {"学": "study", "学校": "school"})
    assert items[0]["answer"] == "学校" and items[0]["before"] == "安娜：去"


def test_a_korean_ending_stays_outside_the_blank():
    items = routes_service.make_cloze("나는 학교에서 공부해요.", "ko", {"학교": "school"})
    assert items[0]["before"] == "나는 " and items[0]["after"] == "에서 공부해요."


def test_a_story_in_an_unspaced_language_with_none_of_your_words_has_no_blanks(make_user):
    c = make_user("alice")
    c.post("/api/words", json={"language": "zh", "word": "苹果", "meaning": "apple"})
    sid = c.post("/api/stories", json={"language": "zh", "body": "安娜：你好，今天天气很好。", "story_type": "dialogue"}).json()["id"]
    r = cloze(c, sid)
    assert r.status_code == 422 and r.json()["error"]["code"] == "no_blanks"


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


def test_a_one_character_word_is_not_blanked_inside_a_longer_chinese_word():
    pytest.importorskip("rjieba")
    import random
    assert routes_service.make_cloze("我喜欢吃面包和水果。", "zh", {"面": "noodle"}, random.Random(1)) == []
    assert routes_service.make_cloze("我喜欢吃面包和水果。", "zh", {"面包": "bread"}, random.Random(1))[0]["answer"] == "面包"


# --- multiple choice ------------------------------------------------------------------------------------------

def test_choice_cards_show_a_word_with_four_meanings_one_of_them_right(make_user):
    c = learner(make_user)
    body = c.get("/api/practice/choices?language=en&limit=50").json()
    assert len(body["items"]) == len(WORDS) and body["total"] == len(WORDS)
    for item in body["items"]:
        assert set(item) == {"id", "prompt", "answer", "choices", "direction"} and item["direction"] == "meaning"
        assert WORDS[item["prompt"]] == item["answer"] and item["answer"] in item["choices"]
        assert len(item["choices"]) == 4 and len(set(item["choices"])) == 4 and set(item["choices"]) <= set(WORDS.values())


def test_choice_cards_can_ask_the_other_way_round(make_user):
    c = learner(make_user)
    for item in c.get("/api/practice/choices?language=en&direction=word").json()["items"]:
        assert item["prompt"] in WORDS.values() and WORDS[item["answer"]] == item["prompt"] and set(item["choices"]) <= set(WORDS)
    assert c.get("/api/practice/choices?language=en&direction=sideways").status_code == 422


def test_choice_cards_never_repeat_the_same_meaning_twice_and_need_two_words(make_user):
    c = learner(make_user, words={"alpha": "same", "beta": "same", "gamma": "other"})
    for item in c.get("/api/practice/choices?language=en").json()["items"]:
        assert len({x.casefold() for x in item["choices"]}) == len(item["choices"]) and item["answer"] in item["choices"]
    one = learner(make_user, "bob", {"solo": "alone"})
    assert one.get("/api/practice/choices?language=en").json() == {"items": [], "total": 1}


def test_choice_cards_use_only_this_learners_words_and_the_chosen_set(make_user):
    alice = learner(make_user)
    learner(make_user, "bob", {"secret": "bobs word", "other": "bobs other"})
    sid = alice.post("/api/sets", json={"language": "en", "name": "Food"}).json()["id"]
    alice.post("/api/words/move", json={"ids": [w["id"] for w in alice.get("/api/words?language=en").json()["items"] if w["word"] in ("water", "bread", "house")], "set_id": sid})
    everything = alice.get("/api/practice/choices?language=en&limit=50").json()
    assert "bobs word" not in str(everything)
    food = alice.get(f"/api/practice/choices?language=en&limit=50&set={sid}").json()
    assert sorted(i["prompt"] for i in food["items"]) == ["bread", "house", "water"]
    general = alice.get("/api/practice/flashcards?language=en&limit=50&set=general").json()
    assert sorted(i["word"] for i in general["items"]) == ["friend", "goodbye", "hello"]
