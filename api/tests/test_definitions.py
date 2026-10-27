"""POST /api/words/define: the model writes meanings for words that have none; it never replaces one the learner wrote."""
import pytest

from app.services.ai_gate import AiGate
from conftest import HEADERS


def learner(make_user, name="alice", words=("casa", "agua", "pan"), meanings=None):
    c = make_user(name)
    for w in words:
        body = {"language": "es", "word": w}
        if meanings and w in meanings:
            body["meaning"] = meanings[w]
        assert c.post("/api/words", json=body).status_code == 201
    return c


class Llm:
    def __init__(self, answer):
        self.answer, self.prompts = answer, []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


@pytest.fixture(autouse=True)
def fresh_gate(app):
    saved = app.state.story_llm, app.state.ai_gate
    app.state.ai_gate = AiGate(slots=2, wait_seconds=0.2, tokens_per_minute=8000)       # a new budget for every test
    yield
    app.state.story_llm, app.state.ai_gate = saved


@pytest.fixture
def llm(app):
    fake = Llm("casa | a house\nagua | water\npan | bread")
    app.state.story_llm = fake
    return fake


def meanings(c):
    return {w["word"]: w["meaning"] for w in c.get("/api/words?language=es&limit=200").json()["items"]}


def define(c, **kw):
    return c.post("/api/words/define", json={"language": "es", **kw}, headers=HEADERS)


def test_it_fills_every_word_without_a_meaning_and_says_none_remain(make_user, llm):
    c = learner(make_user)
    r = define(c)
    assert r.status_code == 200 and r.json() == {"defined": 3, "failed": 0, "remaining": 0}
    assert meanings(c) == {"casa": "a house", "agua": "water", "pan": "bread"}
    assert "Spanish word" in llm.prompts[0] and "in English" in llm.prompts[0]


def test_a_meaning_the_learner_wrote_is_never_replaced_and_is_not_asked_about(make_user, llm):
    c = learner(make_user, meanings={"casa": "my own note"})
    assert define(c).json()["defined"] == 2
    assert meanings(c)["casa"] == "my own note" and "casa" not in llm.prompts[0].split("Entries:")[1]


def test_it_answers_in_the_chosen_language_and_only_for_the_chosen_words(make_user, llm):
    c = learner(make_user)
    ids = {w["word"]: w["id"] for w in c.get("/api/words?language=es").json()["items"]}
    r = define(c, ids=[ids["pan"]], meaning_language="fr")
    assert r.json() == {"defined": 1, "failed": 0, "remaining": 0} and "in French" in llm.prompts[0]
    assert meanings(c)["pan"] == "bread" and meanings(c)["casa"] is None
    assert define(c, meaning_language="xx").status_code == 422


def test_words_the_model_skipped_are_counted_and_stay_empty(make_user, app):
    app.state.story_llm = Llm("casa | a house\nrubbish")
    c = learner(make_user)
    assert define(c).json() == {"defined": 1, "failed": 2, "remaining": 2}


def test_a_failing_model_gives_a_clear_error_and_changes_nothing(make_user, app):
    app.state.story_llm = Llm(RuntimeError("boom"))
    c = learner(make_user)
    r = define(c)
    assert r.status_code == 502 and r.json()["error"]["code"] == "ai_failed" and set(meanings(c).values()) == {None}


def test_a_batch_is_at_most_25_words_and_the_page_asks_again(make_user, llm):
    words = [f"palabra{chr(97 + i // 5)}{chr(97 + i % 5)}" for i in range(30)]
    c = learner(make_user, words=[w.replace("palabra", "p") for w in words])
    llm.answer = "\n".join(f"{w.replace('palabra', 'p')} | m" for w in words)
    first = define(c).json()
    assert first["defined"] == 25 and first["remaining"] == 5
    second = define(c)
    assert second.json() == {"defined": 5, "failed": 0, "remaining": 0}


def test_nothing_to_do_makes_no_model_call(make_user, llm):
    c = learner(make_user, meanings={"casa": "a", "agua": "b", "pan": "c"})
    assert define(c).json() == {"defined": 0, "failed": 0, "remaining": 0} and llm.prompts == []


def test_another_learners_words_are_never_touched_or_sent(make_user, llm):
    alice, bob = learner(make_user), learner(make_user, "bob", words=("secreto",))
    ids = [w["id"] for w in bob.get("/api/words?language=es").json()["items"]]
    r = define(alice, ids=ids)
    assert r.json()["defined"] == 0 and llm.prompts == [] and meanings(bob) == {"secreto": None}


def test_it_needs_login(app):
    from fastapi.testclient import TestClient
    assert TestClient(app, headers=HEADERS).post("/api/words/define", json={"language": "es"}).status_code == 401
