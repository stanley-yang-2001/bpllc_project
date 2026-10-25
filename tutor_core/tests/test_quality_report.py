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
        lines[i % 4] = lines[i % 4].rstrip(".") + f" {w}."
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


def test_a_spanish_story_in_spanish_passes_and_counts_its_words_outside_the_list():
    r = rep(ES, "es", ES_VOCAB)
    v = r["vocabulary"]
    assert r["status"] == "pass" and v["mode"] == "scored" and v["limit"] == 5 and v["ok"] is True
    assert v["outside"] and v["outside_count"] == len(v["outside"])            # zepelín (rules version 4: counted, up to a tenth of the words)
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


def test_one_heading_above_a_narration_is_not_a_speaker():
    diary = "Montag Morgen: Ich stehe früh auf.\nIch trinke Wasser und esse Brot.\nDann gehe ich mit meinem Freund zum Markt.\nWir kaufen Obst und Gemüse.\nAm Abend lese ich einen Brief."
    r = quality.report(diary, "de", ["Wasser", "Brot"])
    assert r["structure"]["style"] == "narration" and r["structure"]["format_ok"] is True
    assert quality.report("Ana: Hola.\nLuis: Adiós.\nAna: Hasta luego.\nLuis: Chao.", "es", ["hola"])["structure"]["style"] == "dialogue"


def test_a_story_cut_off_mid_word_does_not_have_the_right_shape():
    cut = "Ana: Hello, friend.\nBen: Hello, water please.\nAna: Thank you.\nBen: Goodbye, fri"
    r = rep(cut)
    assert r["structure"]["format_ok"] is False and r["status"] == "fail"
    assert quality.ends_complete('He said "yes."') and quality.ends_complete("끝났어요.") and quality.ends_complete("おわり。")
    assert not quality.ends_complete("따뜻하게 잠") and not quality.ends_complete("")


def test_spanish_with_many_rare_words_fails_in_scored_mode_but_a_tier_keeps_it_informational():
    rare = ("Ana: Hola, amigo.\nLuis: El zepelín, la pangolina, el ocarina y el trebuchet vuelan.\n"
            "Ana: El marmota, el quokka y el gazebo son raros.\nLuis: Adiós, Ana.")
    r = rep(rare, "es", ES_VOCAB)
    assert r["vocabulary"]["mode"] == "scored" and r["vocabulary"]["ok"] is False and r["status"] == "fail"
    from tutor_core import difficulty
    assert quality.report(rare, "es", ES_VOCAB, difficulty.TIERS["easy"])["vocabulary"]["mode"] == "informational"
    assert rep(JA, "ja", ["みず"])["vocabulary"]["mode"] == "unavailable"            # no scored mode without a splitter-based rule


def test_very_short_english_does_not_pass_as_a_latin_script_language():
    for lang in ("es", "fr", "de", "it", "pt"):
        r = quality.language_check("Hello my friend, I want some water, thank you very much.", {"es": "Spanish", "fr": "French", "de": "German", "it": "Italian", "pt": "Portuguese"}[lang])
        assert r["ok"] is False and r["verdict"] in ("english", "mixed"), lang
    assert quality.language_check("Hola amigo, quiero agua, gracias por todo.", "Spanish")["ok"] is True
    assert quality.language_check("Bonjour mon ami, je veux de l'eau, merci beaucoup.", "French")["ok"] is True
    assert quality.language_check("Hallo mein Freund, ich möchte Wasser, vielen Dank.", "German")["ok"] is True
    assert quality.language_check("Ciao amico mio, voglio acqua, grazie mille.", "Italian")["ok"] is True
    assert quality.language_check("Olá meu amigo, eu quero água, muito obrigado.", "Portuguese")["ok"] is True
    assert quality.language_check("Hello, friend.", "English")["verdict"] == "not_checked"


def test_a_sentence_that_stops_after_an_article_or_conjunction_is_caught():
    for code, bad, good in (("es", "Luego hablamos sobre el jardín tranquilo y.", "Luego hablamos sobre el jardín tranquilo."),
                            ("fr", "Je me suis réveillé très tôt dans le.", "Je me suis réveillé très tôt."),
                            ("en", "We walked to the market and.", "We walked to the market.")):
        assert quality.has_dangling_sentence(bad, code) and not quality.has_dangling_sentence(good, code)
    assert not quality.has_dangling_sentence("今日は天気がいい。", "ja") and not quality.has_dangling_sentence("Ana: Hola.", "xx")


def test_a_dangling_sentence_fails_the_shape_check_in_the_report():
    text = "Hola Ana.\nHoy voy al mercado con mi amigo y.\nCompro pan y agua.\nLuego vuelvo a mi casa.\nMañana veo el río."
    r = quality.report(text, "es", ["pan", "agua"])
    assert r["structure"]["format_ok"] is False and r["status"] == "fail"


def test_a_story_cut_off_mid_word_is_not_complete():
    assert quality.ends_complete("그리고 우리는 웃었어요.") and not quality.ends_complete("집에 도착해서 창문을 열고 따뜻하게 잠")
    assert quality.ends_complete('She said "hello."')
