"""Part of speech: labelled by hand or by the tutor, per-language categories, never overwritten, practised as cards."""
import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.services.ai_gate import AiGate
from conftest import DB_URL, HEADERS


class Llm:
    """A model that labels every entry 'noun' (or 'phrase' for several words), unless told what to say."""
    def __init__(self):
        self.answer, self.prompts = None, []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if self.answer is not None:
            return self.answer
        entries = prompt.split("Entries:\n", 1)[1].strip().splitlines()
        return "\n".join(f"{w} | {'phrase' if ' ' in w else 'noun'}" for w in entries)


@pytest.fixture
def llm(app):
    saved = app.state.story_llm, app.state.ai_gate
    fake = Llm()
    app.state.story_llm = fake
    app.state.ai_gate = AiGate(slots=2, wait_seconds=0.2, tokens_per_minute=8000)
    yield fake
    app.state.story_llm, app.state.ai_gate = saved


def word(c, w, language="en", **extra):
    r = c.post("/api/words", json={"language": language, "word": w, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def label(c, language="en", **extra):
    return c.post("/api/words/label", json={"language": language, **extra})


def pos_of(c, language="en"):
    return {w["word"]: w["pos"] for w in c.get("/api/words", params={"language": language, "limit": 200}).json()["items"]}


def test_needs_login(app):
    anon = TestClient(app, headers=HEADERS)
    assert anon.post("/api/words/label", json={"language": "en"}).status_code == 401
    assert anon.get("/api/words/parts-of-speech?language=en").status_code == 401
    assert anon.get("/api/practice/pos?language=en").status_code == 401


def test_each_language_has_its_own_list(make_user):
    c = make_user("alice")
    cats = lambda l: c.get(f"/api/words/parts-of-speech?language={l}").json()["items"]
    assert "determiner" in cats("en") and "adjective_i" in cats("ja") and "measure_word" in cats("zh") and "article" in cats("de")
    assert c.get("/api/words/parts-of-speech?language=xx").status_code in (400, 404, 422)


def test_a_word_can_be_added_with_a_label_and_it_is_checked_against_its_language(make_user):
    c = make_user("alice")
    assert word(c, "run", pos="verb")["pos"] == "verb" and word(c, "table")["pos"] is None
    bad = c.post("/api/words", json={"language": "en", "word": "red", "pos": "adjective_i"})
    assert bad.status_code == 422
    assert c.post("/api/words", json={"language": "ja", "word": "高い", "pos": "adjective_i"}).status_code == 201
    assert c.post("/api/words", json={"language": "ja", "word": "静か", "pos": "adjective"}).status_code == 422


def test_the_label_can_be_changed_and_cleared_by_hand(make_user):
    c = make_user("alice")
    w = word(c, "run")
    assert c.patch(f"/api/words/{w['id']}", json={"pos": "noun"}).json()["pos"] == "noun"
    assert c.patch(f"/api/words/{w['id']}", json={"meaning": "to move fast"}).json()["pos"] == "noun"      # editing the meaning keeps it
    assert c.patch(f"/api/words/{w['id']}", json={"pos": "nonsense"}).status_code == 422
    assert c.patch(f"/api/words/{w['id']}", json={"pos": None}).json()["pos"] is None


def test_the_tutor_labels_unlabelled_words_and_keeps_the_learners_labels(make_user, llm):
    c = make_user("alice")
    word(c, "run", pos="verb")
    word(c, "table")
    word(c, "thank you")
    body = label(c).json()
    assert body == {"defined": 2, "failed": 0, "remaining": 0}
    got = pos_of(c)
    assert got == {"run": "verb", "table": "noun", "thank you": "phrase"}                  # the stub says noun, or phrase for several words
    assert label(c).json() == {"defined": 0, "failed": 0, "remaining": 0}


def test_labelling_can_be_limited_to_chosen_words_or_a_set(make_user, llm):
    c = make_user("alice")
    a, b = word(c, "one"), word(c, "two")
    assert label(c, ids=[a["id"]]).json() == {"defined": 1, "failed": 0, "remaining": 0}      # remaining counts within the chosen words
    assert pos_of(c) == {"one": "noun", "two": None}
    s = c.post("/api/sets", json={"language": "en", "name": "x"}).json()["id"]
    c.post("/api/words/move", json={"ids": [b["id"]], "set_id": s})
    assert label(c, set="general").json() == {"defined": 0, "failed": 0, "remaining": 0}
    assert label(c, set=str(s)).json()["defined"] == 1


def test_labelling_never_touches_another_learners_words(make_user, llm):
    alice, bob = make_user("alice"), make_user("bob")
    w = word(bob, "secret")
    label(alice, ids=[w["id"]])
    assert pos_of(bob) == {"secret": None}


def test_a_model_answer_with_a_wrong_code_is_dropped(make_user, llm):
    c = make_user("alice")
    word(c, "run"); word(c, "red")
    llm.answer = "run | verb\nred | adjective_i"
    body = label(c).json()
    assert body["defined"] == 1 and body["failed"] == 1 and body["remaining"] == 1
    assert pos_of(c) == {"run": "verb", "red": None}


def test_export_includes_the_label(make_user):
    c = make_user("alice")
    word(c, "run", pos="verb")
    assert c.get("/api/me/export").json()["words"][0]["pos"] == "verb"


# --- practice -------------------------------------------------------------------------------------------------

def pos_cards(c, **q):
    return c.get("/api/practice/pos", params={"language": "en", "limit": 50, **q}).json()


def test_pos_practice_uses_only_labelled_words_and_this_languages_options(make_user):
    c = make_user("alice")
    word(c, "run", pos="verb"); word(c, "red", pos="adjective"); word(c, "plain")
    body = pos_cards(c)
    assert sorted((x["word"], x["answer"]) for x in body["items"]) == [("red", "adjective"), ("run", "verb")] and body["total"] == 2
    assert body["items"][0]["options"] == c.get("/api/words/parts-of-speech?language=en").json()["items"]
    assert set(body["items"][0]) == {"id", "word", "answer", "options", "meaning"}


def test_pos_practice_is_per_learner_and_limited(make_user):
    c = make_user("alice")
    for w in "abcdef":
        word(c, w * 3, pos="noun")
    word(make_user("bob"), "zzz", pos="noun")
    body = pos_cards(c, limit=4)
    assert len(body["items"]) == 4 and body["total"] == 6 and all(x["word"] != "zzz" for x in body["items"])
    assert pos_cards(make_user("carol"))["items"] == []


def test_pos_practice_due_mode_and_set_filter(make_user):
    c = make_user("alice")
    a, b = word(c, "run", pos="verb"), word(c, "red", pos="adjective")
    c.post("/api/practice/answers", json={"answers": [{"word_id": a["id"], "correct": True}]})
    assert [x["word"] for x in pos_cards(c, due="true")["items"]] == ["red"]
    s = c.post("/api/sets", json={"language": "en", "name": "x"}).json()["id"]
    c.post("/api/words/move", json={"ids": [b["id"]], "set_id": s})
    assert [x["word"] for x in pos_cards(c, set=s)["items"]] == ["red"]


def test_a_label_that_is_not_in_the_languages_list_is_not_offered(make_user):
    c = make_user("alice")
    w = word(c, "run", pos="verb")
    with psycopg2.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute("UPDATE tutor.words SET pos = 'adjective_i' WHERE id = %s", (w["id"],))
    assert pos_cards(c)["items"] == []


def test_the_prompt_uses_the_languages_own_categories(make_user, llm):
    c = make_user("alice")
    word(c, "高い", language="ja")
    label(c, language="ja")
    assert "adjective_na" in llm.prompts[0] and "determiner" not in llm.prompts[0] and "高い" in llm.prompts[0]
