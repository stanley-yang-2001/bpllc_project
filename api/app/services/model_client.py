"""The chat-completions call to a learner's own model (OpenAI-compatible), and the story function built on it.

The address is checked first (model_address), the call goes to that address (pinned_http) without following redirects, with a
timeout and a size cap. Errors are shown with the key removed."""
from __future__ import annotations

import http.client
import json
import ssl

from .model_address import ModelError, check_base_url
from .pinned_http import _Pinned, _PinnedPlain

TIMEOUT_SECONDS = 30
MAX_RESPONSE_BYTES = 1_000_000
MAX_TOKENS = 1500
USER_AGENT = "language-tutor-user-model/1.0"


def _clean(text: str, key: str) -> str:
    text = (text or "").replace("\n", " ")
    if key:
        text = text.replace(key, "***")
    return text[:200]


def call_model(model: str, base_url: str, api_key: str, prompt: str, *, allow_private: bool = False, max_tokens: int = MAX_TOKENS,
               resolver=None, connection_factory=None) -> str:
    scheme, host, port, path, ip = check_base_url(base_url, allow_private, resolver)
    make = connection_factory or (_Pinned if scheme == "https" else _PinnedPlain)
    conn = make(host, ip, port, TIMEOUT_SECONDS)
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": max_tokens}).encode("utf-8")
    headers = {"Content-Type": "application/json", "User-Agent": USER_AGENT}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        conn.request("POST", f"{path}/chat/completions", body, headers)
        resp = conn.getresponse()
        data = resp.read(MAX_RESPONSE_BYTES + 1)
    except (OSError, http.client.HTTPException, ssl.SSLError) as e:
        raise ModelError(f"The model server did not answer ({_clean(type(e).__name__, api_key)}).")
    finally:
        conn.close()
    if len(data) > MAX_RESPONSE_BYTES:
        raise ModelError("The model's answer was too large.")
    if 300 <= resp.status < 400:
        raise ModelError("The model server tried to redirect, which is not allowed. Use its direct address.")
    if resp.status != 200:
        detail = ""
        try:
            err = json.loads(data.decode("utf-8", "replace")).get("error")
            detail = err.get("message", "") if isinstance(err, dict) else str(err or "")
        except ValueError:
            pass
        hint = " Check the key." if resp.status in (401, 403) else (" Check the model name." if resp.status == 404 else "")
        raise ModelError(f"The model server answered {resp.status}.{hint} {_clean(detail, api_key)}".strip())
    try:
        text = json.loads(data.decode("utf-8"))["choices"][0]["message"]["content"]
    except (ValueError, KeyError, IndexError, TypeError):
        raise ModelError("The model server's answer was not in the expected format (an OpenAI-style chat completion).")
    if not isinstance(text, str):
        raise ModelError("The model server's answer was not in the expected format (an OpenAI-style chat completion).")
    return text


def make_call_fn(model: str, base_url: str, api_key: str, allow_private: bool = False):
    """A story function `prompt -> text` for this learner's model. `calls_ai = False` keeps it out of the shared token budget."""
    def call(prompt: str) -> str:
        try:
            return call_model(model, base_url, api_key, prompt, allow_private=allow_private)
        except ModelError as e:
            call.last_error = str(e)         # the story pipeline turns any exception into "failed"; the route shows this text
            raise
    call.calls_ai = False
    call.last_error = ""
    return call
