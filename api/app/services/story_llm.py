"""Which model writes the stories for Story Studio: Groq, or a fixed stand-in for AI_MODE=stub.

The route only ever calls `state.story_llm(prompt) -> text`. A callable with `calls_ai = False` is never charged to the
token budget (the stand-in makes no model call)."""
from __future__ import annotations

import logging
import os
import time

from tutor_core import groq as groq_module

from ..config import Settings
from .langflow_client import TransportError, urllib_transport

log = logging.getLogger("tutor.story")

STUB_STORY = "Ana: Hello, friend.\nBen: Hello, water please.\nAna: Thank you.\nBen: Goodbye, friend."


def stub_llm(_prompt: str) -> str:
    return "Plan: a short chat\n===STORY===\n" + STUB_STORY


stub_llm.calls_ai = False


def make_story_llm(settings: Settings):
    return stub_llm if settings.ai_mode == "stub" else groq_module.call_groq


GROQ_MODELS_URL = "https://api.groq.com/openai/v1/models"       # a list call: it costs no tokens, only a request


class GroqHealth:
    """Is Groq answering with our key? One light call to its models list, remembered for `ttl` seconds so the Settings page
    (or a person pressing Re-check) cannot use up the shared rate limit. Only the kind of failure is reported."""

    def __init__(self, stub: bool, api_key_fn, transport, clock, ttl: float = 60.0, timeout: float = 3.0):
        """`api_key_fn() -> str`, `transport(method, url, payload, headers, timeout)` and `clock() -> seconds` are given, not looked up, so the
        check can be tested without a network, a key or a wait. `make_groq_health` wires the real ones."""
        self.stub, self.ttl, self.timeout = stub, ttl, timeout
        self._key = api_key_fn
        self._transport = transport
        self._clock = clock
        self._cached: tuple[float, dict] | None = None

    def check(self) -> dict:
        if self.stub:
            return {"ok": None, "status": "stub", "detail": None}
        now = self._clock()
        if self._cached and now - self._cached[0] < self.ttl:
            return self._cached[1]
        result = self._probe()
        self._cached = (now, result)
        return result

    def _probe(self) -> dict:
        key = (self._key() or "").strip()
        if not key:
            return {"ok": False, "status": "off", "detail": "no key"}
        headers = {"Authorization": f"Bearer {key}", "User-Agent": "language-tutor-story-tool/1.0"}      # Cloudflare blocks a request without a User-Agent
        try:
            self._transport("GET", GROQ_MODELS_URL, None, headers, self.timeout)
        except TransportError as e:
            log.warning("groq health check failed: %s", e.kind if e.kind != "http" else f"http {e.status}")
            return {"ok": False, "status": "down", "detail": "rejected" if e.status in (401, 403) else e.kind}
        return {"ok": True, "status": "up", "detail": None}


def make_groq_health(settings: Settings) -> GroqHealth:
    """The real wiring: the key from the environment, the standard-library HTTP transport, the monotonic clock."""
    return GroqHealth(stub=settings.ai_mode == "stub", api_key_fn=lambda: os.environ.get("GROQ_API_KEY", ""), transport=urllib_transport, clock=time.monotonic)
