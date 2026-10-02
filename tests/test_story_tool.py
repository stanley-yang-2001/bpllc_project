"""
Tests for the consolidated Story Generator Tool (Story 5+6, as a single agent-callable tool).

Written BEFORE the implementation. Run this now and expect an ImportError, since
custom_components/story_tool.py doesn't exist yet. Re-run after implementing to confirm
green.

Why this exists as a separate, consolidated component: when a component is used as a Tool
by another Agent, Langflow only returns that component's own output — it does not execute
whatever is wired downstream of it on the canvas. The Step 8 pipeline (Word Loader ->
Story Prompt Builder -> Agent -> Final Passage Extractor) is four separate components, so
using the Agent alone as a tool would leak the hidden planning summary straight to the
learner. This module inlines the same logic (vocabulary loading, the empty-vocab guard,
prompt building, delimiter extraction) into one component, so tool invocation returns a
single, already-cleaned result.

The real Groq HTTP call (call_groq) is NOT exercised here — these tests inject a fake
version so they run fast, deterministically, and without real API calls. The real call_groq
is covered by manual Playground testing and smoke_test.py, per the project's "manual pass
last, for anything hard to automate" policy.

Uses a separate `words_test` table so it never touches real seeded vocabulary data.

Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_story_tool.py
"""

import sys

import psycopg2

sys.path.insert(0, "/app/custom_components")

from story_tool import EMPTY_VOCABULARY_MESSAGE, generate_story_for_learner  # noqa: E402
import story_tool  # noqa: E402

DB_CONFIG = dict(dbname="langflow", user="langflow", password="langflow", host="postgres", port=5432)
TEST_TABLE = "words_test"

PASS = "PASS"
FAIL = "FAIL"
failures = []


def check(label, condition):
    if condition:
        print(f"[{PASS}] {label}")
    else:
        print(f"[{FAIL}] {label}")
        failures.append(label)


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def cleanup(conn):
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {TEST_TABLE};")
    conn.commit()


def create_and_seed(conn, words):
    with conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TEST_TABLE} (
                id SERIAL PRIMARY KEY,
                word TEXT UNIQUE NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now()
            );
            """
        )
        for word in words:
            cur.execute(f"INSERT INTO {TEST_TABLE} (word) VALUES (%s);", (word,))
    conn.commit()


def fake_call_groq_echo(prompt: str) -> str:
    """Stands in for the real Groq call — just wraps the prompt in a fake delimited reply."""
    return f"Character: Test. Want: testing. Event: a test runs. Resolution: it passes.\n===STORY===\nHello, this is a fake story."


def fake_call_groq_no_delimiter(prompt: str) -> str:
    """Simulates the model forgetting the ===STORY=== delimiter."""
    return "Hello, this is a fake story with no delimiter."


def test_empty_vocabulary_returns_friendly_message_without_calling_groq():
    conn = get_connection()
    cleanup(conn)
    create_and_seed(conn, [])  # empty vocabulary

    called = {"count": 0}

    def call_groq_should_not_run(prompt):
        called["count"] += 1
        return "should not happen"

    result = generate_story_for_learner(
        "Spanish", conn=conn, table_name=TEST_TABLE, call_groq_fn=call_groq_should_not_run,
        use_cache=False,
    )
    check(
        "empty vocabulary returns EMPTY_VOCABULARY_MESSAGE",
        result == EMPTY_VOCABULARY_MESSAGE,
    )
    check("empty vocabulary never calls Groq", called["count"] == 0)
    conn.close()


def test_nonempty_vocabulary_returns_cleaned_story():
    conn = get_connection()
    cleanup(conn)
    create_and_seed(conn, ["hello", "friend", "water"])

    result = generate_story_for_learner(
        "Spanish", conn=conn, table_name=TEST_TABLE, call_groq_fn=fake_call_groq_echo,
        use_cache=False,
    )
    check(
        "non-empty vocabulary returns only the text after the delimiter",
        result == "Hello, this is a fake story.",
    )
    check(
        "the hidden planning summary is NOT present in the result",
        "Character:" not in result and "Resolution:" not in result,
    )
    conn.close()


def test_groq_failure_returns_friendly_message_instead_of_raising():
    conn = get_connection()
    cleanup(conn)
    create_and_seed(conn, ["hello", "friend"])

    def failing_call_groq(prompt):
        raise RuntimeError("Groq API error 429: rate limit exceeded")

    result = generate_story_for_learner(
        "Spanish", conn=conn, table_name=TEST_TABLE, call_groq_fn=failing_call_groq,
        use_cache=False,
    )
    check(
        "a Groq failure returns a friendly message instead of raising",
        "try again" in result.lower() or "moment" in result.lower(),
    )
    conn.close()


def test_missing_delimiter_falls_back_gracefully():
    conn = get_connection()
    cleanup(conn)
    create_and_seed(conn, ["hello", "friend"])

    result = generate_story_for_learner(
        "Spanish", conn=conn, table_name=TEST_TABLE, call_groq_fn=fake_call_groq_no_delimiter,
        use_cache=False,
    )
    check(
        "missing delimiter falls back to the full response, not an error",
        result == "Hello, this is a fake story with no delimiter.",
    )
    conn.close()


def test_missing_table_raises_clear_error():
    conn = get_connection()
    cleanup(conn)  # table intentionally does NOT exist
    try:
        generate_story_for_learner(
            "Spanish", conn=conn, table_name=TEST_TABLE, call_groq_fn=fake_call_groq_echo,
            use_cache=False,
        )
        check("raises a clear error if the vocabulary table is missing", False)
    except RuntimeError as e:
        check(f"raises a clear error if the vocabulary table is missing ({e})", True)
    conn.close()


def test_repeated_calls_within_ttl_hit_groq_only_once():
    story_tool._STORY_CACHE.clear()
    conn = get_connection()
    cleanup(conn)
    create_and_seed(conn, ["hello", "friend"])

    call_log = []

    def counting_call_groq(prompt):
        call_log.append(1)
        return fake_call_groq_echo(prompt)

    result1 = generate_story_for_learner(
        "Spanish", conn=conn, table_name=TEST_TABLE, call_groq_fn=counting_call_groq,
        use_cache=True,
    )
    result2 = generate_story_for_learner(
        "Spanish", conn=conn, table_name=TEST_TABLE, call_groq_fn=counting_call_groq,
        use_cache=True,
    )
    check("a second call for the same language reuses the cache (Groq called once)", len(call_log) == 1)
    check("both calls return the same cached result", result1 == result2)
    conn.close()


def test_different_languages_are_cached_separately():
    story_tool._STORY_CACHE.clear()
    conn = get_connection()
    cleanup(conn)
    create_and_seed(conn, ["hello", "friend"])

    call_log = []

    def counting_call_groq(prompt):
        call_log.append(1)
        return fake_call_groq_echo(prompt)

    generate_story_for_learner(
        "Spanish", conn=conn, table_name=TEST_TABLE, call_groq_fn=counting_call_groq,
        use_cache=True,
    )
    generate_story_for_learner(
        "French", conn=conn, table_name=TEST_TABLE, call_groq_fn=counting_call_groq,
        use_cache=True,
    )
    check("different languages are NOT deduped against each other", len(call_log) == 2)
    conn.close()


def test_repeated_calls_after_failure_use_cached_fallback_without_retrying():
    story_tool._STORY_CACHE.clear()
    conn = get_connection()
    cleanup(conn)
    create_and_seed(conn, ["hello", "friend"])

    call_log = []

    def always_failing_call_groq(prompt):
        call_log.append(1)
        raise RuntimeError("Groq API error 429: rate limit exceeded")

    result1 = generate_story_for_learner(
        "Spanish", conn=conn, table_name=TEST_TABLE, call_groq_fn=always_failing_call_groq,
        use_cache=True,
    )
    result2 = generate_story_for_learner(
        "Spanish", conn=conn, table_name=TEST_TABLE, call_groq_fn=always_failing_call_groq,
        use_cache=True,
    )
    check(
        "a second call after a failure reuses the cached fallback (Groq attempted once)",
        len(call_log) == 1,
    )
    check("both calls return the same fallback message", result1 == result2)
    conn.close()


def main():
    print("Running Story Generator Tool tests...\n")
    test_empty_vocabulary_returns_friendly_message_without_calling_groq()
    test_nonempty_vocabulary_returns_cleaned_story()
    test_groq_failure_returns_friendly_message_instead_of_raising()
    test_missing_delimiter_falls_back_gracefully()
    test_missing_table_raises_clear_error()
    test_repeated_calls_within_ttl_hit_groq_only_once()
    test_different_languages_are_cached_separately()
    test_repeated_calls_after_failure_use_cached_fallback_without_retrying()

    conn = get_connection()
    cleanup(conn)
    conn.close()

    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    else:
        print("All tests passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()