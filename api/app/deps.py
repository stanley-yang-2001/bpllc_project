from __future__ import annotations

from fastapi import Request
from tutor_core.languages import LANGUAGES

from .db import connection
from .errors import AppError, unauthorized, validation_error
from .security import decode_token
from .services import sessions

COOKIE = "tutor_session"
EXPECTED_USER_HEADER = "x-expected-user"


def session_from_cookie(request: Request) -> tuple[int, str] | None:
    token = request.cookies.get(COOKIE)
    return decode_token(token, request.app.state.settings.jwt_secret) if token else None


def current_user(request: Request) -> dict:
    """The logged-in user. Needs a genuine token AND a live session row for exactly that user.

    A browser shares one cookie across all tabs. If another person logs in on a second tab, this tab's page
    still shows the first person's data. The page therefore sends the id of the user it is showing
    (X-Expected-User); if the cookie now belongs to someone else the request is refused instead of being
    quietly executed as the wrong person."""
    parsed = session_from_cookie(request)
    if parsed is None:
        raise unauthorized()
    user_id, session_id = parsed
    with connection(request.app.state.pool) as conn:
        user = sessions.user_for(conn, session_id, user_id)
    if not user:
        raise unauthorized()
    expected = request.headers.get(EXPECTED_USER_HEADER)
    if expected is not None and expected != str(user["id"]):
        raise AppError("session_changed", "You are signed in as a different user in another tab.", 401)
    request.state.session_id = session_id
    return user


def pool_of(request: Request):
    return request.app.state.pool


def require_language(code: str) -> str:
    if code not in LANGUAGES:
        raise validation_error(f"Unsupported language '{code}'.")
    return code
