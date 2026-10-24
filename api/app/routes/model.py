"""My model: a learner's own OpenAI-compatible model for stories (docs/CUSTOM-MODEL-DESIGN.md, phase 1).

Only accounts the operator switched on can use it (users.custom_model_enabled). The key goes in encrypted and is never sent back:
the page gets only "key ending xxxx". Test and Save call the address the learner typed, so the address guard runs first."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, field_validator

from ..db import connection
from ..deps import current_user
from ..errors import AppError
from ..services import model_secrets, user_models
from ..services.user_model import ModelError, call_model, check_base_url

router = APIRouter(prefix="/me/model", tags=["model"])
_NO_SPACE = re.compile(r"^\S+$")


class ModelIn(BaseModel):
    model: str
    base_url: str
    api_key: str | None = None        # None or "" = keep the saved key (a local server may have none)
    remove_key: bool = False

    @field_validator("model", "base_url", mode="before")
    @classmethod
    def _text(cls, v):
        v = (v or "").strip() if isinstance(v, str) else ""
        if not v:
            raise ValueError("This field is required.")
        return v

    @field_validator("model")
    @classmethod
    def _model(cls, v):
        if len(v) > 100 or not _NO_SPACE.match(v):
            raise ValueError("The model name is up to 100 characters with no spaces, for example gpt-4o-mini.")
        return v

    @field_validator("base_url")
    @classmethod
    def _url(cls, v):
        if len(v) > 200 or not _NO_SPACE.match(v):
            raise ValueError("The model address is up to 200 characters, for example https://api.openai.com/v1.")
        return v

    @field_validator("api_key")
    @classmethod
    def _key(cls, v):
        v = (v or "").strip() if isinstance(v, str) else None
        if v and (len(v) > 300 or not _NO_SPACE.match(v)):
            raise ValueError("The key is up to 300 characters with no spaces.")
        return v or None


def _allowed(request: Request, conn, user: dict) -> None:
    s = request.app.state.settings
    if not s.model_key_secret or not user_models.enabled(conn, user["id"]):
        raise AppError("custom_model_disabled", "Using your own model is not switched on for your account.", 403)


def _view(request: Request, conn, user: dict) -> dict:
    s = request.app.state.settings
    on = bool(s.model_key_secret) and user_models.enabled(conn, user["id"])
    row = user_models.get(conn, user["id"]) if on else None
    return {"enabled": on, "configured": bool(row), "model": row["model"] if row else None, "base_url": row["base_url"] if row else None,
            "key_last4": (row["key_last4"] or None) if row else None, "has_key": bool(row and row["api_key_encrypted"])}


@router.get("")
def show(request: Request, user: dict = Depends(current_user)):
    with connection(request.app.state.pool) as conn:
        return _view(request, conn, user)


def _resolve_key(request: Request, conn, user: dict, body: ModelIn) -> tuple[str, str]:
    """The key to use and to store: the new one, else the saved one, else none. Returns (plain, encrypted)."""
    secret = request.app.state.settings.model_key_secret
    if body.remove_key:
        return "", ""
    if body.api_key:
        return body.api_key, model_secrets.encrypt(secret, body.api_key)
    row = user_models.get(conn, user["id"])
    return (model_secrets.decrypt(secret, row["api_key_encrypted"]), row["api_key_encrypted"]) if row else ("", "")


def _test(request: Request, user: dict, body: ModelIn, plain: str) -> None:
    if not request.app.state.model_test_limiter.allow(user["id"]):
        raise AppError("rate_limited", "Wait a minute before testing again.", 429, retry_after=60)
    try:
        call_model(body.model, body.base_url, plain, "Reply with the single word: OK", allow_private=request.app.state.settings.allow_private_model_urls,
                   max_tokens=16)
    except ModelError as e:
        raise AppError("model_test_failed", str(e), 422)


@router.post("/test")
def test(body: ModelIn, request: Request, user: dict = Depends(current_user)):
    with connection(request.app.state.pool) as conn:
        _allowed(request, conn, user)
        plain, _ = _resolve_key(request, conn, user, body)
    _test(request, user, body, plain)
    return {"ok": True}


@router.put("")
def save(body: ModelIn, request: Request, user: dict = Depends(current_user)):
    with connection(request.app.state.pool) as conn:
        _allowed(request, conn, user)
        try:
            check_base_url(body.base_url, request.app.state.settings.allow_private_model_urls)
        except ModelError as e:
            raise AppError("validation_error", str(e), 422)
        plain, encrypted = _resolve_key(request, conn, user, body)
        user_models.save(conn, user["id"], body.model, body.base_url.rstrip("/"), encrypted, model_secrets.last4(plain))
        return _view(request, conn, user)


@router.delete("", status_code=204)
def remove(request: Request, user: dict = Depends(current_user)):
    with connection(request.app.state.pool) as conn:
        _allowed(request, conn, user)
        user_models.delete(conn, user["id"])
    return Response(status_code=204)
