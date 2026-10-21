"""A short English word list gets only the classic styles when no kind was named (see MIN_WORDS_FOR_VARIED_TYPES)."""
import random

import pytest

from tutor_core import prompts
from tutor_core.prompts import (ALL_STORY_TYPES, MIN_WORDS_FOR_VARIED_TYPES, VALID_STYLES, build_story_prompt, choose_story_type,
                                describe_prompt)

CLASSIC = set(VALID_STYLES)


def picks(n=600, **kw):
    rng = random.Random(7)
    return {choose_story_type(rng, **kw) for _ in range(n)}


@pytest.fixture(autouse=True)
def fresh_topics():
    prompts._RECENT_TOPICS.clear()


def test_the_threshold_is_twenty_words():
    assert MIN_WORDS_FOR_VARIED_TYPES == 20


@pytest.mark.parametrize("count", [0, 1, 12, 19])
def test_below_the_threshold_only_the_classic_styles_are_drawn(count):
    assert picks(word_count=count) == CLASSIC


@pytest.mark.parametrize("count", [20, 21, 500])
def test_at_or_above_the_threshold_every_kind_is_drawn(count):
    assert picks(word_count=count) == set(ALL_STORY_TYPES)


def test_without_a_word_count_nothing_changes():
    assert picks() == set(ALL_STORY_TYPES)


def test_both_classic_styles_still_appear_for_a_short_list():
    kinds = [choose_story_type(random.Random(i), word_count=3) for i in range(200)]
    assert kinds.count("narration") > 20 and kinds.count("dialogue") > 20


def test_a_random_english_prompt_for_a_short_list_is_classic():
    for i in range(60):
        kind, _ = describe_prompt(build_story_prompt("English", "computer", None, None, random.Random(i), word_count=1))
        assert kind in CLASSIC


def test_a_kind_the_learner_named_is_honoured_whatever_the_list_size():
    for kind in ("letter", "diary", "story", "a poem"):
        prompt = build_story_prompt("English", "computer", kind, None, random.Random(1), word_count=1)
        assert describe_prompt(prompt)[0] == kind


def test_other_languages_are_unchanged_by_a_short_list():
    kinds = {describe_prompt(build_story_prompt("Spanish", "pan", None, None, random.Random(i), vocab_in_target=True, word_count=2))[0]
             for i in range(200)}
    assert kinds - CLASSIC, "a Spanish learner with two words still gets the richer kinds"
