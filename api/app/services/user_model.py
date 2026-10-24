"""Calling a learner's own OpenAI-compatible model (docs/CUSTOM-MODEL-DESIGN.md, sections 3 and 5).

The server calls an address a learner typed, so the address is checked first (SSRF): https only (plain http only when private
addresses are allowed), no credentials in the URL, and the name must resolve only to public addresses. The call is then made to
the address that was checked (not looked up again), without following redirects, with a timeout and a size cap. Errors are
shown with the key removed. The model's answer goes through the same story pipeline and quality check as the shared model's."""
from __future__ import annotations

import http.client
import ipaddress
import json
import socket
import ssl
import time
from collections import defaultdict, deque
from urllib.parse import urlsplit

TIMEOUT_SECONDS = 30
MAX_RESPONSE_BYTES = 1_000_000
MAX_TOKENS = 1500
USER_AGENT = "language-tutor-user-model/1.0"


class ModelError(RuntimeError):
    """A failure with a message that is safe to show the learner (never contains their key)."""


def check_base_url(url: str, allow_private: bool = False, resolver=None):
    """Returns (scheme, host, port, path, ip) for a usable address, or raises ModelError saying why not."""
    url = (url or "").strip()
    try:
        parts = urlsplit(url)
        port = parts.port
    except ValueError:
        raise ModelError("That model address is not a valid web address.")
    if parts.scheme not in ("https", "http") or not parts.hostname:
        raise ModelError("The model address must start with https:// and name a server.")
    if parts.scheme == "http" and not allow_private:
        raise ModelError("The model address must start with https://.")
    if parts.username or parts.password:
        raise ModelError("Leave the user name and password out of the address; put the key in the key box.")
    if parts.query or parts.fragment:
        raise ModelError("The model address should be the base address only, for example https://api.openai.com/v1.")
    host = parts.hostname
    resolver = resolver or socket.getaddrinfo
    try:
        infos = resolver(host, port or (443 if parts.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError:
        raise ModelError("That server name could not be found.")
    ips = []
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if getattr(ip, "ipv4_mapped", None):
            ip = ip.ipv4_mapped
        ips.append(ip)
    if not ips:
        raise ModelError("That server name could not be found.")
    if not allow_private:
        for ip in ips:
            if not ip.is_global or ip.is_multicast:
                raise ModelError("That address points inside a private network, which this site will not call.")
    return parts.scheme, host, port or (443 if parts.scheme == "https" else 80), parts.path.rstrip("/"), str(ips[0])


class _Pinned(http.client.HTTPSConnection):
    """HTTPS to an IP that was already checked, while the certificate and Host header are for the real name."""

    def __init__(self, host, ip, port, timeout):
        super().__init__(host, port, timeout=timeout, context=ssl.create_default_context())
        self._ip = ip

    def connect(self):
        sock = socket.create_connection((self._ip, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


class _PinnedPlain(http.client.HTTPConnection):
    def __init__(self, host, ip, port, timeout):
        super().__init__(host, port, timeout=timeout)
        self._ip = ip

    def connect(self):
        self.sock = socket.create_connection((self._ip, self.port), self.timeout)


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


class RequestLimiter:
    """At most `limit` calls per learner per `window` seconds (decision 4: a learner on their own key skips the shared token
    budget but not a request limit)."""

    def __init__(self, limit: int = 10, window: float = 60.0, clock=time.monotonic):
        self.limit, self.window, self.clock = limit, window, clock
        self._hits: dict = defaultdict(deque)

    def allow(self, user_id: int) -> bool:
        now, hits = self.clock(), self._hits[user_id]
        while hits and now - hits[0] > self.window:
            hits.popleft()
        if len(hits) >= self.limit:
            return False
        hits.append(now)
        return True
