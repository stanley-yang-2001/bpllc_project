"""The rating lab (scripts/rate_texts.py, story_eval/ratinglab.py, 16 Nov 2026) and the opt-in rating prompt v2, with the models faked."""
import json
import signal
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from story_eval import fixed_set, health, ratinglab, runner, variants as vs  # noqa: E402
import rate_texts  # noqa: E402
from tutor_core import naturalness  # noqa: E402

TEXT = "I am Ana. I like tea. Tom likes tea too. We drink tea at home."


def source(n=3):
    chosen = vs.resolve("baseline,rules")
    data = runner.new_data(fixed_set.build(["en"], per_language=n, extras=False), chosen, {})
    for r in data["requests"]:
        data["results"][r["id"]] = {v.name: {"ok": True, "text": f"{TEXT} {r['id']} {v.name}"} for v in chosen}
    return data


def test_the_v2_answer_is_two_small_ratings_and_either_one_at_1_fails_the_text():
    parse = naturalness.parse
    assert parse('{"sense": 3, "wording": 3}').score == 5 and parse('{"sense": 3, "wording": 2, "reason": "x"}').score == 4
    assert parse('{"sense": 2, "wording": 2}').score == 3 and parse('{"sense": 2, "wording": 1}').score == 2
    assert parse('{"sense": 3, "wording": 1}').score == 2 and parse('{"sense": 1, "wording": 1}').score == 1
    assert parse('{"sense": 3, "wording": 2}').as_dict()["sense"] == 3 and "sense" not in parse('{"score": 4}').as_dict()
    assert not parse('{"sense": 9, "wording": 9}').ok
    seen = []
    naturalness.rate(lambda p: seen.append(p) or '{"sense": 3, "wording": 3}', TEXT, "English", prompt="v2", level="easy")
    naturalness.rate(lambda p: seen.append(p) or '{"score": 4}', TEXT, "English")
    assert "at a easy level" in seen[0] and "SENSE" in seen[0] and "Rate how NATURAL" in seen[1] and "SENSE" not in seen[1]


def test_the_lab_rates_each_story_again_and_measures_how_steady_a_reviewer_is():
    data = ratinglab.new_data("x.json", ratinglab.stories_from(source()), ["gpt", "qwen"], ["v1", "v2"], 3)
    assert len(data["stories"]) == 6
    calls = {"n": 0}

    def rater(call, text, language, prompt="v1", level=""):
        calls["n"] += 1
        return naturalness.Naturalness(True, 4.0 if "baseline" in text else 2.0)
    chans = {a: runner.Channel(lambda p: "") for a in ("gpt", "qwen")}
    assert ratinglab.run(data, chans, say=lambda *_: None, rater=rater) is True and calls["n"] == 6 * 2 * 2 * 3
    s = ratinglab.summarize(data)
    one = s["each"][("gpt", "v1")]
    assert one["identical"] == 1.0 and one["flips"] == 0.0 and one["fail_share"] == 0.5 and one["icc"] == pytest.approx(1.0)
    assert s["between_reviewers"][("gpt", "qwen", "v1")]["identical"] == 1.0 and s["between_prompts"][("gpt", "v1", "v2")]["passfail"] == 0.0
    text = ratinglab.text_report(data)
    assert "values used" in text and "flips" in text and "gpt vs qwen" in text


def test_a_rating_that_wavers_across_the_pass_line_counts_as_a_flip():
    data = ratinglab.new_data("x.json", ratinglab.stories_from(source(n=2)), ["gpt"], ["v1"], 2)
    turn = {"i": 0}

    def rater(call, text, language, prompt="v1", level=""):
        turn["i"] += 1
        return naturalness.Naturalness(True, 3.0 if turn["i"] % 2 else 2.0)
    ratinglab.run(data, {"gpt": runner.Channel(lambda p: "")}, say=lambda *_: None, rater=rater)
    e = ratinglab.summarize(data)["each"][("gpt", "v1")]
    assert e["flips"] == 1.0 and e["identical"] == 0.0 and e["within_one"] == 1.0


def test_a_daily_limit_stops_the_lab_with_the_reason_and_a_resume_asks_only_what_is_missing():
    data = ratinglab.new_data("x.json", ratinglab.stories_from(source(n=2)), ["gpt"], ["v1"], 1)
    daily = "RuntimeError: Groq API error 429: Rate limit reached on tokens per day (TPD): Limit 200000, Used 199900, Requested 700. Please try again in 8m25.5s."
    state = {"n": 0}

    def rater(call, text, language, prompt="v1", level=""):
        state["n"] += 1
        return naturalness.Naturalness(True, 3.0) if state["n"] <= 2 else naturalness.Naturalness(False, error=daily)
    saved = []
    chans = {"gpt": runner.Channel(lambda p: "")}
    assert ratinglab.run(data, chans, say=lambda *_: None, rater=rater, on_saved=lambda d: saved.append(len(d["ratings"]))) is False
    assert "daily limit" in data["meta"]["stopped"] and saved
    asked = []

    def again(call, text, language, prompt="v1", level=""):
        asked.append(text)
        return naturalness.Naturalness(True, 4.0)
    assert ratinglab.run(data, chans, say=lambda *_: None, rater=again) is True
    assert len(asked) == len(data["stories"]) - 2 and "stopped" not in data["meta"]
    assert all(r["ok"] for r in data["ratings"].values())


@pytest.fixture
def cli_env(monkeypatch):
    from tutor_core import groq
    saved = {n: signal.getsignal(getattr(signal, n)) for n in ("SIGTERM", "SIGHUP") if hasattr(signal, n)}
    monkeypatch.setenv("GROQ_API_KEY", "gsk_testtesttest1234")
    monkeypatch.delenv("GROQ_API_KEY_2", raising=False)
    yield monkeypatch, groq
    for name, handler in saved.items():
        signal.signal(getattr(signal, name), handler)


def test_the_command_rates_saved_stories_resumes_and_prints_the_table(cli_env, tmp_path, capsys):
    monkeypatch, groq = cli_env

    def fake(prompt, **kw):
        if prompt == health.PING:
            return "OK"
        return '{"sense": 3, "wording": 2, "reason": "fine"}' if "SENSE" in prompt else '{"score": 3, "reason": "ok"}'
    monkeypatch.setattr(groq, "call_groq", fake)
    src = tmp_path / "stories.json"
    runner.save(source(n=2), str(src))
    out = tmp_path / "lab.json"
    args = ["--from", str(src), "--reviewers", "gpt,qwen", "--prompts", "v1,v2", "--repeats", "2", "--tpm", "100000000", "--out", str(out)]
    assert rate_texts.main(args) == 0
    saved = json.loads(out.read_text())
    assert len(saved["ratings"]) == 4 * 2 * 2 * 2 and all(r["ok"] for r in saved["ratings"].values())
    assert {r["score"] for k, r in saved["ratings"].items() if "|v1|" in k} == {3.0} and {r["score"] for k, r in saved["ratings"].items() if "|v2|" in k} == {4.0}
    assert "values used" in out.with_suffix(".txt").read_text()
    assert rate_texts.main(["--report", str(out)]) == 0 and "gpt vs qwen" in capsys.readouterr().out
    assert rate_texts.main(["--resume", str(out), "--tpm", "100000000"]) == 0
    assert rate_texts.main(["--reviewers", "llama"]) == 2 and rate_texts.main([]) == 2
