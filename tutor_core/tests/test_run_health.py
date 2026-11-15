"""A run that says what happened to itself (scripts/story_eval/health.py, 14 Nov 2026): reasons, completeness, log, preflight, time budget, kill signal."""
import json
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))

from story_eval import fixed_set, health, report, runner, variants as vs  # noqa: E402
import run_story_methods as cli  # noqa: E402

GOOD = ("María vive en una casa grande cerca del mar. Cada mañana ella abre la ventana y mira el agua. Su amigo Pedro llega con pan fresco. "
        "Los dos desayunan juntos en el jardín y hablan de sus planes. Después caminan por la playa hasta la hora de comer. "
        "Por la tarde vuelven a casa y leen un libro. Al final del día los dos duermen contentos.")
DAILY = ("Groq API error 429: Rate limit reached for model `openai/gpt-oss-120b` in organization `org_01abcdef2345` service tier `on_demand` on tokens per day (TPD): "
         "Limit 200000, Used 199264, Requested 3118. Please try again in 8m25.5s. Need more tokens? Upgrade to Dev Tier today at https://console.groq.com/settings/billing")
MINUTE = "Groq API error 429: Rate limit reached for model `qwen/qwen3.8-27b` on tokens per minute (TPM): Limit 8000, Used 7900, Requested 700. Please try again in 4.2s."


def model(prompt):
    return "===STORY===\n" + GOOD


def make(names="baseline,two_pass"):
    chosen = vs.resolve(names)
    return runner.new_data(fixed_set.build(["es"], extras=False), chosen, {"score_version": 4.1}), chosen


def calls(m=model):
    return runner.Calls(runner.Channel(m))


# --- errors as one readable line ------------------------------------------------------------------------------------------------------------------------------

def test_a_daily_limit_reads_with_its_numbers_and_never_the_organisation():
    line = health.describe_error(DAILY)
    assert line == "daily limit on openai/gpt-oss-120b (tokens per day: used 199,264 of 200,000, this call needs 3,118), retry in 8m26s"
    assert "org_01abcdef2345" not in health.scrub(DAILY) and "org_***" in health.scrub(DAILY)


def test_a_per_minute_limit_is_not_a_daily_one_and_the_other_kinds_are_told_apart():
    assert health.classify(MINUTE) == "rate_limit" and health.classify(DAILY) == "rate_limit_long"
    assert health.classify("Groq API error 429 ... Please try again in 7h12m.") == "rate_limit_long"
    assert health.classify("Groq API error 401: Invalid API Key") == "key"
    assert health.classify("Groq API error 404: The model `qwen/qwen3.6-27b` does not exist") == "model"
    assert health.classify("Groq API error 400: bad request") == "bad_request" and health.classify("Read timed out") == "timeout"
    assert health.classify("Groq API error 503: overloaded") == "server" and health.classify("boom") == "other"
    assert "check the model id" in health.describe_error("Groq API error 404: The model `x` does not exist")
    assert health.classify("Groq API error 400: Requested 4010 tokens") == "bad_request"          # 4010 is not a 401


def test_a_key_in_a_message_is_removed():
    assert "gsk_" not in health.scrub("Incorrect API key provided: gsk_abcdefghijklmnop1234. Authorization: Bearer abcdefghijkl1234")


# --- completeness ---------------------------------------------------------------------------------------------------------------------------------------

def test_a_cut_run_says_what_is_missing_and_where_it_would_go_on():
    data, chosen = make()
    first = data["requests"][0]["id"]
    data["results"][first] = {"baseline": {"ok": True, "audits": {}}}
    c = health.completeness(data)
    n = len(data["requests"])
    assert c["done"] == 1 and c["total"] == 2 * n and not c["complete"] and c["next"] == (first, "two_pass")
    assert health.state(data).startswith("INCOMPLETE") and "killed" in health.state(data)
    data["meta"]["stopped"] = "interrupted (at es-0, two_pass)"
    assert health.state(data) == "STOPPED"
    text = health.status_text(data)
    assert "Done: 1 of" in text and "Why it stopped: interrupted" in text and f"Next to make: {first} with two_pass" in text and "--resume" in text


def test_a_finished_run_says_so():
    data, chosen = make("baseline")
    assert runner.run(data, chosen, calls(), say=lambda *_: None)
    assert health.state(data) == "FINISHED" and "To continue" not in health.status_text(data)


def test_reviews_that_did_not_work_are_counted_with_the_reason():
    data, chosen = make("baseline")
    first = data["requests"][0]["id"]
    bad = {"ok": False, "hits": [], "error": MINUTE, "naturalness": {"ok": False, "error": "RuntimeError: " + DAILY}}
    good = {"ok": True, "hits": [], "error": "", "naturalness": {"ok": True, "score": 4}}
    runner.run(data, chosen, calls(), say=lambda *_: None, limit=1)
    data["results"][first]["baseline"]["audits"] = {"gpt": good, "qwen": bad}
    slot = health.completeness(data)["reviews"]
    assert slot["gpt"]["audit_ok"] == 1 and slot["qwen"]["asked"] == 1 and slot["qwen"]["audit_ok"] == 0 and slot["qwen"]["rating_ok"] == 0
    assert any(k.startswith("review: rate limit") for k in slot["qwen"]["why"]) and any(k.startswith("rating: daily limit") for k in slot["qwen"]["why"])
    page = report.render(data)
    assert "some are missing" in page and "Reviewer <b>qwen</b>: 0 of 1 reviews" in page


def test_the_page_opens_with_the_state_and_a_partial_file_cannot_pass_for_a_whole_one():
    data, chosen = make("baseline,two_pass")
    runner.run(data, vs.resolve("baseline"), calls(), say=lambda *_: None, limit=1)          # one real entry; two_pass and the other requests are missing
    data["meta"].pop("stopped", None)          # as a killed process leaves it: nothing wrote a reason
    page = report.render(data)
    assert page.index("INCOMPLETE") < page.index("Mean score by language") and "Next to make" in page


# --- the run's own record -------------------------------------------------------------------------------------------------------------------------------

def test_the_log_keeps_the_time_and_drops_the_account_and_is_capped():
    shown = []
    log = health.RunLog(keep=3, out=shown.append)
    log("one", "two")
    log(DAILY)
    log("a"), log("b")
    tail = log.tail()
    assert len(tail) == 3 and shown[0] == "one two" and all(len(t) > 9 and t[2] == ":" for t in tail)
    assert "org_01abcdef2345" not in " ".join(tail) and "org_01abcdef2345" in shown[1]          # the screen has what it had; the file does not


def test_the_run_info_has_settings_and_never_a_key():
    env = {"STORY_REFINE": "2", "GROQ_API_KEY": "gsk_secretsecret123", "GROQ_QWEN_MODEL": "qwen/qwen3.8-27b", "GROQ_MODEL": "openai/gpt-oss-120b", "PATH": "/bin", "KAGGLE_KERNEL_RUN_TYPE": "Batch"}
    info = health.run_info(["--variants", "writer", "--audit-models", "gpt,qwen"], env)
    assert info["settings"] == {"GROQ_MODEL": "openai/gpt-oss-120b", "GROQ_QWEN_MODEL": "qwen/qwen3.8-27b", "STORY_REFINE": "2"}
    assert "gsk_" not in json.dumps(info) and info["command"] == "--variants writer --audit-models gpt,qwen" and info["kaggle"] == "Batch" and info["started"].endswith("UTC")


def test_every_save_writes_the_json_the_report_and_a_status_file_with_the_log(tmp_path):
    data, chosen = make("baseline")
    out = str(tmp_path / "run.html")
    log = health.RunLog(out=lambda *_: None)
    log("hello from the run")
    data["meta"]["run"] = health.run_info(["--variants", "baseline"], {})
    runner.run(data, chosen, calls(), on_saved=lambda d: cli.write_outputs(d, out, log), say=log, limit=1)
    saved = json.loads((tmp_path / "run.json").read_text())
    assert any("hello from the run" in l for l in saved["meta"]["log"]) and saved["meta"]["run"]["last_save"].endswith("UTC")
    status = (tmp_path / "run.status.txt").read_text()
    assert status.startswith("State: ") and "Done: 1 of" in status and "Command: --variants baseline" in status
    page = (tmp_path / "run.html").read_text()
    assert "Run log (last" in page and "hello from the run" in page and "<h3>This run</h3>" in page


# --- stopping cleanly -----------------------------------------------------------------------------------------------------------------------------------

def test_a_time_budget_stops_between_two_stories_and_says_so():
    data, chosen = make("baseline")
    saved = []
    done = runner.run(data, chosen, calls(), on_saved=lambda d: saved.append(json.dumps(d)), say=lambda *_: None, deadline=time.monotonic() - 1)
    assert done is False and "time budget" in data["meta"]["stopped"] and "(at es-0, baseline)" in data["meta"]["stopped"] and not data["results"].get("es-0")
    assert saved and "time budget" in saved[-1]
    again = runner.run(data, chosen, calls(), say=lambda *_: None)
    assert again and "stopped" not in data["meta"]


def test_a_kill_signal_becomes_a_recorded_stop_with_its_number(monkeypatch):
    def killed(prompt):
        raise KeyboardInterrupt("signal 15: the host or the notebook stopped the process")
    data, chosen = make("baseline")
    assert runner.run(data, chosen, calls(killed), say=lambda *_: None) is False
    assert data["meta"]["stopped"].startswith("interrupted (signal 15: the host or the notebook stopped the process) (at es-0, baseline)")


def test_a_story_stopped_by_a_daily_limit_says_which_limit():
    def limited(prompt):
        raise RuntimeError(DAILY)
    data, chosen = make("baseline")
    assert runner.run(data, chosen, calls(limited), say=lambda *_: None) is False
    assert data["meta"]["stopped"] == ("limit too long to wait for: daily limit on openai/gpt-oss-120b (tokens per day: used 199,264 of 200,000, this call needs 3,118), "
                                       "retry in 8m26s (at es-0, baseline)")
    assert "org_01" not in json.dumps(data)


# --- preflight ------------------------------------------------------------------------------------------------------------------------------------------

class Named:
    def __init__(self, fn, model_name):
        self.fn, self.model = fn, model_name

    def __call__(self, prompt):
        return self.fn(prompt)


def test_the_preflight_asks_each_model_once_and_finds_what_would_stop_the_run():
    asked = []

    def ok(prompt):
        asked.append(prompt)
        return "OK"

    def wrong_model(prompt):
        raise RuntimeError("Groq API error 404: The model `qwen/qwen3.6-27b` does not exist or you do not have access to it.")

    def daily(prompt):
        raise RuntimeError(DAILY)

    def blip(prompt):
        raise RuntimeError("Groq API error 503: overloaded")

    shared = runner.Channel(Named(ok, "openai/gpt-oss-120b"))
    channels = {"story": shared, "gpt model": shared, "review qwen": runner.Channel(Named(wrong_model, "qwen/qwen3.6-27b")),
                "judge": runner.Channel(Named(daily, "judge")), "review": runner.Channel(Named(blip, "blip"))}
    lines = []
    rows = health.preflight(channels, say=lines.append)
    assert asked == [health.PING] and len(rows) == 4          # the shared channel was asked once, under both names
    assert rows[0]["channel"] == "story + gpt model" and rows[0]["ok"] and rows[0]["model"] == "openai/gpt-oss-120b"
    bad = health.fatal(rows)
    assert [r["channel"] for r in bad] == ["review qwen", "judge"]          # a wrong model and a daily limit stop the run; a server blip does not
    assert "check the model id" in bad[0]["why"] and bad[1]["kind"] == "rate_limit_long"
    assert any("FAILED" in l for l in lines) and not any("org_01abcdef2345" in r["why"] for r in rows)
    assert shared.meter.calls == 0          # the ping is not counted in the first story


# --- the whole command, with the model faked -----------------------------------------------------------------------------------------------------------

@pytest.fixture
def cli_env(monkeypatch):
    import signal
    from tutor_core import groq
    saved = {n: signal.getsignal(getattr(signal, n)) for n in ("SIGTERM", "SIGHUP") if hasattr(signal, n)}
    monkeypatch.setenv("GROQ_API_KEY", "gsk_testtesttest1234")
    for name in ("GROQ_API_KEY_2", "GROQ_JUDGE_MODEL", "GROQ_AUDIT_MODEL"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(groq, "make_model_call", lambda *a, **k: None)
    yield monkeypatch, groq
    for name, handler in saved.items():
        signal.signal(getattr(signal, name), handler)


ARGS = ["--variants", "baseline", "--languages", "es", "--count", "2", "--limit", "1", "--no-translate", "--tpm", "100000000"]


def test_the_command_checks_the_models_first_and_leaves_a_self_explaining_set_of_files(cli_env, tmp_path):
    monkeypatch, groq = cli_env
    prompts = []

    def fake(prompt, **kw):
        prompts.append(prompt)
        return "OK" if prompt == health.PING else "===STORY===\n" + GOOD
    monkeypatch.setattr(groq, "call_groq", fake)
    out = tmp_path / "run.html"
    assert cli.main(ARGS + ["--out", str(out)]) == 1          # --limit 1 stops after one story of two: saved, not finished
    assert prompts[0] == health.PING and sum(p == health.PING for p in prompts) == 1
    saved = json.loads((tmp_path / "run.json").read_text())
    assert saved["meta"]["preflight"][0]["ok"] and saved["meta"]["run"]["command"].startswith("--variants baseline")
    assert any("Preflight" in l for l in saved["meta"]["log"]) and any("preflight story" in l for l in saved["meta"]["log"])
    status = (tmp_path / "run.status.txt").read_text()
    assert "State: STOPPED" in status and "Done: 1 of 2" in status and "--limit 1 reached" in status and "Next to make: es-1 with baseline" in status
    assert "STOPPED" in (tmp_path / "run.html").read_text()


def test_the_command_does_not_start_when_a_model_id_is_wrong_and_says_why_in_the_files(cli_env, tmp_path):
    monkeypatch, groq = cli_env
    calls_made = []

    def fake(prompt, **kw):
        calls_made.append(prompt)
        raise RuntimeError("Groq API error 404: The model `openai/gpt-oss-120b` does not exist or you do not have access to it. org_01abcdef2345")
    monkeypatch.setattr(groq, "call_groq", fake)
    out = tmp_path / "run.html"
    assert cli.main(ARGS + ["--out", str(out)]) == 1
    assert calls_made == [health.PING]                          # one tiny call, no story was attempted
    saved = json.loads((tmp_path / "run.json").read_text())
    assert saved["meta"]["stopped"].startswith("preflight failed, nothing was made: story: model not found (404)") and not any(saved["results"].values())
    assert "org_01abcdef2345" not in json.dumps(saved)
    assert "preflight failed" in (tmp_path / "run.status.txt").read_text() and "State: STOPPED" in (tmp_path / "run.status.txt").read_text()


def test_no_preflight_goes_straight_to_the_stories(cli_env, tmp_path):
    monkeypatch, groq = cli_env
    seen = []
    monkeypatch.setattr(groq, "call_groq", lambda prompt, **kw: seen.append(prompt) or "===STORY===\n" + GOOD)
    cli.main(ARGS + ["--no-preflight", "--out", str(tmp_path / "run.html")])
    assert health.PING not in seen and seen


def test_a_resume_keeps_the_earlier_log_and_remembers_why_the_earlier_run_stopped(cli_env, tmp_path):
    monkeypatch, groq = cli_env
    monkeypatch.setattr(groq, "call_groq", lambda prompt, **kw: "OK" if prompt == health.PING else "===STORY===\n" + GOOD)
    out = tmp_path / "run.html"
    cli.main(ARGS + ["--out", str(out)])
    first = json.loads((tmp_path / "run.json").read_text())
    first["meta"]["stopped"] = "limit too long to wait for: daily limit"          # as an earlier cut run would have left it
    (tmp_path / "run.json").write_text(json.dumps(first))
    cli.main(["--variants", "baseline", "--languages", "es", "--count", "2", "--no-translate", "--tpm", "100000000", "--resume", str(tmp_path / "run.json")])
    again = json.loads((tmp_path / "run.json").read_text())
    assert again["meta"]["run"]["earlier"][-1]["stopped"] == "limit too long to wait for: daily limit" and "stopped" not in again["meta"] and health.state(again) == "FINISHED"
    assert sum("Preflight" in l for l in again["meta"]["log"]) == 2 and len(again["meta"]["log"]) > len(first["meta"]["log"])
