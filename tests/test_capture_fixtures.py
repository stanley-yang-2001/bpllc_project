"""
Tests for the pure helpers in scripts/capture_fixtures.py (milestone M0). The capture itself needs
a live Langflow; these cover the parts that must be right before anything is saved or deleted.

    python tests/test_capture_fixtures.py
"""

import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))

import capture_fixtures as c  # noqa: E402

failures = []


def check(name, condition, detail=""):
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        failures.append(name)


RUN = {"outputs": [{"outputs": [{"results": {"message": {
    "text": "Ana: Hola, tienes agua?",
    "content_blocks": [{"contents": [
        {"type": "text", "text": "thinking"},
        {"type": "tool_use", "name": "Story Generator Tool", "tool_input": {"language": "Spanish"}, "output": "Ana: Hola"},
    ]}]}}}]}]}


def test_parse_case():
    print("cases")
    check("name=message parses", c.parse_case("whoami=Use the tool") == ("whoami", "Use the tool"))
    check("an equals sign inside the message is kept", c.parse_case("a=b=c") == ("a", "b=c"))
    for bad in ("nomessage", "=text", "bad name=text", "x=   ", "../etc=text"):
        try:
            c.parse_case(bad)
            check(f"{bad!r} is rejected", False)
        except ValueError:
            check(f"{bad!r} is rejected", True)


def test_session_ids_are_marked():
    print("session ids")
    sid = c.capture_session_id("story")
    check("starts with capture-", sid.startswith("capture-story-"))
    check("two differ", sid != c.capture_session_id("story"))


def test_describe_run():
    print("describing a run response")
    d = c.describe_run(RUN)
    check("reply text found", d["reply_preview"].startswith("Ana:"), str(d))
    check("reply path recorded", d["reply_path"] == "outputs[0].outputs[0].results.message.text", str(d["reply_path"]))
    check("one tool call found", d["tool_calls"] == 1 and d["tool_names"] == ["Story Generator Tool"], str(d))
    check("an unrecognised shape reports zero, not a crash", c.describe_run({"x": 1})["tool_calls"] == 0)
    check("a non-dict does not crash", c.describe_run([])["tool_calls"] == 0)


def test_describe_messages():
    print("describing stored messages")
    d = c.describe_messages([{"sender": "User", "text": "hi"}, {"sender": "Machine", "content_blocks": RUN["outputs"]}])
    check("count and senders", d["count"] == 2 and d["senders"] == ["User", "Machine"], str(d))
    check("a non-list is reported", c.describe_messages({"detail": "x"})["count"] is None)


def test_redaction_and_saving():
    print("redaction")
    key = "gsk_" + "a" * 40
    text, n = c.redact(f'{{"k": "{key}", "other": "AIza{"b" * 30}", "ok": "hello"}}')
    check("a Groq key is replaced", key not in text and n == 2, text)
    check("plain text is untouched", '"ok": "hello"' in text)
    with tempfile.TemporaryDirectory() as tmp:
        path = c.save_json(tmp, "x.json", {"leak": key})
        saved = open(path, encoding="utf-8").read()
        check("a saved file never contains the key", key not in saved and "REDACTED" in saved)
        check("a saved file is valid JSON", json.loads(saved) == {"leak": "REDACTED"})


def test_delete_probe_only_touches_capture_sessions():
    print("delete safety")
    mixed = ["capture-story-abc", "u17-0123456789abcdef", "someone-else", None, "capture-x-1"]
    check("only capture-* sessions are eligible", c.only_capture_sessions(mixed) == ["capture-story-abc", "capture-x-1"])
    check("a learner's session is never eligible", c.only_capture_sessions(["u17-abc"]) == [])


def main():
    print("Running capture helper tests...\n")
    test_parse_case()
    test_session_ids_are_marked()
    test_describe_run()
    test_describe_messages()
    test_redaction_and_saving()
    test_delete_probe_only_touches_capture_sessions()
    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    print("All tests passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
