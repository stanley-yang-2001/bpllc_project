"""The refine loop with a fake model (10 Nov 2026): what each phase records, when a rewrite is kept, and when it is thrown away."""
import json

from tutor_core import difficulty as d
from tutor_core.story import story_from_words
from tutor_core.story_options import StoryOptions
from tutor_core.story_refine import finding_still_in_text, flagged_sentences, refine_story, splice_flagged, unchanged_share
from tutor_core.quality.grammar import Hit

WORDS = ["casa", "mar", "amigo", "jardín", "pan"]
GOOD = ("María vive en una casa grande cerca del mar. Cada mañana ella abre la ventana y mira el agua. Su amigo Pedro llega con pan fresco. "
        "Los dos desayunan juntos en el jardín y hablan de sus planes. Después caminan por la playa hasta la hora de comer. "
        "Por la tarde vuelven a casa y leen un libro. Al final del día los dos duermen contentos.")
FLAW = GOOD.replace("Los dos desayunan juntos", "Los dos desayunan juntos todos")
TIER = d.resolve("custom", length=60)
REVIEW = json.dumps({"errors": [{"wrong": "juntos todos", "right": "juntos", "type": "extra_word", "why": "unnecessary word"}]})
CLEAN = json.dumps({"errors": []})


class Fake:
    def __init__(self, fixed=GOOD, review=REVIEW, after_review=CLEAN):
        self.fixed, self.reviews, self.after = fixed, [review, after_review], 0
        self.seen = []

    def __call__(self, prompt):
        if "Find the mistakes that a careful native speaker" in prompt:
            self.seen.append("review")
            return self.reviews[min(len(self.seen_of("review")) - 1, 1)]
        self.seen.append("repair")
        self.prompt = prompt
        return "===STORY===\n" + self.fixed

    def seen_of(self, kind):
        return [s for s in self.seen if s == kind]


def run(text, fake, **kw):
    return refine_story(text, "es", WORDS, TIER, "story", fake, review_call=fake, rounds=2, **kw)


def test_flagged_sentences_and_unchanged_share():
    hit = Hit("audit", "audit.extra_word", "juntos todos", "juntos", "grammar", -1, -1, False, "unnecessary word")
    flagged = flagged_sentences(FLAW, [hit])
    assert [n for n, _, _ in flagged] == [4] and "juntos todos" in flagged[0][1] and "should be" in flagged[0][2][0]
    assert unchanged_share(FLAW, GOOD, [4]) == 1.0
    assert unchanged_share(FLAW, "Otra cosa. Nada igual.", [4]) == 0.0


def test_a_fix_that_raises_the_score_is_kept_and_every_phase_is_recorded():
    fake = Fake()
    result = run(FLAW, fake)
    assert result.text == GOOD
    phases = [t["phase"] for t in result.trace]
    assert phases[:4] == ["observe", "plan", "repair", "observe"] and "verify" in phases
    assert "Sentence 4" in fake.prompt and "word for word" in fake.prompt
    verify = next(t for t in result.trace if t["phase"] == "verify")
    assert verify["kept"] and verify["after"] > verify["before"]
    assert any("refine 1 kept" in n for n in result.notes)
    assert result.trace[0]["tools"][-1]["tool"] == "model review" and result.trace[0]["tools"][-1]["found"] == 1


def test_a_rewrite_that_changes_too_much_is_rejected():
    fake = Fake(fixed="Un texto totalmente distinto y corto. Nada que ver con el original.")
    result = run(FLAW, fake)
    assert result.text == FLAW and any("rejected" in n for n in result.notes)
    verify = next(t for t in result.trace if t["phase"] == "verify")
    assert verify["kept"] is False


def test_a_rewrite_that_does_not_help_is_rejected():
    fake = Fake(fixed=FLAW)                         # the model hands the text back unchanged
    result = run(FLAW, fake)
    assert result.text == FLAW and any("rejected" in n for n in result.notes)


def test_nothing_flagged_makes_no_repair_call():
    fake = Fake(review=CLEAN)
    result = run(GOOD, fake)
    assert result.text == GOOD and fake.seen_of("repair") == [] and any("nothing left" in n for n in result.notes)


def test_a_failing_call_keeps_the_text():
    def boom(prompt):
        if "Find the mistakes" in prompt:
            return REVIEW
        raise RuntimeError("down")
    result = refine_story(FLAW, "es", WORDS, TIER, "story", boom, review_call=boom, rounds=2)
    assert result.text == FLAW and any("failed" in n for n in result.notes)


def test_the_pipeline_runs_it_and_returns_the_trace():
    fake = Fake(fixed=GOOD)
    flawed_story = lambda prompt: fake(prompt) if "Find the mistakes" in prompt or "correcting" in prompt else "===STORY===\n" + FLAW  # noqa: E731
    result = story_from_words("es", WORDS, flawed_story, story_type="story", difficulty=TIER, options=StoryOptions(refine=2))
    assert result.ok and result.text == GOOD and result.trace and result.trace[0]["phase"] == "observe"
    assert result.draft == FLAW          # the first draft travels with the result, for a test that reviews both


def test_refine_option_from_env_and_cache_key():
    assert StoryOptions.from_env({"STORY_REFINE": "2"}).refine == 2 and StoryOptions.from_env({"STORY_REFINE": "9"}).refine == 3
    assert StoryOptions.from_env({}) == StoryOptions() and ("refine", 2) in StoryOptions(refine=2).cache_parts()


def test_the_report_shows_every_phase():
    import sys
    sys.path.insert(0, "../scripts")
    from story_eval import report
    page = report._trace({"trace": run(FLAW, Fake()).trace})
    for word in ("Observe (start)", "Plan, round 1", "Repair, round 1", "Verify, round 1", "KEPT", "sentence 4"):
        assert word in page
    assert report._trace({}) == ""


def test_splice_keeps_every_sentence_except_the_flagged_one():
    other = GOOD.replace("María vive", "Ana vive").replace("Pedro llega", "Luis llega")          # the model also rewrote sentences 1 and 3
    spliced = splice_flagged(FLAW, other, [4])
    assert spliced == GOOD and unchanged_share(FLAW, spliced, [4]) == 1.0
    assert splice_flagged(FLAW, "Solo una frase.", [4]) == "Solo una frase."          # a different sentence count is returned as it is


def test_a_model_that_rewrites_other_sentences_still_gets_its_fix_kept():
    fake = Fake(fixed=GOOD.replace("María vive", "Ana vive"))
    result = run(FLAW, fake)
    assert result.text == GOOD and any("refine 1 kept" in n for n in result.notes)


def test_a_fix_that_only_adds_words_is_not_still_in_the_text():
    hit = Hit("audit", "audit.x", "Monday morning I woke", "On Monday morning I woke", "grammar", -1, -1, False, "")
    assert finding_still_in_text(hit, "Monday morning I woke late.") is True
    assert finding_still_in_text(hit, "On Monday morning I woke late.") is False


class Rated(Fake):
    """The fake model that also answers the 1 to 5 naturalness prompt, from a list of ratings given in the order they are asked."""
    def __init__(self, ratings, **kw):
        super().__init__(**kw)
        self.ratings = list(ratings)

    def __call__(self, prompt):
        if "Rate how NATURAL" in prompt:
            self.seen.append("rate")
            return json.dumps({"score": self.ratings.pop(0), "reason": "fake"})
        return super().__call__(prompt)


def run_rated(text, fake, **kw):
    return refine_story(text, "es", WORDS, TIER, "story", fake, review_call=fake, rate_call=fake, rounds=2, **kw)


def test_naturalness_is_rated_at_the_start_and_after_the_repair_and_recorded():
    fake = Rated([3, 4])
    result = run_rated(FLAW, fake)
    assert result.text == GOOD and fake.seen_of("rate") == ["rate", "rate"]
    observes = [t for t in result.trace if t["phase"] == "observe"]
    assert [o["score"]["naturalness"] for o in observes] == [3, 4] and observes[0]["naturalness"]["ok"]
    verify = next(t for t in result.trace if t["phase"] == "verify")
    assert verify["naturalness_before"] == 3 and verify["naturalness_after"] == 4


def test_a_fix_that_clears_the_findings_but_reads_worse_is_thrown_away():
    fake = Rated([4, 3])          # the review is clean after the repair, the rating fell one point
    result = run_rated(FLAW, fake)
    assert result.text == FLAW and any("naturalness 4 -> 3" in n for n in result.notes)
    verify = next(t for t in result.trace if t["phase"] == "verify")
    assert verify["kept"] is False and verify["reason"] == "naturalness 4 -> 3"


def test_an_unnatural_rating_is_part_of_the_score_the_loop_compares():
    plain = run(FLAW, Fake()).trace[0]["score"]["score"]
    rated = run_rated(FLAW, Rated([2, 2])).trace[0]["score"]["score"]
    assert rated < plain          # a rating of 2 fails the story and lowers the score the loop sees, as it lowers the score the reviewers give


def test_a_text_that_still_reads_unnatural_is_said_so_in_the_notes():
    result = run_rated(GOOD, Rated([2], review=CLEAN))
    assert result.text == GOOD and any("still reads unnatural (2/5)" in n for n in result.notes)


def test_a_failed_rating_leaves_naturalness_out_and_does_not_stop_the_loop():
    class NoRating(Fake):
        def __call__(self, prompt):
            if "Rate how NATURAL" in prompt:
                raise RuntimeError("down")
            return super().__call__(prompt)
    result = run_rated(FLAW, NoRating())
    assert result.text == GOOD and result.trace[0]["score"]["naturalness"] is None and result.trace[0]["naturalness"]["ok"] is False


def test_whole_text_needs_are_left_alone_and_never_sent_to_the_model():
    long_flaw = FLAW + " " + " ".join(["Después ellos hablan un rato más sobre el día y sobre la casa."] * 8)       # far over the 60 words asked for
    fake = Fake(fixed=long_flaw.replace("juntos todos", "juntos"))
    result = run(long_flaw, fake)
    plan = next(t for t in result.trace if t["phase"] == "plan")
    assert plan["whole_text"] and plan["whole_text_repaired"] is False
    assert "for the text as a whole" not in fake.prompt and "Sentence 4" in fake.prompt
    assert "juntos todos" not in result.text          # the flagged sentence was still fixed


def test_the_draft_is_kept_on_the_result_even_when_nothing_changes():
    assert run(FLAW, Fake()).draft == FLAW and run(GOOD, Fake(review=CLEAN)).draft == GOOD
