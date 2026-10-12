"""
Tests for scripts/spike_tweaks.py (milestone M0) — written before the spike was trusted.

The spike exists to answer "does each request's tool call see only its own user?". A spike that
cannot fail answers nothing (the diary's lesson from the language check), so these tests drive it
against a FAKE Langflow in several behaviours, some correct and some deliberately broken:

  * correct          each call sees the tweaks of its own request            -> PASS
  * shared state     a global "current user" (a race between requests)       -> FAIL, mixed up
  * ignores tweaks   the tool never receives them                            -> FAIL
  * sequential       a lock, so no two users' calls overlap                  -> INCONCLUSIVE, not PASS
  * Agent skips tool no WHOAMI line at all                                   -> INCONCLUSIVE / FAIL
  * Agent obeys user the Agent can change the hidden input                   -> FAIL on override

No Langflow, Postgres or Groq needed; standard library only. Run from the repo root:
    python tests/test_spike_tweaks.py
"""

import os
import sys
import threading
import time

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import spike_tweaks as s  # noqa: E402

failures = []


def check(name, condition, detail=""):
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        failures.append(name)


KEY = "SpikeWhoAmI-test1"
HOLD = 0.25  # seconds a fake tool call lasts, so calls overlap


def whoami_line(user, language, session, t0, t1, graph_session=None):
    return (f"WHOAMI learner_id={user} language={language} session=NONE "
            f"graph_session={graph_session or session} t0={t0:.3f} t1={t1:.3f} thread=1")


def response_with(line):
    """A response shaped roughly like Langflow's, with the same line in several places (as the real
    one repeats the tool output in the reply and in the content blocks)."""
    return {"outputs": [{"outputs": [{"results": {"message": {
        "text": line,
        "content_blocks": [{"contents": [{"type": "tool_use", "name": "Who Am I (spike)",
                                          "output": line}]}]}}}]}]}


def fake_correct(message, session_id, tweaks):
    t0 = time.time()
    time.sleep(HOLD)
    cfg = (tweaks or {}).get(KEY, {})
    user = cfg.get("learner_id")
    if "999" in message and user is not None:
        user = user  # a correct flow ignores the Agent's attempt
    line = whoami_line(user if user is not None else "NONE", cfg.get("language", "NONE"),
                       session_id, t0, time.time())
    return response_with(line)


def make_shared_state():
    state = {"current": "NONE", "language": "NONE"}

    def run(message, session_id, tweaks):
        cfg = (tweaks or {}).get(KEY, {})
        state["current"], state["language"] = cfg.get("learner_id", "NONE"), cfg.get("language", "NONE")
        t0 = time.time()
        time.sleep(HOLD)
        return response_with(whoami_line(state["current"], state["language"], session_id, t0, time.time()))

    return run


def fake_ignores_tweaks(message, session_id, tweaks):
    t0 = time.time()
    time.sleep(HOLD)
    return response_with(whoami_line("NONE", "NONE", session_id, t0, time.time()))


def make_sequential():
    lock = threading.Lock()

    def run(message, session_id, tweaks):
        with lock:
            return fake_correct(message, session_id, tweaks)

    return run


def fake_agent_skips_tool(message, session_id, tweaks):
    return {"outputs": [{"outputs": [{"results": {"message": {"text": "I am a tutor."}}}]}]}


def fake_agent_obeys_override(message, session_id, tweaks):
    t0 = time.time()
    time.sleep(HOLD)
    user = "999" if "999" in message else (tweaks or {}).get(KEY, {}).get("learner_id", "NONE")
    language = "xx" if "999" in message else (tweaks or {}).get(KEY, {}).get("language", "NONE")
    return response_with(whoami_line(user, language, session_id, t0, time.time()))


def test_session_id_and_tweaks_and_payload():
    print("session ids, tweaks and payloads")
    a, b = s.make_session_id(17), s.make_session_id(17)
    check("session id carries the user prefix", a.startswith("u17-") and len(a) == len("u17-") + 32)
    check("two session ids differ", a != b)
    check("tweaks send the id as a STRING by default (Langflow drops non-strings on text fields)",
          s.build_tweaks("K", 17, "es") == {"K": {"learner_id": "17", "language": "es"}})
    check("tweaks can send integers, to reproduce the drop", s.build_tweaks("K", 17, "es", as_string=False)["K"]["learner_id"] == 17)
    payload = s.build_payload("hi", "u1-x", {"K": {}})
    check("payload has the run fields", payload["input_type"] == "chat" and payload["session_id"] == "u1-x")
    check("payload without tweaks has no tweaks key", "tweaks" not in s.build_payload("hi", "u1-x"))


def test_find_observations():
    print("finding WHOAMI lines in a response")
    line = whoami_line(17, "es", "u17-a", 1.0, 2.0)
    found = s.find_observations(response_with(line))
    check("a line repeated in several places is counted once", len(found) == 1, str(found))
    check("fields are parsed", found and found[0]["learner_id"] == "17" and found[0]["language"] == "es")
    two = {"a": line, "b": whoami_line(17, "es", "u17-a", 3.0, 4.0)}
    check("different calls (different times) are both kept", len(s.find_observations(two)) == 2)
    check("a response with no marker finds nothing", s.find_observations({"x": "hello"}) == [])
    wrapped = {"text": "[{'output': '" + line + "'}]"}
    check("a line inside a larger string is still parsed", len(s.find_observations(wrapped)) == 1)
    check("DEV(5) and NONE parse", s.find_observations({"x": "WHOAMI learner_id=DEV(5) language=NONE t0=1.0 t1=2.0"})[0]["learner_id"] == "DEV(5)")


def test_individual_checks():
    print("individual checks")
    ok = [{"learner_id": "17", "language": "es"}]
    check("matching user passes", s.check_user(17, "es", ok)[0] == s.PASS)
    check("another user's id fails", s.check_user(18, "es", ok)[0] == s.FAIL)
    check("wrong language fails", s.check_user(17, "fr", ok)[0] == s.FAIL)
    check("no observations fails", s.check_user(17, "es", [])[0] == s.FAIL)
    check("one bad call among good ones fails",
          s.check_user(17, "es", ok + [{"learner_id": "5", "language": "es"}])[0] == s.FAIL)
    check("control: NONE passes", s.check_control([{"learner_id": "NONE"}])[0] == s.PASS)
    check("control: DEV(3) passes", s.check_control([{"learner_id": "DEV(3)"}])[0] == s.PASS)
    check("control: a real user without tweaks fails", s.check_control([{"learner_id": "7"}])[0] == s.FAIL)
    check("control: no call is inconclusive", s.check_control([])[0] == s.INCONCLUSIVE)


def test_the_langflow_account_id_is_not_a_learner():
    """First live spike run: the tool reported the Langflow ACCOUNT's UUID (a built-in `user_id` property shadowed the
    input). The checks must treat that as 'no learner', never as a match and never as a leak."""
    shadowed = [{"learner_id": "NONE", "langflow_user": "784d78de-8532-42c1-990e-d6b50f77beb0", "language": "es"}]
    check("account id with no learner passes the control", s.check_control(shadowed)[0] == s.PASS)
    check("account id instead of the learner fails the isolation check", s.check_user(101, "es", shadowed)[0] == s.FAIL)
    leaked = [{"learner_id": "784d78de-8532-42c1-990e-d6b50f77beb0", "language": "es"}]
    check("an account uuid in the learner field fails the control", s.check_control(leaked)[0] == s.FAIL)
    line = whoami_line(5, "es", "u5-a", 1.0, 2.0).replace("session=", "langflow_user=784d78de-8532-42c1-990e-d6b50f77beb0 session=")
    found = s.find_observations({"x": line})
    check("the langflow_user field is parsed alongside learner_id", found and found[0]["learner_id"] == "5" and found[0]["langflow_user"].startswith("784d"))
    check("tweaks use learner_id, not the reserved user_id", set(s.build_tweaks("K", 1, "es")["K"]) == {"learner_id", "language"})


def test_a_report_without_learner_id_says_the_node_has_old_code():
    """Third live run: the checks printed 'saw [None]', which hid that the tool's report had no learner_id field at all
    (the node was running the original spike code). Say so."""
    old = [{"user_id": "784d78de-8532-42c1-990e-d6b50f77beb0", "language": "es"}]
    for status, detail in (s.check_control(old), s.check_user(101, "es", old)):
        check("a report with no learner_id field fails", status == s.FAIL)
        check("and says the node is running old code, naming the fields it did print",
              "no learner_id field" in detail and "OLD code" in detail and "user_id" in detail, detail)
    check("a normal report is unaffected", s.check_control([{"learner_id": "NONE"}])[0] == s.PASS)


def test_pause_and_rate_limit_hint():
    slept = []
    saved = s._sleep
    s._sleep = slept.append
    try:
        s.run_suite(fake_correct, KEY, users=2, rounds=1, pause=7)
        check("with --pause the suite waits between its phases", slept == [7, 7], str(slept))
        slept.clear()
        s.run_suite(fake_correct, KEY, users=2, rounds=1)
        check("without --pause it never sleeps", slept == [])
    finally:
        s._sleep = saved

    def limited(message, session_id, tweaks):
        raise s.ApiError("HTTP 500 ... Error code: 429 - Rate limit reached for model gpt-oss-120b")

    report = s.format_report([s.run_suite(limited, KEY, users=2, rounds=1)])
    check("a rate-limit failure gets a plain-language hint", "rate limit was hit" in report and "--pause 30" in report, report[-300:])
    check("a clean report has no such hint", "rate limit was hit" not in s.format_report([s.run_suite(fake_correct, KEY, users=2, rounds=1)]))


def test_overlap():
    print("overlap detection")
    a = {"learner_id": "1", "t0": "10.0", "t1": "11.5"}
    b = {"learner_id": "2", "t0": "11.0", "t1": "12.5"}
    c = {"learner_id": "2", "t0": "11.5", "t1": "13.0"}  # starts exactly when a ends
    check("different users overlapping is detected", s.spans_overlap({1: [a], 2: [b]}))
    check("back to back (touching) is not overlap", not s.spans_overlap({1: [a], 2: [c]}))
    check("one user's own calls never count", not s.spans_overlap({1: [a, dict(b, learner_id="1")]}))
    check("missing times are ignored", not s.spans_overlap({1: [{"learner_id": "1"}], 2: [b]}))


def test_session_evidence():
    print("Plan B evidence")
    good = [("u1-a", {"graph_session": "u1-a", "session": "NONE"})]
    own = [("u1-a", {"graph_session": "NONE", "session": "u1-a"})]
    bad = [("u1-a", {"graph_session": "UNAVAILABLE", "session": "NONE"})]
    check("graph session equal to the sent id passes", s.session_evidence(good)[0] == s.PASS)
    check("component session equal to the sent id passes", s.session_evidence(own)[0] == s.PASS)
    check("unavailable session fails", s.session_evidence(bad)[0] == s.FAIL)
    check("nothing observed is inconclusive", s.session_evidence([])[0] == s.INCONCLUSIVE)


def test_suite_correct_flow_passes():
    print("suite: a correct flow")
    result = s.run_suite(fake_correct, KEY, users=4, rounds=2)
    checks = result["checks"]
    check("control passes", checks["control"][0] == s.PASS, str(checks["control"]))
    check("parallel passes", checks["parallel"][0] == s.PASS, str(checks["parallel"]))
    check("overlap is proven", checks["overlap"][0] == s.PASS, str(checks["overlap"]))
    check("override passes", checks["override"][0] == s.PASS, str(checks["override"]))
    check("verdict is PASS", result["verdict"] == s.PASS, str(result["verdict"]))
    check("every request is recorded raw", len(result["raw"]) == 1 + 4 * 2 + 1)


def test_suite_catches_a_race():
    print("suite: a flow with shared state (the leak we are guarding against)")
    result = s.run_suite(make_shared_state(), KEY, users=4, rounds=1)
    check("parallel FAILS", result["checks"]["parallel"][0] == s.FAIL, str(result["checks"]["parallel"]))
    check("the failure says mixed up", "MIXED UP" in result["checks"]["parallel"][1])
    check("verdict is FAIL", result["verdict"] == s.FAIL)


def test_suite_catches_ignored_tweaks():
    print("suite: tweaks that never arrive")
    result = s.run_suite(fake_ignores_tweaks, KEY, users=3, rounds=1)
    check("control passes (no user, as expected)", result["checks"]["control"][0] == s.PASS)
    check("parallel FAILS", result["checks"]["parallel"][0] == s.FAIL)
    check("verdict is FAIL", result["verdict"] == s.FAIL)


def test_suite_does_not_pass_without_overlap():
    print("suite: sequential success proves nothing")
    result = s.run_suite(make_sequential(), KEY, users=3, rounds=1)
    check("parallel looks fine", result["checks"]["parallel"][0] == s.PASS)
    check("but overlap is INCONCLUSIVE", result["checks"]["overlap"][0] == s.INCONCLUSIVE, str(result["checks"]["overlap"]))
    check("so the verdict is not PASS", result["verdict"] == s.INCONCLUSIVE, str(result["verdict"]))


def test_suite_agent_not_calling_the_tool():
    print("suite: the Agent never calls the tool")
    result = s.run_suite(fake_agent_skips_tool, KEY, users=2, rounds=1)
    check("control is inconclusive", result["checks"]["control"][0] == s.INCONCLUSIVE)
    check("parallel FAILS (the tool never reported)", result["checks"]["parallel"][0] == s.FAIL)
    check("override is inconclusive", result["checks"]["override"][0] == s.INCONCLUSIVE)
    check("verdict is not PASS", result["verdict"] != s.PASS)


def test_suite_catches_an_override():
    print("suite: an Agent that can change the hidden input")
    result = s.run_suite(fake_agent_obeys_override, KEY, users=2, rounds=1)
    check("override FAILS", result["checks"]["override"][0] == s.FAIL, str(result["checks"]["override"]))
    check("verdict is FAIL", result["verdict"] == s.FAIL)


def test_suite_reports_request_errors_as_errors():
    print("suite: a request that errors is an ERROR, not an isolation verdict")

    def boom(message, session_id, tweaks):
        raise s.ApiError("HTTP 429 from POST /run: rate limited")

    result = s.run_suite(boom, KEY, users=2, rounds=1)
    check("control is ERROR", result["checks"]["control"][0] == s.ERROR)
    check("parallel is ERROR with the message", result["checks"]["parallel"][0] == s.ERROR and "429" in result["checks"]["parallel"][1])
    check("verdict is FAIL (never PASS)", result["verdict"] == s.FAIL)


def test_report_text():
    print("report")
    good = s.run_suite(fake_correct, KEY, users=2, rounds=1)
    bad = s.run_suite(fake_ignores_tweaks, "other-key", users=2, rounds=1)
    report = s.format_report([bad, good])
    check("report names the key that worked", "PLAN A WORKS with key(s): 'SpikeWhoAmI-test1'" in report, report[-300:])
    check("report shows each key", "'other-key'" in report and "'SpikeWhoAmI-test1'" in report)
    none = s.format_report([bad])
    check("report says Plan A is not proven when nothing passed", "Plan A is NOT proven" in none)


def main():
    print("Running spike tweaks tests...\n")
    test_session_id_and_tweaks_and_payload()
    test_find_observations()
    test_individual_checks()
    test_the_langflow_account_id_is_not_a_learner()
    test_a_report_without_learner_id_says_the_node_has_old_code()
    test_pause_and_rate_limit_hint()
    test_overlap()
    test_session_evidence()
    test_suite_correct_flow_passes()
    test_suite_catches_a_race()
    test_suite_catches_ignored_tweaks()
    test_suite_does_not_pass_without_overlap()
    test_suite_agent_not_calling_the_tool()
    test_suite_catches_an_override()
    test_suite_reports_request_errors_as_errors()
    test_report_text()
    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    print("All tests passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
