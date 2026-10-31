"""Reading what a Langflow tool call recorded as its output, as plain text.

One parser for both places that need it: the Tool Result Relay inside Langflow (custom_components/tool_result_relay.py) and the
API's reading of a run response (api/app/services/langflow/reply.py)."""
from __future__ import annotations

import ast
import json

TEXT_KEYS = ("text", "result", "content", "message", "output", "data")
MAX_DEPTH = 6


def parse_structured_string(value: str):
    """If a string holds a JSON or Python-repr dict/list, return it parsed; otherwise None."""
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
    """Turn a tool call's recorded output into plain text. Unusable shapes become ''."""
    if output is None or _depth > MAX_DEPTH:
        return ""
    if isinstance(output, str):
        parsed = parse_structured_string(output)
        if parsed is not None:
            inner = output_to_text(parsed, _depth + 1)
            if inner.strip():
                return inner
        return output                                   # a plain story is returned exactly as it is
    if isinstance(output, dict):
        for key in TEXT_KEYS:
            if key in output:
                inner = output_to_text(output[key], _depth + 1)
                if inner.strip():
                    return inner
        return ""
    if isinstance(output, (list, tuple)):
        return "\n".join(p for p in (output_to_text(i, _depth + 1) for i in output) if p.strip())
    text = getattr(output, "text", None)                # Message / Data and similar objects
    if isinstance(text, str):
        return text
    return str(output)
