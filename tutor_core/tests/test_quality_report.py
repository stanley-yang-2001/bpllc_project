"""M6 commit 2: the report Story Studio shows (design section 8).

{rules_version, status, language, structure, vocabulary: {mode, outside, limit}, read_seconds}. What can be checked
depends on the language, so the report says which mode ran: strict (English: at most 5 words outside the list),
informational (other space-delimited languages: listed, not scored) or unavailable (Japanese, Chinese, Korean).
"""
import json

import pytest

from tutor_core import quality

VOCAB = ["hello", "goodbye", "please", "thank you", "water", "friend", "house", "today"]
DIALOGUE = "Ana: Hello, friend.\nBen: Hello, water please.\nAna: Thank you.\nBen: Goodbye, friend."
KEYS = {"rules_version", "status", "language", "structure", "vocabulary", "read_seconds"}


def rep(text, language="en", vocab=VOCAB):
    return quality.report(text, language, vocab)


# --- shape ---------------------------------------------------------------------------------------------

def test_the_report_has_exactly_the_documented_keys_and_is_plain_json():
    r = rep(DIALOGUE)
    assert set(r) == KEYS and r["rules_version"] == quality.RULES_VERSION
    assert json.loads(json.dumps(r)) == r
    assert set(r["structure"]) == {"ok", "style", "units", "length_ok", "format_ok", "leaked_plan"}
    assert set(r["vocabulary"]) == {"mode", "ok", "outside", "outside_count", "limit"}
    assert set(r["language"]) == {"requested", "ok", "verdict"}


def test_an_unknown_language_is_a_caller_bug():
    with pytest.raises(ValueError):
        rep(DIALOGUE, "xx")


# --- English: strict -----------------------------------------------------------------------------------

def test_a_clean_english_dialogue_passes_in_strict_mode():
    r = rep(DIALOGUE)
    assert r["status"] == "pass" and r["vocabulary"]["mode"] == "strict" and r["vocabulary"]["limit"] == 5
    assert r["vocabulary"]["ok"] is True and r["vocabulary"]["outside"] == [] and r["structure"]["style"] == "dialogue"
    assert r["language"] == {"requested": "en", "ok": True, "verdict": "not_checked"}


def stray_dialogue(n):
    words = ["zeppelin", "quokka", "gazebo", "ocarina", "pangolin", "trebuchet", "marmoset"][:n]     # rare on purpose: everyday words are not strays
    lines = ["Ana: Hello, friend.", "Ben: Please, water.", "Ana: Thank you.", "Ben: Goodbye."]
    for i, w in enumerate(words):
        lines[i % 4] += f" {w}"
    return "\n".join(lines)


def test_five_strays_pass_and_six_fail():
    five, six = rep(stray_dialogue(5)), rep(stray_dialogue(6))
    assert five["status"] == "pass" and five["vocabulary"]["outside_count"] == 5 and five["vocabulary"]["ok"] is True
    assert six["status"] == "fail" and six["vocabulary"]["outside_count"] == 6 and six["vocabulary"]["ok"] is False
    assert "trebuchet" in six["vocabulary"]["outside"] or "ocarina" in six["vocabulary"]["outside"]


def test_too_short_a_passage_fails_on_structure_not_vocabulary():
    r = rep("Ana: Hello, friend.\nBen: Goodbye.")
    assert r["status"] == "fail" and r["structure"]["length_ok"] is False and r["structure"]["ok"] is False
    assert r["vocabulary"]["ok"] is True


def test_a_leaked_plan_fails():
    r = rep("Characters: Ana and Ben\n" + DIALOGUE)
    assert r["status"] == "fail" and r["structure"]["leaked_plan"] is True


def test_an_empty_passage_fails_cleanly():
    r = rep("   ")
    assert r["status"] == "fail" and r["structure"]["ok"] is False and r["vocabulary"]["outside"] is None
    assert r["read_seconds"] >= 1 and set(r) == KEYS


# --- other space-delimited languages: informational ------------------------------------------------------

ES_VOCAB = ["hola", "agua", "amigo", "casa", "gracias", "adiós", "hoy"]
ES = "Ana: Hola, amigo.\nLuis: Hola, agua, zepelín.\nAna: Gracias, amigo.\nLuis: Adiós, Ana."


def test_a_spanish_story_in_spanish_passes_and_lists_words_without_scoring_them():
    r = rep(ES, "es", ES_VOCAB)
    v = r["vocabulary"]
    assert r["status"] == "pass" and v["mode"] == "informational" and v["limit"] is None and v["ok"] is None
    assert v["outside"] and v["outside_count"] == len(v["outside"])            # listed (zepelín), not a failure
    assert r["language"]["ok"] is True and r["language"]["verdict"] == "ok"


def test_the_learners_own_spanish_words_do_not_make_a_spanish_story_look_english():
    """language_check treats the learner's words as English markers; with per-language lists that would call a Spanish
    story made of the learner's Spanish words 'english'. The report therefore checks language without the list."""
    r = rep("Ana: Hola, amigo.\nLuis: Hola, agua.\nAna: Gracias, casa.\nLuis: Adiós, hoy.", "es", ES_VOCAB)
    assert r["language"]["ok"] is True and r["status"] == "pass"


def test_an_english_story_requested_in_spanish_fails_on_language():
    r = rep("Ana: Hello, my friend.\nBen: Hello, I want some water.\nAna: Here you are.\nBen: Thank you very much.", "es", ES_VOCAB)
    assert r["status"] == "fail" and r["language"]["ok"] is False and r["language"]["verdict"] in ("english", "mixed")


# --- Tier 2: unavailable ---------------------------------------------------------------------------------

JA = "アナ: こんにちは、ともだち。\nベン: こんにちは、みずをください。\nアナ: どうぞ。\nベン: ありがとう。"


def test_japanese_checks_script_and_structure_but_not_vocabulary():
    r = rep(JA, "ja", ["みず", "ともだち"])
    v = r["vocabulary"]
    assert (v["mode"], v["ok"], v["outside"], v["outside_count"], v["limit"]) == ("unavailable", None, None, 0, None)
    assert r["status"] == "pass" and r["language"]["ok"] is True


def test_japanese_requested_but_english_returned_fails():
    r = rep(DIALOGUE, "ja", ["みず"])
    assert r["status"] == "fail" and r["language"]["verdict"] == "wrong_script"


# --- read time -------------------------------------------------------------------------------------------

def test_read_time_is_words_over_two_rounded_up_never_zero():
    text = "\n".join(f"Ana: " + " ".join(["hello"] * 5) for _ in range(5))      # 25 words
    assert rep(text)["read_seconds"] == 13
    assert rep("hi")["read_seconds"] == 1


def test_japanese_read_time_comes_from_the_letters_because_there_are_no_spaces():
    letters = sum(1 for ch in "".join(ln.partition(":")[2] for ln in JA.splitlines()) if ch.isalpha())
    expected = -(-letters // 4)                      # letters / 2 per word, / 2 words per second, rounded up
    assert rep(JA, "ja", ["みず"])["read_seconds"] == expected and expected > 3


def test_everyday_words_outside_the_list_are_not_strays():
    text = "Ana: Hello, I want water.\nBen: My friend works at the bakery and finished early.\nAna: Thank you.\nBen: Goodbye."
    r = rep(text, "en", ["water", "bread"])
    assert r["vocabulary"]["outside_count"] <= 2 and r["status"] == "pass"            # friend, works, finished: everyday
    rare = rep("Ana: Hello, I want water.\nBen: A quokka rides a zeppelin to the gazebo with an ocarina and pangolin and marmoset.\nAna: Thank you.\nBen: Goodbye.", "en", ["water"])
    assert rare["vocabulary"]["outside_count"] >= 6 and rare["status"] == "fail"
