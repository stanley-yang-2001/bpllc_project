"""Writer v2, the code-seeded name/place/time, the free stiffness checks and the directive repair (20 Nov 2026). Everything is off unless asked for, so the default prompt and the
default repair are what they were; the model calls here are fakes."""
import random
import sys
from pathlib import Path

import pytest

from tutor_core import difficulty as d
from tutor_core.prompts.builder import build_story_prompt
from tutor_core.story import story_from_words
from tutor_core.story_diagnose import actionable, diagnose, directives, should_repair, signal
from tutor_core.story_options import StoryOptions
from tutor_core.story_repair import repair_story
from tutor_core.story_seed import NAMES, note, pick

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from story_eval import report, rhythm, variants  # noqa: E402

WORDS = ["bread", "shop", "river", "friend", "walk"]
TIER = d.resolve("custom", length=60)
# eight sentences of the same length, three ending on "today"/"now", six opening with "The", one per line: flat rhythm, a repeated opener, filler and layout
FLAT = "\n".join(["The boy walks to the shop today.", "The shop sells fresh bread to him.", "His friend waits near the river now.",
                  "They eat the bread by the water.", "The river is cold and very clear.", "The boy walks home with his friend.",
                  "His mother makes soup for them today.", "The day ends and everyone sleeps."])
MIXED = ("The boy walks to the shop. He wants fresh bread because his friend is waiting by the river. A baker smiles and gives him a warm loaf. "
         "Outside, the morning air is cold. Two boys sit by the water and eat. Then they walk home together, talking about the long day, "
         "and the boy's mother makes soup for all of them. Everyone sleeps well that night.")


def answer(text):
    return "===STORY===\n" + text


# --- the free checks ---------------------------------------------------------------------------------------------------------------------------------------------

def test_a_flat_filler_story_is_flagged_and_a_varied_one_is_not():
    codes = {f["code"] for f in diagnose(FLAT, "en", WORDS)}
    assert {"flat_rhythm", "filler", "one_per_line"} <= codes and should_repair(diagnose(FLAT, "en", WORDS))
    assert diagnose(MIXED, "en", WORDS) == []


def test_the_layout_finding_alone_never_triggers_a_repair():
    one_per_line = "\n".join(MIXED.replace("? ", ". ").split(". "))
    found = diagnose(one_per_line, "en", WORDS)
    assert [f["code"] for f in found] == ["one_per_line"] and actionable(found) == [] and not should_repair(found)


def test_a_dialogue_is_not_judged_by_its_layout_a_short_text_and_an_unspaced_language_are_not_judged_at_all():
    assert "one_per_line" not in {f["code"] for f in diagnose(FLAT, "en", WORDS, "dialogue")}
    assert diagnose("One. Two. Three.", "en") == [] and signal("One. Two.", "en") is None
    assert diagnose("今天天气很好。我们去公园。他们很高兴。我们吃饭。她在家。我们回家。", "zh") == [] and signal("今天天气很好。" * 8, "ja") is None


def test_a_word_the_learner_is_studying_is_not_filler():
    text = FLAT.replace("fresh bread", "fresh bread today")
    with_own = {f["code"] for f in diagnose(text, "en", ["today"])}
    assert "filler" not in with_own and "filler" in {f["code"] for f in diagnose(text, "en", WORDS)}


def test_the_edits_use_the_languages_own_connectors_and_filler_words():
    es = directives([{"code": "flat_rhythm", "sentences": [1, 2], "pairs": [[1, 2]], "detail": ""}, {"code": "filler", "sentences": [1, 2], "detail": ""}], "es")
    assert any("porque" in line for line in es) and any("hoy" in line for line in es) and not any("because" in line for line in es)
    en = directives(diagnose(FLAT, "en", WORDS), "en")
    assert any("because" in line for line in en) and any("paragraphs" in line for line in en) and any("under 20 words" in line for line in en)


def test_the_signal_gives_the_numbers_the_report_shows():
    s = signal(FLAT, "en", WORDS)
    assert s["findings"] == 3 and s["sd"] < 1.0 and s["sentences"] == 8 and 0 < s["opener_share"] <= 1 and "flat_rhythm" in s["codes"]


# --- the seed ---------------------------------------------------------------------------------------------------------------------------------------------------

def test_names_places_and_times_are_drawn_by_code_and_repeat_for_a_seeded_run():
    assert pick("en", "story", random.Random(1)) == pick("en", "story", random.Random(1))
    assert len({tuple(pick("en", "story", random.Random(i))["names"]) for i in range(40)}) > 5
    assert "Maya" not in NAMES["en"] and all(len(v) == len(set(v)) for v in NAMES.values())


def test_a_dialogue_gets_two_names_a_diary_none_and_a_language_without_a_list_none():
    assert len(pick("fr", "dialogue", random.Random(2))["names"]) == 2 and pick("de", "diary", random.Random(2))["names"] == []
    assert pick("ko", "story", random.Random(2))["names"] == [] and "called" not in note("ko", "story", random.Random(2))
    assert "first person" in note("en", "letter", random.Random(2)) and "The main character is called" in note("es", "story", random.Random(2))


# --- the prompt ---------------------------------------------------------------------------------------------------------------------------------------------------

def test_writer_v2_is_off_by_default_so_the_prompt_is_what_it_was():
    a = build_story_prompt("Spanish", "casa, mar", "story", "the sea", random.Random(1), vocab_in_target=True, difficulty=TIER)
    b = build_story_prompt("Spanish", "casa, mar", "story", "the sea", random.Random(1), vocab_in_target=True, difficulty=TIER, writer_v2=False)
    assert a == b and "Setting:" not in a


def test_writer_v2_adds_the_block_with_the_seed_and_no_plan_tags():
    p = build_story_prompt("Spanish", "casa, mar", "story", "the sea", random.Random(1), vocab_in_target=True, writer_v2=True)
    assert "Setting:" in p and "The main character is called" in p and "porque" in p and "paragraphs" in p
    assert "<plan>" not in p and p.rstrip().endswith("then the text.") or "Begin:" in p
    other = build_story_prompt("Spanish", "casa, mar", "story", "the sea", random.Random(1), vocab_in_target=True)
    assert p.index("Setting:") < p.rindex("Begin:") and "Setting:" not in other


def test_a_dialogue_gets_speaker_names_and_no_paragraph_rule():
    p = build_story_prompt("English", "bread, shop", "dialogue", None, random.Random(4), writer_v2=True)
    assert "The two speakers are called" in p and "paragraphs" not in p


def test_writer_v2_reaches_the_story_prompt_through_the_options():
    seen = []
    story_from_words("en", WORDS, lambda p: (seen.append(p), answer(MIXED))[1], story_type="story", difficulty=TIER, options=StoryOptions(writer_v2=True), rng=random.Random(5))
    assert "Setting:" in seen[0]
    seen.clear()
    story_from_words("en", WORDS, lambda p: (seen.append(p), answer(MIXED))[1], story_type="story", difficulty=TIER, rng=random.Random(5))
    assert "Setting:" not in seen[0]


# --- the options ---------------------------------------------------------------------------------------------------------------------------------------------------

def test_the_two_options_are_read_from_the_environment_and_change_the_cache_key():
    o = StoryOptions.from_env({"STORY_WRITER_V2": "1", "STORY_REPAIR_DIRECTIVES": "1"})
    assert o.writer_v2 and o.repair_directives and (("writer_v2",) in o.cache_parts()) and (("repair_directives",) in o.cache_parts())
    assert not StoryOptions.from_env({}).writer_v2 and StoryOptions().cache_parts() == () and StoryOptions(writer_v2=True).normalised().writer_v2


# --- the directive repair ---------------------------------------------------------------------------------------------------------------------------------------

def run_repair(text, rewrite, **kw):
    calls = []

    def call(prompt):
        calls.append(prompt)
        return answer(rewrite)
    out, notes = repair_story(text, "en", WORDS, TIER, "story", call, **kw)
    return out, notes, calls


def test_the_repair_without_directives_leaves_a_story_alone_that_the_score_finds_fine():
    out, notes, calls = run_repair(MIXED, FLAT)
    assert out == MIXED and calls == []


def test_a_flat_story_gets_the_concrete_edits_and_the_better_rewrite_is_kept():
    out, notes, calls = run_repair(FLAT, MIXED, directives=True)
    assert out == MIXED and len(calls) == 1
    assert "Join these neighbouring sentences" in calls[0] and "filler time word" in calls[0]
    assert any("kept (directives)" in n and "findings 3 -> 0" in n for n in notes)


def test_a_rewrite_with_as_many_findings_is_rejected():
    worse = FLAT.replace("fresh ", "")
    out, notes, calls = run_repair(FLAT, worse, directives=True)
    assert out == FLAT and any("rejected (findings not fewer)" in n for n in notes)


def test_a_rewrite_that_drops_the_learners_words_is_rejected():
    no_words = ("The man goes out early. He wants something to eat because he is hungry and the day is long. A woman smiles and gives him a warm cake. "
                "Outside, the morning air is cold. The two of them sit down and eat. Then they go home together, talking about the long day, "
                "and his mother makes soup for all of them. Everyone sleeps well that night.")
    out, notes, calls = run_repair(FLAT, no_words, directives=True)
    assert out == FLAT and any("learner words dropped" in n for n in notes)


def test_a_story_with_one_finding_gets_no_directive_call():
    one = MIXED.replace("Everyone sleeps well that night.", "Everyone sleeps well now.")
    assert not should_repair(diagnose(one, "en", WORDS))
    out, notes, calls = run_repair(one, FLAT, directives=True)
    assert out == one and calls == []


def test_the_directives_reach_the_repair_through_the_pipeline_options():
    prompts = []

    def fake(prompt):
        prompts.append(prompt)
        return answer(MIXED if "meets ALL of these requirements" in prompt else FLAT)
    r = story_from_words("en", WORDS, fake, story_type="story", difficulty=TIER, options=StoryOptions(repair=True, repair_directives=True))
    assert r.text == MIXED and any("Join these neighbouring sentences" in p for p in prompts)
    prompts.clear()
    r = story_from_words("en", WORDS, fake, story_type="story", difficulty=TIER, options=StoryOptions(repair=True))
    assert not any("Join these neighbouring sentences" in p for p in prompts)


# --- the test methods and the report ---------------------------------------------------------------------------------------------------------------------------

def test_the_new_methods_differ_from_their_controls_by_one_thing():
    plan, v2, vd, rd, rr = (variants.BY_NAME[n] for n in ("plan", "v2", "v2_directive", "rr_directive", "review_repair"))
    assert v2.writer_v2 and not plan.writer_v2 and {**v2.as_dict(), "writer_v2": False, "name": "", "label": "", "note": ""} == {**plan.as_dict(), "name": "", "label": "", "note": ""}
    assert rd.repair_directives and {**rd.as_dict(), "repair_directives": False, "name": "", "label": "", "note": ""} == {**rr.as_dict(), "name": "", "label": "", "note": ""}
    assert vd.writer_v2 and vd.repair and vd.repair_directives and not vd.judge
    assert [v.name for v in variants.resolve("v2")] == ["plan", "v2", "v2_directive", "rr_directive"]
    assert all(n in variants.CALLS for n in ("v2", "v2_directive", "rr_directive")) and v2.options().writer_v2 and rd.options().repair_directives


def test_the_report_counts_stiffness_per_method_with_no_model():
    req = {"id": "q1", "code": "en", "words": WORDS, "story_type": "story"}
    flat, mixed = {"ok": True, "text": FLAT}, {"ok": True, "text": MIXED}
    a, b = rhythm.by_method([(req, flat)]), rhythm.by_method([(req, mixed)])
    assert a["mean_findings"] == 3 and a["two_or_more"] == 1 and a["flat"] == 1 and a["filler"] == 1 and b["mean_findings"] == 0 and b["mean_sd"] > a["mean_sd"]
    assert rhythm.by_method([(req, {"ok": False, "text": ""}), (req, None)]) is None
    data = {"variants": [{"name": "x", "label": "Method X"}], "requests": [req]}
    html_ = report._rhythm_table(data, {"x": [(req, flat)]})
    assert "Method X" in html_ and "3.00" in html_ and report._rhythm_table(data, {"x": []}) == ""


def test_v2_rr_is_review_repair_plus_the_block_and_v2_plus_the_review_and_repair():
    rr, v2, v2rr = (variants.BY_NAME[n] for n in ("review_repair", "v2", "v2_rr"))
    skip = {"name": "", "label": "", "note": ""}
    assert {**v2rr.as_dict(), "writer_v2": False, **skip} == {**rr.as_dict(), **skip}
    assert v2rr.writer_v2 and v2rr.judge and v2rr.repair and not v2rr.repair_directives
    assert {**v2rr.as_dict(), "judge": False, "repair": False, **skip} == {**v2.as_dict(), **skip}


# --- outline first (patch 0097) -------------------------------------------------------------------------------------------------------------------------------------

from tutor_core import story_outline  # noqa: E402

OUTLINE = ("1. A boy walks to the shop | words: shop, walk\n2. He buys bread because his friend is hungry | words: bread, friend\n"
           "3. They sit by the river and eat | words: river\n4. They walk home together")


BEATS = ["The boy walks to the shop in the cold morning air.", "He wants fresh bread because his friend is waiting by the river.",
         "Then the two boys sit by the water and eat the warm bread together.", "At last they walk home, talking about the long day, and the boy's mother makes soup."]


def scripted(outline=OUTLINE, text=MIXED, beats=None, fail_beat=None):
    calls = []

    def call(prompt):
        calls.append(prompt)
        if prompt.startswith("Plan a short"):
            return outline
        if "Now write only event" in prompt:
            k = int(prompt.split("Now write only event ")[1].split(" ")[0])
            if k == fail_beat:
                raise RuntimeError("limit")
            return "===STORY===\n" + (beats or BEATS)[k - 1]
        return answer(text)
    return call, calls


def test_the_outline_lines_are_read_and_a_thin_answer_is_not():
    assert len(story_outline.parse_outline(OUTLINE)) == 4
    assert story_outline.parse_outline("1. A boy walks to the shop\n2. He buys bread") == [] and story_outline.parse_outline("") == []
    assert story_outline.parse_outline("Here is the outline:\n- A boy walks to the shop | words: shop\n- He buys bread | words: bread\n* They eat by the river") != []


def test_whole_writes_the_text_from_the_outline_in_two_calls():
    call, calls = scripted()
    r = story_from_words("en", WORDS, call, story_type="story", difficulty=TIER, options=StoryOptions(outline="whole"), rng=random.Random(1))
    assert r.text == MIXED and len(calls) == 2 and calls[0].startswith("Plan a short")
    assert "Follow this outline" in calls[1] and "1. A boy walks to the shop" in calls[1] and calls[1].rstrip().endswith(story_outline._BEGIN) or "Begin:" in calls[1]
    assert any(n.startswith("outline: 4 events, text written from it") for n in r.notes)


def test_beats_writes_one_call_per_event_each_seeing_the_text_so_far():
    call, calls = scripted()
    r = story_from_words("en", WORDS, call, story_type="story", difficulty=TIER, options=StoryOptions(outline="beats"), rng=random.Random(1))
    assert len(calls) == 5 and r.text == " ".join(BEATS)
    assert "Nothing is written yet." in calls[1] and "Text so far:\nThe boy walks to the shop in the cold morning air." in calls[2] and "last event" in calls[4] and "last event" not in calls[3]
    assert any("written one by one" in n for n in r.notes)


def test_a_dialogue_is_written_beat_by_beat_one_line_each():
    call, calls = scripted(beats=["Ana: Hello, Ben. Do you want to walk to the shop with me now?", "Ben: Yes, I do. I want fresh bread for my friend, and the river is near.",
                          "Ana: Good. We can sit by the river and eat the warm bread there together.", "Ben: That is a good plan. Let us walk home after that, and I will make soup."])
    r = story_from_words("en", WORDS, call, story_type="dialogue", difficulty=TIER, options=StoryOptions(outline="beats"), rng=random.Random(1))
    assert r.text.count("\n") == 3 and "speaker's name and a colon" in calls[1]


def test_an_outline_that_cannot_be_read_or_a_failed_step_falls_back_to_the_normal_story():
    call, calls = scripted(outline="Sorry, I cannot.")
    r = story_from_words("en", WORDS, call, story_type="story", difficulty=TIER, options=StoryOptions(outline="whole"), rng=random.Random(1))
    assert r.ok and r.text == MIXED and len(calls) == 2 and any("could not be read" in n for n in r.notes)
    call, calls = scripted(fail_beat=3)
    r = story_from_words("en", WORDS, call, story_type="story", difficulty=TIER, options=StoryOptions(outline="beats"), rng=random.Random(1))
    assert r.ok and r.text == MIXED and any("a step failed" in n for n in r.notes)


def test_outline_off_makes_no_extra_call_and_the_option_is_read_and_cached():
    call, calls = scripted()
    story_from_words("en", WORDS, call, story_type="story", difficulty=TIER, rng=random.Random(1))
    assert len(calls) == 1
    assert StoryOptions.from_env({"STORY_OUTLINE": "Beats"}).outline == "beats" and StoryOptions.from_env({"STORY_OUTLINE": "x"}).outline == ""
    assert ("outline", "whole") in StoryOptions(outline="whole").cache_parts() and StoryOptions(outline="beats").cache_parts() != StoryOptions(outline="whole").cache_parts()
    assert StoryOptions(outline="junk").normalised().outline == ""


def test_the_outline_methods_differ_from_v2_by_the_outline_alone_and_from_each_other_by_the_writing():
    v2, ol, bt = (variants.BY_NAME[n] for n in ("v2", "outline", "beats"))
    skip = {"name": "", "label": "", "note": ""}
    assert {**ol.as_dict(), "outline": "", **skip} == {**v2.as_dict(), **skip} and {**bt.as_dict(), "outline": "whole", **skip} == {**ol.as_dict(), **skip}
    assert ol.options().outline == "whole" and bt.options().outline == "beats" and all(n in variants.CALLS for n in ("outline", "beats"))


# --- spread the words (patch 0098) ---------------------------------------------------------------------------------------------------------------------------------

from tutor_core.prompts.builder import _SPREAD  # noqa: E402


def test_the_spread_sentence_is_off_by_default_and_comes_before_the_final_instruction_when_on():
    args = ("Spanish", "casa, mar", "story", "the sea", random.Random(1))
    off = build_story_prompt(*args, vocab_in_target=True, difficulty=TIER)
    on = build_story_prompt(*args, vocab_in_target=True, difficulty=TIER, spread=True)
    assert _SPREAD not in off and _SPREAD in on and on.index(_SPREAD) < on.rindex("Begin:") and on.replace(_SPREAD + "\n\n", "") == off


def test_spread_is_separate_from_writer_v2_so_each_can_be_measured_alone():
    def build(**kw):                       # a fresh rng each time: the name, place and time are drawn from it
        return build_story_prompt("Spanish", "casa, mar", "story", "the sea", random.Random(1), vocab_in_target=True, difficulty=TIER, **kw)
    v2, both, alone = build(writer_v2=True), build(writer_v2=True, spread=True), build(spread=True)
    assert _SPREAD not in v2 and both.replace(_SPREAD + "\n\n", "") == v2 and "Setting:" not in alone and _SPREAD in alone


def test_spread_reaches_the_prompt_through_the_options_and_the_environment():
    seen = []
    story_from_words("en", WORDS, lambda p: (seen.append(p), answer(MIXED))[1], story_type="story", difficulty=TIER, options=StoryOptions(spread=True), rng=random.Random(5))
    assert _SPREAD in seen[0]
    o = StoryOptions.from_env({"STORY_SPREAD_WORDS": "1"})
    assert o.spread and not StoryOptions.from_env({}).spread and ("spread",) in o.cache_parts() and StoryOptions().cache_parts() == ()
    assert StoryOptions(spread=True, outline="beats").normalised() == StoryOptions(spread=True, outline="beats")      # the last two fields keep their place


def test_v2_spread_is_v2_plus_the_sentence_and_nothing_else():
    v2, sp = variants.BY_NAME["v2"], variants.BY_NAME["v2_spread"]
    skip = {"name": "", "label": "", "note": ""}
    assert sp.spread and not v2.spread and {**sp.as_dict(), "spread": False, **skip} == {**v2.as_dict(), **skip}
    assert sp.options().spread and sp.options().writer_v2 and sp.options().outline == "" and "v2_spread" in variants.CALLS


def test_v2_b_is_v2_made_again_and_the_report_reads_the_gap_as_noise():
    v2, again = variants.BY_NAME["v2"], variants.BY_NAME["v2_b"]
    skip = {"name", "label", "note", "replicate_of"}
    assert {k: v for k, v in again.as_dict().items() if k not in skip} == {k: v for k, v in v2.as_dict().items() if k not in skip}
    assert again.options() == v2.options() and again.replicate_of == "v2" and v2.replicate_of is None and variants.CALLS["v2_b"] == variants.CALLS["v2"]
    assert [x.name for x in variants.resolve("=v2,v2_b")] == ["v2", "v2_b"]      # "v2" alone is a group of four methods; "=v2" is the method
    req = {"id": "q1", "code": "en", "words": WORDS, "story_type": "story"}
    entry = {"ok": True, "text": "x", "audit_scores": {"gpt": {"failed": [], "gated": None}, "qwen": {"failed": [], "gated": None}}}
    data = {"variants": [{"name": "v2", "label": "V2", "replicate_of": None}, {"name": "v2_b", "label": "V2 again", "replicate_of": "v2"}], "requests": [req]}
    notes = report._noise_notes(data, {"v2": [(req, entry)], "v2_b": [(req, entry)]})
    assert len(notes) == 1 and "V2 again is V2 made again" in notes[0] and "noise" in notes[0]


def test_the_report_shows_where_the_learners_words_sit_in_the_text():
    early = "bread shop river friend walk. " + "The day is long and the sky is grey over the town. " * 6
    even = "The boy walks to the shop. " + "The sky is grey over the town and it is cold. " * 2 + "He eats bread. " + "The air is cold over the town. " * 2 + "His friend waits by the river."
    assert rhythm.first_third(early, WORDS, "en") == 1.0 and 0.0 < rhythm.first_third(even, WORDS, "en") < 0.7
    assert rhythm.first_third("The sky is grey.", WORDS, "en") is None and rhythm.first_third("今日は天気がいいです。" * 5, ["天気", "今日", "いい"], "ja") is None
    req = {"id": "q1", "code": "en", "words": WORDS, "story_type": "story"}
    b = rhythm.by_method([(req, {"ok": True, "text": early + FLAT})])
    assert b["first_third"] == 1.0
    html_ = report._rhythm_table({"variants": [{"name": "x", "label": "X"}], "requests": [req]}, {"x": [(req, {"ok": True, "text": early + FLAT})]})
    assert "100%" in html_ and "first third" in html_


def test_a_focus_list_replaces_the_learners_list_but_never_adds_a_word(monkeypatch):
    from tutor_core import story as story_module
    seen = {}
    monkeypatch.setattr(story_module, "load_words", lambda conn, learner, language, set_ids=None: ["apple", "bread", "cheese", "dog", "egg"])
    monkeypatch.setattr(story_module, "_write_story", lambda req, words, *a, **k: seen.setdefault("words", list(words)))
    request = story_module.StoryRequest(1, "en", None, None, None, None, None, False, story_module.StoryOptions().normalised(), ("egg", "zebra", "apple"))
    story_module._make_story(object(), request, None, None)
    assert seen["words"] == ["egg", "apple"]                                       # the caller's order; "zebra" is not the learner's, so it is dropped
    assert story_module.StoryRequest(1, "en").cache_key() != story_module.StoryRequest(1, "en", focus_words=("egg",)).cache_key()
