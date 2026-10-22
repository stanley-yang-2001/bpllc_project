"""A learner's own-language word list must not make a correct story look English (22 Oct 2026: German batch, 14 of 15 called 'mixed')."""
from tutor_core.quality import check_passage, rescore_results

GERMAN_VOCAB = "Haus, Wasser, Brot, Freund, Mutter, Vater, Buch, Schule, Katze, Hund, Tisch, Stuhl, Apfel, Milch, Kaffee"
GERMAN_STORY = ("Anna: Ich brauche Brot.\nBen: Warum hast du kein Brot?\nAnna: Mein Freund hat Brot nicht.\n"
                "Ben: Ich gebe dir Brot vom Tisch.\nAnna: Danke, das ist nett.\nBen: Wir essen Brot nach Schule.")


def test_the_old_way_called_a_german_story_mixed():
    r = check_passage(GERMAN_STORY, GERMAN_VOCAB, check_vocab=False, language="German")
    assert r["language_check"]["verdict"] == "mixed"          # the vocabulary was counted as English markers


def test_a_german_story_with_a_german_list_passes_the_language_check():
    r = check_passage(GERMAN_STORY, GERMAN_VOCAB, check_vocab=False, language="German", vocab_in_target=True)
    assert r["language_check"]["ok"] and r["language_check"]["verdict"] == "ok"


def test_a_story_that_is_really_english_still_fails_with_a_german_list():
    english = "I need bread. Why do you have no bread? My friend has no bread. I give you bread from the table. Thank you, that is nice."
    r = check_passage(english, GERMAN_VOCAB, check_vocab=False, language="German", vocab_in_target=True)
    assert r["language_check"]["verdict"] in ("english", "mixed") and not r["passed"]


def test_rescoring_a_per_language_file_uses_the_target_list_for_other_languages():
    data = {"vocabularies": {"German": GERMAN_VOCAB}, "vocabulary": GERMAN_VOCAB,
            "results": {"German": [{"text": GERMAN_STORY}]}}
    assert rescore_results(data)["German"][0]["language_check"]["ok"]


def test_rescoring_an_old_file_with_one_english_list_is_unchanged():
    data = {"vocabulary": "water, bread", "results": {"Spanish": [{"text": "I want water and bread. Please give me water. Thank you."}]}}
    assert rescore_results(data)["Spanish"][0]["language_check"]["verdict"] == "english"
