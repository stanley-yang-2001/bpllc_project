"""The Groq call, with retry on rate limiting.

Moved from custom_components/story_tool.py (M3). The request is unchanged except that the model comes from GROQ_MODEL
(default: the one Step 10 measured) and the key from GROQ_API_KEY: nothing is hardcoded."""

import json
import os
import time
import urllib.error
import urllib.request
from typing import Callable, Optional


# openai/gpt-oss-20b is a reasoning model: hidden "reasoning" tokens count against max_tokens.
# With max_tokens=400, nearly the whole budget (398 tokens) was spent reasoning, so Groq
# returned finish_reason="length" with content="" — an empty story. A larger budget plus a
# low reasoning effort leaves room for the plan and the passage itself.
DEFAULT_MODEL = "openai/gpt-oss-120b"      # the model Step 10 measured; override with GROQ_MODEL
_MAX_COMPLETION_TOKENS = 4000      # Korean and Japanese use many tokens per word: a 200-word Korean story was cut short at 1500 (24 Oct)
_REASONING_EFFORT = "low"
EFFORTS = ("low", "medium", "high")


def _reasoning_effort(model: str, effort: Optional[str]) -> Optional[str]:
    """What to send as reasoning_effort: only the gpt-oss models take it here, and another model may refuse the whole request, so
    none is sent to it. An effort that is not low, medium or high falls back to low."""
    if "gpt-oss" not in model:
        return None
    return effort if effort in EFFORTS else _REASONING_EFFORT


def call_groq(prompt: str, *, model: Optional[str] = None, effort: Optional[str] = None) -> str:
    """Real Groq call with automatic retry on rate limiting (HTTP 429).

    `model` and `effort` (7 Nov 2026) let one step use another model than the story: the story judge and the grammar review use a
    different model so that a model does not mark its own work, and Groq counts the free tier's tokens per model. Without them the
    request is exactly what it always was: GROQ_MODEL (or the default) and low reasoning effort.

    Same request pattern already proven working in scripts/smoke_test.py — including the
    User-Agent header, without which Cloudflare blocks the request (HTTP 1010).

    Retries up to MAX_RETRIES times on a 429, with a short backoff between attempts, since
    Groq's free-tier TPM limit is a small rolling window that typically clears within a
    second or two — not a long-term block. Non-429 errors are not retried.
    """
    MAX_RETRIES = 3
    BACKOFF_SECONDS = 1.5

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key or api_key == "your-groq-api-key-here":
        raise RuntimeError("GROQ_API_KEY is missing or still the placeholder value.")

    url = "https://api.groq.com/openai/v1/chat/completions"
    name = (model or "").strip() or (os.environ.get("GROQ_MODEL") or "").strip() or DEFAULT_MODEL
    body = {"model": name, "messages": [{"role": "user", "content": prompt}], "max_tokens": _MAX_COMPLETION_TOKENS}
    reasoning = _reasoning_effort(name, effort)
    if reasoning:
        body["reasoning_effort"] = reasoning
    payload = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "language-tutor-story-tool/1.0",
        },
        method="POST",
    )

    last_error = None
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return body["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            if e.code == 429 and attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_SECONDS)
                last_error = RuntimeError(f"Groq API error {e.code}: {detail}")
                continue
            raise RuntimeError(f"Groq API error {e.code}: {detail}") from e

    raise last_error


def make_model_call(model_var: str, effort_var: Optional[str] = None) -> Optional[Callable[[str], str]]:
    """A story function `prompt -> text` for ONE named step (the judge, the grammar review), or None when the model for that step is not
    set. The model name comes from the environment variable `model_var` (GROQ_JUDGE_MODEL, GROQ_AUDIT_MODEL) and the reasoning effort
    from `effort_var`; the story's own model is untouched. None tells the caller to use the story model, or to skip the step."""
    model = (os.environ.get(model_var) or "").strip()
    if not model:
        return None
    effort = ((os.environ.get(effort_var) or "").strip().lower() or None) if effort_var else None

    def call(prompt: str) -> str:
        return call_groq(prompt, model=model, effort=effort)

    call.model = model          # shown in reports: which model graded
    return call


def make_endpoint_call(base_url: str, api_key: str, model: str, *, timeout: int = 60, opener=None):
    """A story function `prompt -> text` that calls ONE OpenAI-compatible address with ONE bearer token (phase 2, design section 10).

    In chat on a learner's own model the address is the API's internal model route and the token is a throwaway one: the learner's
    real key is not here. No reasoning_effort is sent (a model that does not know it may refuse the request)."""
    url = base_url.rstrip("/") + "/chat/completions"
    opener = opener or urllib.request.urlopen

    def call(prompt: str) -> str:
        payload = json.dumps({"model": model, "messages": [{"role": "user", "content": prompt}], "max_tokens": 1500}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, method="POST", headers={
            "Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "User-Agent": "language-tutor-story-tool/1.0"})
        try:
            with opener(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            raise RuntimeError(f"Own model error {e.code}: {e.read().decode('utf-8', errors='replace')[:300]}") from e

    return call
