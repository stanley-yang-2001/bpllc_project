"""Which model answers a request, and the rules every model call shares.

Three sources can answer, tried in this order: the stand-in (AI_MODE=stub, only for jobs that bring their own stub), the learner's own
model, the shared model. Each is a small class with one method, `pick`, so a new source (another provider, a test double) is a new
class in the list, not an edit to the runner. The runner builds the call for one request from the app's parts; routes receive it
through `Depends(ai_runner_for)` and never look into the app's state themselves.

A chosen model is a plain callable `prompt -> text`. One that sets `calls_ai = False` (the stand-in, a learner's own model) is not
charged to the shared token budget. A learner's own model has its own request limit instead (docs/CUSTOM-MODEL-DESIGN.md).
"""
from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Protocol

from fastapi import Request

from ..db import connection
from ..errors import AppError
from . import model_secrets, user_models
from .user_model import RequestLimiter, make_call_fn

Call = Callable[[str], str]


@dataclass(frozen=True)
class Chosen:
    """The model picked for one request. `own_model` is the learner's own model name, or None for the stand-in or the shared model."""
    call: Call
    own_model: str | None = None

    @property
    def metered(self) -> bool:
        return getattr(self.call, "calls_ai", True)

    @property
    def last_error(self) -> str:
        return getattr(self.call, "last_error", "") or "no answer."


class ModelSource(Protocol):
    def pick(self, user_id: int, stub: Call | None) -> Chosen | None: ...


def _unmetered(fn: Call) -> Call:
    def call(prompt: str) -> str:
        return fn(prompt)
    call.calls_ai = False                       # a stand-in makes no model call, so it is never charged to the token budget
    return call


class OwnModels:
    """The learner's saved model with its key decrypted, or None when it is not switched on or not set up."""

    def __init__(self, pool, secret: str):
        self._pool, self._secret = pool, secret

    def find(self, user_id: int, conn=None) -> dict | None:
        if not self._secret:
            return None
        if conn is None:
            with connection(self._pool) as own_conn:
                return self.find(user_id, own_conn)
        if not user_models.enabled(conn, user_id):
            return None
        row = user_models.get(conn, user_id)
        if not row:
            return None
        return {"model": row["model"], "base_url": row["base_url"], "key": model_secrets.decrypt(self._secret, row["api_key_encrypted"])}


class StubSource:
    """AI_MODE=stub: a job that brings its own stand-in is answered by it, with no model call and no token charge."""

    def __init__(self, ai_mode: str):
        self._mode = ai_mode

    def pick(self, user_id: int, stub: Call | None) -> Chosen | None:
        if self._mode != "stub" or stub is None:
            return None
        return Chosen(_unmetered(stub))


class OwnModelSource:
    """The learner's own model, when they have set one up. A request limit applies instead of the shared token budget."""

    def __init__(self, own_models: OwnModels, limiter: RequestLimiter, allow_private: bool):
        self._own, self._limiter, self._allow_private = own_models, limiter, allow_private

    def pick(self, user_id: int, stub: Call | None) -> Chosen | None:
        own = self._own.find(user_id)
        if not own:
            return None
        if not self._limiter.allow(user_id):
            raise AppError("rate_limited", "You are using your own model too quickly. Wait a minute.", 429, retry_after=60)
        return Chosen(make_call_fn(own["model"], own["base_url"], own["key"], self._allow_private), own_model=own["model"])


class SharedSource:
    """The site's model (Groq, or the story stand-in in stub mode). Always answers."""

    def __init__(self, llm: Call):
        self._llm = llm

    def pick(self, user_id: int, stub: Call | None) -> Chosen | None:
        return Chosen(self._llm)


class AiRunner:
    def __init__(self, sources: list[ModelSource], gate):
        self._sources, self._gate = sources, gate

    def choose(self, user_id: int, stub: Call | None = None) -> Chosen:
        for source in self._sources:
            chosen = source.pick(user_id, stub)
            if chosen is not None:
                return chosen
        raise AppError("ai_failed", "No model is available right now.", 502)

    @contextmanager
    def slot(self, user_id: int, chosen: Chosen, tokens: int):
        """A place for one call; `tokens` is reserved from the shared per-minute budget unless the model is not metered."""
        with self._gate.slot(user_id, tokens=tokens if chosen.metered else 0) as ticket:
            yield ticket

    @staticmethod
    def failure(chosen: Chosen, message: str, own_hint: str = "") -> AppError:
        """The error for a model that did not answer: one for a learner's own model (with its reason), one for the shared model."""
        if chosen.own_model:
            return AppError("custom_model_failed", f"Your model ({chosen.own_model}) didn't answer: {chosen.last_error} {own_hint}".strip(), 502)
        return AppError("ai_failed", message, 502)

    def run(self, user_id: int, prompt: str, *, tokens: int, failed_message: str, stub: Call | None = None) -> str:
        """One model call for a short text job: choose, take a slot, call, and turn any failure into the standard error."""
        chosen = self.choose(user_id, stub)
        with self.slot(user_id, chosen, tokens):
            try:
                return chosen.call(prompt)
            except Exception:
                raise self.failure(chosen, failed_message)


def own_models_for(request: Request) -> OwnModels:
    state = request.app.state
    return OwnModels(state.pool, state.settings.model_key_secret)


def ai_runner_for(request: Request) -> AiRunner:
    """The runner for this request, built from the app's current parts (so a test that swaps one in app.state is honoured)."""
    state = request.app.state
    s = state.settings
    return AiRunner(
        [StubSource(s.ai_mode), OwnModelSource(own_models_for(request), state.model_limiter, s.allow_private_model_urls), SharedSource(state.story_llm)],
        state.ai_gate,
    )
