"""The target-language story prompt (build_story_prompt(..., vocab_in_target=True)).

A learner's word list is stored per language, so a Spanish learner's list is already Spanish. The older non-English
prompt called the entries English "meanings" to translate, which is wrong for those learners. These tests pin: the new
wording, that English is untouched, that every style has the variant, and that the old non-English prompt still exists
for callers that pass an English-meaning list."""
import hashlib

import pytest

from tutor_core import prompts
from tutor_core.prompts import ALL_STORY_TYPES, DIALOGUE_TEMPLATE, NARRATION_TEMPLATE, build_story_prompt

WORDS = "pan, queso, casa"
# Same checksums as tests/test_story_prompt_language.py: the English templates must never change.
ORIGINAL_NARRATION_SHA256 = "02eeeae82e165e122f0db6d8f516c19b70666f67a41a1ed4fe148cd7b0bb0776"
ORIGINAL_DIALOGUE_SHA256 = "a77dac64f9c45a1a1d7bd94ed06574b1cad825d98c0ea7083be7f65935dd518e"


def test_english_templates_are_still_byte_for_byte_the_original():
    assert hashlib.sha256(NARRATION_TEMPLATE.encode()).hexdigest() == ORIGINAL_NARRATION_SHA256
    assert hashlib.sha256(DIALOGUE_TEMPLATE.encode()).hexdigest() == ORIGINAL_DIALOGUE_SHA256


@pytest.mark.parametrize("style", ALL_STORY_TYPES)
def test_english_ignores_the_flag(style):
    kw = {"topic": "a market"}
    assert (build_story_prompt("English", WORDS, style, vocab_in_target=True, **kw)
            == build_story_prompt("English", WORDS, style, **kw))


@pytest.mark.parametrize("style", ALL_STORY_TYPES)
def test_the_target_variant_says_the_list_is_already_in_the_language(style):
    p = build_story_prompt("Spanish", WORDS, style, "a market", vocab_in_target=True)
    assert "already written in Spanish" in p
    assert "do not translate" in p
    assert WORDS in p
    assert "===STORY===" in p and "Begin:" in p
    assert "nothing in English" in p


@pytest.mark.parametrize("style", ALL_STORY_TYPES)
def test_the_target_variant_does_not_call_the_words_english_meanings(style):
    p = build_story_prompt("Spanish", WORDS, style, "a market", vocab_in_target=True)
    assert "written in English" not in p
    assert "MEANING" not in p
    assert "equivalent" not in p


@pytest.mark.parametrize("style", ["narration", "dialogue"])
def test_the_english_tone_example_is_left_out(style):
    p = build_story_prompt("Spanish", WORDS, style, vocab_in_target=True)
    assert "I am hungry today" not in p and "Do you have any bread" not in p


@pytest.mark.parametrize("style", ALL_STORY_TYPES)
def test_the_old_non_english_prompt_is_still_what_you_get_by_default(style):
    p = build_story_prompt("Spanish", WORDS, style, "a market")
    assert "written in English" in p and "MEANING" in p
    assert p != build_story_prompt("Spanish", WORDS, style, "a market", vocab_in_target=True)


def test_the_target_variant_keeps_the_reminder_before_begin():
    p = build_story_prompt("French", WORDS, "diary", "a rainy day", vocab_in_target=True)
    assert p.index("Final check") < p.index("Begin:")
    assert "French" in p.split("Final check")[1]


def test_describe_prompt_still_reads_the_variant_back():
    p = build_story_prompt("Spanish", WORDS, "diary", "a rainy day", vocab_in_target=True)
    assert prompts.describe_prompt(p) == ("diary", "a rainy day")
    assert prompts.describe_prompt(build_story_prompt("Spanish", WORDS, "dialogue", vocab_in_target=True)) == ("dialogue", None)
