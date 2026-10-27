"""The signed-in learner's own profile, display preferences and languages (the sensitive account actions are in account.py)."""
from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, field_validator
from tutor_core.languages import LANGUAGES

from ..db import connection
from ..deps import current_user, require_language
from ..errors import validation_error
from ..schemas import PreferencesOut, UserOut
from ..services import preferences, users

router = APIRouter(tags=["me"])


class ProfilePatch(BaseModel):
    display_name: str | None = None
    native_language: str | None = None

    @field_validator("display_name")
    @classmethod
    def _dn(cls, v):
        if v is None:
            return None
        v = " ".join(v.split())
        if not 1 <= len(v) <= 40:
            raise ValueError("must be 1-40 characters")
        return v

    @field_validator("native_language")
    @classmethod
    def _nl(cls, v):
        if v is not None and v not in LANGUAGES:
            raise ValueError("unsupported language")
        return v


_HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
_THEME = re.compile(r"^[a-z][a-z0-9-]{0,23}$")
_COLOR_PARTS = ("page", "cards", "text", "borders", "accent")


class ColorsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    page: str
    cards: str
    text: str
    borders: str
    accent: str

    @field_validator(*_COLOR_PARTS)
    @classmethod
    def _hex(cls, v: str) -> str:
        if not _HEX.match(v):
            raise ValueError("must be a colour like #1a2b3c")
        return v.lower()


class PreferencesPatch(BaseModel):
    """Any subset. Unknown keys are rejected so a typo never silently does nothing. The server checks the *shape* of
    a theme id; what it means is up to the app, so an older app and a newer server never break each other."""
    model_config = ConfigDict(extra="forbid")
    active_language: str | None = None
    ui_follows_study_language: bool | None = None
    chat_in_study_language: bool | None = None
    theme: str | None = None
    custom_colors: ColorsIn | None = None

    @field_validator("theme")
    @classmethod
    def _theme(cls, v):
        if v is not None and not _THEME.match(v):
            raise ValueError("must be a short lowercase id such as dark or ocean")
        return v


class LanguageBody(BaseModel):
    language: str


@router.get("/me", response_model=UserOut)
def me(request: Request, user: dict = Depends(current_user)):
    with connection(request.app.state.pool) as conn:
        return users.profile(conn, user)


@router.patch("/me", response_model=UserOut)
def patch_me(body: ProfilePatch, request: Request, user: dict = Depends(current_user)):
    with connection(request.app.state.pool) as conn:
        updated = users.update_profile(conn, user["id"], body.display_name, body.native_language)
        return users.profile(conn, updated)


@router.patch("/me/preferences", response_model=PreferencesOut)
def patch_preferences(body: PreferencesPatch, request: Request, user: dict = Depends(current_user)):
    """Saves display preferences on the account so they follow the learner to every browser."""
    changes = preferences.changes_from(body.model_dump(include=body.model_fields_set))
    with connection(request.app.state.pool) as conn:
        if changes.get("active_language") is not None and changes["active_language"] not in users.languages_of(conn, user["id"]):
            raise validation_error("active_language: not one of your languages")
        return preferences.save(conn, user["id"], changes)


@router.post("/me/languages", response_model=UserOut)
def add_language(body: LanguageBody, request: Request, user: dict = Depends(current_user)):
    code = require_language(body.language)
    with connection(request.app.state.pool) as conn:
        users.add_language(conn, user["id"], code)
        return users.profile(conn, user)
