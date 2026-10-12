"""Which tutor answers /api/chat: the stub, the real Langflow client, or a polite refusal."""
from __future__ import annotations

import logging

from ..config import Settings
from ..errors import AppError
from .chat_stub import StubChat
from .langflow_client import LangflowClient

log = logging.getLogger("tutor.chat")


class NotReadyChat:
    """Live mode before the operator has confirmed the flow's tools are per-user (LANGFLOW_PER_USER_TOOLS=1).
    Running the flow now would let the shared word list leak between learners, so nothing is sent."""

    def run(self, **_kwargs):
        raise AppError("langflow_unavailable", "The chat tutor isn't switched on yet.", 503)


def make_chat_client(settings: Settings, get_pool):
    if settings.ai_mode == "stub":
        return StubChat(get_pool)
    if not settings.langflow_per_user_tools:
        log.warning("Chat is OFF: AI_MODE=live but LANGFLOW_PER_USER_TOOLS is not 1 (the flow's tools are not yet "
                    "confirmed per-user). Set AI_MODE=stub to develop, or finish M0/M3 and set the flag.")
        return NotReadyChat()
    return LangflowClient(settings.langflow_url, settings.langflow_flow, settings.langflow_api_key,
                          settings.langflow_timeout, settings.langflow_tweak_keys)
