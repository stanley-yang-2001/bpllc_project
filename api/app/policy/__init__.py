"""The privacy policy, as data (design 3I). One complete copy per language, kept as its own JSON file next to this module.

The app never translates the policy. It only chooses which copy to show, and only shows a copy that is `approved` and
whose version equals POLICY_VERSION. A draft is invisible, and a copy that was approved before the policy changed
(stale) is withdrawn automatically: English is shown instead, so a wrong or outdated text is never on display.

Bump POLICY_VERSION whenever the policy changes in a way that matters, and update each copy that should stay available
(the English copy first: it is the fallback and the governing copy). Sign-ups record which version the person accepted."""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

POLICY_VERSION = "2026-10-24"
FALLBACK = "en"
_DIR = Path(__file__).parent


@lru_cache(maxsize=1)
def _all() -> dict[str, dict]:
    return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(_DIR.glob("*.json"))}


def reload() -> None:
    """Forget what was read (tests that change the files on disk)."""
    _all.cache_clear()


def shown(doc: dict) -> bool:
    """The safety rule: approved, with an approver and a date, and current."""
    return (doc.get("status") == "approved" and bool(doc.get("approved_by")) and bool(doc.get("approved_on"))
            and doc.get("version") == POLICY_VERSION)


def languages() -> list[str]:
    """Languages with a copy learners may see, English first."""
    ok = [code for code, doc in _all().items() if shown(doc)]
    return sorted(ok, key=lambda c: (c != FALLBACK, c))


def select(lang: str | None) -> tuple[dict, bool]:
    """The copy to show for `lang`, and whether English had to stand in for it."""
    docs = _all()
    if lang and lang in docs and shown(docs[lang]):
        return docs[lang], False
    return docs[FALLBACK], lang is not None and lang != FALLBACK
