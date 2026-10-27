"""Talking to Langflow (design section 3D). The rest of the API imports from here; the work is in `services/langflow/`:

    payload.py    what we send (session id, hidden tool inputs, reply-language note)
    reply.py      how we read the answer (tool calls, reply text, tokens)
    transport.py  the HTTP call and its failures
    client.py     LangflowClient, and NoStoredChat for tutors that keep no conversation

Which tweak keys work, or whether Plan B (the session id alone) is used, is decided by milestone M0; LANGFLOW_TWEAK_KEYS holds the answer
(empty = no tweaks).
"""
from __future__ import annotations

from .langflow.client import CLEANUP_FAILED, LangflowClient, NoStoredChat, cleanup_failed
from .langflow.payload import build_run_payload, build_session_id, build_tweaks, with_reply_language
from .langflow.reply import (ChatResult, ToolCall, walk_tool_blocks, canonical_tool_name, find_tokens, find_tool_calls, output_to_text,
                             parse_run_response, reply_text)
from .langflow.transport import Transport, TransportError, map_transport_error, urllib_transport

__all__ = [
    "CLEANUP_FAILED", "ChatResult", "LangflowClient", "NoStoredChat", "ToolCall", "Transport", "TransportError", "build_run_payload",
    "build_session_id", "build_tweaks", "canonical_tool_name", "cleanup_failed", "find_tokens", "find_tool_calls", "map_transport_error",
    "output_to_text", "parse_run_response", "reply_text", "urllib_transport", "walk_tool_blocks", "with_reply_language",
]
