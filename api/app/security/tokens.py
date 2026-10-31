"""Session ids and the signed login token."""
from __future__ import annotations

import secrets
import time

import jwt


def new_session_id() -> str:
    return secrets.token_urlsafe(24)


def create_token(user_id: int, session_id: str, secret: str, hours: int) -> str:
    now = int(time.time())
    return jwt.encode({"sub": str(user_id), "jti": session_id, "iat": now, "exp": now + hours * 3600},
                      secret, algorithm="HS256")


def decode_token(token: str, secret: str) -> tuple[int, str] | None:
    """(user_id, session_id) for a well-formed, unexpired, correctly signed token; otherwise None.
    This only proves the token is genuine: the session row must still exist (see services/sessions.py)."""
    try:
        data = jwt.decode(token, secret, algorithms=["HS256"], options={"require": ["sub", "jti", "exp"]})
        return int(data["sub"]), str(data["jti"])
    except (jwt.PyJWTError, KeyError, ValueError):
        return None
