from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import Field, BaseModel, field_validator

from ..deps import current_user, require_language
from ..schemas import ChatOut
from ..services.chat_turn import CHAT_BASE_TOKENS, estimate_tokens, run_turn      # noqa: F401  (re-exported: the tests import estimate_tokens from here)

router = APIRouter(prefix="/chat", tags=["chat"])
MAX_CHARS = 2000


class ChatIn(BaseModel):
    message: str
    language: str
    session_id: str          # 32 random hex characters made by the browser; the user prefix is added here
    set_ids: list[int] | None = Field(default=None, max_length=100)     # the word sets a chat story may use (0 = General); none = all words

    @field_validator("set_ids")
    @classmethod
    def _sets(cls, value):
        if value is not None and any(i < 0 for i in value):
            raise ValueError("Choose the sets from your list.")
        return value

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
    from the body, and the Langflow session id is built from it in the service."""
    require_language(body.language)
    result, session_id = run_turn(request.app.state, user["id"], body.language, body.message, body.session_id, body.set_ids)
    return {"reply": result.reply,
            "tool_calls": [{"name": c.name, "args": c.args, "output": c.output, "failed": c.failed} for c in result.tool_calls],
            "session_id": session_id}
