"""The Groq call, with retry on rate limiting.

Moved from custom_components/story_tool.py (M3). The request is unchanged except that the model comes from GROQ_MODEL
(default: the one Step 10 measured) and the key from GROQ_API_KEY: nothing is hardcoded."""

import json
import time
import urllib.error
import urllib.request


# openai/gpt-oss-20b is a reasoning model: hidden "reasoning" tokens count against max_tokens.
# With max_tokens=400, nearly the whole budget (398 tokens) was spent reasoning, so Groq
# returned finish_reason="length" with content="" — an empty story. A larger budget plus a
# low reasoning effort leaves room for the plan and the passage itself.
DEFAULT_MODEL = "openai/gpt-oss-120b"      # the model Step 10 measured; override with GROQ_MODEL
_MAX_COMPLETION_TOKENS = 4000      # Korean and Japanese use many tokens per word: a 200-word Korean story was cut short at 1500 (24 Oct)
_REASONING_EFFORT = "low"


def call_groq(prompt: str) -> str:
    """Real Groq call with automatic retry on rate limiting (HTTP 429).

    Same request pattern already proven working in scripts/smoke_test.py — including the
    User-Agent header, without which Cloudflare blocks the request (HTTP 1010).

    Retries up to MAX_RETRIES times on a 429, with a short backoff between attempts, since
    Groq's free-tier TPM limit is a small rolling window that typically clears within a
    second or two — not a long-term block. Non-429 errors are not retried.
    """
    import os

    MAX_RETRIES = 3
    BACKOFF_SECONDS = 1.5

    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key or api_key == "your-groq-api-key-here":
        raise RuntimeError("GROQ_API_KEY is missing or still the placeholder value.")

    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = json.dumps(
        {
            "model": (os.environ.get("GROQ_MODEL") or "").strip() or DEFAULT_MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": _MAX_COMPLETION_TOKENS,
            "reasoning_effort": _REASONING_EFFORT,
        }
    ).encode("utf-8")

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
