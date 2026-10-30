"""My model: a learner's own OpenAI-compatible model for stories (docs/CUSTOM-MODEL-DESIGN.md, phase 1).

Only accounts the operator switched on can use it (users.custom_model_enabled). The key goes in encrypted and is never sent back:
the page gets only "key ending xxxx". Test and Save call the address the learner typed, so the address guard runs first."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, field_validator

from ..db import connection
from ..deps import current_user
from ..services import model_settings

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


@router.get("")
def show(request: Request, user: dict = Depends(current_user)):
    with connection(request.app.state.pool) as conn:
        return model_settings.view(conn, request.app.state.settings, user["id"])


@router.post("/test")
def test(body: ModelIn, request: Request, user: dict = Depends(current_user)):
    state = request.app.state
    with connection(state.pool) as conn:
        model_settings.require_enabled(conn, state.settings, user["id"])
        plain, _ = model_settings.resolve_key(conn, state.settings, user["id"], body.api_key, body.remove_key)
    model_settings.test_connection(state.settings, state.model_test_limiter, user["id"], body.model, body.base_url, plain)
    return {"ok": True}


@router.put("")
def save(body: ModelIn, request: Request, user: dict = Depends(current_user)):
    state = request.app.state
    with connection(state.pool) as conn:
        model_settings.require_enabled(conn, state.settings, user["id"])
        return model_settings.save(conn, state.settings, user["id"], body.model, body.base_url, body.api_key, body.remove_key)


@router.delete("", status_code=204)
def remove(request: Request, user: dict = Depends(current_user)):
    state = request.app.state
    with connection(state.pool) as conn:
        model_settings.require_enabled(conn, state.settings, user["id"])
        model_settings.remove(conn, user["id"])
    return Response(status_code=204)
