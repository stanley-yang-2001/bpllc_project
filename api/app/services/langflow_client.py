"""Talking to Langflow (design section 3D).

What we send: the learner's own message, a session id built here (never taken whole from the browser),
and, when the tweak keys are configured, the numeric learner id and language as hidden tool inputs. Nothing
else: no email, no display name, no password ever reaches Langflow or Groq.

What we read back: the Agent's reply text and the list of tool calls (name, arguments, output), from the
run response and, when that shows no tool call, from the session's stored messages. The parsing mirrors
scripts/routing_checks.py and custom_components/tool_result_relay.py, which Step 10 verified against the
real flow. It is defensive on purpose: an unrecognised shape yields an empty result, never an exception.

Which tweak keys work, or whether Plan B (the session id alone) is used, is decided by milestone M0;
LANGFLOW_TWEAK_KEYS holds the answer (empty = no tweaks).
"""
from __future__ import annotations

import ast
import json
import logging
import re
import socket
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable

from ..errors import AppError, validation_error

log = logging.getLogger("tutor.langflow")

_SESSION_PART = re.compile(r"^[0-9a-f]{32}$")
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


# --- what we send ------------------------------------------------------------------------------------

def build_session_id(user_id: int, client_part) -> str:
    """The browser supplies only 32 random hex characters; the user prefix is added here, so a learner can
    never address another learner's Langflow session."""
    if not isinstance(client_part, str) or not _SESSION_PART.match(client_part):
        raise validation_error("session_id must be 32 lowercase hex characters.")
    return f"u{int(user_id)}-{client_part}"


def build_tweaks(keys, user_id: int, language: str) -> dict | None:
    """The hidden tool inputs are named `learner_id` and `active_language` (not `language`: the story tool already has a visible
    `language` argument that the Agent fills in, and the two must not be confused). NOT `user_id`: Langflow reserves that name on every
    component (it returns the Langflow account's UUID) and a tool input called user_id is silently shadowed by it.
    The id is sent as a STRING: Langflow's text-field handling accepts only strings, lists and Data objects and silently
    drops anything else, so an integer never reaches the tool (the tool then sees no learner and, by design, refuses).
    Both found by the M0 spike. The tool turns the string back into an integer and rejects anything else."""
    if not keys:
        return None
    return {key: {"learner_id": str(int(user_id)), "active_language": language} for key in keys}


def with_reply_language(message: str, reply_language: str | None) -> str:
    """The Agent is asked to write ITS OWN sentences in the learner's study language when the learner chose that
    (Settings, "Chat replies in my study language"). The note names only the language, goes in front of the learner's message, and
    says tool names and arguments stay as they are. Fixed tool messages are relayed as the tool wrote them, so they are not affected.
    English gets the note too: a learner studying English who writes in another language still gets English back.
    It also says which language a story is in when the learner names none (24 Oct: with English active, "生成一个故事" came back as a
    Chinese story, because the Agent took the language from the message); a language the learner does name still wins."""
    if not reply_language or not reply_language.strip():
        return message
    return (f"[Note for the tutor: write your own sentences to the learner in {reply_language}. "
            f"If the learner asks for a story without naming a language in words, call the story tool with language \"{reply_language}\", "
            f"whatever language the message is written in. A language the learner does name wins. "
            f"Tool names and every other tool argument stay exactly as they are.]\n\n{message}")


def build_run_payload(message: str, session_id: str, tweaks: dict | None) -> dict:
    payload = {"input_value": message, "input_type": "chat", "output_type": "chat", "session_id": session_id}
    if tweaks:
        payload["tweaks"] = tweaks
    return payload


# --- how we read the answer --------------------------------------------------------------------------

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


def _walk_tool_blocks(obj, _depth: int = 0):
    if _depth > 30:
        return
    if isinstance(obj, dict):
        if obj.get("type") == _TOOL_BLOCK_TYPE:
            yield obj
            return
        for value in obj.values():
            yield from _walk_tool_blocks(value, _depth + 1)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk_tool_blocks(value, _depth + 1)


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
    for block in _walk_tool_blocks(obj):
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


# --- transport and the client ------------------------------------------------------------------------

class TransportError(Exception):
    """kind: 'unreachable' (cannot connect), 'timeout', 'http' (status set), 'badjson'."""

    def __init__(self, kind: str, status: int | None = None, detail: str = ""):
        super().__init__(f"{kind} {status or ''} {detail}".strip())
        self.kind, self.status, self.detail = kind, status, detail


def urllib_transport(method: str, url: str, payload, headers: dict, timeout: float):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    hdrs = dict(headers)
    if data is not None:
        hdrs["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise TransportError("http", e.code, e.read().decode("utf-8", "replace")[:200])
    except (socket.timeout, TimeoutError):
        raise TransportError("timeout")
    except urllib.error.URLError as e:
        if isinstance(e.reason, (socket.timeout, TimeoutError)):
            raise TransportError("timeout")
        raise TransportError("unreachable", None, str(e.reason))
    except OSError as e:
        raise TransportError("unreachable", None, str(e))
    try:
        return json.loads(body) if body else {}
    except ValueError:
        raise TransportError("badjson", 200, body[:100])


def map_transport_error(error: TransportError) -> AppError:
    """Learner-facing messages never mention Langflow, Groq or HTTP; the detail goes to the log."""
    log.warning("langflow call failed: %s", error)
    if error.kind == "unreachable":
        return AppError("langflow_unavailable", "The chat tutor can't be reached right now. The rest of the site still works.", 503)
    if error.kind == "timeout":
        return AppError("ai_failed", "The tutor took too long to answer. Please try again.", 502)
    if error.kind == "http" and error.status == 429:
        return AppError("tutor_busy", "The tutor is busy. Try again in a moment.", 429, retry_after=15)
    if error.kind == "http" and error.status in (401, 403, 404):       # our configuration is wrong
        return AppError("langflow_unavailable", "The chat tutor isn't set up correctly right now.", 503)
    return AppError("ai_failed", "The tutor couldn't answer just now. Please try again.", 502)


Transport = Callable[[str, str, Any, dict, float], Any]


CLEANUP_FAILED = ("We couldn't remove your chat history just now, so your account has not been deleted. "
                  "Please try again in a moment.")


def cleanup_failed() -> AppError:
    return AppError("chat_cleanup_failed", CLEANUP_FAILED, 503, retry_after=15)


class NoStoredChat:
    """For tutors that keep no conversation anywhere (the stub, or live mode that is switched off): there is
    nothing to delete. If a learner nevertheless has recorded sessions, say so rather than pretend."""
    stores_chat = False
    calls_ai = False            # nothing reaches Groq, so nothing is charged to the token budget

    def health(self) -> dict:
        return {"ok": None, "status": "stub", "detail": None}

    def delete_sessions(self, session_ids) -> None:
        if list(session_ids):
            log.error("cannot delete chat sessions: this deployment has no Langflow client")
            raise cleanup_failed()


class LangflowClient:
    stores_chat = True
    calls_ai = True
    HEALTH_TIMEOUT = 3

    def __init__(self, base_url: str, flow: str, api_key: str, timeout: float = 100.0,
                 tweak_keys=(), transport: Transport | None = None, fallback_timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.flow = flow
        self.api_key = api_key
        self.timeout = timeout
        self.tweak_keys = tuple(tweak_keys)
        self.fallback_timeout = fallback_timeout
        self._transport = transport or urllib_transport

    def _headers(self) -> dict:
        return {"x-api-key": self.api_key}

    def _stored_messages(self, session_id: str):
        url = f"{self.base_url}/api/v1/monitor/messages?session_id={urllib.parse.quote(session_id, safe='')}"
        try:
            return self._transport("GET", url, None, self._headers(), self.fallback_timeout)
        except TransportError:
            return None                                 # best effort: the run response is the main source

    def run(self, *, user_id: int, language: str, message: str, session_id: str, reply_language: str | None = None) -> ChatResult:
        payload = build_run_payload(with_reply_language(message, reply_language), session_id, build_tweaks(self.tweak_keys, user_id, language))
        url = f"{self.base_url}/api/v1/run/{urllib.parse.quote(self.flow, safe='')}?stream=false"
        try:
            response = self._transport("POST", url, payload, self._headers(), self.timeout)
        except TransportError as e:
            raise map_transport_error(e)
        stored = None if find_tool_calls(response) else self._stored_messages(session_id)
        result = parse_run_response(response, stored)
        if not result.reply.strip() and not result.tool_calls:
            log.warning("langflow returned no reply and no tool calls")
            raise AppError("ai_failed", "The tutor couldn't answer just now. Please try again.", 502)
        return result

    def health(self) -> dict:
        """Is Langflow answering? Only the kind of failure is reported, never its address or our key."""
        try:
            self._transport("GET", f"{self.base_url}/health", None, {}, self.HEALTH_TIMEOUT)
        except TransportError as e:
            log.warning("langflow health check failed: %s", e)
            return {"ok": False, "status": "down", "detail": e.kind}
        return {"ok": True, "status": "up", "detail": None}

    def delete_sessions(self, session_ids) -> None:
        """Remove these sessions' stored messages from Langflow and CHECK they are gone. Every session is tried;
        if any cannot be confirmed empty, one `chat_cleanup_failed` is raised at the end. Account deletion
        waits for this, so a learner is never told their data is gone when it is not."""
        failed = []
        for session_id in session_ids:
            quoted = urllib.parse.quote(session_id, safe="")
            url = f"{self.base_url}/api/v1/monitor/messages/session/{quoted}"
            try:
                try:
                    self._transport("DELETE", url, None, self._headers(), self.fallback_timeout)
                except TransportError as e:
                    # a 404 (nothing there) or a 200 with an odd body may already mean "gone": the check decides
                    if not (e.kind == "badjson" or (e.kind == "http" and e.status == 404)):
                        raise
                remaining = self._transport("GET", f"{self.base_url}/api/v1/monitor/messages?session_id={quoted}",
                                            None, self._headers(), self.fallback_timeout)
                if not isinstance(remaining, list) or remaining:
                    raise TransportError("badjson", None, "session not confirmed empty")
            except TransportError as e:
                log.error("could not delete langflow session %s: %s", session_id, e)
                failed.append(session_id)
        if failed:
            raise cleanup_failed()
