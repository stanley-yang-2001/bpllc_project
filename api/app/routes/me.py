from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator
from tutor_core.languages import LANGUAGES, stories_enabled

from ..db import connection
from ..deps import COOKIE, current_user, require_language
from ..emails import validate_email
from ..errors import AppError
from ..policy import POLICY_VERSION
from ..routes.auth import check_password_rules
from ..schemas import LanguageOut, MetaOut, UserOut
from ..security import hash_password, verify_password
from ..services import export, sessions, users

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
    if not row or not verify_password(password, row["password_hash"]):
        state.login_guard.failure(user["email"])
        raise AppError("wrong_password", "That password is not correct.", 403)
    state.login_guard.success(user["email"])


@router.get("/meta", response_model=MetaOut)
def meta(request: Request):
    """Public: what the privacy page and sign-up form need to show."""
    return {"policy_version": POLICY_VERSION, "privacy_contact": request.app.state.settings.privacy_contact}


@router.get("/me", response_model=UserOut)
def me(request: Request, user: dict = Depends(current_user)):
    with connection(request.app.state.pool) as conn:
        return users.profile(conn, user)


@router.patch("/me", response_model=UserOut)
def patch_me(body: ProfilePatch, request: Request, user: dict = Depends(current_user)):
    with connection(request.app.state.pool) as conn:
        updated = users.update_profile(conn, user["id"], body.display_name, body.native_language)
        return users.profile(conn, updated)


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
    new_hash = hash_password(body.new_password, request.app.state.settings.bcrypt_rounds)
    with connection(request.app.state.pool) as conn:
        users.set_password(conn, user["id"], new_hash)
        sessions.revoke_others(conn, user["id"], request.state.session_id)


@router.post("/me/delete", status_code=204)
def delete_account(body: PasswordOnly, request: Request, response: Response, user: dict = Depends(current_user)):
    """Permanently deletes the account and everything in it. Needs the password."""
    _reauthenticate(request, user, body.password)
    with connection(request.app.state.pool) as conn:
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
