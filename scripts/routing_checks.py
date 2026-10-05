"""
Routing checks — the pure logic behind the automated end-to-end tests (Step 10).

run_routing_tests.py sends chat messages to the Langflow flow over its HTTP API and hands each
JSON response to evaluate_turn(). Everything here is pure (no network, no database) so it can
be unit-tested: tests/test_routing_checks.py.

What gets checked, per turn (these are the failures actually seen during Step 9):
  * the right tool was called (or none, for small talk),
  * with the right argument (the language named in the LATEST message, the word to add),
  * the chat reply is identical to the tool's output (the Tool Result Relay's job),
  * story quality (English: vocabulary / length / format; other languages: structure only),
  * the empty-vocabulary guard returns its message instead of an invented story.
"""

import json
import re
import sys

sys.path.insert(0, "/app/custom_components")
sys.path.insert(0, "/app/scripts")

from tool_result_relay import output_to_text  # noqa: E402
from vocab_adherence import check_passage  # noqa: E402

GUARD_MARKER = "don't have any vocabulary yet"

# ---------------------------------------------------------------------------------------------
# Test cases. "say" is the chat message. "tool": "story" | "add_word" | None (no tool) |
# "either" (record only). "arg" compares a tool argument to an accepted list (case-insensitive).
# All story requests name a different language from the previous one where possible, because
# the story tool caches per language for ~20 s.
# ---------------------------------------------------------------------------------------------

TEST_WORD = "autotestapple"  # removed from the vocabulary again after the run


def _story(say, languages, kind):
    turn = {"say": say, "tool": "story", "arg": {"key": "language", "any_of": languages}, "story": kind}
    if kind == "other":
        turn["language"] = languages[0].capitalize()  # the story must really be written in it
    return turn


CASES = [
    {"id": "A1", "name": "Add a new word", "turns": [
        {"say": f"Add the word {TEST_WORD}", "tool": "add_word",
         "arg": {"key": "word", "any_of": [TEST_WORD]}, "reply_any": ["added"]}]},
    {"id": "A2", "name": "Adding the same word again is a duplicate", "turns": [
        {"say": f"Add the word {TEST_WORD}", "tool": "add_word",
         "arg": {"key": "word", "any_of": [TEST_WORD]}, "reply_any": ["already"]}]},
    {"id": "A3", "name": "A case variant is a duplicate", "turns": [
        {"say": "Add the word AutoTestApple", "tool": "add_word",
         "arg": {"key": "word", "any_of": [TEST_WORD]}, "reply_any": ["already"]}]},
    {"id": "S1", "name": "English story", "turns": [
        _story("Tell me a story in English", ["english"], "english")]},
    {"id": "S2", "name": "Spanish story", "turns": [
        _story("Tell me a story in Spanish", ["spanish", "español", "espanol"], "other")]},
    {"id": "S3", "name": "French story", "turns": [
        _story("Write a short story in French", ["french", "français", "francais"], "other")]},
    {"id": "S4", "name": "Story requested in the target language's own name", "turns": [
        _story("Story in 日本語", ["japanese", "日本語"], "other")]},
    {"id": "M1", "name": "Language switching in one session (English, Spanish, English, French)", "turns": [
        _story("Create a story in English", ["english"], "english"),
        _story("Create a story in Spanish", ["spanish", "español", "espanol"], "other"),
        _story("Create a story in English", ["english"], "english"),
        _story("Create a story in French", ["french", "français", "francais"], "other")]},
    {"id": "N1", "name": "A greeting needs no tool", "turns": [{"say": "hi", "tool": None}]},
    {"id": "N2", "name": "An unrelated question needs no tool", "turns": [
        {"say": "What's the weather like today?", "tool": None}]},
    {"id": "I1", "name": "Story request without a language (record only)", "turns": [
        {"say": "Tell me a story", "tool": "either", "info": True}]},
    {"id": "E1", "name": "Empty vocabulary returns the guard message", "needs_empty_vocab": True, "turns": [
        {"say": "Tell me a story in English", "tool": "story", "expect_guard": True,
         "arg": {"key": "language", "any_of": ["english"]}}]},
]


# --- parsing the Langflow /api/v1/run response -----------------------------------------------


def _get(obj, *path):
    for key in path:
        if isinstance(obj, dict) and key in obj:
            obj = obj[key]
        elif isinstance(obj, list) and isinstance(key, int) and -len(obj) <= key < len(obj):
            obj = obj[key]
        else:
            return None
    return obj


def _primary_message(resp):
    for path in (("outputs", 0, "outputs", 0, "results", "message"),
                 ("outputs", 0, "outputs", 0, "results", "message", "data")):
        msg = _get(resp, *path)
        if isinstance(msg, dict):
            return msg
    return None


def final_text(resp):
    """The text the learner sees in the chat, wherever this Langflow version puts it."""
    if not isinstance(resp, dict):
        return ""
    for path in (
        ("outputs", 0, "outputs", 0, "results", "message", "text"),
        ("outputs", 0, "outputs", 0, "results", "message", "data", "text"),
        ("outputs", 0, "outputs", 0, "outputs", "message", "message"),
        ("outputs", 0, "outputs", 0, "messages", -1, "message"),
    ):
        value = _get(resp, *path)
        if isinstance(value, str) and value:
            return value
    return ""


def _walk_tool_dicts(obj, found):
    if isinstance(obj, dict):
        if obj.get("type") == "tool_use":
            found.append(obj)
            return
        for value in obj.values():
            _walk_tool_dicts(value, found)
    elif isinstance(obj, list):
        for value in obj:
            _walk_tool_dicts(value, found)


def find_tool_calls(resp):
    """All tool calls in the response: [{name, args, output (text), error}, ...] in order."""
    raw = []
    primary = _primary_message(resp)
    if primary is not None:
        _walk_tool_dicts(primary, raw)
    if not raw:  # shape not recognised: search everything
        _walk_tool_dicts(resp, raw)
    # The first live run listed every call twice. Collapse the same call (same id, or, with no
    # id, an identical dict); genuine repeated calls have different ids and are kept.
    seen, unique = set(), []
    for item in raw:
        key = ("id", item["id"]) if item.get("id") else ("dict", json.dumps(item, sort_keys=True, default=str))
        if key not in seen:
            seen.add(key)
            unique.append(item)
    return [
        {
            "id": item.get("id"),
            "name": str(item.get("name") or ""),
            "args": item.get("tool_input") if isinstance(item.get("tool_input"), dict) else {},
            "output": output_to_text(item.get("output")),
            "error": item.get("error"),
        }
        for item in unique
    ]


def with_tool_blocks(resp, blocks):
    """Copy of `resp` whose primary message carries `blocks` as its content_blocks. Used when the
    run response itself doesn't include the tool calls but Langflow's stored messages do."""
    import copy

    out = copy.deepcopy(resp) if isinstance(resp, dict) else {}
    node = out
    for key in ("outputs", 0, "outputs", 0, "results", "message"):
        if isinstance(key, int):
            if not isinstance(node, list) or not node:
                return out
            node = node[key]
        else:
            node = node.setdefault(key, {} if key != "outputs" else [])
    if isinstance(node, dict):
        node["content_blocks"] = list(blocks)
    return out


# --- evaluating a turn -------------------------------------------------------------------------


def _norm(value):
    return re.sub(r"[\s\"'“”‘’.,!?;:()]+", " ", str(value or "")).strip().lower()


def _tool_matches(name, kind):
    n = name.lower()
    if kind == "story":
        return "story" in n
    if kind == "add_word":
        return "add" in n and "word" in n
    return False


def _c(check, ok, detail="", info=False):
    out = {"check": check, "ok": bool(ok), "detail": detail}
    if info:
        out["info"] = True
    return out


def evaluate_turn(spec, resp, vocab, error=None, max_oov=2):
    """Return a list of {check, ok, detail} for one chat turn. Never raises."""
    if error or resp is None:
        return [_c("request", False, error or "no response")]

    info = bool(spec.get("info"))
    text = final_text(resp)
    calls = find_tool_calls(resp)
    good_calls = [c for c in calls if not c["error"] and c["output"].strip()]
    last = good_calls[-1] if good_calls else (calls[-1] if calls else None)
    expected = spec.get("tool")
    checks = [_c("reply not empty", text.strip(), f"{len(text)} chars", info)]

    # which tool(s) were called
    names = [c["name"] for c in calls]
    if expected == "either":
        checks.append(_c("tool called", True, f"recorded: {names or 'no tool'}", info=True))
    elif expected is None:
        checks.append(_c("tool called", not calls, "no tool expected; called: " + (", ".join(names) or "none"), info))
    else:
        called = any(_tool_matches(n, expected) for n in names)
        extra = f" ({len(calls)} call(s))" if len(calls) > 1 else ""
        checks.append(_c("tool called", called, f"expected {expected}; called: {', '.join(names) or 'none'}{extra}", info))

    # argument
    arg = spec.get("arg")
    if arg and expected not in (None, "either"):
        match = [c for c in calls if _tool_matches(c["name"], expected)]
        actual = _norm(match[-1]["args"].get(arg["key"])) if match else ""
        accepted = [_norm(a) for a in arg["any_of"]]
        checks.append(_c("tool argument", actual in accepted, f"{arg['key']}={actual!r}; accepted {accepted}", info))

    # relay: the learner must see exactly what the tool returned
    if good_calls:
        checks.append(_c("reply equals tool output", text == last["output"],
                         "identical" if text == last["output"] else f"reply {text[:60]!r} != tool {last['output'][:60]!r}", info))

    # reply wording (add-word confirmations)
    if spec.get("reply_any"):
        hit = any(w.lower() in text.lower() for w in spec["reply_any"])
        checks.append(_c("reply wording", hit, f"expected one of {spec['reply_any']}; got {text[:70]!r}", info))

    # empty-vocabulary guard
    if spec.get("expect_guard"):
        is_guard = GUARD_MARKER in text.lower().replace("\u2019", "'")
        checks.append(_c("empty-vocabulary guard", is_guard, text[:80] if text else "no reply", info))

    # story quality
    kind = spec.get("story")
    if kind and not spec.get("expect_guard"):
        result = check_passage(text, vocab, check_vocab=(kind == "english"), max_oov=max_oov,
                               language=spec.get("language"))
        if result["failure"]:
            detail = f"no story: {result['failure_reason']}"
        else:
            lc = result.get("language_check")
            detail = (f"{result['style']}, {result['units']} units"
                      + (f", stray words {result['oov_words']}" if result["oov_words"] else "")
                      + (", leaked plan" if result["leaked_plan"] else "")
                      + (f", language: written in {lc['verdict']} (English share {lc['english_ratio']:.0%})"
                         if lc and not lc["ok"] and lc["english_ratio"] is not None else "")
                      + (f", language: {lc['verdict']}" if lc and not lc["ok"] and lc["english_ratio"] is None else ""))
        checks.append(_c("story quality", result["passed"], detail, info))

    return checks
