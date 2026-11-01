"""M6 commit 2: the report Story Studio shows (design section 8).

{rules_version, status, language, structure, vocabulary: {mode, outside, limit}, read_seconds}. What can be checked
depends on the language, so the report says which mode ran: strict (English: at most 5 words outside the list),
scored (other languages with an everyday list, and Japanese, Chinese and Korean with a splitter: words outside the list and the
everyday words are counted, about one in ten allowed), informational (listed, not scored: a difficulty tier was asked for) or
unavailable (Japanese, Chinese or Korean with no splitter installed).
"""
import json

import pytest

from tutor_core import quality, splitter

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


# --- Chinese, Japanese, Korean: scored with the splitter, unavailable without one ------------------------------

JA = "アナ: こんにちは、ともだち。\nベン: こんにちは、みずをください。\nアナ: どうぞ。\nベン: ありがとう。"
needs_splitter = pytest.mark.skipif(not (splitter.available("ja") and splitter.available("zh") and splitter.available("ko")), reason="the [cjk] extras are not installed")


@needs_splitter
def test_japanese_is_scored_like_the_spaced_languages_with_the_splitter():
    r = rep(JA, "ja", ["みず", "ともだち"])
    v = r["vocabulary"]
    assert (v["mode"], v["ok"], v["outside"], v["outside_count"], v["limit"]) == ("scored", True, [], 0, quality.MAX_STRAYS_ENGLISH)
    assert r["status"] == "pass" and r["language"]["ok"] is True and r["rules_version"] == quality.RULES_VERSION == 6


@needs_splitter
def test_chinese_and_korean_list_their_unusual_words_and_a_story_full_of_them_fails():
    zh = rep("今天我在家里。我喝水，吃面包。朋友来了，我们一起看书。窗外下雨了。", "zh", ["水", "面包"])["vocabulary"]
    assert zh["mode"] == "scored" and zh["outside"] == ["窗外"] and zh["outside_count"] == 1 and zh["ok"] is True
    rare = "壁虎爬上穹顶。蝾螈潜入沼泽。獬豸踏过苔藓。貔貅守着祠堂。鲲鹏掠过峡谷。饕餮吞下琥珀。"
    r = rep(rare, "zh", ["水"])
    assert r["vocabulary"]["mode"] == "scored" and r["vocabulary"]["ok"] is False and r["status"] == "fail" and r["vocabulary"]["outside_count"] > r["vocabulary"]["limit"]
    ko = rep("우리 집 앞에 새로운 친구가 있어요.\n친구는 큰 정원에 꽃을 많이 키워요.", "ko", ["집", "친구", "정원", "꽃"])["vocabulary"]
    assert ko["mode"] == "scored" and ko["ok"] is True and ko["outside_count"] <= ko["limit"]


@needs_splitter
def test_a_tier_keeps_chinese_japanese_and_korean_without_the_stray_count():
    from tutor_core import difficulty
    r = quality.report(JA, "ja", ["みず"], difficulty.TIERS["easy"])
    assert r["vocabulary"]["mode"] == "unavailable" and r["vocabulary"]["outside"] is None


def test_without_a_splitter_japanese_checks_script_and_structure_but_not_vocabulary(monkeypatch):
    monkeypatch.setattr(splitter, "split", lambda text, code: None)
    monkeypatch.setattr(splitter, "available", lambda code: False)
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


def test_a_letters_signature_on_its_own_line_is_not_an_unfinished_sentence():
    for letter in ("你好！\n我很好。\n再见，李华", "你好！\n我很好。\n李华", "Dear Ann,\nI am fine.\nCheers, Pierre", "I am fine.\nPierre",
                   "Todo bien.\nCon cariño, Ana", "元気です。\nさようなら、たろう"):
        assert quality.ends_complete(letter), letter
    for cut in ("우리는 집에 갔어요.\n따뜻하게 잠", "Todo bien.\nLuego fuimos al mer", "Ana: Hola.\nBen: Adi", "我很好。\n我们一起去学校读", "Luego fuimos al mer\nPierre", "따뜻하게 잠"):
        assert not quality.ends_complete(cut), cut


def test_a_chinese_letter_with_a_signature_passes_the_shape_check():
    letter = ("亲爱的朋友小明，你好！\n我在房子里修水管，水漏了。\n妈妈帮我拿工具，爸爸在厨房喝咖啡。\n我把桌子搬到花园，椅子在旁边。\n"
              "修好后我们一起吃面包和苹果。\n明天一起去学校读书吧。\n祝你工作顺利，天气有太阳。\n再见，李华")
    r = rep(letter, "zh", ["房子", "水", "面包", "朋友", "妈妈", "爸爸", "桌子", "椅子", "苹果", "咖啡", "花园", "太阳", "工作", "学校", "书"])
    assert r["structure"]["format_ok"] is True and r["structure"]["ok"] is True


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
