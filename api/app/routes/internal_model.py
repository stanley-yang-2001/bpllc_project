"""The model route only Langflow calls (docs/CUSTOM-MODEL-DESIGN.md section 10): an OpenAI-compatible /chat/completions.

Mounted at /internal/v1, NOT under /api, so the web container's nginx (which forwards /api/ only) never publishes it, and the API
port is not published to the host. Beyond that: a request that came through a proxy (it carries forwarding headers) is refused, and
the bearer must be a live throwaway token (services/turn_tokens.py). The learner's key never appears in a request or a response."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse

from ..db import connection
from ..services import model_secrets, user_models
from ..services.model_proxy import ProxyError, open_upstream

log = logging.getLogger("tutor.model_proxy")
INTERNAL_PREFIX = "/internal/"
FORWARDED = ("x-forwarded-for", "x-real-ip", "x-forwarded-proto", "forwarded")

router = APIRouter(prefix="/internal/v1", tags=["internal"], include_in_schema=False)


def _error(status: int, message: str, token: str = "", tokens=None):
    if tokens is not None and token:
        tokens.note_error(token, message)
    return JSONResponse({"error": {"message": message, "type": "own_model_error", "code": status}}, status_code=status)


@router.post("/chat/completions")
async def chat_completions(request: Request):
    state = request.app.state
    if any(h in request.headers for h in FORWARDED):
        return _error(403, "Not available here.")
    auth = request.headers.get("authorization", "")
    token = auth[7:].strip() if auth.lower().startswith("bearer ") else ""
    user_id = state.turn_tokens.use(token)
    if user_id is None:
        return _error(401, "This request is not allowed.")
    if not state.chat_model_limiter.allow(user_id):
        return _error(429, "Too many requests to your model in a minute. Wait a little and try again.", token, state.turn_tokens)
    raw = await request.body()
    try:
        upstream = await run_in_threadpool(_open, state, user_id, raw)      # database and network work: off the event loop
    except ProxyError as e:
        return _error(e.status, e.message, token, state.turn_tokens)
    state.turn_tokens.clear_error(token)          # a later call that works means the earlier failure is not what the learner needs to hear
    return StreamingResponse(upstream.chunks(), media_type=upstream.content_type)


def _open(state, user_id: int, raw: bytes):
    settings = state.settings
    with connection(state.pool) as conn:
        row = user_models.get(conn, user_id) if user_models.enabled(conn, user_id) and settings.model_key_secret else None
        key = model_secrets.decrypt(settings.model_key_secret, row["api_key_encrypted"]) if row and row["api_key_encrypted"] else ""
    if not row:
        raise ProxyError(409, "Your own model is not set up. Open My model in Settings.")
    return open_upstream(row["model"], row["base_url"], key, raw, allow_private=settings.allow_private_model_urls)
