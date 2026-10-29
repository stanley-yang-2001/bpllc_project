"""The starter packs: every pack exists in every language, every word is one the app would accept, nothing repeats."""
import pytest

from tutor_core import starter
from tutor_core.languages import LANGUAGES
from tutor_core.words import validate_word

LANGS = sorted(LANGUAGES)


def test_there_are_four_packs_and_every_language_has_all_of_them():
    assert starter.pack_ids() == ["basics", "food", "people", "numbers"]
    for lang in LANGS:
        assert starter.has_packs(lang), lang
        for pack in starter.pack_ids():
            assert len(starter.pack_words(pack, lang)) == 12, (lang, pack)


@pytest.mark.parametrize("lang", LANGS)
def test_every_word_is_valid_as_written_and_nothing_repeats(lang):
    seen = []
    for pack in starter.pack_ids():
        for word, _ in starter.pack_words(pack, lang):
            assert validate_word(word, lang) == (word if lang == "de" else word.lower()), (lang, word)
            seen.append(validate_word(word, lang))
    assert len(seen) == len(set(seen)), [w for w in seen if seen.count(w) > 1]


def test_glosses_are_english_except_for_english_itself():
    assert starter.pack_words("basics", "es")[0] == ("hola", "hello")
    assert starter.pack_words("food", "ja")[-1] == ("飲む", "to drink")
    assert all(g is None for _, g in starter.pack_words("basics", "en"))
    assert [w for w, _ in starter.pack_words("numbers", "en")][:3] == ["one", "two", "three"]


def test_unknown_pack_or_language_is_empty():
    assert starter.pack_words("nope", "es") == [] and starter.pack_words("basics", "xx") == []
    assert not starter.has_packs("xx")
