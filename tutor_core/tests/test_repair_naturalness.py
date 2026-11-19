"""The repair that sees how natural the text reads (18 Nov 2026): the judge rates naturalness before and after the rewrite, a rating of 3 or less is a requirement that
quotes the reviewer's reason, and the rewrite is kept only when the score, which then includes the rating, rises. Off unless STORY_REPAIR_NATURALNESS=1."""
import json
import sys
from pathlib import Path

from tutor_core.story import story_from_words
from tutor_core.story_options import StoryOptions
from tutor_core.story_repair import repair_story, requirements
from tutor_core.quality import score_story

from test_story_steps import GOOD, SHORT, TIER, WORDS, answer

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


class FlakyJudge(Judge):
    """Rates fine until `fail_from`-th rating (1-based), after that the answer is not the JSON that was asked for (a timeout, a chatty reply)."""

    def __init__(self, ratings, fail_from, rewrite=REWRITE):
        super().__init__(ratings, rewrite)
        self.fail_from, self.asked = fail_from, 0

    def __call__(self, prompt):
        if "Rate how NATURAL" in prompt:
            self.asked += 1
            self.seen.append("rate")
            if self.asked >= self.fail_from:
                return "I think it reads fine."
            return json.dumps({"score": self.ratings.pop(0), "reason": REASON})
        return super().__call__(prompt)


def test_a_rewrite_whose_rating_cannot_be_read_is_not_kept():
    """18 Nov 2026, found while testing: a score with no rating has no penalty for an unnatural text, so a rewrite that could not be rated went 44.9 -> 100.0 and was kept
    on no evidence. The repair now compares like for like and rejects what it cannot compare."""
    fake = FlakyJudge([2], fail_from=2)
    result = run(fake, repair_naturalness=True)
    assert result.text == GOOD and fake.seen.count("repair") == 1
    assert any("could not be rated" in n for n in result.notes) and not any("kept" in n for n in result.notes)


def test_when_the_first_rating_cannot_be_read_the_rewrite_is_compared_without_ratings():
    """The old text was not rated, so the new text is not rated either (one call saved) and the usual score comparison decides."""
    fake = FlakyJudge([], fail_from=1)
    text, notes = repair_story(SHORT, "es", WORDS, TIER, "story", lambda prompt: answer(GOOD), audit_call=fake, naturalness=True)
    assert text == GOOD and fake.seen.count("rate") == 1
    assert any("kept" in n for n in notes) and not any("naturalness" in n for n in notes)


def test_the_repair_rates_and_rewrites_a_language_without_spaces():
    ja = "私は毎朝六時に起きます。それから窓を開けて、新しい空気を吸います。台所でパンを食べて、お茶を飲みます。友達の田中さんが家に来て、一緒に公園を歩きます。午後は本を読んで、夜は早く寝ます。"
    better = ja.replace("それから窓を開けて、", "窓を開けて、").replace("午後は本を読んで、夜は", "午後は本を読みます。夜は")
    fake = Judge([2, 4], rewrite=better)
    text, notes = repair_story(ja, "ja", ["パン", "お茶", "公園", "友達"], TIER, "story", lambda prompt: answer(better), audit_call=fake, naturalness=True)
    assert text == better and any("naturalness 2 -> 4" in n for n in notes)
