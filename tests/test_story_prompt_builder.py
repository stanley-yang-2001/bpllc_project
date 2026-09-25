"""
Tests for the story prompt template's build logic (Story 5, prompt half).

Covers two interchangeable formats — first-person narration and two-person dialogue — since
the original single narration-only format forced in every vocabulary word (including
conversational words like "yes"/"no" that don't fit narration naturally) and produced
noticeably stiffer output. `style` defaults to a random choice between the two when not
given explicitly, so real usage naturally varies between formats across requests.

Note: the "vocabulary is empty" guard from Story 5's acceptance criteria is NOT tested here
— per workflow-diagram.md, that check happens one step earlier, before the prompt template
is ever built (Step 8's job, not Step 7's). This module assumes it's only ever called with a
non-empty word list.

Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_prompt_template.py
"""

import sys

sys.path.insert(0, "/app/custom_components")

from prompt_template import build_story_prompt  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"
failures = []


def check(label, condition):
    if condition:
        print(f"[{PASS}] {label}")
    else:
        print(f"[{FAIL}] {label}")
        failures.append(label)


def test_narration_style_includes_language_and_words():
    prompt = build_story_prompt("Spanish", "hello, world, friend", style="narration")
    check("narration prompt includes the language", "Spanish" in prompt)
    check("narration prompt includes the word list", "hello, world, friend" in prompt)


def test_narration_style_does_not_request_dialogue_format():
    prompt = build_story_prompt("Spanish", "hello, world, friend", style="narration")
    check(
        "narration prompt does not ask for a 'Name: line' dialogue format",
        "Name: line" not in prompt,
    )


def test_dialogue_style_includes_language_and_words():
    prompt = build_story_prompt("French", "chat, chien", style="dialogue")
    check("dialogue prompt includes the language", "French" in prompt)
    check("dialogue prompt includes the word list", "chat, chien" in prompt)


def test_dialogue_style_requests_dialogue_format():
    prompt = build_story_prompt("French", "chat, chien", style="dialogue")
    check(
        "dialogue prompt asks for a two-person conversation format",
        "dialogue" in prompt.lower() or "conversation" in prompt.lower(),
    )


def test_no_style_given_picks_one_of_the_two_valid_styles():
    seen_narration = False
    seen_dialogue = False
    for _ in range(20):
        prompt = build_story_prompt("Spanish", "hello, world")
        if "Name: line" in prompt or "dialogue" in prompt.lower():
            seen_dialogue = True
        else:
            seen_narration = True
    check(
        "20 calls with no style given produce a mix of both formats (randomized)",
        seen_narration and seen_dialogue,
    )


def test_both_styles_do_not_force_every_word():
    narration = build_story_prompt("Spanish", "hello, world, friend", style="narration")
    dialogue = build_story_prompt("Spanish", "hello, world, friend", style="dialogue")
    check(
        "narration prompt says every word doesn't need to be included",
        "don't need to include every" in narration.lower(),
    )
    check(
        "dialogue prompt says every word doesn't need to be included",
        "don't need to include every" in dialogue.lower(),
    )


def test_invalid_style_raises():
    try:
        build_story_prompt("Spanish", "hello, world", style="poem")
        check("build_story_prompt raises on an invalid style", False)
    except ValueError:
        check("build_story_prompt raises on an invalid style", True)


def test_rejects_empty_language():
    try:
        build_story_prompt("", "hello, world")
        check("build_story_prompt raises on empty language", False)
    except ValueError:
        check("build_story_prompt raises on empty language", True)


def test_rejects_empty_words():
    try:
        build_story_prompt("Spanish", "")
        check("build_story_prompt raises on empty words", False)
    except ValueError:
        check("build_story_prompt raises on empty words", True)


def main():
    print("Running story prompt template tests (Story 5, prompt half)...\n")
    test_narration_style_includes_language_and_words()
    test_narration_style_does_not_request_dialogue_format()
    test_dialogue_style_includes_language_and_words()
    test_dialogue_style_requests_dialogue_format()
    test_no_style_given_picks_one_of_the_two_valid_styles()
    test_both_styles_do_not_force_every_word()
    test_invalid_style_raises()
    test_rejects_empty_language()
    test_rejects_empty_words()

    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    else:
        print("All tests passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()