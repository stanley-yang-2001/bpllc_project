"""POST /api/pronounce and /api/translate: shown to the learner only, one model call at most, strict about input and output."""
import pytest

from app.services.ai_gate import AiGate
from conftest import HEADERS


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
    app.state.ai_gate = AiGate(slots=2, wait_seconds=0.2, tokens_per_minute=8000)
    yield
    app.state.story_llm, app.state.ai_gate = saved


def post(c, path, **body):
    return c.post(f"/api{path}" if not path.startswith("/api") else path, json=body, headers=HEADERS)


def test_pronounce_english_asks_the_model_for_ipa_and_says_it_is_approximate(make_user, app):
    app.state.story_llm = fake = Llm("1 | /brɛd/\n2 | /ˈwɔtər/")
    c = make_user("alice")
    r = post(c, "/pronounce", language="en", texts=["bread", "water"])
    assert r.status_code == 200
    assert r.json() == {"kind": "ipa", "approximate": True, "items": [{"text": "bread", "reading": "/brɛd/"}, {"text": "water", "reading": "/ˈwɔtər/"}]}
    assert "International Phonetic Alphabet" in fake.prompts[0] and "1. bread\n2. water" in fake.prompts[0]


def test_pronounce_chinese_uses_the_library_and_makes_no_model_call(make_user, app):
    pytest.importorskip("pypinyin")
    app.state.story_llm = fake = Llm("should not be used")
    c = make_user("alice")
    r = post(c, "/pronounce", language="zh", texts=["你好"])
    assert r.json() == {"kind": "pinyin", "approximate": False, "items": [{"text": "你好", "reading": "nǐ hǎo"}]}
    assert fake.prompts == []


def test_pronounce_japanese_and_korean(make_user, app):
    pytest.importorskip("pykakasi"); pytest.importorskip("korean_romanizer")
    app.state.story_llm = Llm("unused")
    c = make_user("alice")
    assert post(c, "/pronounce", language="ja", texts=["パン"]).json()["items"][0]["reading"] == "pan"
    assert post(c, "/pronounce", language="ko", texts=["물"]).json()["kind"] == "romanization"


def test_a_line_the_model_skipped_has_no_reading_rather_than_a_guess(make_user, app):
    app.state.story_llm = Llm("2 | /b/")
    c = make_user("alice")
    items = post(c, "/pronounce", language="en", texts=["a", "b"]).json()["items"]
    assert [i["reading"] for i in items] == [None, "/b/"]


def test_pronounce_checks_its_input(make_user, app):
    app.state.story_llm = Llm("")
    c = make_user("alice")
    assert post(c, "/pronounce", language="xx", texts=["a"]).status_code in (400, 422)
    assert post(c, "/pronounce", language="en", texts=[]).status_code == 422
    assert post(c, "/pronounce", language="en", texts=["x"] * 61).status_code == 422
    assert post(c, "/pronounce", language="en", texts=["   "]).status_code == 422
    assert post(c, "/pronounce", language="en", texts=["x" * 401]).status_code == 422


def test_a_model_failure_is_a_clear_502_and_the_text_is_not_stored(make_user, app):
    app.state.story_llm = Llm(RuntimeError("down"))
    c = make_user("alice")
    r = post(c, "/pronounce", language="en", texts=["bread"])
    assert r.status_code == 502 and r.json()["error"]["code"] == "ai_failed"


def test_translate_sends_numbered_lines_and_returns_them_paired(make_user, app):
    app.state.story_llm = fake = Llm("1 | Ana: Hello!\n2 | Ben: Hi.")
    c = make_user("alice")
    r = post(c, "/translate", language="es", target_language="en", texts=["Ana: ¡Hola!", "Ben: Hola."])
    assert r.status_code == 200
    assert r.json() == {"target_language": "en", "items": [{"text": "Ana: ¡Hola!", "translation": "Ana: Hello!"}, {"text": "Ben: Hola.", "translation": "Ben: Hi."}]}
    assert "Spanish line" in fake.prompts[0] and "into English" in fake.prompts[0]


def test_translate_words_uses_the_short_meaning_prompt(make_user, app):
    app.state.story_llm = fake = Llm("1 | bread")
    c = make_user("alice")
    post(c, "/translate", language="es", target_language="en", texts=["pan"], words=True)
    assert "word or phrase" in fake.prompts[0]


def test_translate_needs_two_different_site_languages(make_user, app):
    app.state.story_llm = Llm("1 | x")
    c = make_user("alice")
    assert post(c, "/translate", language="es", target_language="es", texts=["pan"]).status_code in (400, 422)
    assert post(c, "/translate", language="es", target_language="xx", texts=["pan"]).status_code in (400, 422)
    assert post(c, "/translate", language="es", target_language="en", texts=["x" * 601]).status_code == 422


def test_both_need_a_signed_in_learner(client):
    assert client.post("/api/pronounce", json={"language": "en", "texts": ["a"]}, headers=HEADERS).status_code == 401
    assert client.post("/api/translate", json={"language": "en", "target_language": "es", "texts": ["a"]}, headers=HEADERS).status_code == 401


def test_the_same_token_budget_applies(make_user, app):
    app.state.ai_gate = AiGate(slots=2, wait_seconds=0.2, tokens_per_minute=3000)      # room for one 2500-token request a minute
    app.state.story_llm = Llm("1 | x")
    c = make_user("alice")
    assert post(c, "/translate", language="es", target_language="en", texts=["pan"]).status_code == 200
    r = post(c, "/translate", language="es", target_language="en", texts=["pan"])
    assert r.status_code == 429
