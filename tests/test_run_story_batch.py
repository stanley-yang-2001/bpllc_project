"""
Test for scripts/run_story_batch.py: a failed generation must say WHY.

In the variety run, 3 of 10 Japanese stories came back as the fallback message ("I'm having
trouble generating a story..."), with latencies of about 3.4 s. The runner could not say whether
that was a rate limit (HTTP 429), an empty response or something else, because the story
pipeline swallows the exception. The runner now records the error from the model call.

Written BEFORE the change. No database or network.

Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_run_story_batch.py
"""

import sys

sys.path.insert(0, "/app/custom_components")
sys.path.insert(0, "/app/scripts")

import story_tool  # noqa: E402
import run_story_batch  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"
failures = []
WORDS = "hello, water, friend, house, today, book"


def check(label, condition):
    if condition:
        print(f"[{PASS}] {label}")
    else:
        print(f"[{FAIL}] {label}")
        failures.append(label)


class FakeCursor:
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        pass

    def fetchone(self):
        return (True,)

    def fetchall(self):
        return [(w.strip(),) for w in WORDS.split(",")]


class FakeConnection:
    def cursor(self):
        return FakeCursor()


def run(groq_fn, count=3, language="Spanish"):
    original = story_tool.call_groq
    story_tool.call_groq = groq_fn
    story_tool._STORY_CACHE.clear()
    try:
        return run_story_batch.run_language(language, count, 0, FakeConnection(), WORDS, 5, False)
    finally:
        story_tool.call_groq = original
        story_tool._STORY_CACHE.clear()


def test_failures_record_the_error():
    def fail_429(prompt):
        raise RuntimeError('Groq API error 429: {"error":{"message":"Rate limit reached"}}')

    results = run(fail_429)
    check("every failed generation is a failure result", all(r["failure"] for r in results))
    check("the model error is recorded on the result", all("429" in (r.get("error") or "") for r in results))
    check("the error type is included", all("RuntimeError" in (r.get("error") or "") for r in results))


def test_successes_have_no_error():
    results = run(lambda p: "plan\n===STORY===\nHola, soy Ana.\nHoy quiero agua.\nMi amigo dice si.\nGracias, adios.\nHasta manana.")
    check("a successful generation records no error", all(r.get("error") is None for r in results))
    check("successful results keep their story type and topic", all(r.get("story_type") for r in results))


def test_an_empty_response_is_distinguishable_from_an_exception():
    results = run(lambda p: "")
    check("an empty model response is a failure with a clear reason", all(r["failure"] for r in results))
    check("an empty response is reported as empty, not as an exception",
          all((r.get("error") or "").startswith("empty") for r in results))


def main():
    print("Running batch runner tests...\n")
    test_failures_record_the_error()
    test_successes_have_no_error()
    test_an_empty_response_is_distinguishable_from_an_exception()
    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    print("All tests passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
