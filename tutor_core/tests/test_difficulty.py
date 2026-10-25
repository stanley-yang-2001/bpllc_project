import pytest

from tutor_core import difficulty as d
from tutor_core.prompts import build_story_prompt
from tutor_core.quality import report


def test_resolve_presets_and_custom():
    assert d.resolve(None) is None and d.resolve("any") is None
    assert d.resolve("Easy") == {"tier": "easy", "length": 60, "own_words": 3, "uncommon_pct": 5}
    assert d.resolve("custom", length=90) == {"tier": "custom", "length": 90, "own_words": 5, "uncommon_pct": 10}


@pytest.mark.parametrize("args", [("easy", 50), ("custom", 10), ("custom", 401), ("custom", "90"), ("custom", True), ("nope",), (None, 50)])
def test_resolve_rejects(args):
    with pytest.raises(ValueError):
        d.resolve(*args)


def test_resolve_rejects_other_fields():
    with pytest.raises(ValueError):
        d.resolve("custom", own_words=0)
    with pytest.raises(ValueError):
        d.resolve("custom", uncommon_pct=51)


def test_measure_english_and_lists():
    assert all(d.has_everyday_list(c) for c in ("en", "es", "fr", "de", "it", "pt", "ja", "zh", "ko"))
    m = d.measure("Ana: Hello, I want water.\nBen: Here is bread, friend.", "en", ["water", "bread", "house"])
    assert m["length"] == 8 and m["own_words"] == 2 and m["uncommon_pct"] == 0.0   # speaker labels are not counted


def test_uncommon_share_counts_rare_words_but_not_names_or_own_words():
    text = "Today Maria saw a quokka near the zeppelin. She bought a crumpet."
    m = d.measure(text, "en", ["crumpet"])
    assert m["uncommon_pct"] is not None and m["uncommon_pct"] > 15      # quokka, zeppelin; Maria and crumpet do not count


def test_chinese_is_split_into_words_when_a_splitter_is_installed():
    pytest.importorskip("rjieba")
    m = d.measure("安娜：你好，我想要水。\n本：这里有面包。", "zh", ["水", "面包", "学校"])
    assert m["length"] == 11 and m["length_unit"] == "characters" and m["own_words"] == 2
    assert m["uncommon_pct"] == 0.0
    rare = d.measure("我在蜃景里看见一只貔貅。", "zh", [])
    assert rare["uncommon_pct"] > 20


def test_a_one_character_own_word_is_not_found_inside_a_longer_word():
    pytest.importorskip("rjieba")
    assert d.measure("我喜欢面包。", "zh", ["面"])["own_words"] == 0         # 面 is only part of 面包
    assert d.measure("我喜欢面包。", "zh", ["面包"])["own_words"] == 1


def test_japanese_and_korean_are_split_into_words_when_installed():
    pytest.importorskip("janome")
    ja = d.measure("私は友達と公園でパンを食べました。", "ja", ["パン", "食べる"])
    assert ja["own_words"] == 2 and ja["uncommon_pct"] is not None                  # 食べました is found as 食べる
    pytest.importorskip("kiwipiepy")
    ko = d.measure("나는 친구와 공원에서 빵을 먹었습니다.", "ko", ["빵", "먹다"])
    assert ko["own_words"] == 2 and ko["uncommon_pct"] is not None                  # 빵을 is found as 빵


def test_without_a_splitter_the_old_character_matching_still_works(monkeypatch):
    monkeypatch.setattr(d.splitter, "split", lambda text, code: None)
    monkeypatch.setattr(d.splitter, "available", lambda code: False)
    m = d.measure("安娜：你好，我想要水。\n本：这里有面包。", "zh", ["水", "面包"])
    assert m["own_words"] == 2 and m["uncommon_pct"] is None
    assert "%" not in d.prompt_note("zh", d.TIERS["easy"])


def test_evaluate_and_section():
    sec = d.section(d.TIERS["easy"], "Hello friend. I want water and bread.", "en", ["water", "bread", "tea"])
    assert sec["requested"] == d.TIERS["easy"] and sec["list_size"] == 3
    assert sec["met"]["length"] is False and sec["met"]["own_words"] is False     # 7 words against 60; 2 own words against 3


def test_prompt_note_and_prompt():
    assert "about 60 words" in d.prompt_note("en", d.TIERS["easy"]) and "5%" in d.prompt_note("en", d.TIERS["easy"])
    assert "characters" in d.prompt_note("zh", d.TIERS["easy"])
    assert "about 60 words" in d.prompt_note("de", d.TIERS["easy"]) and "5%" in d.prompt_note("de", d.TIERS["easy"])
    p = build_story_prompt("Spanish", "agua, pan", "narration", difficulty=d.TIERS["hard"])
    assert p.startswith("Difficulty") and "about 200 words" in p
    assert not build_story_prompt("Spanish", "agua, pan", "narration").startswith("Difficulty")


def test_report_section_only_when_asked():
    text = "Ana: Hello, I want water.\nBen: Here is bread."
    assert "difficulty" not in report(text, "en", ["water", "bread"])
    r = report(text, "en", ["water", "bread"], d.TIERS["easy"])
    assert r["difficulty"]["measured"]["own_words"] == 2 and r["structure"]["length_ok"] is True


def test_a_tier_replaces_the_template_sentence_count_and_the_strict_stray_rule():
    p = build_story_prompt("English", "water, bread", "narration", difficulty=d.TIERS["hard"])
    assert "aim for about 20 sentences" in p and "5 to 6" not in p
    d_ = build_story_prompt("English", "water, bread", "dialogue", difficulty=d.TIERS["easy"])
    assert "Aim for about 6 lines" in d_
    text = "Ana: Hello, I want water.\nBen: My friend works at the bakery and finished early."
    plain = report(text, "en", ["water", "bread"])
    tier = report(text, "en", ["water", "bread"], d.TIERS["medium"])
    assert plain["vocabulary"]["mode"] == "strict" and tier["vocabulary"]["mode"] == "informational"
    assert tier["vocabulary"]["ok"] is None
    assert tier["status"] == "fail" and tier["difficulty"]["met"]["length"] is False       # two lines is far from 110 words: needs a look (rules version 3)
    assert report(text, "en", ["water", "bread"], d.resolve("custom", length=20, own_words=1, uncommon_pct=50))["difficulty"]["met"]["own_words"] is True


def test_a_missed_own_word_target_needs_a_look():
    text = "Ana: Hello, I want water.\nBen: Here is bread and cheese for you today.\nAna: Thank you, my friend.\nBen: You are welcome."
    r = report(text, "en", ["water", "bread", "cheese", "milk", "apple"], d.resolve("custom", length=20, own_words=5, uncommon_pct=50))
    assert r["difficulty"]["met"]["own_words"] is False and r["status"] == "fail"


def test_a_chunk_the_splitter_keeps_whole_is_not_unusual_when_its_parts_are_everyday():
    pytest.importorskip("rjieba")
    text = "今天，孩子和朋友一起去海边。爸爸和妈妈在车上等他们。海水很清，太阳很暖。朋友笑着喝牛奶，玩水。回家路上，大家一起说今天很开心。"
    assert d.measure(text, "zh", ["孩子"])["uncommon_pct"] < 6
    assert d._covered("喝牛奶", d._everyday("zh")) and not d._covered("蜥蜴", d._everyday("zh"))


def test_verb_forms_count_as_everyday_when_a_lemmatizer_is_installed(monkeypatch):
    pytest.importorskip("simplemma")
    text = "Caminé y respiré. Lavé el coche."
    with_lemmas = d.measure(text, "es", [])["uncommon_pct"]
    monkeypatch.setattr(d, "_lemma", lambda word, code: word)
    assert with_lemmas < d.measure(text, "es", [])["uncommon_pct"]


def test_chinese_japanese_and_korean_prompts_state_the_size_per_sentence_and_in_all():
    zh = build_story_prompt("Chinese (Simplified)", "水, 朋友", "narration", difficulty=d.TIERS["easy"])
    assert "about 16 characters each, about 96 characters in all" in zh
    ko = build_story_prompt("Korean", "물, 친구", "narration", difficulty=d.TIERS["hard"])
    assert "about 10 words each, about 300 words in all" in ko
    assert "in all" not in build_story_prompt("English", "water, bread", "narration", difficulty=d.TIERS["hard"]).split("Difficulty")[1].split("\n\n", 1)[1]


def test_the_prompt_asks_for_more_where_the_model_is_known_to_fall_short_but_the_target_stays():
    assert [d.ask_size("en", n) for n in (60, 110, 200)] == [60, 110, 200]
    assert d.ask_size("zh", 110) == 132 and d.ask_size("zh", 200) == 260 and d.ask_size("zh", 60) == 60
    assert d.ask_size("ja", 110) == 110 and d.ask_size("ja", 200) == 260 and d.ask_size("ko", 110) == 110 and d.ask_size("ko", 200) == 300
    assert "about 416 characters" in d.prompt_note("zh", d.TIERS["hard"])
    assert d.resolve("hard")["length"] == 200            # what the report judges against is unchanged


def test_target_language_stories_end_with_the_story_and_get_a_grammar_rule_but_english_is_unchanged():
    ko = build_story_prompt("Korean", "물, 친구", "narration", vocab_in_target=True)
    assert "no thanks, goodbye, notes or translation" in ko and ko.index("re-read it once for grammar") < ko.index("Begin:")
    assert "re-read it once" not in build_story_prompt("English", "water, bread", "narration", vocab_in_target=True)
    assert "re-read it once" not in build_story_prompt("Korean", "물, 친구", "narration")
