from __future__ import annotations

import re

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, field_validator
from tutor_core.languages import LANGUAGES, stories_enabled

from ..db import connection
from ..deps import COOKIE, current_user, require_language
from ..emails import validate_email
from ..errors import AppError, validation_error
from .. import policy
from ..policy import POLICY_VERSION
from ..routes.auth import check_password_rules
from ..schemas import LanguageOut, MetaOut, PolicyOut, PreferencesOut, UserOut
from ..security import hash_password, new_salt, verify_password
from ..services import chat_sessions, export, preferences, sessions, users

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


class EmailChange(BaseModel):
    email: str
    password: str

    @field_validator("email")
    @classmethod
    def _email(cls, v):
        return validate_email(v)


class PasswordChange(BaseModel):
    current_password: str
    new_password: str

    @field_validator("new_password")
    @classmethod
    def _pw(cls, v):
        return check_password_rules(v)


class PasswordOnly(BaseModel):
    password: str


def _reauthenticate(request: Request, user: dict, password: str) -> None:
    """Sensitive changes need the current password again, so a hijacked session alone can't take over the account.
    Wrong guesses count toward the same lockout as logging in."""
    state = request.app.state
    state.login_guard.check(user["email"])
    with connection(state.pool) as conn:
        row = users.get_by_email(conn, user["email"])
    if not row or not verify_password(password, row["password_hash"], row["password_salt"]):
        state.login_guard.failure(user["email"])
        raise AppError("wrong_password", "That password is not correct.", 403)
    state.login_guard.success(user["email"])


@router.get("/meta", response_model=MetaOut)
def meta(request: Request):
    """Public: what the privacy page and sign-up form need to show."""
    return {"policy_version": POLICY_VERSION, "privacy_contact": request.app.state.settings.privacy_contact,
            "policy_languages": policy.languages()}


@router.get("/policy", response_model=PolicyOut)
def policy_copy(lang: str | None = Query(default=None, max_length=8)):
    """Public: the privacy policy copy to show for `lang`. Only an approved, current copy is ever served; otherwise
    the English copy, with fallback=true (design 3I)."""
    doc, fallback = policy.select(lang)
    return {"language": doc["language"], "version": doc["version"], "fallback": fallback, "doc": doc}


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
    sent = body.model_fields_set
    changes: dict = {}
    if "active_language" in sent:
        changes["active_language"] = body.active_language
    if "theme" in sent:
        if body.theme is None:
            raise validation_error("theme: cannot be empty")
        changes["theme"] = body.theme
    if "ui_follows_study_language" in sent:
        if body.ui_follows_study_language is None:
            raise validation_error("ui_follows_study_language: must be true or false")
        changes["ui_follows_study_language"] = body.ui_follows_study_language
    if "chat_in_study_language" in sent:
        if body.chat_in_study_language is None:
            raise validation_error("chat_in_study_language: must be true or false")
        changes["chat_in_study_language"] = body.chat_in_study_language
    if "custom_colors" in sent:
        changes["custom_colors"] = body.custom_colors.model_dump() if body.custom_colors else None
    with connection(request.app.state.pool) as conn:
        if changes.get("active_language") is not None and changes["active_language"] not in users.languages_of(conn, user["id"]):
            raise validation_error("active_language: not one of your languages")
        return preferences.save(conn, user["id"], changes)


@router.post("/me/email", response_model=UserOut)
def change_email(body: EmailChange, request: Request, user: dict = Depends(current_user)):
    _reauthenticate(request, user, body.password)
    with connection(request.app.state.pool) as conn:
        updated = users.update_email(conn, user["id"], body.email)
        return users.profile(conn, updated)


@router.post("/me/password", status_code=204)
def change_password(body: PasswordChange, request: Request, response: Response, user: dict = Depends(current_user)):
    """Changes the password and ends every OTHER session (a stolen login must not survive the change)."""
    _reauthenticate(request, user, body.current_password)
    salt = new_salt()
    new_hash = hash_password(body.new_password, salt, request.app.state.settings.bcrypt_rounds)
    with connection(request.app.state.pool) as conn:
        users.set_password(conn, user["id"], new_hash, salt)
        sessions.revoke_others(conn, user["id"], request.state.session_id)


@router.post("/me/delete", status_code=204)
def delete_account(body: PasswordOnly, request: Request, response: Response, user: dict = Depends(current_user)):
    """Permanently deletes the account and everything in it, including the chat history Langflow stores. Needs the
    password. The Langflow side goes first and must be confirmed: if it can't be, nothing is deleted and the
    learner is told to retry, because deleting the account row would leave their chat with no way to find it."""
    _reauthenticate(request, user, body.password)
    state = request.app.state
    with state.ai_gate.exclusive(user["id"]):          # no chat turn may add a session while we clean up
        with connection(state.pool) as conn:
            ids = chat_sessions.list_ids(conn, user["id"])
        if ids:
            state.chat.delete_sessions(ids)
        with connection(state.pool) as conn:
            users.delete_user(conn, user["id"])
    response.delete_cookie(COOKIE, path="/")


@router.get("/me/export")
def export_my_data(request: Request, user: dict = Depends(current_user)):
    with connection(request.app.state.pool) as conn:
        data = export.build(conn, user["id"])
    return JSONResponse(jsonable_encoder(data), headers={"Content-Disposition": 'attachment; filename="language-tutor-my-data.json"'})


@router.post("/me/languages", response_model=UserOut)
def add_language(body: LanguageBody, request: Request, user: dict = Depends(current_user)):
    code = require_language(body.language)
    with connection(request.app.state.pool) as conn:
        users.add_language(conn, user["id"], code)
        return users.profile(conn, user)


@router.get("/languages", response_model=list[LanguageOut])
def languages():
    """Public: the registration form needs it, and it contains nothing private."""
    return [{"code": l.code, "name": l.name, "native": l.native, "tier": l.tier, "stories_enabled": stories_enabled(l.code)}
            for l in LANGUAGES.values()]
