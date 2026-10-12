from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, field_validator

from ..deps import current_user, require_language
from ..schemas import ChatOut
from ..services.langflow_client import build_session_id

router = APIRouter(prefix="/chat", tags=["chat"])
MAX_CHARS = 2000


class ChatIn(BaseModel):
    message: str
    language: str
    session_id: str          # 32 random hex characters made by the browser; the user prefix is added here

    @field_validator("message")
    @classmethod
    def _message(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Type a message first.")
        if len(value) > MAX_CHARS:
            raise ValueError(f"Keep messages under {MAX_CHARS} characters.")
        return value


@router.post("", response_model=ChatOut)
def chat(body: ChatIn, request: Request, user: dict = Depends(current_user)):
    """One chat turn. Made as the logged-in user and nobody else: the id comes from the session cookie, never
    from the body, and the Langflow session id is built from it here."""
    require_language(body.language)
    session_id = build_session_id(user["id"], body.session_id)
    state = request.app.state
    with state.ai_gate.slot(user["id"]):
        result = state.chat.run(user_id=user["id"], language=body.language, message=body.message, session_id=session_id)
    return {"reply": result.reply,
            "tool_calls": [{"name": c.name, "args": c.args, "output": c.output, "failed": c.failed} for c in result.tool_calls],
            "session_id": body.session_id}
