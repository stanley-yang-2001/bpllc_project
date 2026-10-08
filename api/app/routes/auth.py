from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, field_validator
from tutor_core.languages import LANGUAGES

from ..db import connection
from ..deps import COOKIE, current_user, session_from_cookie
from ..emails import normalize_email, validate_email
from ..errors import AppError
from ..policy import POLICY_VERSION
from ..schemas import UserOut
from ..security import MAX_PASSWORD_BYTES, create_token, hash_password, verify_password
from ..services import sessions, users

router = APIRouter(prefix="/auth", tags=["auth"])


def check_password_rules(v: str) -> str:
    if len(v) < 8:
        raise ValueError("must be at least 8 characters")
    if len(v.encode()) > MAX_PASSWORD_BYTES:
        raise ValueError(f"must be at most {MAX_PASSWORD_BYTES} bytes")
    return v


class RegisterBody(BaseModel):
    email: str
    password: str
    display_name: str
    language: str = "en"
    accept_privacy: bool                     # required on purpose: a default would skip the validator below

    @field_validator("email")
    @classmethod
    def _email(cls, v: str) -> str:
        return validate_email(v)

    @field_validator("password")
    @classmethod
    def _pw(cls, v: str) -> str:
        return check_password_rules(v)

    @field_validator("display_name")
    @classmethod
    def _dn(cls, v: str) -> str:
        v = " ".join((v or "").split())
        if not 1 <= len(v) <= 40:
            raise ValueError("must be 1-40 characters")
        return v

    @field_validator("language")
    @classmethod
    def _lang(cls, v: str) -> str:
        if v not in LANGUAGES:
            raise ValueError("unsupported language")
        return v

    @field_validator("accept_privacy")
    @classmethod
    def _consent(cls, v: bool) -> bool:
        if v is not True:
            raise ValueError("you must accept the privacy policy to create an account")
        return v


class LoginBody(BaseModel):
    email: str
    password: str


def _start_session(request: Request, response: Response, conn, user_id: int) -> None:
    """Revoke whatever session this browser already had, then start a fresh one (never reuse an id)."""
    s = request.app.state.settings
    old = session_from_cookie(request)
    if old:
        sessions.revoke(conn, old[1])
    sid = sessions.create(conn, user_id, s.jwt_hours)
    response.set_cookie(COOKIE, create_token(user_id, sid, s.jwt_secret, s.jwt_hours), max_age=s.jwt_hours * 3600,
                        httponly=True, samesite="lax", secure=s.cookie_secure, path="/")


@router.post("/register", status_code=201, response_model=UserOut)
def register(body: RegisterBody, request: Request, response: Response):
    s = request.app.state.settings
    pw_hash = hash_password(body.password, s.bcrypt_rounds)
    with connection(request.app.state.pool) as conn:
        user = users.create_user(conn, body.email, pw_hash, body.display_name, body.language, POLICY_VERSION)
        data = users.profile(conn, user)
        _start_session(request, response, conn, user["id"])
    return data


@router.post("/login", response_model=UserOut)
def login(body: LoginBody, request: Request, response: Response):
    state = request.app.state
    email = normalize_email(body.email)
    state.login_guard.check(email)
    with connection(state.pool) as conn:
        user = users.get_by_email(conn, email)
        stored = user["password_hash"] if user else state.dummy_hash      # always spend one bcrypt check
        ok = verify_password(body.password, stored) and user is not None
        if not ok:
            state.login_guard.failure(email)
            raise AppError("login_failed", "Wrong email or password.", 401)
        state.login_guard.success(email)
        data = users.profile(conn, user)
        _start_session(request, response, conn, user["id"])
    return data


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response):
    """Ends this session on the server (not just in the browser), so a copied cookie stops working."""
    parsed = session_from_cookie(request)
    if parsed:
        with connection(request.app.state.pool) as conn:
            sessions.revoke(conn, parsed[1])
    response.delete_cookie(COOKIE, path="/")


@router.post("/logout-all", status_code=204)
def logout_all(request: Request, response: Response, user: dict = Depends(current_user)):
    """Ends every session of this user, on every browser. For a shared or lost computer."""
    with connection(request.app.state.pool) as conn:
        sessions.revoke_all(conn, user["id"])
    response.delete_cookie(COOKIE, path="/")
