"""What a run says about itself (14 Nov 2026).

The 13 Nov Kaggle run of the overnight set ended after one story and the JSON that came back could not say why: no log, no reason, nothing that told a complete
run from a cut one. This module is what makes the files self-explaining, so the JSON (and the .status.txt next to it) is enough to know what happened:

    scrub / describe_error / classify   a model error as one readable line, without the organisation id or a key
    completeness                        done and missing per method, what runs next, how many reviews worked and why the others did not
    status_text                         the same as plain text, written next to the JSON on every save
    RunLog                              the lines a run prints, with the time, kept (last 400) in the JSON
    run_info                            when, what command, which commit, which STORY_*/model settings (never a key)
    preflight                           one tiny call per model before the run, so a wrong model id, a refused key or a used-up daily limit is found in the first minute
"""
from __future__ import annotations

import collections
import os
import platform
import re
import subprocess
import sys
import time
from typing import Callable, Optional

_ORG = re.compile(r"org_[A-Za-z0-9]+")
_KEY = re.compile(r"\b(?:gsk|sk|xai|hf)_[A-Za-z0-9_\-]{8,}")
_BEARER = re.compile(r"(?i)bearer\s+[A-Za-z0-9._\-]{8,}")
_LIMIT = re.compile(r"on\s+(requests|tokens)\s+per\s+(second|minute|hour|day)\s*\((\w+)\):\s*Limit\s+(\d+),\s*Used\s+(\d+),\s*Requested\s+(\d+)", re.I)
_MODEL = re.compile(r"for model\s+[`'\"]?([\w./:\-]+)[`'\"]?", re.I)
_RETRY = re.compile(r"try again in\s+((?:\d+(?:\.\d+)?\s*(?:ms|h|m|s)\s*)+)", re.I)
_UNIT = {"h": 3600.0, "m": 60.0, "s": 1.0, "ms": 0.001}
LONG_WAIT_SECONDS = 180.0           # the same as patient(): a hint longer than this is a daily limit, not worth waiting for
PING = "Reply with the single word OK."
FATAL = {"rate_limit_long", "key", "model", "bad_request"}          # the run cannot work (or stops at once); the others are worth trying


def scrub(text) -> str:
    """The text without anything that identifies the account: the organisation id, an API key, a bearer token."""
    return _BEARER.sub("Bearer ***", _KEY.sub("***", _ORG.sub("org_***", str(text))))


def _retry_seconds(text: str) -> Optional[float]:
    found = _RETRY.search(text)
    if not found:
        return None
    return sum(float(n) * _UNIT[u.lower()] for n, u in re.findall(r"(\d+(?:\.\d+)?)\s*(ms|h|m|s)", found.group(1), re.I))


def classify(error) -> str:
    """rate_limit_long (a daily limit or a hint over three minutes), rate_limit, key, model, bad_request, timeout, server or other."""
    low = scrub(error).casefold()
    if re.search(r"\b429\b", low) or "rate limit" in low or "rate_limit" in low:
        seconds = _retry_seconds(low)
        limit = _LIMIT.search(scrub(error))
        daily = bool(limit and limit.group(2).lower() in ("day", "hour")) or (seconds is not None and seconds > LONG_WAIT_SECONDS)
        return "rate_limit_long" if daily else "rate_limit"
    if re.search(r"\b40[13]\b", low) or "invalid api key" in low or "invalid_api_key" in low or "unauthorized" in low or "permission" in low:
        return "key"
    if re.search(r"\b404\b", low) or "model_not_found" in low or "does not exist" in low or "decommissioned" in low or "not found" in low:
        return "model"
    if re.search(r"\b400\b", low) or "bad request" in low or "invalid_request" in low:
        return "bad_request"
    if "timed out" in low or "timeout" in low:
        return "timeout"
    if re.search(r"\b5\d\d\b", low) or "overloaded" in low or "unavailable" in low:
        return "server"
    return "other"


def _fmt_seconds(seconds: float) -> str:
    seconds = int(round(seconds))
    return f"{seconds // 3600}h{seconds % 3600 // 60:02d}m" if seconds >= 3600 else f"{seconds // 60}m{seconds % 60:02d}s" if seconds >= 60 else f"{seconds}s"


def describe_error(error) -> str:
    """One readable line for a model error: the kind, and the numbers that tell a daily limit from a bad key from a wrong model id."""
    text = scrub(error)
    kind = classify(text)
    model = _MODEL.search(text)
    on = f" on {model.group(1)}" if model else ""
    if kind in ("rate_limit", "rate_limit_long"):
        limit, seconds = _LIMIT.search(text), _retry_seconds(text)
        what = ""
        if limit:
            noun = "token" if limit.group(1).lower() == "tokens" else "request"
            what = f" ({noun}s per {limit.group(2).lower()}: used {int(limit.group(5)):,} of {int(limit.group(4)):,}, this call needs {int(limit.group(6)):,})"
        retry = f", retry in {_fmt_seconds(seconds)}" if seconds is not None else ""
        return ("daily limit" if kind == "rate_limit_long" else "rate limit") + on + what + retry
    label = {"key": "key refused (401/403): check the key", "model": "model not found (404): check the model id", "bad_request": "request refused (400)",
             "timeout": "timed out", "server": "Groq server error (5xx)"}.get(kind)
    detail = re.sub(r"\s+", " ", text).strip()[:140]
    return f"{label}{on}: {detail}" if label else detail


# --- completeness ------------------------------------------------------------------------------------------------------------------------------------------

def completeness(data: dict) -> dict:
    """What is done and what is not. `complete` only when every method has a story for every request; `next` is the first one missing (where a killed run was)."""
    requests, variants = data.get("requests") or [], data.get("variants") or []
    results = data.get("results") or {}
    per, nxt = [], None
    for v in variants:
        missing = [r["id"] for r in requests if v["name"] not in (results.get(r["id"]) or {})]
        failed = [r["id"] for r in requests if (results.get(r["id"]) or {}).get(v["name"], {}).get("ok") is False]
        per.append({"name": v["name"], "label": v.get("label", v["name"]), "done": len(requests) - len(missing), "total": len(requests), "missing": missing, "failed": failed})
    for r in requests:
        for v in variants:
            if v["name"] not in (results.get(r["id"]) or {}):
                nxt = nxt or (r["id"], v["name"])
    done, total = sum(p["done"] for p in per), sum(p["total"] for p in per)
    reviews: dict = {}
    for row in results.values():
        for entry in row.values():
            if not entry.get("ok"):
                continue
            for label, audit in (entry.get("audits") or {}).items():
                slot = reviews.setdefault(label, {"asked": 0, "audit_ok": 0, "rating_ok": 0, "why": collections.Counter()})
                slot["asked"] += 1
                rating = audit.get("naturalness")
                slot["audit_ok"] += bool(audit.get("ok"))
                slot["rating_ok"] += bool(rating and rating.get("ok"))
                if not audit.get("ok") and audit.get("error"):
                    slot["why"]["review: " + describe_error(audit["error"])[:90]] += 1
                if rating is not None and not rating.get("ok") and rating.get("error"):
                    slot["why"]["rating: " + describe_error(rating["error"])[:90]] += 1
    for slot in reviews.values():
        slot["why"] = dict(slot["why"].most_common(3))
    return {"requests": len(requests), "variants": per, "done": done, "total": total, "complete": bool(total) and done == total, "next": nxt, "reviews": reviews,
            "stopped": (data.get("meta") or {}).get("stopped")}


def state(data: dict) -> str:
    c = completeness(data)
    if c["complete"]:
        return "FINISHED"
    return "STOPPED" if c["stopped"] else "INCOMPLETE (no stop reason: the process was probably killed)"


def status_text(data: dict) -> str:
    """The plain-text version of the above, for the .status.txt next to the JSON: readable without opening anything."""
    c, meta = completeness(data), data.get("meta") or {}
    run = meta.get("run") or {}
    lines = [f"State: {state(data)}", f"Done: {c['done']} of {c['total']} stories (" + ", ".join(f"{p['name']} {p['done']}/{p['total']}" for p in c["variants"]) + ")"]
    if c["stopped"]:
        lines.append(f"Why it stopped: {c['stopped']}")
    if c["next"]:
        lines.append(f"Next to make: {c['next'][0]} with {c['next'][1]}")
    failed = [f"{p['name']}: {', '.join(p['failed'])}" for p in c["variants"] if p["failed"]]
    if failed:
        lines.append("Stories that failed to be written: " + "; ".join(failed))
    for label, slot in c["reviews"].items():
        why = ("; " + "; ".join(f"{k} x{n}" for k, n in slot["why"].items())) if slot["why"] else ""
        lines.append(f"Reviewer {label}: {slot['audit_ok']} of {slot['asked']} reviews and {slot['rating_ok']} ratings worked{why}")
    pre = [p for p in (meta.get("preflight") or []) if not p.get("ok")]
    if pre:
        lines.append("Preflight problems: " + "; ".join(f"{p['channel']}: {p['why']}" for p in pre))
    if run.get("started"):
        lines.append(f"Started {run.get('started')}, last saved {run.get('last_save')} (score version {meta.get('score_version', '?')}, commit {run.get('commit') or '?'})")
        if run.get("command"):
            lines.append(f"Command: {run['command']}")
    if not c["complete"]:
        lines.append("To continue: the same command with --resume <this run's .json>.")
    return "\n".join(lines) + "\n"


# --- the run's own record -----------------------------------------------------------------------------------------------------------------------------------

def now_iso() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())


class RunLog:
    """`print` that also remembers: every line gets the time and loses anything that identifies the account. The last `keep` lines go into the JSON."""

    def __init__(self, keep: int = 400, out: Callable = print):
        self.lines = collections.deque(maxlen=keep)
        self.out = out

    def __call__(self, *parts, **_):
        text = " ".join(str(p) for p in parts)
        self.out(text)
        stamp = time.strftime("%H:%M:%S")
        for line in scrub(text).splitlines() or [""]:
            self.lines.append(f"{stamp} {line}")

    def tail(self) -> list:
        return list(self.lines)


def _commit() -> Optional[str]:
    try:
        here = os.path.dirname(os.path.abspath(__file__))
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=here, capture_output=True, text=True, timeout=3).stdout.strip() or None
    except Exception:           # noqa: BLE001 - a missing git or a copied folder is normal on a notebook
        return None


def run_info(argv, environ=None) -> dict:
    """Facts that help to read a result later: when, the command, where (Python, platform, commit) and the STORY_* and model settings. Never a key."""
    environ = os.environ if environ is None else environ
    keep = {k: v for k, v in sorted(environ.items()) if k.startswith("STORY_") or (k.startswith("GROQ_") and k.endswith(("_MODEL", "_EFFORT")))}
    return {"started": now_iso(), "last_save": now_iso(), "command": scrub(" ".join(str(a) for a in argv)), "python": platform.python_version(), "platform": platform.platform(),
            "commit": _commit(), "settings": keep, "kaggle": environ.get("KAGGLE_KERNEL_RUN_TYPE") or None}


# --- preflight ----------------------------------------------------------------------------------------------------------------------------------------------

def preflight(channels: dict, say: Callable = print) -> list:
    """One tiny call on each model the run will use. `channels` maps a label to a Channel. A model reached by two labels is asked once.
    Returns [{"channel", "model", "ok", "kind", "why", "seconds"}]; the call goes through the same pacing and key rotation as the run."""
    seen, out = {}, []
    for label, channel in channels.items():
        if id(channel) in seen:
            seen[id(channel)]["channel"] += f" + {label}"
            continue
        started = time.monotonic()
        row = {"channel": label, "model": getattr(getattr(channel.meter, "call", None), "model", None), "ok": True, "kind": None, "why": "", "seconds": 0.0}
        try:
            channel.call(PING)
        except Exception as exc:       # noqa: BLE001 - the point is to find out why
            row.update(ok=False, kind=classify(exc), why=describe_error(exc))
        row["seconds"] = round(time.monotonic() - started, 1)
        channel.reset()                 # the meter belongs to the stories, not to this call
        seen[id(channel)] = row
        out.append(row)
    for row in out:
        say(f"  preflight {row['channel']}{' (' + row['model'] + ')' if row['model'] else ''}: " + ("ok" if row["ok"] else "FAILED: " + row["why"]))
    return out


def fatal(rows: list) -> list:
    """The preflight failures that mean the run cannot work: a refused key, a wrong model id, a refused request, a limit that will not lift for hours."""
    return [r for r in rows if not r["ok"] and r["kind"] in FATAL]
