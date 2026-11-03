from __future__ import annotations

import json
import logging
import queue
import threading

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import Field, BaseModel, field_validator

from ..deps import current_user, require_language
from ..errors import AppError
from ..schemas import ChatOut
from ..services.chat_turn import CHAT_BASE_TOKENS, estimate_tokens, run_turn      # noqa: F401  (re-exported: the tests import estimate_tokens from here)

log = logging.getLogger("tutor.chat")
router = APIRouter(prefix="/chat", tags=["chat"])
NDJSON = "application/x-ndjson"
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


def _payload(result, session_id: str) -> dict:
    return {"reply": result.reply,
            "tool_calls": [{"name": c.name, "args": c.args, "output": c.output, "failed": c.failed} for c in result.tool_calls],
            "session_id": session_id, "notice": result.notice or None}


def _streams(request: Request) -> bool:
    """The page asks for a stream with `Accept: application/x-ndjson`; it gets one only when the operator switched streaming on (CHAT_STREAM=1)
    and the tutor behind the route can stream. Everything else gets the one JSON answer, exactly as before."""
    state = request.app.state
    return NDJSON in request.headers.get("accept", "") and state.settings.chat_stream and getattr(state.chat, "streams", False)


def _stream(state, user_id: int, body: ChatIn) -> StreamingResponse:
    """The turn runs in its own thread and puts events on a queue; the response writes them as lines of JSON:
    {"event": "delta", "text"}, then one {"event": "final", ...the usual answer} or {"event": "error", "status", "error": {code, message, retry_after}}.
    The turn itself is the ordinary run_turn (gate, session note, token settle), so streaming changes how the answer travels and nothing else."""
    events: queue.Queue = queue.Queue()

    def work():
        try:
            result, session_id = run_turn(state, user_id, body.language, body.message, body.session_id, body.set_ids,
                                          on_delta=lambda text: events.put({"event": "delta", "text": text}))
            events.put({"event": "final", **_payload(result, session_id)})
        except AppError as e:
            events.put({"event": "error", "status": e.status, "error": {"code": e.code, "message": e.message, "retry_after": e.retry_after}})
        except Exception:                      # noqa: BLE001  the page must always get an ending
            log.exception("chat stream failed")
            events.put({"event": "error", "status": 500, "error": {"code": "internal_error", "message": "Something went wrong. Please try again.", "retry_after": None}})
        finally:
            events.put(None)

    threading.Thread(target=work, daemon=True).start()

    def lines():
        while True:
            item = events.get()
            if item is None:
                return
            yield json.dumps(item) + "\n"

    return StreamingResponse(lines(), media_type=NDJSON)


@router.post("", response_model=ChatOut)
def chat(body: ChatIn, request: Request, user: dict = Depends(current_user)):
    """One chat turn. Made as the logged-in user and nobody else: the id comes from the session cookie, never
    from the body, and the Langflow session id is built from it in the service."""
    require_language(body.language)
    if _streams(request):
        return _stream(request.app.state, user["id"], body)
    result, session_id = run_turn(request.app.state, user["id"], body.language, body.message, body.session_id, body.set_ids)
    return _payload(result, session_id)
