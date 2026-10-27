"""The sensitive parts of an account: email, password, deleting everything, and downloading it. Each asks for the password again."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel, field_validator

from ..db import connection
from ..deps import COOKIE, current_user
from ..emails import validate_email
from ..schemas import UserOut
from ..security import check_password_rules, hash_password, new_salt
from ..services import chat_sessions, export, sessions, users
from ..services.reauth import reauthenticate

router = APIRouter(tags=["account"])


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


@router.post("/me/email", response_model=UserOut)
def change_email(body: EmailChange, request: Request, user: dict = Depends(current_user)):
    reauthenticate(request.app.state, user, body.password)
    with connection(request.app.state.pool) as conn:
        updated = users.update_email(conn, user["id"], body.email)
        return users.profile(conn, updated)


@router.post("/me/password", status_code=204)
def change_password(body: PasswordChange, request: Request, response: Response, user: dict = Depends(current_user)):
    """Changes the password and ends every OTHER session (a stolen login must not survive the change)."""
    reauthenticate(request.app.state, user, body.current_password)
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
    reauthenticate(request.app.state, user, body.password)
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
