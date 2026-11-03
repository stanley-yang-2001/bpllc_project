"""Chat on a learner's own model (docs/CUSTOM-MODEL-DESIGN.md section 10): when a turn should use it, and what Langflow is told.

Langflow is given the learner's model NAME, the API's own internal address and a throwaway token (services/turn_tokens.py). The real key
stays in the API, which swaps it in when Langflow's request comes back to /internal/v1/chat/completions."""
from __future__ import annotations

from ..errors import AppError
from . import user_models


def plan(state, conn, user_id: int) -> dict | None:
    """None when this turn runs on the shared model. Otherwise {node, model, url, token}; the caller must revoke the token afterwards."""
    settings = state.settings
    if not (settings.chat_own_model and settings.model_key_secret and state.chat.calls_ai):
        return None
    if not user_models.enabled(conn, user_id):
        return None
    row = user_models.get(conn, user_id)
    if not row:
        return None             # switched on but nothing saved yet: the shared tutor answers, as before
    token = state.turn_tokens.issue(user_id, ttl=settings.langflow_timeout + 60)
    return {"node": settings.langflow_model_node, "model": row["model"], "url": settings.internal_api_url, "token": token}


def failure(state, own: dict, error: AppError) -> AppError:
    """A failed turn on the learner's own model says why (as Story Studio does), with the key already removed by the proxy."""
    message = state.turn_tokens.last_error(own["token"])
    return AppError("own_model_failed", message, 502) if message else error
