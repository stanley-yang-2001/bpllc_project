"""LanguageTool as a grammar source (7 Nov 2026). Optional: you run the server, nothing here installs or starts it.

LanguageTool is a rule-based checker with thousands of hand-written rules (a 2025 count: Spanish 1644, French 6984, German 5224,
Portuguese 2919, Chinese 1863, Japanese 735, Italian only 141, and no Korean at all; https://dev.languagetool.org/languages). It finds
far more than the built-in rules and it is deterministic, so the same text always scores the same.

Set LANGUAGETOOL_URL to a server you run (for example the community Docker image, `docker run -p 8010:8010 erikvl87/languagetool`, then
LANGUAGETOOL_URL=http://localhost:8010). Do not point it at a public server for learners' text: that would send text to a third party,
which the privacy policy does not cover. Without the variable this source is simply absent.

Only grammar and spelling matches are kept. Style, typography and punctuation remarks are dropped, and a "misspelling" of a capitalised
word is dropped too (it is a name).
"""
from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Callable, Sequence

from .base import Hit

LANGUAGE_CODES = {"en": "en-US", "es": "es", "fr": "fr", "de": "de-DE", "it": "it", "pt": "pt-PT", "zh": "zh-CN", "ja": "ja-JP"}
_STYLE_ISSUES = {"style", "typographical", "register", "uncategorized", "whitespace", "duplication"}
_STYLE_CATEGORIES = {"TYPOGRAPHY", "PUNCTUATION", "STYLE", "REDUNDANCY", "PLAIN_ENGLISH", "WIKIPEDIA", "COLLOQUIALISMS", "CREATIVE_WRITING"}


def _post(url: str, fields: dict, timeout: float) -> dict:
    data = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    with urllib.request.urlopen(request, timeout=timeout) as response:     # noqa: S310 - the address comes from the operator's own setting
        return json.loads(response.read().decode("utf-8"))


def from_env():
    """A LanguageToolChecker for LANGUAGETOOL_URL, or None when it is not set."""
    url = os.environ.get("LANGUAGETOOL_URL", "").strip()
    return LanguageToolChecker(url) if url else None


class LanguageToolChecker:
    name = "languagetool"

    def __init__(self, url: str, post: Callable[[str, dict, float], dict] = _post, timeout: float = 15.0):
        self.endpoint = url.rstrip("/") + "/v2/check"
        self.post, self.timeout = post, timeout
        self.last_error = ""

    def supports(self, language: str) -> bool:
        return language in LANGUAGE_CODES

    def check(self, text: str, language: str, words: Sequence[str] = ()) -> list[Hit]:
        self.last_error = ""
        if not self.supports(language) or not text.strip():
            return []
        try:
            answer = self.post(self.endpoint, {"text": text, "language": LANGUAGE_CODES[language], "level": "default"}, self.timeout)
        except Exception as exc:        # noqa: BLE001 - an unreachable server must not stop a story from being scored
            self.last_error = f"{type(exc).__name__}: {exc}"
            return []
        return _hits(answer, text)


def _hits(answer: dict, text: str) -> list[Hit]:
    out = []
    for match in answer.get("matches", []):
        rule = match.get("rule") or {}
        issue = str(rule.get("issueType") or "").lower()
        category = str((rule.get("category") or {}).get("id") or "").upper()
        if issue in _STYLE_ISSUES or category in _STYLE_CATEGORIES:
            continue
        start, length = int(match.get("offset", -1)), int(match.get("length", 0))
        if start < 0 or length <= 0:
            continue
        wrong = text[start:start + length]
        kind = "spelling" if issue == "misspelling" else "grammar"
        if kind == "spelling" and wrong[:1].isupper():
            continue                                      # an unknown capitalised word is a name
        replacements = match.get("replacements") or []
        fix = str(replacements[0].get("value", "")) if replacements else ""
        out.append(Hit("languagetool", f"lt.{rule.get('id', 'rule')}", wrong, fix, kind, start, start + length, False,
                       str(match.get("shortMessage") or match.get("message") or "")[:80]))
    return out
