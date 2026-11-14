"""The multi-method runner (scripts/story_eval) with a fake model: no network, no database, no waiting."""
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from story_eval import fixed_set, report, runner, variants as vs  # noqa: E402

GOOD = ("María vive en una casa grande cerca del mar. Cada mañana ella abre la ventana y mira el agua. Su amigo Pedro llega con pan fresco. "
        "Los dos desayunan juntos en el jardín y hablan de sus planes. Después caminan por la playa hasta la hora de comer. "
        "Por la tarde vuelven a casa y leen un libro. Al final del día los dos duermen contentos.")


def fake_model(prompt):
    if "Find the mistakes that a careful native speaker" in prompt:
        return json.dumps({"errors": [{"wrong": "Cada mañana ella abre", "right": "Cada mañana ella abría", "type": "verb", "why": "tense"}]})
    if "Translate this" in prompt:
        return "Mary lives in a big house."
    return "===STORY===\n" + GOOD


def calls(model=fake_model, wrap=lambda c: c, judge=False, audit=False, translate=False):
    return runner.Calls(runner.Channel(model, wrap), runner.Channel(model, wrap) if judge else None, runner.Channel(model, wrap) if audit else None,
                        (lambda text, code: "Mary lives.") if translate else None)


def make(names="baseline,two_pass,candidates", languages=("es",), **kw):
    chosen = vs.resolve(names)
    data = runner.new_data(fixed_set.build(list(languages), extras=False), chosen, {"score_version": 4.1})
    return data, chosen


def test_the_fixed_set_is_twenty_requests_and_never_changes():
    a, b = fixed_set.build(), fixed_set.build()
    assert a == b and len(a) == 20 and len({r["id"] for r in a}) == 20
    assert {r["code"] for r in a} == {"en", "es", "fr", "de", "it", "pt", "ja", "zh", "ko"}
    assert all(r["words"] and r["tier"] in fixed_set.TIERS and r["story_type"] in fixed_set.KINDS and r["topic"] for r in a)
    assert len(fixed_set.build(["es"], extras=False)) == 2 and len(fixed_set.build(["en"])) == 3      # en has an extra


def test_variant_names_and_each_adds_one_thing():
    assert [v.name for v in vs.resolve("default")] == vs.DEFAULT and len(vs.resolve("all")) == len(vs.ALL) == 18
    with pytest.raises(ValueError, match="unknown variant"):
        vs.resolve("baseline,magic")
    o = vs.BY_NAME["repair"].options()
    assert (o.candidates, o.judge, o.repair) == (3, True, True) and vs.BY_NAME["baseline"].options().candidates == 1
    assert [v.name for v in vs.resolve("cascade")] == ["baseline", "plan", "mixed_gates", "cascade", "cascade_proofread"]
    c = vs.BY_NAME["cascade"].options()
    assert (c.mixed, c.gates, c.plan, c.repair) == (True, True, True, True)
    assert {v.story_model for v in vs.resolve("mix")} <= {None, "gpt", "qwen"} and len(vs.resolve("mix")) == 6


def test_two_models_each_get_their_own_channel_and_reviewers_are_compared():
    seen = {"gpt": [], "qwen": []}

    def model_for(alias):
        def call(prompt):
            seen[alias].append(prompt)
            return fake_model(prompt)
        return call
    chans = {a: runner.Channel(model_for(a)) for a in seen}
    data, chosen = make("gpt_qwen")
    c = runner.Calls(runner.Channel(fake_model), models=lambda a: chans[a], audits={"gpt": chans["gpt"], "qwen": chans["qwen"]})
    runner.run(data, chosen, c, say=lambda *_: None, limit=1)
    entry = next(iter(data["results"].values()))["gpt_qwen"]
    assert seen["gpt"] and seen["qwen"] and set(entry["audits"]) == {"gpt", "qwen"} and entry["gate"] is not None
    assert "naturalness" in entry["audits"]["gpt"] and entry["audits"]["gpt"]["naturalness"] is not None
    assert entry["audit"] == entry["audits"]["gpt"] and set(entry["audit_scores"]) == {"gpt", "qwen"}
    page = report.render(data)
    assert "Reviewers compared" in page and "Free checks" in page
    assert set(report.rescore(data)["results"][next(iter(data["results"]))]["gpt_qwen"]["audit_scores"]) == {"gpt", "qwen"}


def test_a_run_fills_every_request_and_method_and_counts_calls_and_time():
    data, chosen = make()
    assert runner.run(data, chosen, calls(), say=lambda *_: None) is True
    assert len(data["results"]) == 2 and all(set(row) == {"baseline", "two_pass", "candidates"} for row in data["results"].values())
    row = next(iter(data["results"].values()))
    # a story outside the tier's length is written again by the usual retry, so the counts are "at least"
    assert row["baseline"]["calls"] >= 1 and row["two_pass"]["calls"] >= 2 and row["candidates"]["calls"] >= 4
    for e in row.values():
        assert e["ok"] and e["score"]["score"] >= 80 and 0 <= e["model_seconds"] <= e["seconds"] and e["wait_seconds"] >= 0
    assert any("candidates" in n for n in row["candidates"]["notes"])


def test_waiting_for_the_rate_limit_is_counted_apart_from_model_time():
    def slow_wrap(call):
        def wrapped(prompt):
            time.sleep(0.05)               # what the pacing does before a call
            return call(prompt)
        return wrapped

    data, chosen = make("baseline")
    runner.run(data, chosen, calls(wrap=slow_wrap), say=lambda *_: None)
    e = next(iter(data["results"].values()))["baseline"]
    assert e["wait_seconds"] >= 0.04 and e["seconds"] >= e["wait_seconds"] and e["model_seconds"] < e["seconds"]


def test_saved_after_every_story_and_resume_makes_only_what_is_missing(tmp_path):
    data, chosen = make("baseline,two_pass")
    path = str(tmp_path / "run.json")
    saved = []
    c = calls()
    runner.run(data, chosen, c, on_saved=lambda d: (runner.save(d, path), saved.append(1)), say=lambda *_: None, limit=1)
    assert len(saved) == 2 and len(runner.load(path)["results"]) == 1
    again = runner.load(path)
    first = json.dumps(again["results"]["es-0"], sort_keys=True)
    seen = []
    runner.run(again, chosen, calls(lambda p: seen.append(p) or fake_model(p)), say=lambda *_: None)
    assert len(again["results"]) == 2 and json.dumps(again["results"]["es-0"], sort_keys=True) == first      # the first request is untouched
    full = []
    fresh, _ = make("baseline,two_pass")
    runner.run(fresh, chosen, calls(lambda p: full.append(p) or fake_model(p)), say=lambda *_: None)
    assert 0 < len(seen) < len(full)                                  # fewer calls than doing both requests again


def test_a_long_rate_limit_stops_the_run_and_saves_nothing_for_that_story():
    def limited(prompt):
        raise RuntimeError("Groq API error 429: Rate limit reached ... Please try again in 7h12m. ")

    data, chosen = make("baseline")
    said = []
    assert runner.run(data, chosen, calls(limited), say=said.append) is False
    assert data["results"] == {next(iter(data["results"]))} or all(not row for row in data["results"].values())
    assert any("--resume" in s for s in said)


def test_another_failure_is_saved_as_a_failed_story():
    def broken(prompt):
        raise RuntimeError("500 server error")

    data, chosen = make("baseline")
    runner.run(data, chosen, calls(broken), say=lambda *_: None)
    e = next(iter(data["results"].values()))["baseline"]
    assert not e["ok"] and e["reason"] == "failed" and e["score"] is None and "500" in e["error"]


def test_a_method_that_needs_the_database_is_skipped_without_it():
    data, chosen = make("baseline,examples")
    said = []
    runner.run(data, chosen, calls(), say=said.append)
    assert all("examples" not in row for row in data["results"].values()) and any("example bank" in s for s in said)


def test_the_independent_review_and_translation_are_recorded_but_not_counted_as_story_calls():
    data, chosen = make("baseline")
    runner.run(data, chosen, calls(audit=True, translate=True), say=lambda *_: None)
    e = next(iter(data["results"].values()))["baseline"]
    assert e["calls"] >= 1 and e["translation"] == "Mary lives." and e["audit"]["ok"] and len(e["audit"]["hits"]) == 1
    assert e["audit_score"]["score"] < e["score"]["score"] and e["audit_seconds"] is not None


def test_stats_report_and_rescore():
    data, chosen = make("baseline,two_pass,candidates", ("es",))
    runner.run(data, chosen, calls(audit=True), say=lambda *_: None)
    s = report.stats(data, "baseline")
    assert s["stories"] == 2 and s["score"] > 80 and s["calls"] >= 1 and s["pass_rate"] is not None and s["mistakes_found"] == 1
    page = report.render(data)
    for label in ("Baseline", "+ two passes", "+ 3 candidates", "Summary", "Spanish", "Seconds in model", "Model review: 1 mistake"):
        assert label in page
    old = json.loads(json.dumps(data))
    for row in old["results"].values():
        for e in row.values():
            e["score"] = {"score": 1.0, "parts": {}, "gated": None}
    fresh = report.rescore(old)
    assert next(iter(fresh["results"].values()))["baseline"]["score"]["score"] >= 80
    assert next(iter(old["results"].values()))["baseline"]["score"]["score"] == 1.0         # the input is not changed


def test_pass_rule():
    assert report.passes({"gated": None, "parts": {"a": 90.0, "b": None}}) and not report.passes({"gated": None, "parts": {"a": 79.9}})
    assert not report.passes({"gated": "empty", "parts": {}}) and not report.passes(None)


def test_estimate_grows_with_methods_and_extras():
    reqs = fixed_set.build()
    small = runner.estimate(reqs, vs.resolve("baseline"), False, False)
    big = runner.estimate(reqs, vs.resolve("all"), True, True)
    assert small["calls"] < big["calls"] and small["minutes"] <= big["minutes"] and small["requests"] == 20


def test_the_command_line_rescores_a_saved_run_without_a_key(tmp_path, monkeypatch):
    import run_story_methods
    data, chosen = make("baseline")
    runner.run(data, chosen, calls(), say=lambda *_: None)
    saved = str(tmp_path / "m.json")
    runner.save(data, saved)
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert run_story_methods.main(["--rescore", saved]) == 0
    assert (tmp_path / "m_rescored.html").exists() and (tmp_path / "m_rescored.json").exists()
    assert run_story_methods.main(["--dry-run", "--variants", "nope"]) == 2
    assert run_story_methods.main(["--dry-run", "--languages", "es"]) == 0


# --- 14 Nov 2026: the draft against its own repair, failed reviews, and why a run stopped -------------------------------------------------------------------------

FLAW = GOOD.replace("Los dos desayunan juntos", "Los dos desayunan juntos todos")
GOOD_ANSWER = "===STORY===\n" + GOOD


def refine_model(prompt):
    """The writer gives a draft with one mistake, the review finds it where it is, the repair fixes it, the rating is 4."""
    if "Rate how NATURAL" in prompt:
        return json.dumps({"score": 4, "reason": "fine"})
    if "Find the mistakes that a careful native speaker" in prompt:
        wrong = "juntos todos" in prompt
        return json.dumps({"errors": [{"wrong": "juntos todos", "right": "juntos", "type": "extra_word", "why": "extra word"}] if wrong else []})
    if "correcting a short reading text" in prompt:
        return "===STORY===\n" + GOOD
    if "Translate this" in prompt:
        return "Mary lives in a big house."
    return "===STORY===\n" + FLAW


def refine_calls(model=refine_model):
    chans = {a: runner.Channel(model) for a in ("gpt", "qwen")}
    return runner.Calls(runner.Channel(model), models=lambda a: chans[a], audits={"gpt": runner.Channel(model), "qwen": runner.Channel(model)})


def test_a_changed_draft_is_reviewed_by_the_same_reviewers_as_its_result():
    data, chosen = make("refine")
    runner.run(data, chosen, refine_calls(), say=lambda *_: None, limit=1)
    e = next(iter(data["results"].values()))["refine"]
    assert e["ok"] and e["text"] == GOOD and e["draft"]["changed"] and e["draft"]["text"] == FLAW
    assert set(e["draft"]["audits"]) == {"gpt", "qwen"} and set(e["draft"]["audit_scores"]) == {"gpt", "qwen"} and e["draft"]["audit_union"] is not None
    assert e["draft"]["audits"]["gpt"]["hits"] and not e["audits"]["gpt"]["hits"]          # the reviewers find the mistake in the draft and not in the result
    assert e["draft"]["audit_union"]["score"] < e["audit_union"]["score"]


def test_a_draft_the_loop_left_alone_is_not_reviewed_again():
    def clean(prompt):
        if "Find the mistakes that a careful native speaker" in prompt:
            return json.dumps({"errors": []})
        return GOOD_ANSWER if "Rate how NATURAL" not in prompt else json.dumps({"score": 4})
    data, chosen = make("refine")
    runner.run(data, chosen, refine_calls(clean), say=lambda *_: None, limit=1)
    e = next(iter(data["results"].values()))["refine"]
    assert e["draft"] == {"text": GOOD, "changed": False}


def test_the_report_counts_failed_reviews_and_compares_the_draft_with_its_repair():
    data, chosen = make("baseline,refine")
    c = refine_calls()
    c.story = runner.Channel(refine_model)
    runner.run(data, chosen, c, say=lambda *_: None, limit=1)
    s = report.stats(data, "refine")
    assert s["reviews"] == 2 and s["failed_reviews"] == 0 and s["naturalness"] == 4
    page = report.render(data)
    assert "The draft against its own repair" in page and "Failed reviews" in page and "Failed reviews, draft" in page
    assert "naturalness 4" in page and "measured, left alone" in page
    # a failed review: a rating of 2 fails the story
    entry = next(iter(data["results"].values()))["refine"]
    for r in entry["audits"].values():
        r["naturalness"]["score"] = 2
    again = report.rescore(data)
    assert report.stats(again, "refine")["failed_reviews"] == 2
    fresh = next(iter(again["results"].values()))["refine"]
    assert fresh["draft"]["changed"] and fresh["draft"]["audit_scores"] and fresh["draft"]["score"]["score"] > 0      # the draft block is scored again too


def test_a_run_that_stops_says_why_in_the_json_and_a_resume_clears_it(tmp_path):
    def limited(prompt):
        raise RuntimeError("Groq API error 429: Rate limit reached ... Please try again in 7h12m. ")
    data, chosen = make("baseline")
    path = str(tmp_path / "run.json")
    assert runner.run(data, chosen, calls(limited), on_saved=lambda d: runner.save(d, path), say=lambda *_: None) is False
    stopped = runner.load(path)["meta"]["stopped"]
    assert "rate limit too long to wait for" in stopped and "(at es-0, baseline)" in stopped
    again = runner.load(path)
    assert runner.run(again, chosen, calls(), say=lambda *_: None) is True and "stopped" not in again["meta"]


def test_a_crash_is_written_down_before_it_is_raised(monkeypatch, tmp_path):
    def boom(*a, **k):
        raise ValueError("bad row")
    monkeypatch.setattr(runner, "run_one", boom)
    data, chosen = make("baseline")
    path = str(tmp_path / "run.json")
    with pytest.raises(ValueError):
        runner.run(data, chosen, calls(), on_saved=lambda d: runner.save(d, path), say=lambda *_: None)
    assert runner.load(path)["meta"]["stopped"].startswith("crashed: ValueError: bad row (at es-0")
    assert "This run stopped early" in report.render(runner.load(path))
