"""
Tests for the empty-vocabulary guard (Story 5's "ask the learner to add words first" case).

Written BEFORE the implementation. Run this now and expect an ImportError, since
custom_components/story_guard.py doesn't exist yet. Re-run after implementing to confirm
green.

This mirrors the check that gets wired in Langflow's UI using the built-in If-Else
(Conditional Router) component: input_text = Word Loader's output, match_text = "",
operator = "equals". True (matches empty) -> show EMPTY_VOCABULARY_MESSAGE instead of
generating. False -> proceed to the Prompt Template.

Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_story_guard.py
"""

import sys

sys.path.insert(0, "/app/custom_components")

from story_guard import EMPTY_VOCABULARY_MESSAGE, should_generate_story  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"
failures = []


def check(label, condition):
    if condition:
        print(f"[{PASS}] {label}")
    else:
        print(f"[{FAIL}] {label}")
        failures.append(label)


def test_empty_string_should_not_generate():
    check("empty string -> should not generate", should_generate_story("") is False)


def test_whitespace_only_should_not_generate():
    check(
        "whitespace-only string -> should not generate",
        should_generate_story("   ") is False,
    )


def test_nonempty_words_should_generate():
    check(
        "non-empty word list -> should generate",
        should_generate_story("hello, world, friend") is True,
    )


def test_single_word_should_generate():
    check("a single word -> should generate", should_generate_story("hello") is True)


def test_empty_vocabulary_message_is_helpful():
    check(
        "EMPTY_VOCABULARY_MESSAGE mentions adding words",
        "add" in EMPTY_VOCABULARY_MESSAGE.lower()
        and "word" in EMPTY_VOCABULARY_MESSAGE.lower(),
    )


def main():
    print("Running empty-vocabulary guard tests (Story 5)...\n")
    test_empty_string_should_not_generate()
    test_whitespace_only_should_not_generate()
    test_nonempty_words_should_generate()
    test_single_word_should_generate()
    test_empty_vocabulary_message_is_helpful()

    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    else:
        print("All tests passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()