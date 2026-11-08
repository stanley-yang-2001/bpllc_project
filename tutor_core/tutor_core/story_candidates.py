"""Several candidates, one winner (7 Nov 2026; the cascade of 8 Nov 2026). OFF unless STORY_CANDIDATES is 2 or more.

The cascade, cheapest first:
    1  score every candidate (offline, no model)
    2  gates (`gates=True`, story_gates.py): a candidate that fails a gate is dropped when another one passes, with no model call
    3  review (`audit_call`, the judge model): the best JUDGED candidates are reviewed for grammar mistakes (every quote checked against the
       text, quality/grammar/audit.py) and scored again with what was found
    4  pairwise pick: when the two best are within PAIRWISE_GAP points, the judge is asked which reads better, in both orders; the pick counts only
       when both orders agree, otherwise the higher score stands

Use another model for the review than for the writing (GROQ_JUDGE_MODEL): a model marks its own writing leniently.
"""
from __future__ import annotations

from typing import Callable, Optional

from .languages import LANGUAGES
from .prompts import build_pairwise_prompt
from .quality import score_story
from .quality.grammar.audit import run_audit
from .story_gates import check as run_gates

JUDGED = 2          # how many of the best candidates the model reviews
PAIRWISE_GAP = 2.0  # points: closer than this, the judge picks between the two


def _pick(call: Callable[[str], str], name: str, a: str, b: str) -> Optional[int]:
    """0 if the judge prefers `a`, 1 if it prefers `b`, None when it says tie, contradicts itself or fails."""
    verdicts = []
    for first, second, flip in ((a, b, False), (b, a, True)):
        try:
            answer = (call(build_pairwise_prompt(name, first, second)) or "").strip().upper()
        except Exception:       # noqa: BLE001 - a failed judge never fails the story
            return None
        letter = "A" if answer.startswith("A") else "B" if answer.startswith("B") else None
        if letter is None:
            return None
        verdicts.append((0 if letter == "A" else 1) ^ (1 if flip else 0))
    return verdicts[0] if verdicts[0] == verdicts[1] else None


def choose(texts: list[str], language: str, words, difficulty: Optional[dict], kind: Optional[str], *,
           audit_call: Optional[Callable[[str], str]] = None, gates: bool = False) -> tuple[str, list, list[str]]:
    """(the chosen text, its model-found hits ([] without a judge), notes). `texts` must not be empty."""
    name = LANGUAGES[language].name if language in LANGUAGES else language
    scored = [score_story(t, language, words, difficulty, kind) for t in texts]
    notes = [f"{len(texts)} candidates, offline scores: " + ", ".join(str(s["score"]) for s in scored)]
    pool = list(range(len(texts)))
    if gates:
        verdicts = [run_gates(t, language, words, difficulty, kind, s) for t, s in zip(texts, scored)]
        passing = [i for i in pool if verdicts[i]["passed"]]
        notes.append("gates: " + "; ".join(f"#{i + 1} " + ("passed" if verdicts[i]["passed"] else "failed " + "+".join(verdicts[i]["failed"])) for i in pool))
        if passing:
            pool = passing
        else:
            notes.append("no candidate passed the gates: the highest score is kept for the repair")
    hits = {i: [] for i in pool}
    if audit_call is not None and len(pool) > 1:
        ranked = sorted(pool, key=lambda i: (-scored[i]["score"], i))[:JUDGED]
        for i in ranked:
            if scored[i]["gated"]:
                continue
            review = run_audit(audit_call, texts[i], name)
            if review.ok:
                hits[i] = review.hits
                scored[i] = score_story(texts[i], language, words, difficulty, kind, hits=review.hits)
            notes.append(f"judge reviewed #{i + 1}: " + (f"{len(review.hits)} mistake(s) found" if review.ok else f"no usable answer ({review.error[:60]})"))
        pool = ranked
    order = sorted(pool, key=lambda i: (-scored[i]["score"], i))
    best = order[0]
    if audit_call is not None and len(order) > 1 and scored[order[0]]["score"] - scored[order[1]]["score"] < PAIRWISE_GAP:
        winner = _pick(audit_call, name, texts[order[0]], texts[order[1]])
        notes.append(f"pairwise: #{order[0] + 1} vs #{order[1] + 1} -> " + ("no agreement, the score decides" if winner is None else f"#{order[winner] + 1}"))
        if winner is not None:
            best = order[winner]
    notes.append(f"chose #{best + 1} (score {scored[best]['score']})")
    return texts[best], hits.get(best, []), notes
