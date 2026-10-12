"""The Add Word normalisation cases from tests/test_add_word_normalization.py (M3), against the one shared rule
(tutor_core.words) that the API, the CSV upload and the Add Word tool now all use."""
import pytest

from tutor_core.words import WordError, normalize_word, validate_word


@pytest.mark.parametrize("raw, expected", [
    ("water", "water"), ("  water \n", "water"), ("Water", "water"), ("thank   you", "thank you"), ("bread.", "bread"),
    ('"bread"', "bread"), ("\u201cbread\u201d", "bread"), ("(bread)", "bread"), ("Don't", "don't"), ("well-known", "well-known"),
    ("\u00d1and\u00fa", "\u00f1and\u00fa"), ("\u65e5\u672c\u8a9e", "\u65e5\u672c\u8a9e"),
])
def test_the_original_normalisation_cases(raw, expected):
    assert normalize_word(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", "...", '""', None])
def test_a_word_that_is_empty_after_normalising_is_rejected(raw):
    with pytest.raises(WordError):
        validate_word(raw)


def test_case_and_punctuation_variants_are_one_word():
    assert {validate_word(w) for w in ("Water", "water", "  WATER. ")} == {"water"}
    assert validate_word("Thank   You") == "thank you"
