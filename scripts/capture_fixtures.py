"""
M0 capture: save REAL Langflow responses so the API's `langflow_client` is tested against what
Langflow actually returns, not against what we assume it returns (the diary's lesson from the
Tool Result Relay: tests built from assumed shapes passed while the real shape failed).

For each case it sends one message in a fresh session, then saves
    <name>_run.json        the response of POST /api/v1/run/<flow>
    <name>_messages.json   the stored messages of that session (the fallback source)
and prints what it found (reply text, number of tool calls, where they sit in the response).

    docker compose exec langflow python /app/scripts/capture_fixtures.py --flow language-tutor
    docker compose exec langflow python /app/scripts/capture_fixtures.py --flow language-tutor-spike \\
        --case whoami="Use the Who Am I tool once with note x." --tweaks-file /app/scripts/tweaks.json

Default cases are read-only: a greeting (no tool) and a Spanish story request (reads the words
table, one Groq call). It never adds a word. Files go to scripts/captured/ (git-ignored): look
them over, then move the ones you want into api/tests/fixtures/langflow/.

--probe-delete answers the M5 acceptance question "what does Langflow keep about a chat, and can
we remove it per user?": it lists stored sessions, deletes the sessions this script just created
through the monitor API, and re-reads them. It only ever touches sessions named capture-*.

Authentication: --api-key / $LANGFLOW_API_KEY, else it logs in like run_routing_tests.py.
"""

import argparse
import json
import os
import re
import sys
import urllib.parse
import uuid

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from spike_tweaks import ApiError, _request, get_api_key  # noqa: E402

DEFAULT_CASES = [
    ("greeting", "Hi! How are you today?"),
    ("story", "Tell me a story in Spanish."),
]


# --- pure helpers (tested in tests/test_capture_fixtures.py) -----------------------------------


def parse_case(text: str) -> tuple:
    """'name=message' -> (name, message). The name becomes part of a file name."""
    if "=" not in text:
        raise ValueError(f"--case must look like name=message, got {text!r}")
    name, message = text.split("=", 1)
    name = name.strip()
    if not name or not all(c.isalnum() or c in "-_" for c in name):
        raise ValueError(f"case name {name!r} must be letters, digits, - or _")
    if not message.strip():
        raise ValueError(f"case {name!r} has an empty message")
    return name, message.strip()


def capture_session_id(name: str) -> str:
    return f"capture-{name}-{uuid.uuid4().hex[:12]}"


def find_tool_blocks(obj, path="$") -> list:
    """[(path, block)] for every dict with type 'tool_use' (how Langflow marks a tool call)."""
    found = []
    if isinstance(obj, dict):
        if obj.get("type") == "tool_use":
            return [(path, obj)]
        for key, value in obj.items():
            found.extend(find_tool_blocks(value, f"{path}.{key}"))
    elif isinstance(obj, list):
        for i, value in enumerate(obj):
            found.extend(find_tool_blocks(value, f"{path}[{i}]"))
    return found


def reply_text(resp) -> tuple:
    """(text, path) of the first chat reply found in a run response, or ('', None)."""
    for path in ("outputs[0].outputs[0].results.message.text",
                 "outputs[0].outputs[0].results.message.data.text",
                 "outputs[0].outputs[0].outputs.message.message"):
        node = resp
        ok = True
        for part in path.replace("]", "").replace("[", ".").split("."):
            if isinstance(node, dict) and part in node:
                node = node[part]
            elif isinstance(node, list) and part.isdigit() and int(part) < len(node):
                node = node[int(part)]
            else:
                ok = False
                break
        if ok and isinstance(node, str) and node:
            return node, path
    return "", None


def describe_run(resp) -> dict:
    text, path = reply_text(resp)
    blocks = find_tool_blocks(resp)
    return {
        "reply_path": path,
        "reply_preview": text[:80],
        "tool_calls": len(blocks),
        "tool_paths": sorted({p for p, _ in blocks})[:6],
        "tool_names": [b.get("name") for _, b in blocks],
        "top_level_keys": sorted(resp.keys()) if isinstance(resp, dict) else type(resp).__name__,
    }


def describe_messages(msgs) -> dict:
    if not isinstance(msgs, list):
        return {"count": None, "note": f"expected a list, got {type(msgs).__name__}"}
    return {
        "count": len(msgs),
        "senders": [str(m.get("sender")) for m in msgs if isinstance(m, dict)],
        "tool_calls_in_stored": len(find_tool_blocks(msgs)),
        "keys_of_first": sorted(msgs[0].keys()) if msgs and isinstance(msgs[0], dict) else [],
    }


_SECRET = re.compile(r"gsk_[A-Za-z0-9]{20,}|AIza[0-9A-Za-z_\-]{20,}|sk-[A-Za-z0-9_\-]{20,}")


def redact(text: str) -> tuple:
    """(text with anything key-shaped replaced, number of replacements). A fixture is meant to be
    committed, and an exported flow once carried a live Groq key."""
    return _SECRET.subn("REDACTED", text)


def only_capture_sessions(session_ids) -> list:
    """The delete probe must never touch anything but this script's own sessions."""
    return [s for s in session_ids if isinstance(s, str) and s.startswith("capture-")]


# --- the run -------------------------------------------------------------------------------------


def save_json(directory, filename, data):
    os.makedirs(directory, exist_ok=True)
    path = os.path.join(directory, filename)
    text, redactions = redact(json.dumps(data, indent=2, ensure_ascii=False))
    if redactions:
        print(f"  NOTE: {redactions} key-shaped value(s) were replaced with REDACTED in {filename}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)
    return path


def probe_delete(base, api_key, session_ids, out_dir) -> dict:
    """What does Langflow keep, and can it be removed per session? Best effort; records every
    status so the answer is evidence, not a guess."""
    headers = {"x-api-key": api_key}
    report = {"endpoints_tried": []}

    def attempt(label, method, url):
        try:
            result = _request(method, url, headers=headers)
            report["endpoints_tried"].append({"label": label, "method": method, "url": url, "ok": True})
            return result
        except ApiError as e:
            report["endpoints_tried"].append({"label": label, "method": method, "url": url,
                                              "ok": False, "error": str(e)[:300]})
            return None

    listed = attempt("list sessions", "GET", f"{base}/api/v1/monitor/messages/sessions")
    if isinstance(listed, list):
        report["sessions_listed"] = len(listed)
        report["our_sessions_visible"] = sorted(set(listed) & set(session_ids))
        report["prefix_filter_works"] = [s for s in listed if isinstance(s, str) and s.startswith("capture-")] != []
    for session_id in only_capture_sessions(session_ids):
        quoted = urllib.parse.quote(session_id)
        before = attempt("read before", "GET", f"{base}/api/v1/monitor/messages?session_id={quoted}")
        attempt("delete session", "DELETE", f"{base}/api/v1/monitor/messages/session/{quoted}")
        after = attempt("read after", "GET", f"{base}/api/v1/monitor/messages?session_id={quoted}")
        report.setdefault("sessions", {})[session_id] = {
            "messages_before": len(before) if isinstance(before, list) else None,
            "messages_after": len(after) if isinstance(after, list) else None,
        }
    deleted = [v for v in report.get("sessions", {}).values()
               if v["messages_before"] and v["messages_after"] == 0]
    report["conclusion"] = (
        "per-session delete through the monitor API works" if deleted
        else "NOT shown to work: read the endpoints_tried list and check the database tables directly")
    save_json(out_dir, "probe_delete.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description="Capture real Langflow responses (see the module docstring).")
    parser.add_argument("--base-url", default="http://localhost:7860")
    parser.add_argument("--flow", required=True, help="flow id or endpoint name")
    parser.add_argument("--case", action="append", help='name=message (repeatable); default: greeting and story')
    parser.add_argument("--tweaks-file", help="JSON file with a tweaks object to send with every case")
    parser.add_argument("--out", default=os.path.join(os.path.dirname(os.path.abspath(__file__)), "captured"))
    parser.add_argument("--probe-delete", action="store_true")
    parser.add_argument("--api-key")
    args = parser.parse_args(argv)

    cases = [parse_case(c) for c in args.case] if args.case else DEFAULT_CASES
    tweaks = None
    if args.tweaks_file:
        with open(args.tweaks_file, encoding="utf-8") as f:
            tweaks = json.load(f)

    base = args.base_url.rstrip("/")
    api_key = get_api_key(base, args.api_key)
    sessions = []
    for name, message in cases:
        session_id = capture_session_id(name)
        sessions.append(session_id)
        payload = {"input_value": message, "input_type": "chat", "output_type": "chat",
                   "session_id": session_id}
        if tweaks:
            payload["tweaks"] = tweaks
        print(f"\n[{name}] sending: {message!r}", flush=True)
        try:
            run = _request("POST", f"{base}/api/v1/run/{args.flow}?stream=false", payload=payload,
                           headers={"x-api-key": api_key})
        except ApiError as e:
            print(f"  FAILED: {e}")
            continue
        run_path = save_json(args.out, f"{name}_run.json", run)
        print(f"  saved {run_path}")
        print("  run response:", json.dumps(describe_run(run), ensure_ascii=False))
        try:
            msgs = _request("GET", f"{base}/api/v1/monitor/messages?session_id={urllib.parse.quote(session_id)}",
                            headers={"x-api-key": api_key})
            msg_path = save_json(args.out, f"{name}_messages.json", msgs)
            print(f"  saved {msg_path}")
            print("  stored messages:", json.dumps(describe_messages(msgs), ensure_ascii=False))
        except ApiError as e:
            print(f"  stored messages not available: {e}")

    if args.probe_delete:
        print("\nProbing what Langflow keeps and whether it can be deleted per session ...")
        print(json.dumps(probe_delete(base, api_key, sessions, args.out), indent=2))
    print(f"\nFiles are in {args.out}. Review them, then move the ones you want to keep into "
          "api/tests/fixtures/langflow/ (they hold your flow id and Langflow user id; key-shaped values were redacted).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
