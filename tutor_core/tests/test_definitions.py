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


def test_the_modes_pick_the_languages_and_both_never_repeats_one_language():
    assert d.meaning_languages("native", "fr", "es") == ["fr"]
    assert d.meaning_languages("study", "fr", "es") == ["es"]
    assert d.meaning_languages("both", "fr", "es") == ["fr", "es"]
    assert d.meaning_languages("both", "es", "es") == ["es"]
    assert d.meaning_languages("anything else", "fr", "es") == ["fr"]


def test_a_meaning_in_the_study_language_asks_for_simple_words_without_the_word_itself():
    p = d.build_prompt(["casa"], "Spanish", "Spanish")
    assert "simple everyday Spanish words" in p and "without using the word itself" in p
    assert "simple everyday" not in d.build_prompt(["casa"], "Spanish", "English")


def test_two_languages_are_asked_for_in_order_with_a_shorter_limit_each():
    p = d.build_prompt(["casa"], "Spanish", ["English", "Spanish"])
    assert "in English, then ` / `, then the same meaning in Spanish" in p and f"at most {d.MAX_MEANING_CHARS // 3} characters for each" in p
    assert d.parse("casa | a house / un lugar donde vive la gente", ["casa"]) == {"casa": "a house / un lugar donde vive la gente"}
