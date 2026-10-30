"""Calling a learner's own OpenAI-compatible model (docs/CUSTOM-MODEL-DESIGN.md, sections 3 and 5).

The work is in four files; this one keeps the old import path working:

    model_address.py  the address guard (SSRF): who may be called
    pinned_http.py    connections pinned to the address that was checked
    model_client.py   the chat-completions call and the story function built on it
    rate_limit.py     the per-learner request limit
"""
from __future__ import annotations

import socket          # noqa: F401  (tests patch user_model.socket.getaddrinfo, which is the shared module)

from .model_address import ModelError, check_base_url
from .model_client import MAX_RESPONSE_BYTES, MAX_TOKENS, TIMEOUT_SECONDS, USER_AGENT, call_model, make_call_fn
from .pinned_http import _Pinned, _PinnedPlain
from .rate_limit import RequestLimiter

__all__ = ["MAX_RESPONSE_BYTES", "MAX_TOKENS", "ModelError", "RequestLimiter", "TIMEOUT_SECONDS", "USER_AGENT", "_Pinned", "_PinnedPlain",
           "call_model", "check_base_url", "make_call_fn"]
