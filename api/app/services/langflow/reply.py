"""How we read Langflow's answer: the Agent's reply text and the list of tool calls (name, arguments, output), from the run response and,
when that shows no tool call, from the session's stored messages. The parsing mirrors scripts/routing_checks.py and
custom_components/tool_result_relay.py, which Step 10 verified against the real flow. It is defensive on purpose: an unrecognised shape
yields an empty result, never an exception."""
from __future__ import annotations

import ast
import json
import re
from dataclasses import dataclass, field

_TOOL_BLOCK_TYPE = "tool_use"
_TEXT_KEYS = ("text", "result", "content", "message", "output", "data")
_MAX_DEPTH = 6
# The tools return these as ordinary text when they fail, so the reply is passed through unchanged and
# the matching tool call is flagged for the trace. (They move to tutor_core in M3.)
_FAILURE_MARKERS = ("Couldn't add word", "Add word failed", "I'm having trouble generating a story", "I can't write a story",
                    "Stories in ")
_REPLY_PATHS = (
    ("outputs", 0, "outputs", 0, "results", "message", "text"),
    ("outputs", 0, "outputs", 0, "results", "message", "data", "text"),
    ("outputs", 0, "outputs", 0, "outputs", "message", "message"),
)


@dataclass
class ToolCall:
    name: str
    args: dict
    output: str
    failed: bool = False


@dataclass
class ChatResult:
    reply: str
    tool_calls: list[ToolCall] = field(default_factory=list)
    tokens: int | None = None            # what Langflow says the turn used (total tokens), if it said


def _parse_structured_string(value: str):
    stripped = value.strip()
    if stripped[:1] not in ("{", "["):
        return None
    try:
        return json.loads(stripped)
    except ValueError:
        pass
    try:
        parsed = ast.literal_eval(stripped)
    except (ValueError, SyntaxError):
        return None
    return parsed if isinstance(parsed, (dict, list)) else None


def output_to_text(output, _depth: int = 0) -> str:
    """A tool call's recorded output as plain text. Unusable shapes become ''."""
    if output is None or _depth > _MAX_DEPTH:
        return ""
    if isinstance(output, str):
        parsed = _parse_structured_string(output)
        if parsed is not None:
            inner = output_to_text(parsed, _depth + 1)
            if inner.strip():
                return inner
        return output                                   # a plain story is returned exactly as it is
    if isinstance(output, dict):
        for key in _TEXT_KEYS:
            if key in output:
                inner = output_to_text(output[key], _depth + 1)
                if inner.strip():
                    return inner
        return ""
    if isinstance(output, (list, tuple)):
        return "\n".join(p for p in (output_to_text(i, _depth + 1) for i in output) if p.strip())
    return str(output)


def walk_tool_blocks(obj, _depth: int = 0):
    if _depth > 30:
        return
    if isinstance(obj, dict):
        if obj.get("type") == _TOOL_BLOCK_TYPE:
            yield obj
            return
        for value in obj.values():
            yield from walk_tool_blocks(value, _depth + 1)
    elif isinstance(obj, list):
        for value in obj:
            yield from walk_tool_blocks(value, _depth + 1)


_TOOL_NAMES = {"addword": "Add Word", "storygeneratortool": "Story Generator Tool"}


def canonical_tool_name(raw) -> str:
    """Langflow reports a tool by its snake_case name (`add_word`, found in the M0 spike: `spike_who_am_i`), not the display
    name on the canvas. The page and the vocabulary refresh key off the display names, so map them here."""
    text = str(raw or "").strip()
    if not text:
        return "tool"
    known = _TOOL_NAMES.get(re.sub(r"[^a-z0-9]", "", text.lower()))
    if known:
        return known
    return re.sub(r"[_\s]+", " ", text).strip().title() if "_" in text else text


def find_tool_calls(obj) -> list[ToolCall]:
    calls, seen = [], set()
    for block in walk_tool_blocks(obj):
        args = block.get("tool_input")
        args = args if isinstance(args, dict) else {}
        output = output_to_text(block.get("output"))
        key = (str(block.get("name")), json.dumps(args, sort_keys=True, default=str), output)
        if key in seen:                                 # Langflow repeats the same block in several places
            continue
        seen.add(key)
        failed = bool(block.get("error")) or output.lstrip().startswith(_FAILURE_MARKERS)
        calls.append(ToolCall(canonical_tool_name(block.get("name")), args, output, failed))
    return calls


def reply_text(resp) -> str:
    for path in _REPLY_PATHS:
        node = resp
        for part in path:
            if isinstance(part, int):
                node = node[part] if isinstance(node, list) and part < len(node) else None
            else:
                node = node.get(part) if isinstance(node, dict) else None
            if node is None:
                break
        if isinstance(node, str) and node.strip():
            return node
    return ""


def _machine_messages(stored) -> list:
    if not isinstance(stored, list):
        return []
    machine = [m for m in stored if isinstance(m, dict) and str(m.get("sender", "")).lower() not in ("user", "human")]
    return machine[-1:] if machine else []


def find_tokens(obj, _depth: int = 0) -> int | None:
    """The token count Langflow reports in a message's `properties.usage` (total_tokens, else input + output).
    Not found, or not a plain non-negative integer: None (the caller keeps its estimate)."""
    if _depth > 30:
        return None
    if isinstance(obj, dict):
        usage = obj.get("usage")
        if isinstance(usage, dict):
            total = usage.get("total_tokens")
            if isinstance(total, int) and not isinstance(total, bool) and total >= 0:
                return total
            parts = [usage.get("input_tokens"), usage.get("output_tokens")]
            if all(isinstance(p, int) and not isinstance(p, bool) and p >= 0 for p in parts):
                return sum(parts)
        children = obj.values()
    elif isinstance(obj, list):
        children = obj
    else:
        return None
    for child in children:
        found = find_tokens(child, _depth + 1)
        if found is not None:
            return found
    return None


def _one_story_call(calls: list, reply: str) -> list:
    """A reply holds ONE story, so it gets one story call (24 Oct: a chat showed three "Used Story Generator Tool" and three
    "Save story" buttons for one reply, so the learner could save a story they were never shown). Keep the story call whose output is
    the reply (else the last one); other tools' calls are untouched and keep their order."""
    stories = [c for c in calls if c.name == "Story Generator Tool"]
    if len(stories) < 2:
        return calls
    norm = lambda t: re.sub(r"\s+", " ", t or "").strip()
    keep = next((c for c in reversed(stories) if norm(c.output) == norm(reply)), stories[-1])
    return [c for c in calls if c.name != "Story Generator Tool" or c is keep]


def parse_run_response(resp, stored_messages=None) -> ChatResult:
    calls = find_tool_calls(resp)
    if not calls and stored_messages:
        calls = find_tool_calls(_machine_messages(stored_messages))
    reply = reply_text(resp)
    if not reply.strip() and calls:
        reply = calls[-1].output
    calls = _one_story_call(calls, reply)
    return ChatResult(reply=reply, tool_calls=calls, tokens=find_tokens(resp))
