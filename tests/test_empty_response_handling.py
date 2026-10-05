"""
Tests for the "Groq returned nothing usable" bug found during Step 9.

Symptom: the Story Generator Tool's output was an EMPTY string, so the Agent filled the gap
by inventing its own answer (a made-up story, or a made-up "Invalid language specified"
error). Root cause: openai/gpt-oss-20b is a reasoning model, and with max_tokens=400 nearly
all of the budget was spent on hidden reasoning (398 reasoning tokens), so Groq returned
finish_reason="length" with content="". An empty passage was then cached as a *success*.

Written BEFORE the fix. Run now and expect failures; re-run after the fix to confirm green.

These tests do not need Postgres: a tiny fake connection stands in for it. The real Groq
call is not made either; call_groq's request payload is checked by intercepting urlopen.

Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_empty_response_handling.py
"""

import json
import sys
from unittest.mock import MagicMock, patch

sys.path.insert(0, "/app/custom_components")

import story_tool  # noqa: E402
from story_tool import FAILURE_FALLBACK_MESSAGE, generate_story_for_learner  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"
failures = []


def check(label, condition):
    if condition:
        print(f"[{PASS}] {label}")
    else:
        print(f"[{FAIL}] {label}")
        failures.append(label)


class FakeCursor:
    def __init__(self, words):
        self._words = words
        self._last = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        self._last = sql

    def fetchone(self):
        return (True,)  # the table "exists"

    def fetchall(self):
        return [(w,) for w in self._words]


class FakeConnection:
    def __init__(self, words):
        self._words = words

    def cursor(self):
        return FakeCursor(self._words)


def fresh_conn():
    return FakeConnection(["hello", "friend", "water"])


# --- Empty / unusable model output must never reach the Agent as an empty string ---------


def test_empty_response_returns_fallback_message():
    story_tool._STORY_CACHE.clear()
    result = generate_story_for_learner(
        "English", conn=fresh_conn(), call_groq_fn=lambda p: "", use_cache=False
    )
    check("empty model response returns the fallback message", result == FAILURE_FALLBACK_MESSAGE)


def test_none_response_returns_fallback_message():
    story_tool._STORY_CACHE.clear()
    result = generate_story_for_learner(
        "English", conn=fresh_conn(), call_groq_fn=lambda p: None, use_cache=False
    )
    check("None model response returns the fallback message", result == FAILURE_FALLBACK_MESSAGE)


def test_whitespace_only_response_returns_fallback_message():
    story_tool._STORY_CACHE.clear()
    result = generate_story_for_learner(
        "English", conn=fresh_conn(), call_groq_fn=lambda p: "  \n\t ", use_cache=False
    )
    check("whitespace-only response returns the fallback message", result == FAILURE_FALLBACK_MESSAGE)


def test_empty_passage_after_delimiter_returns_fallback_message():
    story_tool._STORY_CACHE.clear()
    raw = "Character: Anna\nWant: bread\n===STORY===\n   \n"
    result = generate_story_for_learner(
        "English", conn=fresh_conn(), call_groq_fn=lambda p: raw, use_cache=False
    )
    check("a plan with an empty passage after ===STORY=== returns the fallback", result == FAILURE_FALLBACK_MESSAGE)


def test_empty_response_is_cached_as_a_failure_not_a_success():
    story_tool._STORY_CACHE.clear()
    calls = []

    def empty_groq(prompt):
        calls.append(1)
        return ""

    r1 = generate_story_for_learner("English", conn=fresh_conn(), call_groq_fn=empty_groq, use_cache=True)
    r2 = generate_story_for_learner("English", conn=fresh_conn(), call_groq_fn=empty_groq, use_cache=True)
    kind = story_tool._STORY_CACHE.get("english", (None, None, None))[2]
    check("empty response is cached as a failure (short TTL)", kind == "failure")
    check("both calls return the fallback, never an empty string", r1 == r2 == FAILURE_FALLBACK_MESSAGE)
    check("the repeat call reuses the cached failure (Groq called once)", len(calls) == 1)


def test_good_response_still_returns_the_passage():
    story_tool._STORY_CACHE.clear()
    raw = "Character: Anna\n===STORY===\nHello, my friend. I like water."
    result = generate_story_for_learner(
        "English", conn=fresh_conn(), call_groq_fn=lambda p: raw, use_cache=False
    )
    check("a normal response is unaffected by the fix", result == "Hello, my friend. I like water.")


# --- call_groq must leave room for the answer after the model's hidden reasoning ---------


def make_groq_response(content="ok"):
    body = json.dumps({"choices": [{"message": {"content": content}, "finish_reason": "stop"}]})
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = body.encode("utf-8")
    return cm


def capture_payload():
    captured = {}

    def fake_urlopen(req, timeout=30):
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return make_groq_response()

    with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
        with patch("story_tool.urllib.request.urlopen", side_effect=fake_urlopen):
            story_tool.call_groq("hello")
    return captured["payload"]


def test_call_groq_leaves_room_for_the_answer_after_reasoning():
    payload = capture_payload()
    check(
        "max_tokens is large enough that reasoning cannot consume the whole budget (>= 1500)",
        payload.get("max_tokens", 0) >= 1500,
    )


def test_call_groq_requests_low_reasoning_effort():
    payload = capture_payload()
    check("request asks for reasoning_effort='low'", payload.get("reasoning_effort") == "low")


def test_call_groq_still_targets_the_story_model_and_prompt():
    payload = capture_payload()
    check("model is the story model (openai/gpt-oss-120b)", payload.get("model") == "openai/gpt-oss-120b")
    check("prompt is sent as the user message", payload["messages"] == [{"role": "user", "content": "hello"}])


def main():
    print("Running empty-response handling tests...\n")
    test_empty_response_returns_fallback_message()
    test_none_response_returns_fallback_message()
    test_whitespace_only_response_returns_fallback_message()
    test_empty_passage_after_delimiter_returns_fallback_message()
    test_empty_response_is_cached_as_a_failure_not_a_success()
    test_good_response_still_returns_the_passage()
    test_call_groq_leaves_room_for_the_answer_after_reasoning()
    test_call_groq_requests_low_reasoning_effort()
    test_call_groq_still_targets_the_story_model_and_prompt()

    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    else:
        print("All tests passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()
