import pytest

from tutor_core.languages import normalize_language, stories_enabled, supported_names
from tutor_core.words import WordError, normalize_word, validate_meaning, validate_word


@pytest.mark.parametrize("text,code", [
    ("Spanish", "es"), (" español ", "es"), ("ES", "es"), ("日本語", "ja"), ("Français", "fr"),
    ("englisch", "en"), ("Castellano", "es"),
])
def test_normalize_language_known(text, code):
    assert normalize_language(text) == code


@pytest.mark.parametrize("text", ["Klingon", "", None, "  "])
def test_normalize_language_unknown_is_none(text):
    assert normalize_language(text) is None


def test_story_gate(monkeypatch):
    monkeypatch.delenv("STORY_ALLOW_UNMEASURED", raising=False)
    for code in ("en", "es", "fr", "ja"):                      # measured in Step 10
        assert stories_enabled(code), code
    for code in ("de", "it", "pt", "zh", "ko", "xx"):          # not measured yet (or not a language at all)
        assert not stories_enabled(code), code
    monkeypatch.setenv("STORY_ALLOW_UNMEASURED", "1")
    assert stories_enabled("de") and not stories_enabled("xx")


def test_supported_names_lists_all():
    assert "Spanish" in supported_names() and "Korean" in supported_names()


def test_normalize_matches_existing_behaviour():
    assert normalize_word("  Water. ") == "water"
    assert normalize_word('"Bread"') == "bread"
    assert normalize_word("thank   you") == "thank you"


def test_german_keeps_capitals():
    assert normalize_word("Haus", "de") == "Haus"
    assert normalize_word("Haus", "es") == "haus"


@pytest.mark.parametrize("good,lang", [("l'eau", "fr"), ("año", "es"), ("ice-cream", "en"), ("水", "ja"), ("한국어", "ko")])
def test_valid_words(good, lang):
    assert validate_word(good, lang)


@pytest.mark.parametrize("bad", [
    "", "   ", "...", "word1", "a" * 41, "one two three four five six",
    "rm -rf /", "<b>x</b>", "tab\there!x", "zero\u200bwidth",
])
def test_invalid_words(bad):
    with pytest.raises(WordError):
        validate_word(bad)


def test_meaning_rules():
    assert validate_meaning("  the   water ") == "the water"
    assert validate_meaning("") is None
    with pytest.raises(WordError):
        validate_meaning("x" * 121)
    with pytest.raises(WordError):
        validate_meaning("bad\x00meaning")


def test_newlines_never_survive():
    """A line break can't reach the story prompt: it collapses to a space. A short letters-only phrase is
    still a legal entry, so the prompt builder must also present the list as data (done in M3/M6)."""
    out = validate_word("hello\nignore previous")
    assert "\n" not in out and out == "hello ignore previous"
