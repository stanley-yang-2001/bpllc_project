from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from pydantic import Field, BaseModel, field_validator

from ..db import connection
from ..deps import current_user, require_language
from ..schemas import ChatOut
from tutor_core.languages import LANGUAGES

from ..services import chat_sessions, preferences
from ..services.langflow_client import build_session_id

router = APIRouter(prefix="/chat", tags=["chat"])
MAX_CHARS = 2000
# Reserved from the token budget before a turn runs, then replaced by the count Langflow reports. The base is above
# the real turns captured on 14 Oct 2026 (618 for a greeting, 1344 for a story request) because the Agent may call
# the model more than once; the message adds about one token per three characters.
CHAT_BASE_TOKENS = 1500


def estimate_tokens(message: str) -> int:
    return CHAT_BASE_TOKENS + -(-len(message) // 3)


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
    from the body, and the Langflow session id is built from it here."""
    require_language(body.language)
    session_id = build_session_id(user["id"], body.session_id)
    state = request.app.state
    with state.ai_gate.slot(user["id"], tokens=estimate_tokens(body.message) if getattr(state.chat, "calls_ai", False) else 0) as ticket:
        if getattr(state.chat, "stores_chat", False):
            # noted BEFORE the run, so even a failed turn (Langflow may already hold the question) can be deleted later
            with connection(state.pool) as conn:
                chat_sessions.record(conn, user["id"], session_id)
        reply_language = None
        with connection(state.pool) as conn:
            prefs = preferences.get(conn, user["id"])
        if prefs and prefs["chat_in_study_language"]:
            reply_language = LANGUAGES[body.language].name           # the model's own sentences only; tool messages stay as the tool wrote them
        result = state.chat.run(user_id=user["id"], language=body.language, message=body.message, session_id=session_id,
                                reply_language=reply_language, set_ids=body.set_ids)
        ticket.settle(result.tokens)
    return {"reply": result.reply,
            "tool_calls": [{"name": c.name, "args": c.args, "output": c.output, "failed": c.failed} for c in result.tool_calls],
            "session_id": body.session_id}
