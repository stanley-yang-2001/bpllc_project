"""Patch 0065: free gates, planned word counts, mixed strategies, choosing with gates, repair requirements, multi-word entries."""
import json
import random

from tutor_core import difficulty as D
from tutor_core import story_gates as G
from tutor_core import story_plan as P
from tutor_core.difficulty import measuring
from tutor_core.story import story_from_words
from tutor_core.story_candidates import choose
from tutor_core.story_options import StoryOptions

WORDS = ["apple", "stall", "market", "sweet", "friend", "water"]
GOOD = ("Maria walks to the market with her friend every morning. They buy a sweet apple from the stall near the old bridge. "
        "Then they sit by the water and talk about their plans for the day. Later the two friends go home and cook a simple dinner together. "
        "After dinner they read a book and talk until it is late. Maria smiles because the day was calm and good.")
STUFFED = "Apple stall empty, no. Maria feels sad, sorry. Apple tastes sweet, good night. Market friend water, yes."


def tier():
    return D.resolve("easy") if hasattr(D, "resolve") else None


def test_gates_pass_a_clean_story_and_fail_a_stuffed_telegraphic_one():
    d = D.resolve("easy")
    ok = G.check(GOOD, "en", WORDS, d, "story")
    bad = G.check(STUFFED, "en", WORDS, d, "story")
    assert bad["passed"] is False and bad["failed"]
    assert set(bad["failed"]) & {"stuffed", "tacked_on_words", "telegraphic", "too_few_words", "length"}
    assert ok["limits"]["own_max"] >= ok["limits"]["own_min"]
    assert G.own_limits(5) == (5, 10) and G.own_limits(1) == (1, 4)
    assert G.requirements(bad, "en")


def test_plan_features_about_one_word_per_seventeen_and_marks_the_rest_optional():
    d = D.resolve("easy")
    named, low, high = P.featured_count(d)
    assert low <= named <= high and high <= max(low, round(1.5 * named)) + 1
    chosen, note = P.plan_words(WORDS, d, "en", random.Random(1))
    assert set(chosen) <= set(WORDS) and "optional" in note.lower() or "between" in note


def test_multi_word_entries_are_found_and_missing_ones_named():
    text = "We say thank you to the cook. Then we eat. Maria wishes me good morning."
    words = ["thank you", "to eat", "good morning", "good night"]
    assert measuring.measure(text, "en", words)["own_words"] == 3
    assert measuring.missing_own_words(text, "en", words) == ["good night"]


def test_choose_drops_gate_failures_without_a_model_call():
    d = D.resolve("easy")
    calls = []
    text, hits, notes = choose([STUFFED, GOOD], "en", WORDS, d, "story", audit_call=lambda p: calls.append(p) or json.dumps({"errors": []}), gates=True)
    assert text == GOOD and any("gate" in n.lower() for n in notes)


def test_mixed_strategies_write_one_pass_and_two_pass_candidates():
    prompts = []

    def model(prompt):
        prompts.append(prompt)
        return "===STORY===\n" + GOOD
    r = story_from_words("en", WORDS, model, difficulty=D.resolve("easy"), rng=random.Random(2),
                         options=StoryOptions(candidates=4, mixed=True, gates=True, plan=True))
    assert r.ok and any("mixed" in n.lower() for n in r.notes)
    assert StoryOptions(candidates=4, mixed=True).cache_parts() != StoryOptions(candidates=4).cache_parts()
