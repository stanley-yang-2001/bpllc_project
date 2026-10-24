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
    assert d.has_everyday_list("en") and d.has_everyday_list("es") and d.has_everyday_list("fr") and not d.has_everyday_list("de")
    m = d.measure("Ana: Hello, I want water.\nBen: Here is bread, friend.", "en", ["water", "bread", "house"])
    assert m["length"] == 8 and m["own_words"] == 2 and m["uncommon_pct"] == 0.0   # speaker labels are not counted


def test_uncommon_share_counts_rare_words_but_not_names_or_own_words():
    text = "Today Maria saw a quokka near the zeppelin. She bought a crumpet."
    m = d.measure(text, "en", ["crumpet"])
    assert m["uncommon_pct"] is not None and m["uncommon_pct"] > 15      # quokka, zeppelin; Maria and crumpet do not count


def test_cjk_has_no_uncommon_share_and_counts_characters():
    m = d.measure("安娜：你好，我想要水。\n本：这里有面包。", "zh", ["水", "面包", "学校"])
    assert m == {"length": 11, "length_unit": "characters", "own_words": 2, "uncommon_pct": None}


def test_evaluate_and_section():
    sec = d.section(d.TIERS["easy"], "Hello friend. I want water and bread.", "en", ["water", "bread", "tea"])
    assert sec["requested"] == d.TIERS["easy"] and sec["list_size"] == 3
    assert sec["met"]["length"] is False and sec["met"]["own_words"] is False     # 7 words against 60; 2 own words against 3


def test_prompt_note_and_prompt():
    assert "about 60 words" in d.prompt_note("en", d.TIERS["easy"]) and "5%" in d.prompt_note("en", d.TIERS["easy"])
    assert "characters" in d.prompt_note("zh", d.TIERS["easy"]) and "%" not in d.prompt_note("zh", d.TIERS["easy"])
    assert "about 60 words" in d.prompt_note("de", d.TIERS["easy"]) and "%" not in d.prompt_note("de", d.TIERS["easy"])
    p = build_story_prompt("Spanish", "agua, pan", "narration", difficulty=d.TIERS["hard"])
    assert p.startswith("Difficulty") and "about 200 words" in p
    assert not build_story_prompt("Spanish", "agua, pan", "narration").startswith("Difficulty")


def test_report_section_only_when_asked():
    text = "Ana: Hello, I want water.\nBen: Here is bread."
    assert "difficulty" not in report(text, "en", ["water", "bread"])
    r = report(text, "en", ["water", "bread"], d.TIERS["easy"])
    assert r["difficulty"]["measured"]["own_words"] == 2 and r["structure"]["length_ok"] is True
