"""The chat tutors the API can talk to: the real Langflow client, and the base for those that keep no conversation."""
from __future__ import annotations

import logging
import urllib.parse

from ...errors import AppError
from .payload import build_run_payload, build_tweaks, with_reply_language
from .reply import ChatResult, find_tool_calls, parse_run_response
from .transport import Transport, TransportError, map_transport_error, urllib_transport

log = logging.getLogger("tutor.langflow")

CLEANUP_FAILED = ("We couldn't remove your chat history just now, so your account has not been deleted. "
                  "Please try again in a moment.")


def cleanup_failed() -> AppError:
    return AppError("chat_cleanup_failed", CLEANUP_FAILED, 503, retry_after=15)


class NoStoredChat:
    """For tutors that keep no conversation anywhere (the stub, or live mode that is switched off): there is
    nothing to delete. If a learner nevertheless has recorded sessions, say so rather than pretend."""
    stores_chat = False
    calls_ai = False            # nothing reaches Groq, so nothing is charged to the token budget

    def health(self) -> dict:
        return {"ok": None, "status": "stub", "detail": None}

    def delete_sessions(self, session_ids) -> None:
        if list(session_ids):
            log.error("cannot delete chat sessions: this deployment has no Langflow client")
            raise cleanup_failed()


class LangflowClient:
    stores_chat = True
    calls_ai = True
    HEALTH_TIMEOUT = 3

    def __init__(self, base_url: str, flow: str, api_key: str, timeout: float = 100.0,
                 tweak_keys=(), transport: Transport | None = None, fallback_timeout: float = 10.0):
        self.base_url = base_url.rstrip("/")
        self.flow = flow
        self.api_key = api_key
        self.timeout = timeout
        self.tweak_keys = tuple(tweak_keys)
        self.fallback_timeout = fallback_timeout
        self._transport = transport or urllib_transport

    def _headers(self) -> dict:
        return {"x-api-key": self.api_key}

    def _stored_messages(self, session_id: str):
        url = f"{self.base_url}/api/v1/monitor/messages?session_id={urllib.parse.quote(session_id, safe='')}"
        try:
            return self._transport("GET", url, None, self._headers(), self.fallback_timeout)
        except TransportError:
            return None                                 # best effort: the run response is the main source

    def run(self, *, user_id: int, language: str, message: str, session_id: str, reply_language: str | None = None, set_ids=None) -> ChatResult:
        payload = build_run_payload(with_reply_language(message, reply_language), session_id, build_tweaks(self.tweak_keys, user_id, language, set_ids))
        url = f"{self.base_url}/api/v1/run/{urllib.parse.quote(self.flow, safe='')}?stream=false"
        try:
            response = self._transport("POST", url, payload, self._headers(), self.timeout)
        except TransportError as e:
            raise map_transport_error(e)
        stored = None if find_tool_calls(response) else self._stored_messages(session_id)
        result = parse_run_response(response, stored)
        if not result.reply.strip() and not result.tool_calls:
            log.warning("langflow returned no reply and no tool calls")
            raise AppError("ai_failed", "The tutor couldn't answer just now. Please try again.", 502)
        return result

    def health(self) -> dict:
        """Is Langflow answering? Only the kind of failure is reported, never its address or our key."""
        try:
            self._transport("GET", f"{self.base_url}/health", None, {}, self.HEALTH_TIMEOUT)
        except TransportError as e:
            log.warning("langflow health check failed: %s", e)
            return {"ok": False, "status": "down", "detail": e.kind}
        return {"ok": True, "status": "up", "detail": None}

    def delete_sessions(self, session_ids) -> None:
        """Remove these sessions' stored messages from Langflow and CHECK they are gone. Every session is tried;
        if any cannot be confirmed empty, one `chat_cleanup_failed` is raised at the end. Account deletion
        waits for this, so a learner is never told their data is gone when it is not."""
        failed = []
        for session_id in session_ids:
            quoted = urllib.parse.quote(session_id, safe="")
            url = f"{self.base_url}/api/v1/monitor/messages/session/{quoted}"
            try:
                try:
                    self._transport("DELETE", url, None, self._headers(), self.fallback_timeout)
                except TransportError as e:
                    # a 404 (nothing there) or a 200 with an odd body may already mean "gone": the check decides
                    if not (e.kind == "badjson" or (e.kind == "http" and e.status == 404)):
                        raise
                remaining = self._transport("GET", f"{self.base_url}/api/v1/monitor/messages?session_id={quoted}",
                                            None, self._headers(), self.fallback_timeout)
                if not isinstance(remaining, list) or remaining:
                    raise TransportError("badjson", None, "session not confirmed empty")
            except TransportError as e:
                log.error("could not delete langflow session %s: %s", session_id, e)
                failed.append(session_id)
        if failed:
            raise cleanup_failed()
