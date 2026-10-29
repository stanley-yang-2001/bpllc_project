"""The story use case called without HTTP: the rules live in services/story_generation.py, the route only checks the request."""
import pytest

from app.errors import AppError
from app.schemas import GenerateIn, SaveIn
from app.services import story_generation
from conftest import HEADERS  # noqa: F401  (keeps the conftest fixtures importable in this module)

WORDS = ["hello", "goodbye", "please", "water", "friend"]
BODY = "Ana: Hello, friend.\nBen: Hello, water please.\nAna: Thank you.\nBen: Goodbye, friend."


class NoOwnModel:
    def find(self, user_id, conn=None):
        return None


class MyOwnModel:
    def find(self, user_id, conn=None):
        return {"model": "my-model"}


class NeverCalled:
    def choose(self, user_id):
        raise AssertionError("the AI must not be reached")


def user_with_words(app, make_user, words):
    c = make_user("alice")
    for w in words:
        c.post("/api/words", json={"language": "en", "word": w})
    return c.get("/api/me").json()["id"]


def test_too_few_words_is_refused_before_any_ai_call(app, make_user):
    uid = user_with_words(app, make_user, WORDS[:3])
    with pytest.raises(AppError) as e:
        story_generation.generate(app.state.pool, uid, GenerateIn(language="en"), NeverCalled())
    assert e.value.code == "not_enough_words" and e.value.status == 422 and "at least 5 English words" in e.value.message


def test_the_message_says_when_the_chosen_sets_are_too_small(app, make_user):
    uid = user_with_words(app, make_user, WORDS[:3])
    with pytest.raises(AppError) as e:
        story_generation.generate(app.state.pool, uid, GenerateIn(language="en", set_ids=[0]), NeverCalled())
    assert e.value.code == "not_enough_words" and "in the sets you chose" in e.value.message


def test_a_negative_set_id_is_refused(app, make_user):
    uid = user_with_words(app, make_user, WORDS)
    with pytest.raises(AppError) as e:
        story_generation.generate(app.state.pool, uid, GenerateIn(language="en", set_ids=[-1]), NeverCalled())
    assert e.value.code == "validation_error"


def test_save_makes_the_report_itself_and_ignores_an_unknown_model_name(app, make_user):
    uid = user_with_words(app, make_user, WORDS)
    saved = story_generation.save(app.state.pool, uid, SaveIn(language="en", body=BODY, story_type="dialogue", model="someone-elses"), NoOwnModel())
    assert saved["passed"] is True and "model" not in saved["report"]


def test_save_remembers_the_learners_own_model_name_only_when_it_matches(app, make_user):
    uid = user_with_words(app, make_user, WORDS)
    saved = story_generation.save(app.state.pool, uid, SaveIn(language="en", body=BODY, story_type="dialogue", model="my-model"), MyOwnModel())
    assert saved["report"]["model"] == {"custom": True, "name": "my-model"}
    other = story_generation.save(app.state.pool, uid, SaveIn(language="en", body=BODY, story_type="dialogue", model="not-mine"), MyOwnModel())
    assert "model" not in other["report"]


def test_save_stops_at_the_library_limit(app, make_user, monkeypatch):
    uid = user_with_words(app, make_user, WORDS)
    monkeypatch.setattr(story_generation, "MAX_STORIES", 1)
    story_generation.save(app.state.pool, uid, SaveIn(language="en", body=BODY, story_type="dialogue"), NoOwnModel())
    with pytest.raises(AppError) as e:
        story_generation.save(app.state.pool, uid, SaveIn(language="en", body=BODY, story_type="dialogue"), NoOwnModel())
    assert e.value.code == "library_full"


def test_a_topic_is_dropped_for_the_classic_types(app, make_user):
    uid = user_with_words(app, make_user, WORDS)
    saved = story_generation.save(app.state.pool, uid, SaveIn(language="en", body=BODY, story_type="dialogue", topic="travel"), NoOwnModel())
    assert saved["topic"] is None
