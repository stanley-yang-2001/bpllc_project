"""The Story Test Desk's data and its local server, on a made-up report folder (11 Nov 2026). No Docker, no Groq."""
import json
import os
import sys
import threading
import time
import urllib.request
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path[:0] = ["tutor_core", "scripts"]
import story_desk  # noqa: E402
from story_eval import desk  # noqa: E402

LOG = """4 requests x 5 methods: about 174 model calls, 313,200 tokens, at least 45 minutes at 7000 tokens a minute.
Keys per family (the next one is used when a key hits its limit): GROQ_API_KEY x2, GROQ_QWEN_API_KEY x1, GROQ_JUDGE_API_KEY x1; switching only when Groq refuses
[1/4] en-0 easy   baseline   score 98.6  calls 1     4.6s (model 2.7s)
  pacing: waiting 40s to stay under the token limit
  GROQ_API_KEY is rate limited (try again in 337s) [TPD]
  switching key GROQ_API_KEY -> GROQ_API_KEY_2 (at its limit)
[1/4] en-0 easy   plan       score 96.0  calls 2     3.1s (model 3.1s)
  rate limited: waiting 85s (try 1/8)
"""
SUMMARY_RUNNING = "Overnight run started Wed 11/11/2026  9:36:17.18 \nStep 1 story test started  9:36:32.04 \n"
SUMMARY_DONE = SUMMARY_RUNNING + "Step 1 story test: exit code 0 at  9:59:04.29. 0 means it finished. \nFinished Wed 11/11/2026  9:59:30.00 \n"
RESULT = {"variants": [{"name": "baseline", "label": "Baseline", "note": "n"}], "requests": [{"id": "en-0", "code": "en", "tier": "easy", "story_type": "story", "topic": "t", "words": ["a", "b"]}],
          "results": {"en-0": {"baseline": {"score": {"score": 98.6, "parts": {"naturalness": None}}, "audit_union": {"score": 59.7}, "audit_scores": {"gpt": {"score": 71.6, "parts": {"naturalness": 50.0}}},
                                            "audits": {"gpt": {"hits": [1, 2]}}, "notes": ["judge reviewed #1: 2 mistake(s) found; naturalness 3/5"], "calls": 1, "seconds": 4.6,
                                            "trace": [{"phase": "observe", "label": "start", "tools": [{"tool": "model review", "found": 2}], "gates": [], "score": {"score": 71.0}},
                                                      {"phase": "verify", "round": 1, "kept": True, "before": 71.0, "after": 88.5}]}}},
          "meta": {"story model": "m"}, "created": "x"}


def make(tmp_path, summary, age=0):
    folder = tmp_path / "test-reports" / "overnight-20261111_093617"
    folder.mkdir(parents=True)
    (folder / "SUMMARY.txt").write_text(summary)
    (folder / "01-story-test.log").write_text(LOG)
    old = time.time() - age
    os.utime(folder / "01-story-test.log", (old, old))
    (tmp_path / "scripts").mkdir()
    return folder


def test_log_and_summary_are_parsed(tmp_path):
    make(tmp_path, SUMMARY_DONE)
    run = desk.collect(tmp_path / "test-reports", tmp_path / "scripts")["runs"][0]
    assert run["total"] == 20 and len(run["entries"]) == 2 and run["entries"][1]["variant"] == "plan"
    assert run["pacing"] == {"count": 1, "seconds": 40} and run["waits"][0]["wait"] == 85
    assert run["limits"][0] == {"key": "GROQ_API_KEY", "hint": 337, "kind": "TPD", "to": "GROQ_API_KEY_2", "before": "en-0 plan"}
    assert run["keys"]["GROQ_API_KEY"] == 2 and run["exit"] == 0 and run["storyStart"] == 9 * 3600 + 36 * 60 + 32 and not run["running"]


def test_running_means_no_finish_line_and_a_fresh_log(tmp_path):
    make(tmp_path, SUMMARY_RUNNING, age=30)
    assert desk.collect(tmp_path / "test-reports", tmp_path / "scripts")["runs"][0]["running"]
    make_old = tmp_path / "old"
    make_old.mkdir()
    make(make_old, SUMMARY_RUNNING, age=3600)
    assert not desk.collect(make_old / "test-reports", make_old / "scripts")["runs"][0]["running"]


def test_results_are_read_from_scripts_or_the_report_folder(tmp_path):
    folder = make(tmp_path, SUMMARY_DONE)
    (tmp_path / "scripts" / "overnight_20261111_093617.json").write_text(json.dumps(RESULT))
    data = desk.collect(tmp_path / "test-reports", tmp_path / "scripts")
    cell = data["results"]["cells"][0]
    assert data["resultsRun"] == "20261111_093617" and cell["reviewed"] == 59.7 and cell["natGpt"] == 50.0 and cell["judgeNat"] == [3] and cell["hitsGpt"] == 2
    assert data["results"]["byVariant"][0]["offline"] == 98.6
    assert cell["trace"] == ["Observe (start): score 71; findings: model review 2", "Verify, round 1: kept, score 71 to 88.5"]
    (tmp_path / "scripts" / "overnight_20261111_093617.json").unlink()
    (folder / "overnight_20261111_093617.json").write_text(json.dumps(RESULT))
    assert desk.collect(tmp_path / "test-reports", tmp_path / "scripts")["results"] is not None


def test_key_evidence_and_key_status(tmp_path):
    make(tmp_path, SUMMARY_DONE)
    (tmp_path / "scripts" / "key_status.json").write_text(json.dumps({"checked_at": "t", "keys": []}))
    data = desk.collect(tmp_path / "test-reports", tmp_path / "scripts")
    assert data["keyEvidence"]["GROQ_API_KEY"]["switchedTo"] == ["GROQ_API_KEY_2"] and data["keyEvidence"]["GROQ_API_KEY"]["kinds"] == ["TPD"]
    assert data["keyStatus"]["checked_at"] == "t" and data["families"]["GROQ_API_KEY"]["keys"] == 2


def test_an_empty_folder_gives_an_empty_desk(tmp_path):
    data = desk.collect(tmp_path / "nothing", tmp_path / "scripts")
    assert data["runs"] == [] and data["results"] is None and data["resultsRun"] is None


def test_the_server_serves_the_page_the_state_and_the_key_check(tmp_path):
    make(tmp_path, SUMMARY_DONE)
    calls = []

    class Done:
        returncode, stdout, stderr = 0, "ok", ""
    handler = story_desk.make_handler(tmp_path, run_command=lambda *a, **k: calls.append(a[0]) or Done())
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        page = urllib.request.urlopen(base + "/").read().decode()
        assert "Story Test Desk" in page and "let DATA = null;" in page
        state = json.loads(urllib.request.urlopen(base + "/api/state").read())
        assert state["live"] and state["runs"][0]["id"] == "20261111_093617"
        posted = json.loads(urllib.request.urlopen(urllib.request.Request(base + "/api/key-status", data=b"", method="POST")).read())
        assert posted["ok"] and calls[0][:4] == ["docker", "compose", "exec", "-T"]
        try:
            urllib.request.urlopen(base + "/nope")
            assert False
        except urllib.error.HTTPError as e:
            assert e.code == 404
    finally:
        server.shutdown()


def test_a_refine_step_is_its_own_run_and_the_checks_bar_follows_it(tmp_path):
    folder = make(tmp_path, SUMMARY_DONE.replace("Finished", "Step 2 refine test started  10:00:10.00 \nStep 2 refine test: exit code 0 at 10:20:00.00. \nStep 3 run-checks.bat --round: exit code 0 at 10:40:00.00. \nFinished"))
    (folder / "02-refine-test.log").write_text(LOG.replace("en-0 easy   baseline", "en-0 easy   refine  "))
    (tmp_path / "scripts" / "refine_20261111_093617.json").write_text(json.dumps(RESULT))
    runs = desk.collect(tmp_path / "test-reports", tmp_path / "scripts")["runs"]
    assert [r["id"] for r in runs] == ["20261111_093617", "20261111_093617-refine"] and [r["kind"] for r in runs] == ["cascade", "refine"]
    assert runs[0]["checksEnd"] is None and runs[1]["checksEnd"] == 10 * 3600 + 40 * 60 and runs[1]["storyStart"] == 10 * 3600 + 10
    assert runs[1]["json"] and not runs[0]["json"] and runs[1]["exit"] == 0
