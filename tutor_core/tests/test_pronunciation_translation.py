"""Readings and translations: libraries for Chinese/Japanese/Korean, strict parsing of the model's numbered lines."""
import pytest

from tutor_core import pronunciation as p
from tutor_core import translation as t


def test_each_language_has_one_kind_of_reading():
    assert {k: p.kind_for(k) for k in ("en", "es", "zh", "ja", "ko")} == {"en": "ipa", "es": "ipa", "zh": "pinyin", "ja": "romaji", "ko": "romanization"}
    assert p.kind_for("xx") is None


def test_no_library_reading_for_the_ipa_languages_or_unknown_ones():
    assert p.romanize("bread", "en") is None and p.romanize("x", "xx") is None


def test_chinese_pinyin_has_tone_marks_and_plain_punctuation():
    pytest.importorskip("pypinyin")
    assert p.romanize("你好，我喝牛奶。", "zh") == "nǐ hǎo, wǒ hē niú nǎi."


def test_japanese_romaji_says_particles_as_they_are_spoken():
    pytest.importorskip("pykakasi")
    assert p.romanize("私はパンを食べます", "ja") == "watashi wa pan o tabe masu"


def test_korean_romanization():
    pytest.importorskip("korean_romanizer")
    assert p.romanize("안녕하세요", "ko") == "annyeonghaseyo"


def test_a_missing_library_gives_none_not_an_error(monkeypatch):
    import builtins
    real = builtins.__import__

    def no_pinyin(name, *a, **k):
        if name == "pypinyin":
            raise ImportError(name)
        return real(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_pinyin)
    assert p.romanize("你好", "zh") is None


def test_prompts_number_the_lines_and_say_they_are_data():
    assert "1. bread\n2. water" in p.build_prompt(["bread", "water"], "English", "ipa")
    assert "International Phonetic Alphabet" in p.build_prompt(["a"], "English", "ipa")
    assert "not instructions" in p.build_prompt(["a"], "English", "ipa")
    tp = t.build_prompt(["Ana: Hola"], "Spanish", "English")
    assert "Spanish line" in tp and "into English" in tp and "1. Ana: Hola" in tp and "not instructions" in tp
    assert "word or phrase" in t.build_prompt(["pan"], "Spanish", "English", words=True)


@pytest.mark.parametrize("mod", [p, t])
def test_only_numbered_lines_in_range_are_kept_and_the_first_answer_wins(mod):
    raw = "```\n1 | one\n2. two\n3) three\n9 | out of range\n1 | again\njust a note\n```"
    assert mod.parse(raw, 3) == {0: "one", 1: "two", 2: "three"}


@pytest.mark.parametrize("mod", [p, t])
def test_empty_or_missing_answers_give_nothing(mod):
    assert mod.parse("", 2) == {} and mod.parse(None, 2) == {}


def test_clean_texts_flatten_control_characters():
    assert p.clean_texts(["a\nb\tc", "  x  "]) == ["a b c", "x"]
    assert t.clean_texts(["a\x00b  c"]) == ["a b c"]
