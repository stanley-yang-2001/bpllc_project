"""The Groq call, with retry on rate limiting.

Moved from custom_components/story_tool.py (M3). The request is unchanged except that the model comes from GROQ_MODEL
(default: the one Step 10 measured) and the key from GROQ_API_KEY: nothing is hardcoded."""

import json
import os
import re
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


_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)


def _reasoning_effort(model: str, effort: Optional[str]) -> Optional[str]:
    """What to send as reasoning_effort. The gpt-oss models take low, medium or high (anything else means low). Qwen models think out loud
    by default, which would eat the token budget and put the thinking into the story, so they get "none" unless "default" is asked for.
    Any other model gets nothing: it may refuse the whole request."""
    name = model.casefold()
    if "gpt-oss" in name:
        return effort if effort in EFFORTS else _REASONING_EFFORT
    if "qwen" in name:
        return "default" if effort == "default" else "none"
    return None


PLACEHOLDER_KEY = "your-groq-api-key-here"


def key_for(key_var: Optional[str] = None) -> str:
    """The Groq key for a step: the one in `key_var` when that is set, else GROQ_API_KEY."""
    own = (os.environ.get(key_var) or "").strip() if key_var else ""
    return own or os.environ.get("GROQ_API_KEY", "")


def key_label(key_var: Optional[str] = None) -> str:
    """Which key a step uses, safe to print: the variable's name and the last 4 characters (never the key)."""
    var = key_var if key_var and (os.environ.get(key_var) or "").strip() else "GROQ_API_KEY"
    key = key_for(key_var)
    return f"{var} (...{key[-4:]})" if len(key) >= 8 else f"{var} (not set)"


def _clean(content) -> str:
    """The reply without a <think>...</think> block (a model that thinks aloud puts it in front of the answer)."""
    return _THINK.sub("", content or "").strip() if content and "think>" in content.lower() else (content or "")


def call_groq(prompt: str, *, model: Optional[str] = None, effort: Optional[str] = None, key_var: Optional[str] = None) -> str:
    """Real Groq call with automatic retry on rate limiting (HTTP 429).

    `model` and `effort` (7 Nov 2026) let one step use another model than the story: the story judge and the grammar review use a
    different model so that a model does not mark its own work, and Groq counts the free tier's tokens per model. Without them the
    request is exactly what it always was: GROQ_MODEL (or the default) and low reasoning effort.

    `key_var` (8 Nov 2026) names an environment variable that holds ANOTHER Groq key for this step (GROQ_JUDGE_API_KEY, GROQ_AUDIT_API_KEY,
    GROQ_QWEN_API_KEY): a second account has its own free-tier allowance. Empty or unset means GROQ_API_KEY, exactly as before.

    Same request pattern already proven working in scripts/smoke_test.py — including the
    User-Agent header, without which Cloudflare blocks the request (HTTP 1010).

    Retries up to MAX_RETRIES times on a 429, with a short backoff between attempts, since
    Groq's free-tier TPM limit is a small rolling window that typically clears within a
    second or two — not a long-term block. Non-429 errors are not retried.
    """
    MAX_RETRIES = 3
    BACKOFF_SECONDS = 1.5

    api_key = key_for(key_var)
    if not api_key or api_key == PLACEHOLDER_KEY:
        raise RuntimeError(f"{key_var if key_var and (os.environ.get(key_var) or '').strip() else 'GROQ_API_KEY'} is missing or still the placeholder value.")

    url = "https://api.groq.com/openai/v1/chat/completions"
    name = (model or "").strip() or (os.environ.get("GROQ_MODEL") or "").strip() or DEFAULT_MODEL
    request_body = {"model": name, "messages": [{"role": "user", "content": prompt}], "max_tokens": _MAX_COMPLETION_TOKENS}
    reasoning = _reasoning_effort(name, effort)
    if reasoning:
        request_body["reasoning_effort"] = reasoning
    payload = json.dumps(request_body).encode("utf-8")

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
    dropped_effort = False
    for attempt in range(MAX_RETRIES):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                body = json.loads(resp.read().decode("utf-8"))
                return _clean(body["choices"][0]["message"]["content"])
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", errors="replace")
            if e.code == 400 and "reasoning" in detail.lower() and reasoning and not dropped_effort:
                # a model that does not know this reasoning_effort value: ask again without it rather than fail the story
                dropped_effort = True
                request_body.pop("reasoning_effort", None)
                req = urllib.request.Request(url, data=json.dumps(request_body).encode("utf-8"), headers=dict(req.header_items()), method="POST")
                continue
            if e.code == 429 and attempt < MAX_RETRIES - 1:
                time.sleep(BACKOFF_SECONDS)
                last_error = RuntimeError(f"Groq API error {e.code}: {detail}")
                continue
            raise RuntimeError(f"Groq API error {e.code}: {detail}") from e

    raise last_error


def make_model_call(model_var: str, effort_var: Optional[str] = None, key_var: Optional[str] = None, pool=None) -> Optional[Callable[[str], str]]:
    """A story function `prompt -> text` for ONE named step (the judge, the grammar review), or None when the model for that step is not
    set. The model name comes from the environment variable `model_var` (GROQ_JUDGE_MODEL, GROQ_AUDIT_MODEL) and the reasoning effort
    from `effort_var`; the story's own model is untouched. None tells the caller to use the story model, or to skip the step."""
    model = (os.environ.get(model_var) or "").strip()
    if not model:
        return None
    effort = ((os.environ.get(effort_var) or "").strip().lower() or None) if effort_var else None

    def call(prompt: str) -> str:
        return call_groq(prompt, model=model, effort=effort, key_var=key_var)

    if pool is not None:        # the comparison runs only: more keys for the same model (key_pool.py); the app never passes a pool
        from .key_pool import rotating
        call = rotating(lambda prompt, kv: call_groq(prompt, model=model, effort=effort, key_var=kv), pool)
    call.model = model          # shown in reports: which model graded
    call.key_var = key_var
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
