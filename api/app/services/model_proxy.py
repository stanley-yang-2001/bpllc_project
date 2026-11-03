"""The API's side of chat on a learner's own model (docs/CUSTOM-MODEL-DESIGN.md section 10).

Langflow sends its model request to the API's internal route with a throwaway token; this module turns that into a call to the
learner's real model: the stored model name, the stored (decrypted) key, the SAME address guard as Story Studio with the call
pinned to the address that was checked, no redirects, a timeout and a size cap. The answer is handed back chunk by chunk, so a
streamed answer stays streamed. Whatever goes wrong is turned into a short message that never contains the key."""
from __future__ import annotations

import http.client
import json
import ssl

from .model_address import ModelError, check_base_url
from .model_client import USER_AGENT, _clean
from .pinned_http import _Pinned, _PinnedPlain

TIMEOUT_SECONDS = 60
MAX_REQUEST_BYTES = 1_000_000
MAX_RESPONSE_BYTES = 8_000_000
CHUNK = 8192


class ProxyError(Exception):
    """What the model route answers with: an HTTP status and a message that is safe to show (no key)."""

    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status, self.message = status, message


class Upstream:
    """An open, successful answer from the learner's model."""

    def __init__(self, conn, resp):
        self._conn, self._resp = conn, resp
        self.content_type = resp.getheader("Content-Type") or "application/json"

    def chunks(self):
        sent = 0
        try:
            while True:
                data = self._resp.read1(CHUNK) if hasattr(self._resp, "read1") else self._resp.read(CHUNK)
                if not data:
                    return
                sent += len(data)
                if sent > MAX_RESPONSE_BYTES:
                    return          # the cap: the stream just ends; nothing more is read
                yield data
        except (OSError, http.client.HTTPException, ssl.SSLError):
            return                  # the model server dropped the connection: end the stream
        finally:
            self._conn.close()


def prepare_body(raw: bytes, model: str) -> bytes:
    """The request Langflow made, with the model forced to the learner's saved one (the token only ever means this learner's model)."""
    if len(raw) > MAX_REQUEST_BYTES:
        raise ProxyError(413, "The request to the model was too large.")
    try:
        body = json.loads(raw.decode("utf-8"))
    except ValueError:
        raise ProxyError(400, "The request to the model was not valid JSON.")
    if not isinstance(body, dict) or not isinstance(body.get("messages"), list):
        raise ProxyError(400, "The request to the model was not an OpenAI-style chat request.")
    body["model"] = model
    return json.dumps(body).encode("utf-8")


def _upstream_message(status: int, data: bytes, key: str) -> str:
    detail = ""
    try:
        err = json.loads(data.decode("utf-8", "replace")).get("error")
        detail = err.get("message", "") if isinstance(err, dict) else str(err or "")
    except (ValueError, AttributeError):
        pass
    hint = " Check the key." if status in (401, 403) else (" Check the model name." if status == 404 else "")
    return f"The model server answered {status}.{hint} {_clean(detail, key)}".strip()


def open_upstream(model: str, base_url: str, api_key: str, raw_body: bytes, *, allow_private: bool = False,
                  resolver=None, connection_factory=None) -> Upstream:
    try:
        scheme, host, port, path, ip = check_base_url(base_url, allow_private, resolver)
    except ModelError as e:
        raise ProxyError(502, str(e))
    body = prepare_body(raw_body, model)
    make = connection_factory or (_Pinned if scheme == "https" else _PinnedPlain)
    conn = make(host, ip, port, TIMEOUT_SECONDS)
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        conn.request("POST", f"{path}/chat/completions", body, headers)
        resp = conn.getresponse()
    except (OSError, http.client.HTTPException, ssl.SSLError) as e:
        conn.close()
        raise ProxyError(502, f"The model server did not answer ({_clean(type(e).__name__, api_key)}).")
    if 300 <= resp.status < 400:
        conn.close()
        raise ProxyError(502, "The model server tried to redirect, which is not allowed. Use its direct address.")
    if resp.status != 200:
        try:
            data = resp.read(65536)
        except (OSError, http.client.HTTPException, ssl.SSLError):
            data = b""
        finally:
            conn.close()
        raise ProxyError(429 if resp.status == 429 else (resp.status if 400 <= resp.status < 500 else 502), _upstream_message(resp.status, data, api_key))
    return Upstream(conn, resp)
