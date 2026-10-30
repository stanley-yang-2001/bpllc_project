"""My model, the rules: who may use it, what the page may see, how the key is kept, and the Test, Save and Remove steps.

The route (routes/model.py) checks the form and shapes the answer; the address guard, the encryption and the rate limit are here.
"""
from __future__ import annotations

from ..errors import AppError
from . import model_secrets, user_models
from .user_model import ModelError, call_model, check_base_url


def require_enabled(conn, settings, user_id: int) -> None:
    if not settings.model_key_secret or not user_models.enabled(conn, user_id):
        raise AppError("custom_model_disabled", "Using your own model is not switched on for your account.", 403)


def view(conn, settings, user_id: int) -> dict:
    """What the page may see. The key is never part of it: only whether there is one and its last four characters."""
    on = bool(settings.model_key_secret) and user_models.enabled(conn, user_id)
    row = user_models.get(conn, user_id) if on else None
    return {"enabled": on, "configured": bool(row), "model": row["model"] if row else None, "base_url": row["base_url"] if row else None,
            "key_last4": (row["key_last4"] or None) if row else None, "has_key": bool(row and row["api_key_encrypted"])}


def resolve_key(conn, settings, user_id: int, new_key: str | None, remove_key: bool) -> tuple[str, str]:
    """The key to use and to store: the new one, else the saved one, else none. Returns (plain, encrypted)."""
    if remove_key:
        return "", ""
    if new_key:
        return new_key, model_secrets.encrypt(settings.model_key_secret, new_key)
    row = user_models.get(conn, user_id)
    return (model_secrets.decrypt(settings.model_key_secret, row["api_key_encrypted"]), row["api_key_encrypted"]) if row else ("", "")


def test_connection(settings, limiter, user_id: int, model: str, base_url: str, plain_key: str) -> None:
    """One tiny request to the learner's model, rate limited per learner. Raises AppError with what went wrong."""
    if not limiter.allow(user_id):
        raise AppError("rate_limited", "Wait a minute before testing again.", 429, retry_after=60)
    try:
        call_model(model, base_url, plain_key, "Reply with the single word: OK", allow_private=settings.allow_private_model_urls, max_tokens=16)
    except ModelError as e:
        raise AppError("model_test_failed", str(e), 422)


def save(conn, settings, user_id: int, model: str, base_url: str, new_key: str | None, remove_key: bool) -> dict:
    try:
        check_base_url(base_url, settings.allow_private_model_urls)       # the address guard runs before anything is stored
    except ModelError as e:
        raise AppError("validation_error", str(e), 422)
    plain, encrypted = resolve_key(conn, settings, user_id, new_key, remove_key)
    user_models.save(conn, user_id, model, base_url.rstrip("/"), encrypted, model_secrets.last4(plain))
    return view(conn, settings, user_id)


def remove(conn, user_id: int) -> None:
    user_models.delete(conn, user_id)
