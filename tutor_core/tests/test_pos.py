from tutor_core import pos
from tutor_core.languages import LANGUAGES


def test_every_language_has_a_list_with_phrase_and_no_repeats():
    assert set(pos.CATEGORIES) == set(LANGUAGES)
    for lang, cats in pos.CATEGORIES.items():
        assert "phrase" in cats and len(cats) == len(set(cats)) and "noun" in cats and "verb" in cats, lang
        assert all(c in pos._MEANING for c in cats), lang


def test_each_language_follows_its_own_rules():
    assert "adjective_i" in pos.categories("ja") and "adjective_na" in pos.categories("ja") and "adjective" not in pos.categories("ja")
    assert "measure_word" in pos.categories("zh") and "measure_word" in pos.categories("ko") and "measure_word" not in pos.categories("en")
    assert "determiner" in pos.categories("en") and "article" not in pos.categories("en")
    assert "article" in pos.categories("de") and "article" in pos.categories("es") and "determiner" not in pos.categories("fr")
    assert pos.categories("xx") == () and not pos.valid("xx", "noun")
    assert pos.valid("en", "verb") and not pos.valid("en", "adjective_i") and not pos.valid("ja", "adjective")


def test_prompt_lists_only_this_languages_codes_and_the_words():
    p = pos.build_prompt(["run", "red"], "en", "English")
    assert "determiner" in p and "adjective_i" not in p and "run\nred" in p and "word | code" in p
    ja = pos.build_prompt(["高い"], "ja", "Japanese")
    assert "adjective_i" in ja and "adjective_na" in ja and "determiner" not in ja and "measure_word" in ja


def test_parse_keeps_valid_codes_for_asked_words_only():
    raw = "```\nrun | verb\n1. red | Adjective\nthe | determiner\nfoo | noun\nrun | noun\nblue | adjective_i\ncat → noun\n```"
    assert pos.parse(raw, ["run", "red", "the", "blue", "cat"], "en") == {"run": "verb", "red": "adjective", "the": "determiner", "cat": "noun"}


def test_parse_accepts_spaces_or_hyphens_and_ignores_junk():
    assert pos.parse("高い | adjective-i\n静か | adjective na\n水 | stuff", ["高い", "静か", "水"], "ja") == {"高い": "adjective_i", "静か": "adjective_na"}
    assert pos.parse("", ["a"], "en") == {} and pos.parse(None, ["a"], "en") == {}
