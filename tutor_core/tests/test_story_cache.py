"""The story cache and the retry policy, without a database or a model."""
from tutor_core import difficulty
from tutor_core.story import StoryRequest, StoryResult
from tutor_core.story_cache import FAILURE_TTL_SECONDS, SUCCESS_TTL_SECONDS, StoryCache
from tutor_core.story_retries import RetryPolicy


def result(ok=True):
    return StoryResult("t", ok, None if ok else "failed", "en")


def test_a_success_and_a_failure_are_kept_for_different_times():
    c = StoryCache()
    c.remember("a", 100.0, result(True))
    c.remember("b", 100.0, result(False))
    assert c.fresh("a", 100.0 + SUCCESS_TTL_SECONDS - 1) and c.fresh("b", 100.0 + FAILURE_TTL_SECONDS - 1)
    assert c.fresh("a", 100.0 + SUCCESS_TTL_SECONDS + 1) is None and c.fresh("b", 100.0 + FAILURE_TTL_SECONDS + 1) is None
    assert c.fresh("never", 100.0) is None


def test_the_cache_key_names_the_learner_language_kind_topic_and_what_else_changes_the_story():
    base = StoryRequest(1, "es")
    assert base.cache_key() == (1, "es", "", "")
    assert StoryRequest(2, "es").cache_key() != base.cache_key() and StoryRequest(1, "fr").cache_key() != base.cache_key()
    assert StoryRequest(1, "es", "diary", "rain").cache_key() == (1, "es", "diary", "rain")
    assert StoryRequest(1, "es", difficulty={"tier": "easy", "length": 40}).cache_key() != base.cache_key()
    assert StoryRequest(1, "es", set_ids=[0, 2]).cache_key() != StoryRequest(1, "es", set_ids=[]).cache_key() != base.cache_key()


def test_the_unspaced_languages_are_a_public_fact():
    assert difficulty.is_unspaced("zh") and difficulty.is_unspaced("ja") and not difficulty.is_unspaced("ko") and not difficulty.is_unspaced("en")
    assert difficulty.UNSPACED == ("zh", "ja")


def test_a_story_in_the_wrong_language_gets_one_more_try_and_the_right_one_is_kept():
    answers = iter(["plan\n===STORY===\nMaría tiene una casa grande y bonita.", "unused"])
    calls = []

    def call(prompt):
        calls.append(prompt)
        return next(answers)

    policy = RetryPolicy("es", "PROMPT", ["casa"], None, call)
    english = "The girl has a big house and she likes the garden because it is very nice."
    out = policy.improve(english)
    assert len(calls) == 1 and out.startswith("María")


def test_a_fine_story_is_returned_without_another_call():
    calls = []
    policy = RetryPolicy("es", "PROMPT", ["casa"], None, lambda p: calls.append(p) or "x")
    assert policy.improve("María tiene una casa grande.") == "María tiene una casa grande." and calls == []
