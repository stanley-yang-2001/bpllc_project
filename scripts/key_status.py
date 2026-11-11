#!/usr/bin/env python3
"""What is left on each Groq key? (11 Nov 2026) One tiny call per key and model; reads Groq's rate-limit headers; writes key_status.json for the
test-details page (open the page, Load key status). Keys are never printed or written, only the variable names.

  docker compose exec langflow python /app/scripts/key_status.py --out /app/scripts/key_status.json

Each call asks for 1 token and costs one request of the day's allowance. Groq's headers show the per-minute token limit and the day's request
limit; the day's TOKEN limit is not in the headers, so it is read from the message of a refused call when a key is already at its limit."""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path[:0] = [str(Path(__file__).resolve().parent.parent / "tutor_core")]
from tutor_core import groq, key_pool  # noqa: E402

URL = "https://api.groq.com/openai/v1/chat/completions"
FAMILIES = [("GROQ_API_KEY", "GROQ_MODEL", "story writer and gpt reviewer"), ("GROQ_QWEN_API_KEY", "GROQ_QWEN_MODEL", "qwen reviewer"),
            ("GROQ_JUDGE_API_KEY", "GROQ_JUDGE_MODEL", "judge"), ("GROQ_AUDIT_API_KEY", "GROQ_AUDIT_MODEL", "grammar review")]
HEADERS = {"limit_requests": "x-ratelimit-limit-requests", "remaining_requests": "x-ratelimit-remaining-requests", "reset_requests": "x-ratelimit-reset-requests",
           "limit_tokens": "x-ratelimit-limit-tokens", "remaining_tokens": "x-ratelimit-remaining-tokens", "reset_tokens": "x-ratelimit-reset-tokens"}
KIND = re.compile(r"\((TPM|TPD|RPM|RPD)\)", re.I)
LIMIT = re.compile(r"Limit\s+(\d+),\s*Used\s+(\d+)", re.I)


def limit_info(text: str) -> dict:
    """Which limit a refusal names (TPM per minute, TPD per day, RPM, RPD) and its numbers, from Groq's message."""
    kind, nums, hint = KIND.search(text or ""), LIMIT.search(text or ""), re.search(r"try again in\s+([\dhms.]+)", text or "", re.I)
    return {"kind": kind.group(1).upper() if kind else None, "limit": int(nums.group(1)) if nums else None,
            "used": int(nums.group(2)) if nums else None, "try_again_in": hint.group(1) if hint else None}


def number(value):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def probe(var, model, opener=urllib.request.urlopen, environ=None) -> dict:
    """One 1-token call with the key named by `var` (None = GROQ_API_KEY). Never raises."""
    environ = os.environ if environ is None else environ
    key = (environ.get(var or "GROQ_API_KEY") or "").strip()
    out = {"var": var or "GROQ_API_KEY", "model": model, "ok": False, "http": None, "error": None, **{k: None for k in HEADERS}, "refused": None}
    if not key:
        out["error"] = "not set"
        return out
    body = json.dumps({"model": model, "messages": [{"role": "user", "content": "hi"}], "max_tokens": 1}).encode()
    req = urllib.request.Request(URL, data=body, method="POST", headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                                                                         "User-Agent": "language-tutor-story-tool/1.0"})
    try:
        with opener(req, timeout=30) as resp:
            headers, out["http"], out["ok"] = resp.headers, resp.status, True
    except urllib.error.HTTPError as e:
        headers, out["http"] = e.headers, e.code
        detail = e.read().decode("utf-8", errors="replace")
        out["error"] = detail[:300]
        out["refused"] = limit_info(detail) if e.code == 429 else None
    except Exception as e:      # noqa: BLE001 - a network problem is a result, not a crash
        out["error"] = f"{type(e).__name__}: {e}"[:300]
        return out
    for name, header in HEADERS.items():
        value = headers.get(header)
        out[name] = number(value) if name.startswith(("limit", "remaining")) else value
    return out


def main(argv=None, opener=urllib.request.urlopen, environ=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="key_status.json")
    args = ap.parse_args(argv)
    environ = os.environ if environ is None else environ
    rows = []
    for base, model_var, role in FAMILIES:
        model = (environ.get(model_var) or "").strip() or ((environ.get("GROQ_MODEL") or groq.DEFAULT_MODEL) if base == "GROQ_API_KEY" else "")
        if not model:
            print(f"{base}: {model_var} is not set, skipped")
            continue
        for var in key_pool.key_vars(base, environ):
            row = probe(var, model, opener, environ)
            row.update(family=base, role=role)
            rows.append(row)
            left = f"{row['remaining_tokens']}/{row['limit_tokens']} tokens a minute, {row['remaining_requests']}/{row['limit_requests']} requests a day" if row["ok"] else (row["error"] or "")[:90]
            print(f"{row['var']:22} {model:28} {'ok     ' if row['ok'] else 'REFUSED'} {left}")
    Path(args.out).write_text(json.dumps({"checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "keys": rows}, indent=1), encoding="utf-8")
    print(f"written to {args.out}")
    return rows


if __name__ == "__main__":
    main()
