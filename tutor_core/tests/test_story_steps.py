"""The optional quality steps with a fake model: several candidates, the judge, the targeted repair and the level wording (7 Nov 2026).

The fake answers by the kind of prompt it receives, so each test says exactly what the model "writes" at each step."""
import json

import pytest

from tutor_core import difficulty as d
from tutor_core.story import StoryRequest, story_from_words
from tutor_core.story_options import StoryOptions

WORDS = ["casa", "mar", "amigo", "jardín", "pan"]
GOOD = ("María vive en una casa grande cerca del mar. Cada mañana ella abre la ventana y mira el agua. Su amigo Pedro llega con pan fresco. "
        "Los dos desayunan juntos en el jardín y hablan de sus planes. Después caminan por la playa hasta la hora de comer. "
        "Por la tarde vuelven a casa y leen un libro. Al final del día los dos duermen contentos.")
BAD_ARTICLE = GOOD.replace("una casa", "un casa")
SHORT = "María vive cerca del mar. Su amigo llega con pan."
TIER = d.resolve("custom", length=60)


def answer(text):
    return "===STORY===\n" + text


class Fake:
    """kind of prompt -> list of answers, used in order (the last one repeats)."""

    def __init__(self, story=(GOOD,), repair=(), audit=()):
        self.queues = {"story": list(story), "repair": list(repair), "audit": list(audit)}
        self.seen = []

    def __call__(self, prompt):
        kind = "audit" if "Find the mistakes that a careful native speaker" in prompt else "repair" if "meets ALL of these requirements" in prompt else "story"
        self.seen.append(kind)
        q = self.queues[kind]
        item = q.pop(0) if len(q) > 1 else q[0]
        return item if kind == "audit" else answer(item)


def test_everything_off_is_one_call_and_no_notes():
    fake = Fake()
    result = story_from_words("es", WORDS, fake, story_type="story", difficulty=TIER)
    assert result.ok and fake.seen == ["story"] and result.notes == ()


def test_options_from_env_and_cache_key():
    assert StoryOptions.from_env({}) == StoryOptions()
    o = StoryOptions.from_env({"STORY_CANDIDATES": "9", "STORY_JUDGE": "1", "STORY_REPAIR": "1"})
    assert o == StoryOptions(5, True, True)
    assert StoryOptions.from_env({"STORY_CANDIDATES": "x"}).candidates == 1
    base = StoryRequest(1, "es").cache_key()
    assert StoryRequest(1, "es", options=StoryOptions()).cache_key() == base
    assert StoryRequest(1, "es", options=StoryOptions(3)).cache_key() != base


def test_candidates_keep_the_highest_scoring_text():
    fake = Fake(story=[SHORT, BAD_ARTICLE, GOOD])
    result = story_from_words("es", WORDS, fake, story_type="story", difficulty=TIER, options=StoryOptions(candidates=3))
    assert fake.seen[:3] == ["story"] * 3 and result.text == GOOD
    assert result.notes[0].startswith("3 candidates") and "chose #3" in result.notes[-1]


def test_a_failed_extra_candidate_does_not_fail_the_story():
    calls = {"n": 0}

    def flaky(prompt):
        calls["n"] += 1
        if calls["n"] > 1:
            raise RuntimeError("429")
        return answer(GOOD)

    result = story_from_words("es", WORDS, flaky, story_type="story", difficulty=TIER, options=StoryOptions(candidates=3))
    assert result.ok and result.text == GOOD


def test_the_first_call_failing_is_still_a_failed_story():
    def boom(prompt):
        raise RuntimeError("down")

    result = story_from_words("es", WORDS, boom, story_type="story", difficulty=TIER, options=StoryOptions(candidates=3))
    assert not result.ok and result.reason == "failed"


def test_the_judge_can_overturn_the_offline_order():
    # offline both read the same except one article; the judge finds a real mistake in the first, which the rules cannot see
    first = GOOD
    second = GOOD.replace("Su amigo Pedro llega", "Su amigo Pedro viene")
    review = json.dumps({"errors": [{"wrong": "Cada mañana ella abre", "right": "Cada mañana ella abría", "type": "verb", "why": "tense"}]})
    fake = Fake(story=[first, second], audit=[review, '{"errors": []}'])
    result = story_from_words("es", WORDS, fake, story_type="story", difficulty=TIER, options=StoryOptions(candidates=2, judge=True))
    assert result.text == second and fake.seen.count("audit") == 2 and any("judge reviewed" in n for n in result.notes)


def test_repair_names_the_missing_requirement_and_keeps_a_better_text():
    fake = Fake(story=[SHORT], repair=[GOOD])
    result = story_from_words("es", WORDS, fake, story_type="story", difficulty=TIER, options=StoryOptions(repair=True))
    assert result.text == GOOD and "repair" in fake.seen
    assert any("kept" in n for n in result.notes)


def test_repair_prompt_lists_length_and_missing_words():
    from tutor_core.quality import score_story
    from tutor_core.story_repair import requirements
    r = score_story(SHORT, "es", WORDS, TIER, "story")
    reqs = requirements(r, SHORT, "es", WORDS, TIER, "story")
    joined = " ".join(reqs)
    assert "between 54 and 66 words" in joined
    r2 = score_story(GOOD, "es", ["zapato", "lluvia", "reloj", "casa"], TIER, "story")
    assert "zapato" in " ".join(requirements(r2, GOOD, "es", ["zapato", "lluvia", "reloj", "casa"], TIER, "story"))


def test_a_repair_that_does_not_help_is_rejected_and_the_text_stays():
    fake = Fake(story=[SHORT], repair=[SHORT])
    result = story_from_words("es", WORDS, fake, story_type="story", difficulty=TIER, options=StoryOptions(repair=True))
    assert result.text == SHORT and any("rejected" in n for n in result.notes)
    assert fake.seen.count("repair") == 1                      # it stops at the first rewrite that does not raise the score


def test_a_repair_that_writes_the_wrong_language_is_rejected():
    english = ("Mary lives in a big house near the sea. Every morning she opens the window and looks at the water. Her friend Peter comes "
               "with fresh bread. They eat together in the garden and talk about the day. Later they walk along the beach.")
    fake = Fake(story=[SHORT], repair=[english])
    assert story_from_words("es", WORDS, fake, story_type="story", difficulty=TIER, options=StoryOptions(repair=True)).text == SHORT


def test_certain_mistakes_are_fixed_without_a_model_call():
    flawed = GOOD.replace("Su amigo Pedro llega con pan fresco", "Su amigo Pedro llega a el parque con pan fresco")
    fake = Fake(story=[flawed])
    result = story_from_words("es", WORDS, fake, story_type="story", difficulty=TIER, options=StoryOptions(repair=True))
    assert "a el parque" not in result.text and "al parque" in result.text and "repair" not in fake.seen


def test_repair_failure_keeps_the_story():
    calls = []

    def fake(prompt):
        calls.append(prompt)
        if "meets ALL of these requirements" in prompt:
            raise RuntimeError("429")
        return answer(SHORT)

    result = story_from_words("es", WORDS, fake, story_type="story", difficulty=TIER, options=StoryOptions(repair=True))
    assert result.ok and result.text == SHORT and any("failed" in n for n in result.notes)


def test_two_pass_with_candidates_drafts_once(monkeypatch):
    from tutor_core.two_pass import two_pass_passages
    calls = []

    def fake(prompt):
        calls.append("draft" if "Length: about" in prompt else "adapt")
        return answer(GOOD)

    out = two_pass_passages(fake, "es", "Spanish", "Write a story", WORDS, TIER, 3)
    assert calls == ["draft", "adapt", "adapt", "adapt"] and len(out) == 3


def test_the_draft_names_the_tier_level_when_the_range_prompt_is_on(monkeypatch):
    from tutor_core.difficulty.note import LEVELS
    from tutor_core.two_pass import two_pass_passages
    seen = []
    monkeypatch.setenv("STORY_RANGE_PROMPT", "1")
    two_pass_passages(lambda p: seen.append(p) or answer(GOOD), "es", "Spanish", "Write a story", WORDS, d.resolve("easy"), 1)
    assert LEVELS["easy"] in seen[0]
    seen.clear()
    monkeypatch.setenv("STORY_RANGE_PROMPT", "0")
    two_pass_passages(lambda p: seen.append(p) or answer(GOOD), "es", "Spanish", "Write a story", WORDS, d.resolve("easy"), 1)
    assert "Level: beginner (A1 to A2)" in seen[0]


def test_missing_words_and_uncommon_words_helpers():
    assert d.missing_own_words(GOOD, "es", ["casa", "zapato", "pan", "reloj"]) == ["zapato", "reloj"]
    text = "María vive en una casa. Su amigo lleva un telescopio enorme."
    share = d.measure(text, "es", ["casa"])["uncommon_pct"]
    listed = d.uncommon_words(text, "es", ["casa"])
    assert share > 0 and "telescopio" in listed and "casa" not in listed
