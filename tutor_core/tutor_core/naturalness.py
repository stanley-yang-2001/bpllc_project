"""A model's 1 to 5 rating of how natural a story reads (9 Nov 2026). The score takes it as `naturalness=` (weight 35, the largest part; a rating of 2
or less fails the story). It asks about the wording and the sense, not grammar mistakes (those come from the review in quality/grammar/audit.py).

Like the review it never raises: a failed call is a result with ok False and the score then simply leaves naturalness out.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Callable, Optional, Sequence

from .prompts import build_naturalness_prompt, build_naturalness_prompt_v2

_NUMBER = re.compile(r"\b([1-5])(?:[.,]\d)?\b")


@dataclass
class Naturalness:
    ok: bool
    score: Optional[float] = None
    reason: str = ""
    error: str = ""
    sense: Optional[int] = None          # only with the v2 prompt: the two 1 to 3 answers the rating was made from
    wording: Optional[int] = None
    repeats: tuple = ()                  # only when the text was rated more than once: every rating that worked, `score` being their median

    def as_dict(self) -> dict:
        out = {"ok": self.ok, "score": self.score, "reason": self.reason, "error": self.error}
        if self.sense is not None:
            out.update(sense=self.sense, wording=self.wording)
        if len(self.repeats) > 1:
            out["repeats"] = list(self.repeats)
        return out


def median_of(results: Sequence["Naturalness"]) -> "Naturalness":
    """One rating from several of the same text (16 Nov 2026). The rating lab found one reviewer rating the same text again gives the same 1 to 5 only about two times in
    three, and a pass/fail flip for 22% (gpt) and 30% (qwen) of the stories; the median of three removes most of that. The reason is the one of the rating nearest the
    median. With none that worked the first failure is returned, so the caller still sees why."""
    good = sorted((r for r in results if r.ok and r.score is not None), key=lambda r: r.score)
    if not good:
        return results[0] if results else Naturalness(False, error="no rating was asked")
    scores = [r.score for r in good]
    mid = scores[len(scores) // 2] if len(scores) % 2 else (scores[len(scores) // 2 - 1] + scores[len(scores) // 2]) / 2
    nearest = min(good, key=lambda r: abs(r.score - mid))
    return Naturalness(True, float(mid), nearest.reason, repeats=tuple(scores))


def from_parts(sense: float, wording: float) -> float:
    """1 to 5 from the v2 answers: sense + wording - 1, and 2 at most when either part is 1 (nonsense, or often unnatural, fails the text whatever the other says)."""
    rating = round(sense) + round(wording) - 1
    return float(min(rating, 2) if round(sense) == 1 or round(wording) == 1 else rating)


def parse(raw: str) -> Naturalness:
    """Read {"score": 4, "reason": "..."} (inside fences or text too); a bare digit 1 to 5 is accepted as a last resort."""
    raw = raw or ""
    match = re.search(r"\{.*\}", raw, re.S)
    if match:
        try:
            obj = json.loads(match.group(0))
            if "sense" in obj and "wording" in obj:
                sense, wording = float(obj["sense"]), float(obj["wording"])
                if 1 <= sense <= 3 and 1 <= wording <= 3:
                    return Naturalness(True, from_parts(sense, wording), str(obj.get("reason", ""))[:120], sense=round(sense), wording=round(wording))
            value = float(obj.get("score"))
            if 1 <= value <= 5:
                return Naturalness(True, round(value * 2) / 2, str(obj.get("reason", ""))[:120])
        except (ValueError, TypeError, AttributeError):
            pass
    found = _NUMBER.search(raw)
    if found:
        return Naturalness(True, float(found.group(1)), "")
    return Naturalness(False, error="no rating in the answer")


def rate(call: Callable[[str], str], text: str, language_name: str, prompt: str = "v1", level: str = "") -> Naturalness:
    """prompt 'v1' (the default, what every score so far used) or 'v2' (sense and wording apart, level named: opt-in, measured by scripts/rate_texts.py)."""
    try:
        asked = build_naturalness_prompt_v2(language_name, text, level) if prompt == "v2" else build_naturalness_prompt(language_name, text)
        return parse(call(asked))
    except Exception as exc:        # noqa: BLE001 - a failed rating must not fail the story
        return Naturalness(False, error=f"{type(exc).__name__}: {exc}")


def combine(ratings: Sequence[Optional[float]]) -> Optional[float]:
    """Several reviewers' ratings as one: their mean in half points (None when nobody rated)."""
    values = [r for r in ratings if r is not None]
    return round(sum(values) / len(values) * 2) / 2 if values else None
