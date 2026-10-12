"""The command-line scripts, run the way a person runs them, against a fake Langflow on a real socket.

Why this exists: scripts/spike_tweaks.py first shipped with a `--pause` option that was documented, used in the code and
covered by unit tests of the suite function, yet never registered with the argument parser, so the first real run
died with "unrecognized arguments". The unit tests never called main(). These do, through a subprocess, so the
parser, the HTTP code and the file output are all exercised.

    python tests/test_cli_end_to_end.py
"""
import glob
import json
import os
import subprocess
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fake_langflow import ACCOUNT, FakeLangflow  # noqa: E402

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
SPIKE = os.path.join(ROOT, "scripts", "spike_tweaks.py")
CAPTURE = os.path.join(ROOT, "scripts", "capture_fixtures.py")
failures = []


def check(name, condition, detail=""):
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        failures.append(name)


def run(script, *args):
    env = {k: v for k, v in os.environ.items() if k != "LANGFLOW_API_KEY"}
    return subprocess.run([sys.executable, script, *args], capture_output=True, text=True, timeout=120, env=env)


def test_spike_with_the_exact_options_a_person_types():
    print("spike_tweaks.py, the command that failed in the first live run")
    with FakeLangflow(key="SpikeWhoAmI-KuKYY") as lf, tempfile.TemporaryDirectory() as out:
        r = run(SPIKE, "--base-url", lf.url, "--flow", "ca6efe52-edeb-486f-ab44-f07692083b88",
                "--key", "SpikeWhoAmI-KuKYY", "--users", "2", "--pause", "0.2", "--out-dir", out)
        check("it runs (exit 0)", r.returncode == 0, r.stdout[-400:] + r.stderr[-400:])
        check("--pause is accepted", "unrecognized arguments" not in r.stderr, r.stderr)
        check("it reports Plan A working", "PLAN A WORKS" in r.stdout, r.stdout[-500:])
        check("every check passed", "PASS         control" in r.stdout and "PASS         parallel" in r.stdout
              and "PASS         overlap" in r.stdout and "PASS         override" in r.stdout, r.stdout)
        saved = glob.glob(os.path.join(out, "spike_tweaks_*.json"))
        check("raw responses were saved", len(saved) == 1)
        check("the API key used was the one the server issued",
              all(q[2] in (None, "fake-api-key") for q in lf.requests if q[0] == "POST"))


def test_spike_with_integer_ids_reproduces_the_silent_drop():
    print("spike_tweaks.py --int-ids (what the second live run did)")
    with FakeLangflow(key="K") as lf, tempfile.TemporaryDirectory() as out:
        r = run(SPIKE, "--base-url", lf.url, "--flow", "f", "--key", "K", "--users", "2", "--int-ids", "--out-dir", out)
        check("it exits non-zero", r.returncode == 1, r.stdout[-300:])
        check("the control passes", "PASS         control" in r.stdout, r.stdout)
        check("parallel FAILS: the tool saw NONE", "FAIL         parallel" in r.stdout and "'NONE'" in r.stdout, r.stdout)
        check("it says integers were sent", "sent as integers" in r.stdout)
        r = run(SPIKE, "--base-url", lf.url, "--flow", "f", "--key", "K", "--users", "2", "--string-ids", "--out-dir", out)
        check("--string-ids is still accepted and passes", r.returncode == 0 and "PLAN A WORKS" in r.stdout, r.stdout[-300:])
        check("the default run says strings were sent", "sent as strings" in r.stdout)


def test_spike_says_so_when_the_node_still_has_the_old_code():
    print("spike_tweaks.py against a node running the ORIGINAL spike code (third live run)")
    with FakeLangflow(key="K", legacy=True) as lf, tempfile.TemporaryDirectory() as out:
        r = run(SPIKE, "--base-url", lf.url, "--flow", "f", "--key", "K", "--users", "2", "--out-dir", out)
        check("it exits non-zero", r.returncode == 1)
        check("the report names the cause", "no learner_id field" in r.stdout and "OLD code" in r.stdout, r.stdout)
        check("it does not claim Plan A works", "PLAN A WORKS" not in r.stdout)


def test_spike_reports_the_shadowed_field_bug_as_a_failure():
    print("spike_tweaks.py against a flow that reproduces the first live run's bug")
    with FakeLangflow(key="K", shadow=True) as lf, tempfile.TemporaryDirectory() as out:
        r = run(SPIKE, "--base-url", lf.url, "--flow", "f", "--key", "K", "--users", "2", "--out-dir", out)
        check("it exits non-zero", r.returncode == 1, r.stdout[-300:])
        check("parallel FAILS", "FAIL         parallel" in r.stdout, r.stdout)
        check("the control FAILS too: a learner id appeared where none was sent (what the first live run showed)",
              "FAIL         control" in r.stdout, r.stdout)
        check("it does not claim Plan A works", "PLAN A WORKS" not in r.stdout)


def test_spike_with_the_wrong_key_is_not_a_pass():
    print("spike_tweaks.py with a tweaks key that matches nothing")
    with FakeLangflow(key="RealKey") as lf, tempfile.TemporaryDirectory() as out:
        r = run(SPIKE, "--base-url", lf.url, "--flow", "f", "--key", "WrongKey", "--users", "2", "--out-dir", out)
        check("it fails rather than passing", r.returncode == 1 and "PLAN A WORKS" not in r.stdout, r.stdout[-300:])


def test_spike_argument_errors():
    print("spike_tweaks.py argument handling")
    r = run(SPIKE, "--flow", "f", "--key", "K", "--users", "1")
    check("one user is refused with an explanation", r.returncode == 2 and "at least 2" in r.stderr, r.stderr)
    r = run(SPIKE, "--key", "K")
    check("a missing --flow is refused", r.returncode == 2 and "--flow" in r.stderr)
    r = run(SPIKE, "--help")
    check("--help lists --pause and --out-dir", "--pause" in r.stdout and "--out-dir" in r.stdout)


def test_capture_end_to_end():
    print("capture_fixtures.py with --probe-delete")
    with FakeLangflow() as lf, tempfile.TemporaryDirectory() as out:
        r = run(CAPTURE, "--base-url", lf.url, "--flow", "language-tutor", "--out", out, "--probe-delete")
        check("it runs (exit 0)", r.returncode == 0, r.stdout[-400:] + r.stderr[-400:])
        names = sorted(os.listdir(out))
        check("it saved run and message files for both cases",
              {"greeting_run.json", "greeting_messages.json", "story_run.json", "story_messages.json"} <= set(names), str(names))
        story = json.load(open(os.path.join(out, "story_run.json"), encoding="utf-8"))
        check("the saved run is the server's response", story["outputs"][0]["outputs"][0]["results"]["message"]["text"].startswith("Ana:"))
        check("it reports one tool call for the story", '"tool_calls": 1' in r.stdout and "story_generator_tool" in r.stdout, r.stdout)
        probe = json.load(open(os.path.join(out, "probe_delete.json"), encoding="utf-8"))
        check("the delete probe concludes that per-session delete works", "works" in probe["conclusion"] and "NOT" not in probe["conclusion"], probe["conclusion"])
        check("the sessions are really gone afterwards", lf.sessions == {})
        check("it only deleted its own capture-* sessions", all(q[1].split("/")[-1].startswith("capture-") for q in lf.requests if q[0] == "DELETE"))


def test_capture_case_option():
    print("capture_fixtures.py --case")
    with FakeLangflow(key="K") as lf, tempfile.TemporaryDirectory() as out:
        tw = os.path.join(out, "tweaks.json")
        json.dump({"K": {"learner_id": "5", "language": "es"}}, open(tw, "w"))
        r = run(CAPTURE, "--base-url", lf.url, "--flow", "f", "--out", out, "--case", "whoami=Use the Who Am I tool", "--tweaks-file", tw)
        check("it runs", r.returncode == 0, r.stdout[-300:] + r.stderr[-300:])
        run_json = open(os.path.join(out, "whoami_run.json"), encoding="utf-8").read()
        check("the tweaks file was sent (the tool saw learner 5)", "learner_id=5" in run_json, run_json[:300])
        r = run(CAPTURE, "--base-url", lf.url, "--flow", "f", "--out", out, "--case", "bad name=x")
        check("a bad case name is refused", r.returncode != 0 and "case name" in (r.stderr + r.stdout))


def main():
    print("Running command-line end-to-end tests...\n")
    test_spike_with_the_exact_options_a_person_types()
    test_spike_with_integer_ids_reproduces_the_silent_drop()
    test_spike_says_so_when_the_node_still_has_the_old_code()
    test_spike_reports_the_shadowed_field_bug_as_a_failure()
    test_spike_with_the_wrong_key_is_not_a_pass()
    test_spike_argument_errors()
    test_capture_end_to_end()
    test_capture_case_option()
    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    print("All tests passed.")


if __name__ == "__main__":
    main()
