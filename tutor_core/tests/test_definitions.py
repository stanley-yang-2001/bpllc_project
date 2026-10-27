"""Meanings written by the model: the prompt carries only the learner's validated words, and the answer is parsed strictly."""
from tutor_core import definitions as d


def test_the_prompt_lists_each_word_on_its_own_line_and_says_the_form():
    p = d.build_prompt(["casa", "agua"], "Spanish", "English")
    assert "Entries:\ncasa\nagua\n" in p and "word | meaning" in p and "in English" in p and "Spanish word" in p


def test_only_lines_for_the_asked_words_are_used():
    raw = "casa | a house\nagua | water\nextra | not asked for\nnonsense line\n```\n"
    assert d.parse(raw, ["casa", "agua", "pan"]) == {"casa": "a house", "agua": "water"}


def test_numbering_bullets_bold_and_arrows_are_tolerated():
    raw = "1. **casa** | a house\n- agua → water\n3) Pan | bread"
    assert d.parse(raw, ["casa", "agua", "pan"]) == {"casa": "a house", "agua": "water", "pan": "bread"}


def test_a_meaning_that_is_too_long_empty_or_the_word_itself_is_dropped_and_the_first_answer_wins():
    raw = f"casa | {'x' * 200}\nagua | agua\npan | bread\npan | something else"
    assert d.parse(raw, ["casa", "agua", "pan"]) == {"pan": "bread"}


def test_nothing_comes_back_from_an_empty_or_missing_answer():
    assert d.parse("", ["casa"]) == {} and d.parse(None, ["casa"]) == {}
