"""Where the learner's words stand in a text: the reader's matcher (tutor_core.story_gloss)."""
import pytest

from tutor_core import splitter, story_gloss
from tutor_core.difficulty import measuring
from tutor_core.story_gloss import Span, find


def shown(text, spans):
    return [(text[s.start:s.end], s.word_id) for s in spans]


def test_english_forms_are_found_with_true_positions():
    text = "She walked home. The dogs were running."
    spans = find(text, "en", [(1, "walk"), (2, "dog"), (3, "run")])
    assert shown(text, spans) == [("walked", 1), ("dogs", 2), ("running", 3)]
    assert spans[0] == Span(4, 10, 1)


def test_to_verb_entry_matches_the_verb_forms():
    text = "He went. They are going. Go now."
    assert shown(text, find(text, "en", [(7, "to go")])) == [("went", 7), ("going", 7), ("Go", 7)]


def test_an_irregular_form_the_score_does_not_know_is_not_underlined_either():
    """The score's list of irregular verbs has seven (go, see, say, give, get, take, come): "ate" is not counted for "eat", so it is not underlined."""
    text = "He ate. They are eating."
    assert shown(text, find(text, "en", [(7, "to eat")])) == [("eating", 7)]
    assert measuring._own_found("He ate.", "en", ["to eat"]) == 0


def test_irregular_forms():
    text = "We went home and she goes out."
    assert shown(text, find(text, "en", [(1, "go")])) == [("went", 1), ("goes", 1)]


def test_a_phrase_is_its_words_side_by_side_and_not_across_a_sentence():
    text = "Good morning, Ana. Good. Morning came."
    spans = find(text, "en", [(1, "good morning")])
    assert shown(text, spans) == [("Good morning", 1)]


def test_the_longer_span_wins_where_they_overlap():
    text = "Good morning to you. That is good."
    spans = find(text, "en", [(1, "good"), (2, "good morning")])
    assert shown(text, spans) == [("Good morning", 2), ("good", 1)]


def test_case_and_apostrophes():
    text = "Don't stop. DON'T."
    assert shown(text, find(text, "en", [(1, "don't")])) == [("Don't", 1), ("DON'T", 1)]


def test_other_spaced_languages_need_the_written_form_like_the_score():
    text = "Los perros corren. El perro duerme."
    assert shown(text, find(text, "es", [(1, "perro")])) == [("perro", 1)]          # "perros" is not counted by the score either


def test_offsets_are_into_the_text_as_given_even_when_lowercasing_changes_its_length():
    text = "Eine Straße und die STRASSE, Straße!"            # "Straße" lowercases to the longer "strasse": a whole-text copy would shift every later offset
    spans = find(text, "de", [(1, "straße")])
    assert shown(text, spans) == [("Straße", 1), ("STRASSE", 1), ("Straße", 1)]
    assert spans[2].start == text.rindex("Straße")


def test_empty_inputs():
    assert find("", "en", [(1, "dog")]) == []
    assert find("A dog.", "en", []) == []
    assert find("A dog.", "en", [(1, "  "), (2, "")]) == []


def test_the_first_word_with_a_form_keeps_it():
    text = "She saw it."
    assert [s.word_id for s in find(text, "en", [(5, "see"), (9, "saw")])] == [5]


def tokens(*rows):
    return [splitter.Token(*r) for r in rows]


JA = tokens(("私", "私", True), ("は", "は", False), ("毎日", "毎日", True), ("りんご", "りんご", True), ("を", "を", False),
            ("食べ", "食べる", True), ("ます", "ます", False), ("。", "。", False))
JA_TEXT = "私は毎日りんごを食べます。"


def test_japanese_by_surface_by_dictionary_form_and_by_joining_pieces(monkeypatch):
    monkeypatch.setattr(story_gloss.splitter, "split", lambda text, code: JA)
    both = find(JA_TEXT, "ja", [(1, "りんご"), (2, "食べる"), (3, "食べます"), (4, "毎日")])
    # 食べ is the dictionary form 食べる (id 2), and 食べ+ます joined is 食べます (id 3): same start, the longer one stays
    assert shown(JA_TEXT, both) == [("毎日", 4), ("りんご", 1), ("食べます", 3)]
    assert shown(JA_TEXT, find(JA_TEXT, "ja", [(2, "食べる")])) == [("食べ", 2)]


def test_a_speaker_label_is_not_story_text_for_chinese(monkeypatch):
    text = "小明：你好吗？"
    seen = {}

    def fake(masked, code):
        seen["masked"] = masked
        return tokens(("你好", "你好", True), ("吗", "吗", False), ("？", "？", False))

    monkeypatch.setattr(story_gloss.splitter, "split", fake)
    assert find(text, "zh", [(1, "小明"), (2, "你好")]) == [Span(3, 5, 2)]
    assert len(seen["masked"]) == len(text) and seen["masked"].startswith("   ")


def test_with_no_splitter_the_word_is_looked_for_anywhere(monkeypatch):
    monkeypatch.setattr(story_gloss.splitter, "split", lambda text, code: None)
    text = "我喜欢苹果。苹果很好吃。"
    assert find(text, "zh", [(1, "苹果")]) == [Span(3, 5, 1), Span(6, 8, 1)]


CASES = [
    ("She walked home. The dogs were running.", "en", ["walk", "dog", "run", "cat"]),
    ("He ate. They are eating. Eat well.", "en", ["to eat", "to drink"]),
    ("Good morning, Ana. Thank you very much.", "en", ["good morning", "thank you", "good night"]),
    ("Los perros corren. El perro duerme.", "es", ["perro", "gato", "dormir"]),
    ("Das Haus ist groß. Ich gehe nach Hause.", "de", ["Haus", "Hause", "groß", "Auto"]),
]


@pytest.mark.parametrize("text,code,words", CASES)
def test_the_words_found_are_the_words_the_story_score_counts(text, code, words):
    """What the reader underlines is what the report counts as used (difficulty.measuring._own_found, one word at a time)."""
    pairs = list(enumerate(words, start=1))
    underlined = {s.word_id for s in find(text, code, pairs)}
    counted = {i for i, w in pairs if measuring._own_found(text, code, [w]) == 1}
    assert underlined == counted
