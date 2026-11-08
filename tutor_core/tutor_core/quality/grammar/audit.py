"""A model reviews a finished text and lists its mistakes (7 Nov 2026). Optional: it costs one model call per text.

The review is only as good as the model, and a model can invent mistakes or miss real ones, so the answer is never taken at its word:

  * each mistake must quote words that really are in the text; one that does not is counted as `unverified` and ignored;
  * a "mistake" whose correction is the same words is ignored; so is one quoting more than eight words;
  * at most twelve mistakes are kept.

Use a model other than the one that wrote the story when you can (GROQ_AUDIT_MODEL, see docs/STORY-SCORING.md): a model that
grades its own writing finds fewer faults in it.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Callable, Sequence

from ...prompts.audit import AUDIT_TYPES, build_audit_prompt
from .base import Hit

MAX_HITS = 12
MAX_QUOTE_WORDS = 8
_KIND = {"spelling": "spelling", "meaning": "meaning"}


@dataclass
class AuditResult:
    ok: bool                                  # the model answered and its answer could be read
    hits: list = field(default_factory=list)
    unverified: int = 0                       # mistakes quoted from words that are not in the text
    error: str = ""

    def as_dict(self) -> dict:
        return {"ok": self.ok, "hits": [h.as_dict() for h in self.hits], "unverified": self.unverified, "error": self.error}


def _json_object(raw: str):
    raw = (raw or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.I)
    first, last = raw.find("{"), raw.rfind("}")
    if first < 0 or last <= first:
        return None
    try:
        return json.loads(raw[first:last + 1])
    except ValueError:
        return None


def _squash(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().casefold()


def parse_audit(raw: str, text: str) -> AuditResult:
    data = _json_object(raw)
    if not isinstance(data, dict) or not isinstance(data.get("errors"), list):
        return AuditResult(False, error="the answer was not the JSON list that was asked for")
    haystack = _squash(text)
    hits, seen, unverified = [], set(), 0
    for item in data["errors"]:
        if not isinstance(item, dict):
            continue
        wrong, right = str(item.get("wrong") or "").strip(), str(item.get("right") or "").strip()
        wrong = wrong.strip("\"'“”‘’«»")
        if not wrong or _squash(wrong) == _squash(right) or len(wrong.split()) > MAX_QUOTE_WORDS:
            continue
        at = text.casefold().find(wrong.casefold())
        if at < 0 and _squash(wrong) not in haystack:
            unverified += 1
            continue
        if _squash(wrong) in seen:
            continue
        seen.add(_squash(wrong))
        kind_name = str(item.get("type") or "").strip().lower()
        why = str(item.get("why") or "").strip()[:80]
        hits.append(Hit("audit", f"audit.{kind_name if kind_name in AUDIT_TYPES else 'other'}", wrong, right, _KIND.get(kind_name, "grammar"),
                        at, at + len(wrong) if at >= 0 else -1, False, why))
        if len(hits) >= MAX_HITS:
            break
    return AuditResult(True, hits, unverified)


def run_audit(call: Callable[[str], str], text: str, language_name: str) -> AuditResult:
    """Ask `call` (a prompt -> text function) to review `text`. Never raises: a failed call is an AuditResult with ok False."""
    try:
        raw = call(build_audit_prompt(language_name, text))
    except Exception as exc:        # noqa: BLE001 - a failed review must not fail the story
        return AuditResult(False, error=f"{type(exc).__name__}: {exc}")
    return parse_audit(raw, text)


class AuditChecker:
    """The model review as a grammar `Checker`. `last` keeps the full result of the latest check (ok, unverified, error)."""
    name = "audit"

    def __init__(self, call: Callable[[str], str]):
        self.call = call
        self.last = AuditResult(False, error="not run")

    def check(self, text: str, language: str, words: Sequence[str] = ()) -> list[Hit]:
        from ...languages import LANGUAGES
        self.last = run_audit(self.call, text, LANGUAGES[language].name if language in LANGUAGES else language)
        return self.last.hits
