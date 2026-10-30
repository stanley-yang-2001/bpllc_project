"""One chat turn: take a place in the AI gate, note the session, work out the reply language, ask the tutor, settle the tokens.

The route (routes/chat.py) only checks the request and shapes the answer; the rules of a turn live here.
"""
from __future__ import annotations

from typing import Protocol

from tutor_core.languages import LANGUAGES

from ..db import connection
from . import chat_sessions, preferences
from .langflow_client import ChatResult, build_session_id

# Reserved from the token budget before a turn runs, then replaced by the count Langflow reports. The base is above
# the real turns captured on 14 Oct 2026 (618 for a greeting, 1344 for a story request) because the Agent may call
# the model more than once; the message adds about one token per three characters.
CHAT_BASE_TOKENS = 1500


def estimate_tokens(message: str) -> int:
    return CHAT_BASE_TOKENS + -(-len(message) // 3)


class ChatClient(Protocol):
    """What the API needs from a tutor: the stub, the Langflow client and the "not switched on" refusal all have this shape."""
    stores_chat: bool       # the tutor keeps the conversation somewhere (so the session is noted and can be deleted later)
    calls_ai: bool          # a turn reaches the model, so it is charged to the token budget

    def run(self, *, user_id: int, language: str, message: str, session_id: str, reply_language: str | None = None, set_ids=None) -> ChatResult: ...

    def health(self) -> dict: ...

    def delete_sessions(self, session_ids) -> None: ...


def run_turn(state, user_id: int, language: str, message: str, browser_session_id: str, set_ids) -> tuple[ChatResult, str]:
    """Runs one turn as this learner and nobody else. Returns the result and the browser's own session id."""
    chat: ChatClient = state.chat
    session_id = build_session_id(user_id, browser_session_id)
    with state.ai_gate.slot(user_id, tokens=estimate_tokens(message) if chat.calls_ai else 0) as ticket:
        if chat.stores_chat:
            # noted BEFORE the run, so even a failed turn (Langflow may already hold the question) can be deleted later
            with connection(state.pool) as conn:
                chat_sessions.record(conn, user_id, session_id)
        reply_language = None
        with connection(state.pool) as conn:
            prefs = preferences.get(conn, user_id)
        if prefs and prefs["chat_in_study_language"]:
            reply_language = LANGUAGES[language].name           # the model's own sentences only; tool messages stay as the tool wrote them
        result = chat.run(user_id=user_id, language=language, message=message, session_id=session_id,
                          reply_language=reply_language, set_ids=set_ids)
        ticket.settle(result.tokens)
    return result, browser_session_id
