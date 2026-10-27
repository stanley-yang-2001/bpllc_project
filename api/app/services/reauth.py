"""Sensitive changes need the current password again, so a hijacked session alone can't take over the account.
Wrong guesses count toward the same lockout as logging in."""
from __future__ import annotations

from ..db import connection
from ..errors import AppError
from ..security import verify_password
from . import users


def reauthenticate(state, user: dict, password: str) -> None:
    state.login_guard.check(user["email"])
    with connection(state.pool) as conn:
        row = users.get_by_email(conn, user["email"])
    if not row or not verify_password(password, row["password_hash"], row["password_salt"]):
        state.login_guard.failure(user["email"])
        raise AppError("wrong_password", "That password is not correct.", 403)
    state.login_guard.success(user["email"])
