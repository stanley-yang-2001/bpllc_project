"""
Tests for the language-aware story prompt (Step 10, LO 7).

Found in the first live routing run: only 5 of 15 non-English stories were actually written in
the requested language (stories "in Spanish" came back in English, "in Japanese" in English,
French with English words left in). Two likely causes, both fixed here:
  1. the vocabulary list is English, and the prompt just says "use words from this list", so the
     model stays in English  -> for non-English languages the prompt now says the list holds
     English MEANINGS to be expressed in the target language, with no English left in;
  2. the prompt's tone examples are written in English, which primes English output  -> for
     non-English languages the English example is left out.
The English prompt must stay EXACTLY as it was (English stories already pass ~85-89%), so the
original templates are pinned by checksum. Also: a language given by its own name ("日本語",
"español") is normalized to the English name, which is what the prompt and the cache key use.

Written BEFORE the change. No database or network (a fake connection stands in).

Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_story_prompt_language.py
"""

import hashlib
import sys

sys.path.insert(0, "/app/custom_components")

from tutor_core.prompts import DIALOGUE_TEMPLATE, NARRATION_TEMPLATE, build_story_prompt, normalize_language  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"
failures = []

# sha256 of the English templates BEFORE this change (do not edit these to make a test pass)
ORIGINAL_NARRATION_SHA256 = "02eeeae82e165e122f0db6d8f516c19b70666f67a41a1ed4fe148cd7b0bb0776"
ORIGINAL_DIALOGUE_SHA256 = "a77dac64f9c45a1a1d7bd94ed06574b1cad825d98c0ea7083be7f65935dd518e"

WORDS = "hello, water, friend, house, thank you"
ENGLISH_NARRATION_EXAMPLE = "I am hungry today. I see a small shop with fresh bread"
ENGLISH_DIALOGUE_EXAMPLE = "Mia: Hello! Do you have any bread?"


def check(label, condition):
    if condition:
        print(f"[{PASS}] {label}")
    else:
        print(f"[{FAIL}] {label}")
        failures.append(label)


# --- English is untouched ---------------------------------------------------------------------


def test_english_templates_are_unchanged():
    check("the narration template is byte-for-byte the original",
          hashlib.sha256(NARRATION_TEMPLATE.encode()).hexdigest() == ORIGINAL_NARRATION_SHA256)
    check("the dialogue template is byte-for-byte the original",
          hashlib.sha256(DIALOGUE_TEMPLATE.encode()).hexdigest() == ORIGINAL_DIALOGUE_SHA256)


def test_english_prompts_are_unchanged():
    for style, template in (("narration", NARRATION_TEMPLATE), ("dialogue", DIALOGUE_TEMPLATE)):
        expected = template.format(language="English", words=WORDS)
        check(f"English {style} prompt is exactly the original", build_story_prompt("English", WORDS, style) == expected)
        check(f"'english' / ' English ' give the same {style} prompt",
              build_story_prompt("english", WORDS, style) == expected and build_story_prompt(" English ", WORDS, style) == expected)


# --- other languages: translate, and no English example ---------------------------------------


def test_non_english_prompt_asks_for_translation():
    for style in ("narration", "dialogue"):
        p = build_story_prompt("Spanish", WORDS, style)
        check(f"[{style}] names the language", "Spanish" in p)
        check(f"[{style}] still contains the vocabulary", WORDS in p)
        check(f"[{style}] says the whole passage must be in the language", "ENTIRE" in p and "Spanish" in p)
        check(f"[{style}] says the list holds English meanings to be translated", "English" in p and "meaning" in p.lower())
        check(f"[{style}] forbids leftover English words", "no English" in p.lower() or "do not leave any english" in p.lower())
        check(f"[{style}] keeps the planning/delimiter protocol", "===STORY===" in p and "Begin:" in p)


def test_non_english_prompt_drops_the_english_example():
    n = build_story_prompt("French", WORDS, "narration")
    d = build_story_prompt("French", WORDS, "dialogue")
    check("narration: the English tone example is left out", ENGLISH_NARRATION_EXAMPLE not in n and "Tone example" not in n)
    check("dialogue: the English tone example is left out", ENGLISH_DIALOGUE_EXAMPLE not in d and "Tone example" not in d)
    check("dialogue: the 'Name: line' format rule is kept", "Name: line" in d)
    check("the English prompt still has its example", ENGLISH_NARRATION_EXAMPLE in build_story_prompt("English", WORDS, "narration"))


def test_non_english_prompt_has_no_unfilled_placeholders():
    for style in ("narration", "dialogue"):
        p = build_story_prompt("German", WORDS, style)
        check(f"[{style}] no '{{language}}' / '{{words}}' left unfilled", "{language}" not in p and "{words}" not in p)


# --- language names ---------------------------------------------------------------------------


def test_normalize_language():
    cases = {
        "\u65e5\u672c\u8a9e": "Japanese", "\u4e2d\u6587": "Chinese", "\u6c49\u8bed": "Chinese",
        "\ud55c\uad6d\uc5b4": "Korean", "espa\u00f1ol": "Spanish", "Espa\u00f1ol": "Spanish",
        "fran\u00e7ais": "French", "FRAN\u00c7AIS": "French", "deutsch": "German", "italiano": "Italian",
        "portugu\u00eas": "Portuguese", "\u0440\u0443\u0441\u0441\u043a\u0438\u0439": "Russian",
        "spanish": "Spanish", " Spanish ": "Spanish", "Spanish": "Spanish", "english": "English",
        "Klingon": "Klingon", "": "", None: "",
    }
    for given, expected in cases.items():
        check(f"normalize_language({given!r}) == {expected!r}", normalize_language(given) == expected)


def test_prompt_uses_the_normalized_language():
    p = build_story_prompt("\u65e5\u672c\u8a9e", WORDS, "narration")
    check("a request for '日本語' puts 'Japanese' in the prompt", "Japanese" in p and "\u65e5\u672c\u8a9e" not in p)


def main():
    print("Running language-aware story prompt tests...\n")
    test_english_templates_are_unchanged()
    test_english_prompts_are_unchanged()
    test_non_english_prompt_asks_for_translation()
    test_non_english_prompt_drops_the_english_example()
    test_non_english_prompt_has_no_unfilled_placeholders()
    test_normalize_language()
    test_prompt_uses_the_normalized_language()
    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    print("All tests passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
