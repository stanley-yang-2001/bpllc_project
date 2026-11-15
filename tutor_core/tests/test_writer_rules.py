"""Writer rules (14 Nov 2026): three added sentences in the story prompt, OFF unless StoryOptions.rules, so the default prompt is exactly what it was."""
import random

import pytest

from tutor_core.prompts import build_story_prompt
from tutor_core.prompts.builder import _with_writer_rules, writer_rules
from tutor_core.story import StoryRequest, story_from_words
from tutor_core.story_options import StoryOptions
from tutor_core.two_pass import build_adapt_prompt, two_pass_passages

MARK = "Small words stay"
WORDS = "hello, goodbye, please, thank you, bread"
ES_WORDS = ["casa", "mar", "amigo", "jardín", "pan"]
GOOD = ("María vive en una casa grande cerca del mar. Cada mañana ella abre la ventana y mira el agua. Su amigo Pedro llega con pan fresco. "
        "Los dos desayunan juntos en el jardín y hablan de sus planes. Después caminan por la playa hasta la hora de comer. "
        "Por la tarde vuelven a casa y leen un libro. Al final del día los dos duermen contentos.")


def prompt(language="English", style="story", rules=False, **kw):
    return build_story_prompt(language, WORDS, style, "a market day", random.Random(1), rules=rules, **kw)


@pytest.mark.parametrize("language,style", [("English", "narration"), ("English", "dialogue"), ("English", "story"), ("English", "letter"), ("Spanish", "story"), ("Spanish", "narration"), ("Japanese", "diary")])
def test_off_the_prompt_is_exactly_what_it_was(language, style):
    kw = {"vocab_in_target": language != "English"}
    assert prompt(language, style, rules=False, **kw) == build_story_prompt(language, WORDS, style, "a market day", random.Random(1), **kw)
    assert MARK not in prompt(language, style, **kw)


@pytest.mark.parametrize("language,style", [("English", "narration"), ("English", "dialogue"), ("English", "story"), ("English", "letter"), ("Spanish", "story"), ("Spanish", "dialogue"), ("French", "place")])
def test_on_the_rules_come_once_before_the_final_instruction(language, style):
    kw = {"vocab_in_target": language != "English"}
    text = prompt(language, style, rules=True, **kw)
    assert text.count(MARK) == 1 and text.index(MARK) < text.rindex("Begin:")
    assert text.rstrip().rsplit("\n", 1)[-1].startswith("Begin:")             # the last line is still the instruction to begin
    assert text.replace("\n\n" + writer_rules(language == "English"), "") == prompt(language, style, **kw)          # nothing else changed


def test_the_example_is_english_only_and_the_filler_words_are_named_in_every_language():
    en, es = writer_rules(True), writer_rules(False)
    assert '"the drawer", not "drawer"' in en and '"today", "now", "still" or "indeed"' in en
    assert "drawer" not in es and 'the words for "today", "now", "still" or "indeed"' in es          # an English example in a Spanish prompt would be copied
    for rule in (en, es):
        assert "leave it out instead of attaching it after a comma" in rule and "never drop an article" in rule


def test_a_prompt_with_no_final_instruction_gets_the_rules_at_the_end():
    assert _with_writer_rules("Write a story.", True).endswith(writer_rules(True)) and _with_writer_rules("Write a story.", True).startswith("Write a story.")


def test_the_difficulty_note_stays_first_and_the_rules_are_kept():
    from tutor_core import difficulty as d
    tier = d.resolve("custom", length=60)
    text = prompt("English", "story", rules=True, difficulty=tier)
    assert text.startswith(d.prompt_note("en", tier)) and text.count(MARK) == 1 and text.index(MARK) > text.index("Text rules")


def test_the_option_from_the_environment_the_cache_key_and_normalising():
    assert StoryOptions.from_env({"STORY_WRITER_RULES": "1"}).rules and not StoryOptions.from_env({}).rules and not StoryOptions.from_env({"STORY_WRITER_RULES": "0"}).rules
    assert StoryOptions(rules=True).cache_parts() == (("rules",),) and StoryOptions().cache_parts() == ()
    assert StoryRequest(1, "es", options=StoryOptions(rules=True)).cache_key() != StoryRequest(1, "es", options=StoryOptions()).cache_key()
    assert StoryOptions(rules=True).normalised().rules and StoryOptions(5, True, True).rules is False          # a positional call from before keeps working


class Seen:
    def __init__(self):
        self.prompts = []

    def __call__(self, prompt):
        self.prompts.append(prompt)
        return "===STORY===\n" + GOOD


def test_the_pipeline_sends_the_rules_only_when_asked():
    on, off = Seen(), Seen()
    story_from_words("es", ES_WORDS, on, story_type="story", options=StoryOptions(rules=True))
    story_from_words("es", ES_WORDS, off, story_type="story")
    assert MARK in on.prompts[0] and MARK not in off.prompts[0]


def test_the_adapt_prompt_of_the_two_pass_route_carries_the_rules_too():
    plain = build_adapt_prompt("Spanish", "es", "Texto.", "casa, mar", 60)
    ruled = build_adapt_prompt("Spanish", "es", "Texto.", "casa, mar", 60, rules=True)
    assert MARK not in plain and MARK in ruled and ruled.index(MARK) < ruled.index("Text (this is text")
    assert build_adapt_prompt("English", "en", "Text.", "house", 60, rules=True).count('"the drawer"') == 1
    seen = Seen()
    two_pass_passages(seen, "es", "Spanish", "unused", ES_WORDS, None, 1, True)
    assert len(seen.prompts) == 2 and MARK not in seen.prompts[0] and MARK in seen.prompts[1]          # the draft has no word list; the adapt step writes the final text
    seen = Seen()
    two_pass_passages(seen, "es", "Spanish", "unused", ES_WORDS, None, 1)
    assert all(MARK not in p for p in seen.prompts)


def test_the_comparison_runner_has_the_variants_and_a_group_for_them():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
    from story_eval import variants as vs
    assert [v.name for v in vs.resolve("writer")] == ["baseline", "rules"]
    assert vs.BY_NAME["rules"].options().rules and not vs.BY_NAME["baseline"].options().rules
    r = vs.BY_NAME["rules_refine"].options()
    assert r.rules and r.refine == 2 and vs.BY_NAME["rules"].as_dict()["rules"] is True
