"""Several versions of the word-applying step, and the best one kept (7 Nov 2026, step 5 of the quality plan). OFF unless
STORY_CANDIDATES is 2 or more.

`choose` scores every candidate with the story score (offline, no model) and keeps the highest; ties keep the earlier one. With the judge on
(STORY_JUDGE=1) the best two by offline score are also reviewed by a model for grammar mistakes (every quote checked against the text, see
quality/grammar/audit.py) and re-scored with what it found, so a text with a wrong verb ending cannot win on length and word count alone.
Use another model for the review than for the story: GROQ_JUDGE_MODEL.
"""
from __future__ import annotations

from typing import Callable, Optional

from .languages import LANGUAGES
from .quality import score_story
from .quality.grammar.audit import run_audit

JUDGED = 2          # how many of the best candidates the model reviews


def choose(texts: list[str], language: str, words, difficulty: Optional[dict], kind: Optional[str], *,
           audit_call: Optional[Callable[[str], str]] = None) -> tuple[str, list, list[str]]:
    """(the chosen text, its model-found hits ([] without a judge), notes). `texts` must not be empty."""
    name = LANGUAGES[language].name if language in LANGUAGES else language
    scored = [(score_story(t, language, words, difficulty, kind), t) for t in texts]
    notes = [f"{len(texts)} candidates, offline scores: " + ", ".join(str(s["score"]) for s, _ in scored)]
    hits = {i: [] for i in range(len(texts))}
    if audit_call is not None and len(texts) > 1:
        ranked = sorted(range(len(texts)), key=lambda i: (-scored[i][0]["score"], i))[:JUDGED]
        for i in ranked:
            if scored[i][0]["gated"]:
                continue
            review = run_audit(audit_call, texts[i], name)
            if review.ok:
                hits[i] = review.hits
                scored[i] = (score_story(texts[i], language, words, difficulty, kind, hits=review.hits), texts[i])
            notes.append(f"judge reviewed #{i + 1}: " + (f"{len(review.hits)} mistake(s) found" if review.ok else f"no usable answer ({review.error[:60]})"))
        eligible = ranked or list(range(len(texts)))
    else:
        eligible = list(range(len(texts)))
    best = max(eligible, key=lambda i: (scored[i][0]["score"], -i))
    notes.append(f"chose #{best + 1} (score {scored[best][0]['score']})")
    return texts[best], hits[best], notes
