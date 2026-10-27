"""The wire to Langflow: one small function that does the HTTP call, and the translation of its failures into messages a learner can
read (never mentioning Langflow, Groq or HTTP; the detail goes to the log)."""
from __future__ import annotations

import json
import logging
import socket
import urllib.error
import urllib.request
from typing import Any, Callable

from ...errors import AppError

log = logging.getLogger("tutor.langflow")

class TransportError(Exception):
    """kind: 'unreachable' (cannot connect), 'timeout', 'http' (status set), 'badjson'."""

    def __init__(self, kind: str, status: int | None = None, detail: str = ""):
        super().__init__(f"{kind} {status or ''} {detail}".strip())
        self.kind, self.status, self.detail = kind, status, detail


def urllib_transport(method: str, url: str, payload, headers: dict, timeout: float):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    hdrs = dict(headers)
    if data is not None:
        hdrs["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            body = response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        raise TransportError("http", e.code, e.read().decode("utf-8", "replace")[:200])
    except (socket.timeout, TimeoutError):
        raise TransportError("timeout")
    except urllib.error.URLError as e:
        if isinstance(e.reason, (socket.timeout, TimeoutError)):
            raise TransportError("timeout")
        raise TransportError("unreachable", None, str(e.reason))
    except OSError as e:
        raise TransportError("unreachable", None, str(e))
    try:
        return json.loads(body) if body else {}
    except ValueError:
        raise TransportError("badjson", 200, body[:100])


def map_transport_error(error: TransportError) -> AppError:
    """Learner-facing messages never mention Langflow, Groq or HTTP; the detail goes to the log."""
    log.warning("langflow call failed: %s", error)
    if error.kind == "unreachable":
        return AppError("langflow_unavailable", "The chat tutor can't be reached right now. The rest of the site still works.", 503)
    if error.kind == "timeout":
        return AppError("ai_failed", "The tutor took too long to answer. Please try again.", 502)
    if error.kind == "http" and error.status == 429:
        return AppError("tutor_busy", "The tutor is busy. Try again in a moment.", 429, retry_after=15)
    if error.kind == "http" and error.status in (401, 403, 404):       # our configuration is wrong
        return AppError("langflow_unavailable", "The chat tutor isn't set up correctly right now.", 503)
    return AppError("ai_failed", "The tutor couldn't answer just now. Please try again.", 502)


Transport = Callable[[str, str, Any, dict, float], Any]
