"""
Tests for automatic retry-with-backoff when Groq returns HTTP 429 (rate limit exceeded).

Written BEFORE the implementation. Run this now — call_groq currently has no retry logic,
so these should fail (specifically: a single 429 should currently propagate as an error
immediately, not retry and succeed).

Uses unittest.mock to simulate urllib.request.urlopen raising a 429 HTTPError, so this
tests the retry behavior deterministically without needing a real rate-limited API call.

Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_call_groq_retry.py
"""

import io
import sys
import urllib.error
from unittest.mock import MagicMock, patch

sys.path.insert(0, "/app/custom_components")

import story_tool  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"
failures = []


def check(label, condition):
    if condition:
        print(f"[{PASS}] {label}")
    else:
        print(f"[{FAIL}] {label}")
        failures.append(label)


def make_429_error():
    body = b'{"error":{"message":"Rate limit reached... Please try again in 457.5ms.","type":"tokens","code":"rate_limit_exceeded"}}'
    return urllib.error.HTTPError(
        url="https://api.groq.com/openai/v1/chat/completions",
        code=429,
        msg="Too Many Requests",
        hdrs=None,
        fp=io.BytesIO(body),
    )


def make_success_response(content="Hello, this is a real story."):
    body = f'{{"choices": [{{"message": {{"content": "{content}"}}}}]}}'.encode("utf-8")
    cm = MagicMock()
    cm.__enter__.return_value.read.return_value = body
    return cm


def test_retries_once_after_a_single_429_then_succeeds():
    call_log = []

    def fake_urlopen(req, timeout=30):
        if len(call_log) == 0:
            call_log.append("429")
            raise make_429_error()
        call_log.append("success")
        return make_success_response()

    with patch("urllib.request.urlopen", side_effect=fake_urlopen), \
         patch("time.sleep", return_value=None):
        import os
        os.environ["GROQ_API_KEY"] = "fake-key-for-test"
        result = story_tool.call_groq("a test prompt")

    check("retries after one 429 and succeeds on the second attempt", len(call_log) == 2)
    check("returns the successful response's content", result == "Hello, this is a real story.")


def test_gives_up_after_max_retries_and_raises_clear_error():
    call_log = []

    def always_429(req, timeout=30):
        call_log.append("429")
        raise make_429_error()

    with patch("urllib.request.urlopen", side_effect=always_429), \
         patch("time.sleep", return_value=None):
        import os
        os.environ["GROQ_API_KEY"] = "fake-key-for-test"
        try:
            story_tool.call_groq("a test prompt")
            check("raises RuntimeError after exhausting retries", False)
        except RuntimeError as e:
            check(f"raises RuntimeError after exhausting retries ({e})", True)

    check("attempted more than once before giving up", len(call_log) > 1)
    check("did not retry forever (capped)", len(call_log) <= 5)


def test_non_429_errors_are_not_retried():
    call_log = []

    def make_500_error():
        body = b'{"error":{"message":"Internal server error"}}'
        return urllib.error.HTTPError(
            url="https://api.groq.com/openai/v1/chat/completions",
            code=500,
            msg="Internal Server Error",
            hdrs=None,
            fp=io.BytesIO(body),
        )

    def always_500(req, timeout=30):
        call_log.append("500")
        raise make_500_error()

    with patch("urllib.request.urlopen", side_effect=always_500), \
         patch("time.sleep", return_value=None):
        import os
        os.environ["GROQ_API_KEY"] = "fake-key-for-test"
        try:
            story_tool.call_groq("a test prompt")
        except RuntimeError:
            pass

    check("a non-429 error (e.g. 500) fails fast, without retrying", len(call_log) == 1)


def main():
    print("Running call_groq retry tests...\n")
    test_retries_once_after_a_single_429_then_succeeds()
    test_gives_up_after_max_retries_and_raises_clear_error()
    test_non_429_errors_are_not_retried()

    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    else:
        print("All tests passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()