"""The repair that sees how natural the text reads (18 Nov 2026): the judge rates naturalness before and after the rewrite, a rating of 3 or less is a requirement that
quotes the reviewer's reason, and the rewrite is kept only when the score, which then includes the rating, rises. Off unless STORY_REPAIR_NATURALNESS=1."""
import json
import sys
from pathlib import Path

from tutor_core.story import story_from_words
from tutor_core.story_options import StoryOptions
from tutor_core.story_repair import requirements
from tutor_core.quality import score_story

from test_story_steps import GOOD, TIER, WORDS, answer

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
from story_eval import variants  # noqa: E402

REWRITE = GOOD.replace("Después caminan por la playa", "Luego pasean por la playa")
REASON = "events do not follow and the time words repeat"
NO_MISTAKES = json.dumps({"mistakes": []})


class Judge:
    """Answers by the kind of prompt; ratings are used in order."""

    def __init__(self, ratings, rewrite=REWRITE):
        self.ratings, self.rewrite, self.seen, self.repair_prompts = list(ratings), rewrite, [], []

    def __call__(self, prompt):
        if "Rate how NATURAL" in prompt:
            self.seen.append("rate")
            return json.dumps({"score": self.ratings.pop(0), "reason": REASON})
        if "Find the mistakes that a careful native speaker" in prompt:
            self.seen.append("audit")
            return NO_MISTAKES
        if "meets ALL of these requirements" in prompt:
            self.seen.append("repair")
            self.repair_prompts.append(prompt)
            return answer(self.rewrite)
        self.seen.append("story")
        return answer(GOOD)


def run(fake, **opts):
    return story_from_words("es", WORDS, fake, story_type="story", difficulty=TIER, options=StoryOptions(repair=True, judge=True, **opts))


def test_a_low_rating_makes_a_repair_that_quotes_the_reviewers_reason():
    fake = Judge([2, 4])
    result = run(fake, repair_naturalness=True)
    assert result.text == REWRITE and fake.seen.count("repair") == 1 and fake.seen.count("rate") == 2
    assert REASON in fake.repair_prompts[0]
    assert any("naturalness 2 -> 4" in n for n in result.notes) and any("before the repair" in n for n in result.notes)


def test_a_good_rating_means_no_repair_call():
    fake = Judge([4])
    result = run(fake, repair_naturalness=True)
    assert result.text == GOOD and "repair" not in fake.seen and fake.seen.count("rate") == 1


def test_a_rewrite_that_does_not_read_better_is_rejected():
    fake = Judge([3, 3])
    result = run(fake, repair_naturalness=True)
    assert result.text == GOOD and any("rejected" in n for n in result.notes)


def test_without_the_option_nothing_is_rated_and_a_fine_story_is_left_alone():
    fake = Judge([2])
    result = run(fake)
    assert result.text == GOOD and "rate" not in fake.seen and "repair" not in fake.seen


def test_the_requirement_names_the_reason_and_replaces_the_generic_sentence():
    scored = score_story(GOOD, "es", WORDS, TIER, "story", naturalness=2)
    reqs = requirements(scored, GOOD, "es", WORDS, TIER, "story", REASON)
    assert any(REASON in r for r in reqs)
    assert not any(r.startswith("Rewrite it so it reads naturally") for r in reqs)
    assert not any("A reviewer said" in r for r in requirements(scored, GOOD, "es", WORDS, TIER, "story", ""))
    assert requirements(score_story(GOOD, "es", WORDS, TIER, "story", naturalness=4), GOOD, "es", WORDS, TIER, "story", REASON) == []


def test_the_option_is_in_the_environment_the_cache_key_and_the_variant():
    assert StoryOptions.from_env({"STORY_REPAIR_NATURALNESS": "1"}).repair_naturalness is True
    assert StoryOptions.from_env({}).repair_naturalness is False
    assert StoryOptions().cache_parts() == () and ("repair_naturalness",) in StoryOptions(repair=True, repair_naturalness=True).cache_parts()
    v = variants.BY_NAME["review_repair_nat"]
    assert v.options().repair_naturalness and v.repair and v.judge and not variants.BY_NAME["review_repair"].options().repair_naturalness
    assert [x.name for x in variants.resolve("naturalness")] == ["baseline", "review_repair", "review_repair_nat"]
    assert variants.CALLS["review_repair_nat"] > variants.CALLS["review_repair"]
