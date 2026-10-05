"""
Tool Result Relay — makes the learner see exactly what the tool returned.

Why this exists (Step 9): the top-level Agent sometimes shortened, reworded, or added notes to
the Story Generator Tool's output, even with strict instructions. An LLM writes the Agent's
final reply, so prompt tuning cannot guarantee a faithful relay. This component sits between
the Agent and Chat Output:

    Chat Input -> Agent -> Tool Result Relay -> Chat Output

If the Agent called a tool, the reply text is replaced with that tool's own output, exactly.
If no tool was called (small talk), the Agent's own text passes through unchanged. The Agent
still decides WHICH tool to call and with what argument; code decides WHAT the learner sees.

The pure functions are kept separate from the Langflow class so they can be tested directly
(see tests/test_tool_result_relay.py).
"""

import ast
import json

from langflow.custom import Component
from langflow.io import MessageInput, Output
from langflow.schema.message import Message

_TOOL_BLOCK_TYPE = "tool_use"
_TEXT_KEYS = ("text", "result", "content", "message", "output", "data")
_MAX_DEPTH = 6


def _parse_structured_string(value):
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


def output_to_text(output, _depth=0):
    """Turn a tool call's recorded output into plain text. Unusable shapes become ''."""
    if output is None or _depth > _MAX_DEPTH:
        return ""
    if isinstance(output, str):
        parsed = _parse_structured_string(output)
        if parsed is not None:
            inner = output_to_text(parsed, _depth + 1)
            if inner.strip():
                return inner
        return output  # a plain story is returned exactly as it is
    if isinstance(output, dict):
        for key in _TEXT_KEYS:
            if key in output:
                inner = output_to_text(output[key], _depth + 1)
                if inner.strip():
                    return inner
        return ""
    if isinstance(output, (list, tuple)):
        parts = [output_to_text(item, _depth + 1) for item in output]
        return "\n".join(p for p in parts if p.strip())
    text = getattr(output, "text", None)  # Message / Data and similar objects
    if isinstance(text, str):
        return text
    return str(output)


def _walk_content(blocks, _depth=0):
    """Yield every content item, whether it sits directly in content_blocks (how Langflow
    builds an Agent message) or inside a ContentBlock wrapper."""
    if _depth > _MAX_DEPTH:
        return
    for block in blocks or []:
        yield block
        yield from _walk_content(getattr(block, "contents", None), _depth + 1)


def extract_last_tool_output(message):
    """Return the output of the last successful, non-empty tool call on this message, or None."""
    blocks = getattr(message, "content_blocks", None)
    if not blocks:
        return None

    last = None
    for item in _walk_content(blocks):
        if getattr(item, "type", None) != _TOOL_BLOCK_TYPE:
            continue
        if getattr(item, "error", None):
            continue
        text = output_to_text(getattr(item, "output", None))
        if text.strip():
            last = text
    return last


def relay_message(message):
    """Replace the Agent's reply text with the tool output (if any), keeping everything else.

    The same Message object is returned, so its id and tool-call trace are preserved and Chat
    Output updates the existing chat bubble instead of adding a second one.
    """
    if message is None:
        return Message(text="")
    if isinstance(message, str):
        return Message(text=message)

    tool_text = extract_last_tool_output(message)
    if tool_text is not None:
        message.text = tool_text
    return message


class ToolResultRelay(Component):
    display_name = "Tool Result Relay"
    description = (
        "Shows the learner exactly what the tool returned instead of the Agent's rewording. "
        "If no tool was called, the Agent's own reply passes through unchanged."
    )

    inputs = [
        MessageInput(
            name="agent_response",
            display_name="Agent Response",
            info="Connect the Agent's Response output here.",
        ),
    ]

    outputs = [
        Output(display_name="Relayed Response", name="relayed_response", method="relay"),
    ]

    def relay(self) -> Message:
        import json, time
        msg = self.agent_response
        lines = [f"--- relay ran at {time.strftime('%H:%M:%S')} ---"]
        try:
            blocks = getattr(msg, "content_blocks", None) or []
            lines.append(f"type={type(msg).__name__} text={repr(getattr(msg, 'text', None))[:150]} blocks={len(blocks)}")
            for b in blocks:
                lines.append(f"block {type(b).__name__}")
                for item in getattr(b, "contents", None) or []:
                    out = getattr(item, "output", None)
                    lines.append(
                        f"  item {type(item).__name__} type={getattr(item, 'type', None)} "
                        f"output_type={type(out).__name__} error={getattr(item, 'error', None)} "
                        f"output={repr(out)[:500]}"
                    )
        except Exception as e:
            lines.append(f"debug failed: {e!r}")
        try:
            with open("/app/custom_components/relay_debug.log", "a", encoding="utf-8") as f:
                f.write("\n".join(lines) + "\n")
        except Exception:
            pass

        result = relay_message(msg)
        self.status = result.text
        return result
