"""Check, then fix only what was found, and keep the fix only if the score rises (10 Nov 2026). OFF unless StoryOptions.refine > 0.

14 Nov 2026 (after the 13 Nov Kaggle run, which gave 5 of 6 failed reviews on hard stories against 1 of 6 without refine, and 0 of 6 against 5 of 6 on medium ones):
the loop now also RATES NATURALNESS at every observe (the score weights it 35, and a rating of 2 fails the story, but the loop's own score used to leave it out, so
it could report 83 -> 96 for a text the same reviewer then rated 2 of 5), a repair is thrown away when the rating drops, and the whole-text needs (length, uncommon
words, how many of the learner's words) are no longer sent to the model: they made it pad the text with filler ("today", "now", "indeed") or rewrite everything, which
was then rejected. They stay in the plan record, as measured and left alone.

A bounded loop, not a free-form agent. Each round has the phases below, and every phase writes a record to `trace`, so a run can show exactly
what each step saw and did:

    observe   the tools look at the text: the built-in grammar rules and gates (free), LanguageTool when LANGUAGETOOL_URL is set (free), and a model
              review when a review call is given (one call). Their findings are merged and the story is scored with them.
    plan      code turns the findings into a list: which sentences are wrong and why, plus whole-text needs (length, the learner's words).
    repair    ONE model call rewrites only the listed sentences (prompts/repair.py `build_sentence_repair_prompt`).
    verify    the new text is accepted only if it is not gated, most unflagged sentences are untouched, and the score rose by MIN_GAIN.
              Otherwise it is thrown away and the loop stops.

It stops at `rounds` rounds, when nothing is flagged, or at the first rejected rewrite. The returned text never scores lower than the one given.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence

from .languages import LANGUAGES
from .prompts import extract_final_passage
from .prompts.repair import build_sentence_repair_prompt
from .naturalness import rate as rate_naturalness
from .quality import score_story
from .quality.score import GATE_NATURALNESS
from .quality.grammar import Hit, apply_certain, locate, merge, sentence_spans
from .quality.grammar.audit import AuditChecker
from .story_gates import check as run_gates
from .story_repair import requirements as whole_text_requirements

MIN_GAIN = 0.5            # a rewrite must beat the text by this many points
KEEP_SHARE = 0.7          # at least this share of the sentences that were not flagged must come back unchanged
MAX_FLAGGED = 6           # sentences listed in one call


@dataclass
class RefineResult:
    text: str
    trace: list = field(default_factory=list)
    notes: list = field(default_factory=list)
    draft: str = ""                 # the text as it came in, so a test can review the draft and the result with the same reviewers


def _sentences(text: str) -> list[str]:
    return [text[a:b].strip() for a, b in sentence_spans(text)]


def flagged_sentences(text: str, hits: Sequence[Hit]) -> list[tuple[int, str, list[str]]]:
    """[(sentence number from 1, the sentence, [problems])] for every sentence a finding touches, in order, at most MAX_FLAGGED."""
    spans = sentence_spans(text)
    problems: dict[int, list[str]] = {}
    for hit in hits:
        hit = locate(text, hit)
        if hit.start < 0 or hit.kind == "style":
            continue
        for k, (a, b) in enumerate(spans):
            if a <= hit.start < b:
                said = f'"{hit.wrong}" should be "{hit.fix}"' if hit.fix else f'"{hit.wrong}" is wrong'
                problems.setdefault(k, []).append(said + (f" ({hit.note})" if hit.note else ""))
                break
    return [(k + 1, text[spans[k][0]:spans[k][1]].strip(), problems[k]) for k in sorted(problems)][:MAX_FLAGGED]


def unchanged_share(before: str, after: str, flagged_numbers: Sequence[int]) -> float:
    """Of the sentences that were not flagged, the share that are still in the new text word for word (1.0 when everything was flagged)."""
    old = _sentences(before)
    new = set(_sentences(after))
    keep = [s for k, s in enumerate(old, 1) if k not in set(flagged_numbers)]
    return 1.0 if not keep else sum(1 for s in keep if s in new) / len(keep)


def splice_flagged(before: str, after: str, flagged_numbers: Sequence[int]) -> str:
    """Keep every sentence of `before` word for word except the flagged ones, which are taken from `after` (13 Nov 2026: on the 12 Nov test the model
    rewrote the whole text in 3 of 9 stories even though only some sentences were named). Needs the same number of sentences; otherwise `after` is returned."""
    old, new = sentence_spans(before), sentence_spans(after)
    if len(old) != len(new) or not flagged_numbers:
        return after
    out, last = [], 0
    for k, (a, b) in enumerate(old, 1):
        out.append(before[last:a])
        out.append(after[new[k - 1][0]:new[k - 1][1]] if k in set(flagged_numbers) else before[a:b])
        last = b
    out.append(before[last:])
    return "".join(out)


def finding_still_in_text(hit: Hit, text: str) -> bool:
    """A finding is still there when its wrong wording is in the text and its fix is not (a fix that only adds a word, such as "On Monday" for
    "Monday", contains the wrong wording and must not count as still there)."""
    wrong, fix = (hit.wrong or "").casefold(), (hit.fix or "").casefold()
    return bool(wrong) and wrong in text.casefold() and not (fix and fix in text.casefold())


def refine_tools() -> list:
    """The free external checkers that are set up: LanguageTool when LANGUAGETOOL_URL is set."""
    from .quality.grammar import languagetool
    tool = languagetool.from_env()
    return [tool] if tool else []


def _hit_dict(hit: Hit) -> dict:
    return {"source": hit.source, "wrong": hit.wrong, "fix": hit.fix, "note": hit.note, "certain": hit.certain}


def _brief(score: dict, naturalness: Optional[float] = None) -> dict:
    return {"score": score["score"], "parts": score["parts"], "gated": score["gated"], "findings": len(score.get("grammar_hits", [])), "naturalness": naturalness}


def refine_story(text: str, language: str, words, difficulty: Optional[dict], kind: Optional[str], call: Callable[[str], str], *,
                 tools: Sequence = (), review_call: Optional[Callable[[str], str]] = None, rate_call: Optional[Callable[[str], str]] = None,
                 rounds: int = 2) -> RefineResult:
    """`tools` are grammar checkers (`check(text, language, words) -> [Hit]`), for example LanguageTool. `review_call` adds a model review and `rate_call`
    a 1 to 5 naturalness rating (one more call per observe). Never raises; a failed call is recorded in the trace and the text stays as it is."""
    name = LANGUAGES[language].name if language in LANGUAGES else language
    words = list(words)
    out = RefineResult(text, draft=text)

    def observe(t: str, label: str) -> tuple[dict, list[Hit], Optional[float]]:
        groups, seen = [], []
        base = score_story(t, language, words, difficulty, kind)
        groups.append([Hit(**h) for h in base["grammar_hits"]])
        seen.append({"tool": "built-in rules", "found": len(groups[-1])})
        for tool in tools:
            found = list(tool.check(t, language, words))
            groups.append(found)
            seen.append({"tool": tool.name, "found": len(found), "error": getattr(tool, "last_error", "") or None})
        if review_call is not None:
            checker = AuditChecker(review_call)
            found = checker.check(t, language, words)
            groups.append(found)
            seen.append({"tool": "model review", "found": len(found), "error": checker.last.error or None})
        hits = merge(*groups)
        rating = rate_naturalness(rate_call, t, name) if rate_call is not None else None
        nat = rating.score if rating is not None and rating.ok else None
        scored = score_story(t, language, words, difficulty, kind, hits=hits, naturalness=nat)
        out.trace.append({"phase": "observe", "label": label, "tools": seen, "hits": [_hit_dict(h) for h in hits], "gates": run_gates(t, language, words, difficulty, kind, scored)["failed"],
                          "naturalness": rating.as_dict() if rating is not None else None, "score": _brief(scored, nat)})
        return scored, hits, nat

    current = text
    score, hits, nat = observe(current, "start")
    if score["gated"]:
        out.notes.append(f"refine skipped: story is gated ({score['gated']})")
        return out
    certain = [h for h in hits if h.certain and h.fix]
    if certain:
        fixed = apply_certain(current, certain)
        if fixed != current and not score_story(fixed, language, words, difficulty, kind)["gated"]:
            out.trace.append({"phase": "code fix", "changes": [_hit_dict(h) for h in certain]})
            out.notes.append(f"code fixed {len(certain)} certain mistake(s) with no model call")
            current = fixed
            score, hits, nat = observe(current, "after code fix")

    for number in range(1, max(0, rounds) + 1):
        flagged = flagged_sentences(current, hits)
        left = [r for r in whole_text_requirements(score, current, language, words, difficulty, kind) if not r.startswith("Fix these grammar")]
        out.trace.append({"phase": "plan", "round": number, "flagged": [{"sentence": n, "text": s, "problems": p} for n, s, p in flagged], "whole_text": left,
                          "whole_text_repaired": False})
        if not flagged:
            out.notes.append("refine: nothing left to fix" if number == 1 else "refine: done")
            break
        prompt = build_sentence_repair_prompt(name, current, flagged, [], ", ".join(words))          # sentences only: a whole-text request made the model pad or rewrite everything
        try:
            raw = call(prompt)
        except Exception as exc:        # noqa: BLE001 - a failed repair keeps the text as it is
            out.trace.append({"phase": "repair", "round": number, "error": f"{type(exc).__name__}: {exc}"})
            out.notes.append(f"refine {number} failed: {type(exc).__name__}")
            break
        new = extract_final_passage(raw)
        out.trace.append({"phase": "repair", "round": number, "prompt_chars": len(prompt), "reply": new})
        if not new.strip():
            out.notes.append(f"refine {number} returned nothing")
            break
        if new.strip() == current.strip():          # a reviewer that answers differently the second time must not make a no-op look like a gain
            out.trace.append({"phase": "verify", "round": number, "kept": False, "reason": "the model returned the text unchanged"})
            out.notes.append(f"refine {number} rejected: text unchanged")
            break
        new = splice_flagged(current, new, [n for n, _, _ in flagged])          # only the named sentences may change, whatever the model returned
        if new.strip() == current.strip():
            out.trace.append({"phase": "verify", "round": number, "kept": False, "reason": "the named sentences came back unchanged"})
            out.notes.append(f"refine {number} rejected: text unchanged")
            break
        after = score_story(new, language, words, difficulty, kind)          # the free checks first: do not pay for a review of a bad rewrite
        share = unchanged_share(current, new, [n for n, _, _ in flagged])
        still = [h.wrong for h in hits if h.kind != "style" and finding_still_in_text(h, new)]
        verdict = {"phase": "verify", "round": number, "unchanged_share": round(share, 2), "findings_still_in_text": still, "gated": after["gated"], "free_score": after["score"]}
        if after["gated"] or share < KEEP_SHARE:
            verdict.update(kept=False, reason=f"gated ({after['gated']})" if after["gated"] else f"rewrote too much: {round(share * 100)}% of the other sentences kept")
            out.trace.append(verdict)
            out.notes.append(f"refine {number} rejected: {verdict['reason']}")
            break
        new_score, new_hits, new_nat = observe(new, f"after repair {number}")
        gain = new_score["score"] - score["score"]
        lower = nat is not None and new_nat is not None and new_nat < nat          # a fix that makes the text read worse is not a fix, whatever the findings say
        kept = gain >= MIN_GAIN and not lower
        reason = None if kept else (f"naturalness {nat:g} -> {new_nat:g}" if lower else f"score {score['score']} -> {new_score['score']}")
        verdict.update(before=score["score"], after=new_score["score"], naturalness_before=nat, naturalness_after=new_nat, kept=kept, reason=reason)
        out.trace.append(verdict)
        if not kept:
            out.notes.append(f"refine {number} rejected: {reason}")
            break
        out.notes.append(f"refine {number} kept: {score['score']} -> {new_score['score']} ({len(flagged)} sentence(s))")
        current, score, hits, nat = new, new_score, new_hits, new_nat
    if nat is not None and nat <= GATE_NATURALNESS:
        out.notes.append(f"refine: still reads unnatural ({nat:g}/5); fixing single sentences cannot change that")
    out.text = current
    return out
