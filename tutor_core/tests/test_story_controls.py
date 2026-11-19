"""The controls and the extra comparisons of the story report (19 Nov 2026): the baseline made again, the verdict-based comparison, the level fit, each reviewer alone, and the
comparison of two saved runs. No model, no network."""
import json
import math
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from story_eval import fit, repeat, report, runner, stats, variants as vs, verdicts as vd  # noqa: E402
from tutor_core import difficulty as _d  # noqa: E402
from tutor_core.difficulty.note import LEVELS  # noqa: E402
from tutor_core.quality import score_story  # noqa: E402

from test_story_eval import _entry, calls, make  # noqa: E402
from test_story_steps import GOOD, TIER, WORDS  # noqa: E402


# --- builders ------------------------------------------------------------------------------------------------------------------------------------------------

def _req(i, tier="easy", story_type="story", pack="basics", code="en", words=None):
    return {"id": f"{code}-{i}", "code": code, "tier": tier, "story_type": story_type, "topic": "a market day", "pack": pack, "words": words or ["hello", "bread"], "seed": 1000 + i}


def _story(ratings, failed=(), mean=7.0):
    """A reviewed story: the reviewers' ratings, who failed it and the mean sentence length the free score measured."""
    entry = _entry(ratings, failed)
    entry["score"] = {"score": 95.0, "gated": None, "parts": {}, "measured": {"mean_sentence": mean}}
    entry["models"] = {"story": "default", "judge": None}
    entry.update(calls=1, seconds=1.0, model_seconds=1.0, wait_seconds=0.0, text="A story.", notes=[], trace=[], translation="", error=None, reason=None)
    return entry


def _data(requests, by_variant: dict, replicate_of=None, meta=None, range_prompt=()):
    """A saved run: by_variant is {name: [entry for each request]}; `replicate_of` is {name: the method it repeats}."""
    replicate_of = replicate_of or {}
    variants = [{"name": n, "label": n.replace("_", " ").capitalize(), "note": "", "range_prompt": n in range_prompt, "replicate_of": replicate_of.get(n)} for n in by_variant]
    results = {r["id"]: {n: es[i] for n, es in by_variant.items()} for i, r in enumerate(requests)}
    return {"format": runner.FORMAT, "meta": meta if meta is not None else {}, "variants": variants, "requests": requests, "results": results}


PASS_ALL, FAIL_ALL = ({"gpt": 4, "qwen": 4}, ()), ({"gpt": 2, "qwen": 2}, ("gpt", "qwen"))


# --- stats ---------------------------------------------------------------------------------------------------------------------------------------------------

def test_the_spread_and_the_requests_needed_follow_the_usual_formula():
    assert stats.sd([1, 2, 3, 4]) == pytest.approx(1.2909944)
    assert stats.sd([5]) is None and stats.sd([]) is None and stats.sd([1, None, 3]) == pytest.approx(math.sqrt(2))
    assert stats.requests_needed(0.5, 0.15) == 90                      # ((1.96 + 0.84) x 0.5 / 0.15) squared = 87.1, so 88, plus two for the t distribution
    assert stats.requests_needed(0.5, 0.30) < stats.requests_needed(0.5, 0.15) < stats.requests_needed(0.8, 0.15)
    assert stats.requests_needed(0, 0.15) is None and stats.requests_needed(None, 0.15) is None and stats.requests_needed(0.5, 0) is None


# --- the level fit -------------------------------------------------------------------------------------------------------------------------------------------

def test_the_asked_sentence_range_is_the_one_the_writer_is_told():
    """The table cannot drift from the note: the range is read from the level text itself, and this pins the three values the design asks for."""
    assert fit.SENTENCE_RANGE == {"easy": (5, 8), "medium": (8, 12), "hard": (10, 16)}
    for tier, (low, high) in fit.SENTENCE_RANGE.items():
        assert f"about {low} to {high} words" in LEVELS[tier]
    assert fit.asked("hard") == "10 to 16" and fit.asked("nope") == "?"


def test_a_story_is_in_range_short_or_long_for_its_own_level():
    def got(mean, tier, code="en", **kw):
        entry = _story({"gpt": 4}, mean=mean)
        entry.update(kw)
        return fit.sentence_fit(entry, tier, code)
    assert [got(m, "easy") for m in (4.9, 5, 6.5, 8, 8.1)] == [fit.SHORT, fit.IN, fit.IN, fit.IN, fit.LONG]
    assert [got(m, "hard") for m in (9.5, 10, 16, 16.5)] == [fit.SHORT, fit.IN, fit.IN, fit.LONG]
    assert got(10, "medium") == fit.IN and got(10, "easy") == fit.LONG                  # the same story, two levels
    assert got(7, "easy", ok=False) is None and got(7, "nope") is None and fit.sentence_fit(None, "easy", "en") is None
    assert got(7, "easy", code="ja") is None and got(7, "easy", code="zh") is None       # Chinese and Japanese count characters, not words
    assert fit.sentence_fit({"ok": True, "score": {"gated": "wrong language", "measured": {}}}, "easy", "en") is None


def test_it_reads_the_number_the_score_really_records():
    """A rename of `mean_sentence` in the score would silently empty the table: read it from a real score."""
    scored = score_story(GOOD, "es", WORDS, TIER, "story")
    mean = scored["measured"]["mean_sentence"]
    assert 5 < mean < 15
    entry = {"ok": True, "score": scored}
    low, high = fit.SENTENCE_RANGE["medium"]
    assert fit.sentence_fit(entry, "medium", "es") == (fit.IN if low <= mean <= high else fit.SHORT if mean < low else fit.LONG)


def test_the_fit_of_a_method_is_counted_in_all_and_by_level():
    reqs = [_req(0, "easy"), _req(1, "easy"), _req(2, "medium"), _req(3, "hard"), _req(4, "hard")]
    entries = [_story({"gpt": 4}, mean=m) for m in (7, 10, 9, 17, 12)]          # in, long, in, long, in
    got = fit.by_method(list(zip(reqs, entries)))
    assert (got["stories"], got[fit.IN], got[fit.SHORT], got[fit.LONG]) == (5, 3, 0, 2)
    assert got["tiers"]["easy"] == {fit.IN: 1, fit.SHORT: 0, fit.LONG: 1} and got["tiers"]["hard"] == {fit.IN: 1, fit.SHORT: 0, fit.LONG: 1}
    assert got["in_range"][0] < 0.6 < got["in_range"][1]
    assert fit.by_method([]) == {} and fit.by_method([(_req(0, code="ja"), _story({"gpt": 4}))]) == {}


# --- the verdict comparison ----------------------------------------------------------------------------------------------------------------------------------

def _pairs(entries):
    return [(_req(i), e) for i, e in enumerate(entries)]


def test_two_methods_are_compared_on_what_the_reviewers_decided():
    n = 10
    base = _pairs([_story(*FAIL_ALL) for _ in range(n)])
    gain = _pairs([_story(*PASS_ALL) for _ in range(n)])
    c = vd.paired_verdicts(base, gain)
    assert c["requests"] == n and c["up"] == n and c["change"] == 1.0 and c["reading"] == "clear gain" and c["p"] < 0.01
    assert c["by_reviewer"] == {"gpt": 1.0, "qwen": 1.0}
    half = _pairs([_story({"gpt": 4, "qwen": 2}, ("qwen",)) for _ in range(n)])            # a split is worth half a pass
    assert vd.paired_verdicts(base, half)["change"] == 0.5
    assert vd.paired_verdicts(base, half)["by_reviewer"] == {"gpt": 1.0, "qwen": 0.0}
    loss = vd.paired_verdicts(gain, base)
    assert loss["change"] == -1.0 and loss["reading"] == "clear loss"


def test_a_story_nobody_reviewed_is_left_out_of_the_comparison_and_never_counted_as_a_pass():
    base = _pairs([_story(*FAIL_ALL) for _ in range(8)])
    other = _pairs([_story(*PASS_ALL) for _ in range(6)] + [{"ok": True, "audit_scores": {}}, _story(*PASS_ALL, mean=7) | {"ok": False}])
    c = vd.paired_verdicts(base, other)
    assert c["requests"] == 6 and c["up"] == 6
    assert vd.paired_verdicts(base, [])["requests"] == 0 and vd.paired_verdicts(base, [])["change"] is None


def test_the_reading_needs_enough_requests_and_the_reviewers_to_agree():
    n = 10
    base = _pairs([_story(*FAIL_ALL) for _ in range(n)])
    assert vd.paired_verdicts(base[:4], _pairs([_story(*PASS_ALL)] * 4))["reading"] == "too few requests"
    # gpt passes every story the second method wrote, qwen fails every one: they disagree, so no gain is claimed
    split_view = _pairs([_story({"gpt": 4, "qwen": 2}, ("qwen",)) for _ in range(n)])
    flipped_base = _pairs([_story({"gpt": 2, "qwen": 4}, ("gpt",)) for _ in range(n)])
    assert vd.paired_verdicts(flipped_base, split_view)["reading"] == "reviewers disagree"
    # one reviewer sees a gain and the other sees no change: not a disagreement, still a gain on the stories passed
    only_gpt = _pairs([_story({"gpt": 4, "qwen": 2}, ("qwen",)) for _ in range(n)])
    c = vd.paired_verdicts(base, only_gpt)
    assert c["reading"] == "clear gain" and c["by_reviewer"]["qwen"] == 0.0
    # a scatter of ups and downs is within noise
    mixed = _pairs([_story(*(PASS_ALL if i % 2 else FAIL_ALL)) for i in range(n)])
    assert vd.paired_verdicts(base, mixed)["reading"] in ("within noise", "clear gain")      # five better of ten: the range must tell
    same = vd.paired_verdicts(base, _pairs([_story(*FAIL_ALL) for _ in range(n)]))
    assert same["reading"] == "within noise" and same["change"] == 0 and same["needed"] is None      # no spread: nothing to size


def test_the_spread_of_the_changes_sizes_how_many_requests_would_show_a_gain():
    n = 20
    base = _pairs([_story(*FAIL_ALL) for _ in range(n)])
    mixed = _pairs([_story(*(PASS_ALL if i % 3 == 0 else FAIL_ALL)) for i in range(n)])
    c = vd.paired_verdicts(base, mixed)
    assert c["spread"] == pytest.approx(stats.sd([1.0 if i % 3 == 0 else 0.0 for i in range(n)]))
    assert c["needed"] == stats.requests_needed(c["spread"], vd.WANTED_GAP) and c["wanted"] == vd.WANTED_GAP


# --- the methods ---------------------------------------------------------------------------------------------------------------------------------------------

def test_the_repeated_baseline_is_the_baseline_and_the_controls_group_has_what_was_never_measured():
    a, b = vs.BY_NAME["baseline"], vs.BY_NAME["baseline_b"]
    skip = {"name", "label", "note", "replicate_of"}
    assert {k: v for k, v in a.as_dict().items() if k not in skip} == {k: v for k, v in b.as_dict().items() if k not in skip}
    assert b.options() == a.options() and b.replicate_of == "baseline" and a.replicate_of is None
    assert [v.name for v in vs.resolve("controls")] == ["baseline", "baseline_b", "range", "plan", "review_repair", "review_repair_nat"]
    assert b.as_dict()["replicate_of"] == "baseline" and vs.CALLS["baseline_b"] == vs.CALLS["baseline"]
    assert vs.BY_NAME["range"].range_prompt and not vs.BY_NAME["range"].plan and vs.BY_NAME["plan"].plan and vs.BY_NAME["plan"].range_prompt


def test_the_repeat_is_made_as_a_separate_story_with_its_own_entry():
    data, chosen = make("baseline,baseline_b")
    runner.run(data, chosen, calls(), say=lambda *_: None, limit=2)
    row = data["results"][data["requests"][0]["id"]]
    assert set(row) == {"baseline", "baseline_b"} and row["baseline"]["ok"] and row["baseline_b"]["ok"]
    assert [v["replicate_of"] for v in data["variants"]] == [None, "baseline"]


# --- the page ------------------------------------------------------------------------------------------------------------------------------------------------

def _controls_run(replicate=True):
    """12 requests over three levels, two word packs and three story types; the baseline fails most, the repeat about the same, the plan fits its level and passes more."""
    tiers = ["easy", "medium", "hard"] * 4
    types = ["story", "diary", "letter"] * 4
    reqs = [_req(i, tiers[i], types[i], "basics" if i % 2 else "food") for i in range(12)]
    asked = {"easy": 7.0, "medium": 10.0, "hard": 13.0}
    base = [_story(*(PASS_ALL if i in (0, 5) else FAIL_ALL), mean=10.0) for i in range(12)]
    again = [_story(*(PASS_ALL if i in (0, 5, 7) else FAIL_ALL), mean=10.0) for i in range(12)]
    plan = [_story(*(FAIL_ALL if i in (1, 2) else PASS_ALL), mean=asked[tiers[i]]) for i in range(12)]
    by_variant = {"baseline": base, **({"baseline_b": again} if replicate else {}), "plan": plan}
    meta = {"story model": "openai/gpt-oss-120b", "gpt model": "openai/gpt-oss-120b", "qwen model": "qwen/qwen3.8-27b"}
    return _data(reqs, by_variant, {"baseline_b": "baseline"} if replicate else {}, meta, range_prompt=("plan",))


def test_the_page_shows_the_noise_of_a_repeat_the_level_fit_and_each_reviewer_alone():
    page = report.render(_controls_run())
    for heading in ("Passed stories: each method against Baseline, request by request", "Does the story fit its level?", "Each reviewer on its own", "Failed reviews by story type"):
        assert heading in page
    assert "Baseline b made again" not in page and "Baseline b is Baseline made again for the same 12 requests" in page       # the noise note
    assert "the same method again: this is noise" in page
    assert "Passed by gpt (also the writer)" in page and "Passed by qwen</th>" in page                       # gpt is the model that wrote the stories
    assert "Easy (5 to 8 words)" in page and "Hard (10 to 16 words)" in page
    order = [page.index(x) for x in ("What the reviewers decided", "Passed stories: each method against", "Each method against Baseline", "Does the story fit its level?",
                                      "Each reviewer on its own", "Brief fit and cost")]
    assert order == sorted(order)


def test_the_fit_table_shows_a_method_that_misses_its_level_and_one_that_does_not():
    data = _controls_run()
    pairs = report._pairs(data)
    base = fit.by_method(pairs["baseline"])
    assert base[fit.IN] == 8 and base[fit.LONG] == 4 and base["tiers"]["easy"][fit.IN] == 0      # a 10-word sentence fits medium and hard, and is too long for easy
    assert fit.by_method(pairs["plan"])[fit.IN] == 12                                              # the plan writes each level's own length
    text = report._fit_table(data, pairs)
    assert "8 of 12" in text and "12 of 12" in text and "0 of 4" in text and "not told the range" in text


def test_a_file_that_repeats_nothing_says_the_noise_of_a_run_is_not_measured_and_how_to_measure_it():
    page = report.render(_controls_run(replicate=False))
    assert "No method is made twice in this file" in page and "--variants baseline,baseline_b" in page
    assert "the same method again" not in page


def test_the_reviewer_that_is_also_the_writer_is_named_and_a_default_story_model_counts_as_the_run_story_model():
    data = _controls_run()
    pairs = report._pairs(data)
    assert report._own_reviewers(data, pairs, ["gpt", "qwen"]) == ["gpt"]
    data["meta"] = {"story model": "x", "gpt model": "openai/gpt-oss-120b"}
    assert report._own_reviewers(data, report._pairs(data), ["gpt", "qwen"]) == []
    for row in data["results"].values():
        for e in row.values():
            e["models"]["story"] = "openai/gpt-oss-120b"
    assert report._own_reviewers(data, report._pairs(data), ["gpt", "qwen"]) == ["gpt"]


def test_a_file_without_a_review_shows_none_of_the_new_tables():
    plain, chosen = make("baseline,baseline_b")
    runner.run(plain, chosen, calls(), say=lambda *_: None, limit=2)
    page = report.render(plain)
    for heading in ("Passed stories: each method", "Each reviewer on its own", "Does the story fit its level?"):
        assert heading not in page
    assert "No model review in this file" in page


def test_labels_are_escaped_in_the_new_tables_and_an_old_file_without_the_new_fields_still_renders():
    data = _controls_run()
    data["variants"][0]["label"] = "<b>Base</b>"
    for v in data["variants"]:
        v.pop("replicate_of", None)               # a file made before 19 Nov
    page = report.render(data)
    assert "<b>Base</b></h3>" not in page and "&lt;b&gt;Base&lt;/b&gt;" in page and "Each reviewer on its own" in page


# --- two saved runs ------------------------------------------------------------------------------------------------------------------------------------------

def _two_runs():
    reqs = [_req(i, ["easy", "medium", "hard"][i % 3]) for i in range(10)]
    first = _data(reqs, {"baseline": [_story(*(PASS_ALL if i < 3 else FAIL_ALL)) for i in range(10)],
                         "rules": [_story(*(PASS_ALL if i < 3 else FAIL_ALL)) for i in range(10)]},
                  meta={"judge model": "gpt-oss-20b", "score_version": 4.1})
    second = _data([dict(r) for r in reqs], {"baseline": [_story(*(PASS_ALL if i < 5 else FAIL_ALL)) for i in range(10)],
                          "cascade": [_story(*PASS_ALL) for _ in range(10)]},
                   meta={"judge model": "gpt-oss-20b", "score_version": 4.1, "rating repeats": 3})
    return first, second


def test_two_runs_are_compared_only_on_requests_that_are_the_same_in_both():
    first, second = _two_runs()
    assert len(repeat.shared_requests(first, second)) == 10
    second["requests"][0] = dict(second["requests"][0], words=["other", "words"])           # the same id with other learner words is not the same request
    second["requests"][1] = dict(second["requests"][1], id="en-99")
    assert [r["id"] for r in repeat.shared_requests(first, second)] == [f"en-{i}" for i in range(2, 10)]
    c = repeat.compare(first, second, "baseline")
    assert c["shared"] == 8 and c["requests"] == 8 and c["method_a"] == c["method_b"] == "baseline"


def test_the_same_method_in_two_runs_is_its_own_noise_and_a_different_method_can_be_compared():
    first, second = _two_runs()
    c = repeat.compare(first, second, "baseline")
    assert (c["passed_a"], c["passed_b"], c["reviewed_b"]) == (3, 5, 10) and c["up"] == 2 and c["same"] == 8 and c["down"] == 0
    assert c["reading"] == "within noise"
    d = repeat.compare(first, second, "rules", "cascade")
    assert d["method_a"] == "rules" and d["method_b"] == "cascade" and d["up"] == 7 and d["reading"] == "clear gain"
    assert [x["method_a"] for x in repeat.same_method_everywhere(first, second)] == ["baseline"]


def test_what_differs_in_how_two_runs_were_made_is_listed_next_to_the_numbers():
    first, second = _two_runs()
    assert repeat.meta_differences(first, second) == [("rating repeats", None, 3)]
    text = repeat.text(repeat.same_method_everywhere(first, second))
    assert "baseline: 10 requests; passed 3 -> 5 of 10" in text and "made differently" in text and "rating repeats: None | 3" in text
    assert repeat.text([]).startswith("Nothing to compare")


def test_the_script_compares_two_files_and_says_what_is_wrong_when_it_cannot(tmp_path, capsys):
    import compare_story_runs as script
    first, second = _two_runs()
    a, b = tmp_path / "a.json", tmp_path / "b.json"
    runner.save(first, str(a))
    runner.save(second, str(b))
    assert script.main([str(a), str(b)]) == 0
    out = capsys.readouterr().out
    assert "10 requests are the same in both files" in out and "baseline: 10 requests" in out
    assert script.main([str(a), str(b), "--a", "rules", "--b", "cascade"]) == 0 and "rules -> cascade" in capsys.readouterr().out
    assert script.main([str(a), str(b), "--a", "nope"]) == 2 and "has no method 'nope'" in capsys.readouterr().err
    assert script.main([str(a), str(tmp_path / "missing.json")]) == 2 and "Cannot read the runs" in capsys.readouterr().err
    (tmp_path / "other.json").write_text(json.dumps({"format": "something else"}), encoding="utf-8")
    assert script.main([str(a), str(tmp_path / "other.json")]) == 2


# --- the settings reach the containers ------------------------------------------------------------------------------------------------------------------------

def test_every_story_option_the_code_reads_reaches_both_containers_and_is_documented():
    """19 Nov 2026: STORY_REFINE, STORY_WRITER_RULES and STORY_REPAIR_NATURALNESS were read by the code but never passed by docker-compose, so setting them in .env did nothing."""
    import re
    root = Path(__file__).resolve().parents[2]
    names = set()
    for folder in ("tutor_core/tutor_core", "api/app"):
        for path in (root / folder).rglob("*.py"):
            names |= set(re.findall(r'(?:get|getenv)\(\s*["\'](STORY_[A-Z_]+)["\']', path.read_text(encoding="utf-8")))
    names -= {"STORY_ALLOW_UNMEASURED"}                 # a flag of the measurement scripts, not of the app
    compose, docs = (root / "docker-compose.yml").read_text(encoding="utf-8"), (root / "docs/ENVIRONMENT.md").read_text(encoding="utf-8")
    assert len(names) >= 12
    assert [n for n in sorted(names) if compose.count(f"- {n}=") != 2] == []
    assert [n for n in sorted(names) if n not in docs] == []
