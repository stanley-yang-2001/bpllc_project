"""English stories with no kind named are narration or dialogue only; richer kinds only when the learner names one."""
import random

import pytest

from tutor_core import prompts
from tutor_core.prompts import ALL_STORY_TYPES, VALID_STYLES, build_story_prompt, choose_story_type, describe_prompt

CLASSIC = set(VALID_STYLES)


@pytest.fixture(autouse=True)
def fresh_topics():
    prompts._RECENT_TOPICS.clear()


def test_classic_only_draws_just_the_two_classic_styles():
    rng = random.Random(7)
    assert {choose_story_type(rng, classic_only=True) for _ in range(600)} == CLASSIC


def test_both_classic_styles_still_appear():
    kinds = [choose_story_type(random.Random(i), classic_only=True) for i in range(200)]
    assert kinds.count("narration") > 20 and kinds.count("dialogue") > 20


def test_by_default_every_kind_is_still_drawn():
    rng = random.Random(7)
    assert {choose_story_type(rng) for _ in range(600)} == set(ALL_STORY_TYPES)


def test_a_random_english_prompt_is_always_classic():
    for i in range(80):
        kind, _ = describe_prompt(build_story_prompt("English", "computer, bear, tree", None, None, random.Random(i)))
        assert kind in CLASSIC


def test_a_kind_the_learner_named_is_honoured_for_english():
    for kind in ("letter", "diary", "story", "a poem"):
        prompt = build_story_prompt("English", "computer", kind, None, random.Random(1))
        assert describe_prompt(prompt)[0] == kind


def test_other_languages_still_get_the_richer_kinds():
    kinds = {describe_prompt(build_story_prompt("Spanish", "pan", None, None, random.Random(i), vocab_in_target=True))[0]
             for i in range(200)}
    assert kinds - CLASSIC
