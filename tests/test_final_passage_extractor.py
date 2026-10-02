"""
Tests for extracting the final passage/dialogue from the model's raw output, discarding the
hidden planning summary that comes before the ===STORY=== delimiter.

Written BEFORE the implementation. Run this now and expect an ImportError, since
custom_components/final_passage_extractor.py doesn't exist yet. Re-run after implementing to
confirm green.

This is deliberately a deterministic, code-level split rather than trusting the model to
simply "not show" the summary — smaller open-source models aren't reliably obedient about
that on their own.

Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_final_passage_extractor.py
"""

import sys

sys.path.insert(0, "/app/custom_components")

from final_passage_extractor import extract_final_passage  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"
failures = []


def check(label, condition):
    if condition:
        print(f"[{PASS}] {label}")
    else:
        print(f"[{FAIL}] {label}")
        failures.append(label)


def test_extracts_text_after_delimiter():
    raw = "Summary: two friends meet.\n===STORY===\nHello! I have food."
    result = extract_final_passage(raw)
    check(
        "returns only the text after the delimiter",
        result == "Hello! I have food.",
    )


def test_strips_surrounding_whitespace():
    raw = "Summary here.\n===STORY===\n\n  Hello! I have food.  \n\n"
    result = extract_final_passage(raw)
    check("strips leading/trailing whitespace from the extracted passage", result == "Hello! I have food.")


def test_splits_on_first_occurrence_only():
    raw = "Plan.\n===STORY===\nHello! ===STORY=== still counts as story text."
    result = extract_final_passage(raw)
    check(
        "splits on the first delimiter only, keeping the rest as-is",
        result == "Hello! ===STORY=== still counts as story text.",
    )


def test_missing_delimiter_falls_back_to_full_text():
    raw = "  The model forgot the delimiter and just wrote the story directly.  "
    result = extract_final_passage(raw)
    check(
        "falls back to the full (stripped) text if the delimiter is missing",
        result == "The model forgot the delimiter and just wrote the story directly.",
    )


def test_empty_input_returns_empty_string():
    check("empty input returns an empty string, no crash", extract_final_passage("") == "")


def test_none_input_returns_empty_string():
    check("None input returns an empty string, no crash", extract_final_passage(None) == "")


def main():
    print("Running final passage extractor tests...\n")
    test_extracts_text_after_delimiter()
    test_strips_surrounding_whitespace()
    test_splits_on_first_occurrence_only()
    test_missing_delimiter_falls_back_to_full_text()
    test_empty_input_returns_empty_string()
    test_none_input_returns_empty_string()

    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    else:
        print("All tests passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()