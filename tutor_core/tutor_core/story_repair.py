"""Fix what the score still finds wrong, by name (7 Nov 2026, step 6 of the quality plan). OFF unless STORY_REPAIR=1.

The older retries (story_retries.py) regenerate blindly or fix one family of problem. This one reads the story score and writes a
repair prompt that lists every requirement the story misses: the learner's words it left out, the length it should be, the uncommon
words to swap, sentences that are too long, the grammar mistakes found, placeholders and repeats. Three guards keep it safe:

  * mistakes with a certain fix (a contraction, a doubled word, a capital) are fixed by code, with no model call;
  * at most `max_calls` model calls (2 by default), and it stops at the first rewrite that does not raise the score;
  * a rewrite replaces the text only when its score is higher and it is not gated (wrong language, empty, leaked plan).
"""
from __future__ import annotations

from typing import Callable, Optional

from . import difficulty as _d
from .languages import LANGUAGES
from .naturalness import rate as rate_naturalness
from .prompts import build_targeted_prompt, extract_final_passage
from .quality import score_story
from .quality.grammar import Hit, apply_certain
from .quality.grammar.audit import run_audit
from .story_diagnose import actionable, diagnose, directives as edit_directives, should_repair
from .story_gates import check as run_gates, requirements as gate_requirements

MAX_CALLS = 1          # repair once: a second rewrite gained about a point in the runs of 7 Nov and cost the most waiting
GOOD = 85.0            # a part at or above this is not worth a call
GRAMMAR_GOOD = 95.0
MIN_GAIN = 0.5         # a rewrite must beat the text by this many points
MAX_LISTED = 6
NATURAL_FIX_AT = 50.0   # naturalness part (rating 3 or less) worth a rewrite when the repair rates naturalness (18 Nov 2026)
DIRECTIVE_TOLERANCE = 3.0   # a directive rewrite (joined sentences, new openers) may lose this many score points: the score's one ruler (6 to 12 words a sentence) does not value rhythm

_STRUCTURAL = {"placeholder": "Remove every blank or placeholder such as [Your name] or [Name]: write a real name instead.",
               "repeated_word": "Do not repeat the same word over and over; use different words.",
               "run_on": "Split long run-on sentences into short sentences."}


def requirements(result: dict, text: str, language: str, words, difficulty: Optional[dict], kind: Optional[str], reason: str = "") -> list[str]:
    """Plain sentences naming each requirement the scored story misses (empty when it misses none worth a call). `reason` is the reviewer's short reason for a naturalness
    rating of 3 or less (only when the repair rates naturalness): it is quoted to the writer, so the rewrite fixes what the reviewer saw (choppy, list-like, events that do not follow)."""
    if result.get("gated"):
        return []
    parts, targets, m = result["parts"], result["targets"], result["measured"]
    unspaced = _d.is_unspaced(language)
    unit = "characters" if unspaced else "words"
    out: list[str] = []
    if parts["length"] is not None and parts["length"] < GOOD:
        t = targets["length"]
        out.append(f"Make the text between {round(t * 0.9)} and {round(t * 1.1)} {unit} long (it is {m['length']} {unit} now).")
    if parts["own_words"] is not None and parts["own_words"] < GOOD:
        if m.get("own_density", 0) > 0.25:
            out.append("Do not crowd the text with the learner's words: use each at most once or twice and make most words ordinary everyday words.")
        if m["own_words"] < targets["own_words"]:
            missing = _d.missing_own_words(text, language, words)[:MAX_LISTED]
            if missing:
                need = targets["own_words"] - m["own_words"]
                out.append(f"Use at least {need} more of the learner's words, each in a natural sentence, for example: {', '.join(missing)}.")
    if parts.get("uncommon") is not None and parts["uncommon"] < GOOD:
        rare = _d.uncommon_words(text, language, words)[:8]
        out.append("Replace uncommon words with simpler everyday ones" + (f" (for example: {', '.join(rare)})." if rare else "."))
    if parts["sentence_length"] is not None and parts["sentence_length"] < GOOD:
        want = "8 to 24 characters" if unspaced else "6 to 12 words"
        out.append(f"Write sentences of {want} (the average is {m['mean_sentence']} {unit} now); split any sentence that is much longer.")
    fixes = [h for h in result.get("grammar_hits", []) if h.get("kind") != "style"][:MAX_LISTED]
    if parts["grammar"] is not None and parts["grammar"] < GRAMMAR_GOOD:
        if fixes:
            shown = "; ".join(f'"{h["wrong"]}"' + (f' should be "{h["fix"]}"' if h.get("fix") else " is wrong") for h in fixes)
            out.append(f"Fix these grammar mistakes: {shown}.")
        for p in result.get("problems", []):
            out.append(_STRUCTURAL.get(p, p[:1].upper() + p[1:] + ("" if p.endswith(".") else ".")))
    verdict = run_gates(text, language, words, difficulty, kind, result)
    verdict["failed"] = [f for f in verdict["failed"] if f in ("stuffed", "tacked_on_words", "telegraphic", "too_many_errors", "unnatural", "markdown")]   # length and word counts are above
    out += [r for r in gate_requirements(verdict, language) if r not in out]
    if parts["language_format"] is not None and parts["language_format"] < 100 and not any("blank" in r for r in out):
        if kind == "dialogue":
            out.append("Write it as a dialogue: every line starts with a speaker name and a colon.")
        out.append("End on a finished sentence, with nothing cut off.")
    nat = parts.get("naturalness")
    if nat is not None and nat <= NATURAL_FIX_AT:
        out = [r for r in out if not r.startswith("Rewrite it so it reads naturally")]
        said = f' A reviewer said: "{reason.strip()[:120]}".' if reason and reason.strip() else ""
        out.append("Rewrite the parts that read unnaturally so the story makes sense from start to end and flows like a good writer's: events that follow one another, "
                   "no repeated time words or filler, no list-like sentences." + said)
    return out


def repair_story(text: str, language: str, words, difficulty: Optional[dict], kind: Optional[str], call: Callable[[str], str], *,
                 hits: Optional[list] = None, audit_call: Optional[Callable[[str], str]] = None, max_calls: int = MAX_CALLS,
                 naturalness: bool = False, directives: bool = False) -> tuple[str, list[str]]:
    """(the best text, notes saying what was done). Never raises and never returns a text with a lower score than it was given.
    `naturalness=True` (with an `audit_call`): the judge also rates how natural the text reads, before and after each rewrite; a rating of 3 or less is a requirement
    that quotes the reviewer's reason, and a rewrite is kept only when the score, which then includes the rating, rises.
    `directives=True` (20 Nov 2026): when the free checks (story_diagnose.py) find 2 or more of flat rhythm, a repeated opener and filler time words, the repair gets one concrete edit
    for each, and the repair runs even when the score has nothing to fix. Such a rewrite is kept only if the findings went down, the learner-word part of the score did not drop,
    nothing is gated and the score lost at most DIRECTIVE_TOLERANCE points (the score does not value rhythm, so it cannot be asked to rise)."""
    notes: list[str] = []
    name = LANGUAGES[language].name if language in LANGUAGES else language
    last = {"reason": "", "rating": None}          # the rating of the text graded last, which is the text the next rewrite starts from

    def grade(t: str, known: Optional[list] = None, rate: bool = True) -> dict:
        extra = list(known or [])
        if audit_call is not None and known is None:
            extra = run_audit(audit_call, t, name).hits
        rating = rate_naturalness(audit_call, t, name) if naturalness and rate and audit_call is not None else None
        ok = rating is not None and rating.ok
        last["reason"], last["rating"] = (rating.reason, rating.score) if ok else ("", None)
        return score_story(t, language, words, difficulty, kind, hits=extra, naturalness=rating.score if ok else None)

    current = text
    score = grade(current, hits if hits is not None or audit_call is None else None)
    if score["gated"]:
        return text, [f"repair skipped: story is gated ({score['gated']})"]
    certain = [Hit(**h) for h in score["grammar_hits"] if h.get("certain")]
    if certain:
        fixed = apply_certain(current, certain)
        if fixed != current and not score_story(fixed, language, words, difficulty, kind)["gated"]:
            regraded = grade(fixed, rate=last["rating"] is not None)        # like for like: rated again only when the text before it was rated
            notes.append(f"code fixed certain mistake(s) without a model call: {score['score']} -> {regraded['score']}")
            current, score = fixed, regraded
    if last["rating"] is not None:
        notes.append(f"naturalness {last['rating']:g}/5 before the repair")
    for attempt in range(1, max_calls + 1):
        reqs = requirements(score, current, language, words, difficulty, kind, last["reason"])
        found = diagnose(current, language, words, kind) if directives else []
        directed = directives and should_repair(found)
        if directed:
            reqs = reqs + edit_directives(found, language)
        if not reqs:
            notes.append("repair: nothing left worth a call" if attempt == 1 else "repair: done")
            break
        try:
            new = extract_final_passage(call(build_targeted_prompt(name, current, reqs, ", ".join(words))))
        except Exception as exc:        # noqa: BLE001 - a failed repair keeps the text as it is
            notes.append(f"repair {attempt} failed: {type(exc).__name__}")
            break
        if not new.strip():
            notes.append(f"repair {attempt} returned nothing")
            break
        before_rating = last["rating"]
        after = grade(new, rate=before_rating is not None)       # compared like for like: rated when the old text was, not rated when it was not
        if before_rating is not None and last["rating"] is None and not after["gated"]:
            # a score without a rating has no penalty for an unnatural text, so it would beat the old text's rated score for no reason (18 Nov 2026: 44.9 -> 100.0 on a failed rating)
            notes.append(f"repair {attempt} rejected: the new text could not be rated, so it cannot be compared with the old one")
            break
        if directed:
            left = len(actionable(diagnose(new, language, words, kind)))
            before_n = len(actionable(found))
            low = after["parts"]["own_words"] is not None and score["parts"]["own_words"] is not None and after["parts"]["own_words"] < score["parts"]["own_words"]
            if after["gated"] or left >= before_n or low or after["score"] < score["score"] - DIRECTIVE_TOLERANCE:
                why = "gated" if after["gated"] else "findings not fewer" if left >= before_n else "learner words dropped" if low else "score fell"
                notes.append(f"repair {attempt} rejected ({why}): findings {before_n} -> {left}, score {score['score']} -> {after['score']}")
                break
            notes.append(f"repair {attempt} kept (directives): findings {before_n} -> {left}, score {score['score']} -> {after['score']}")
            current, score = new, after
            continue
        if after["gated"] or after["score"] < score["score"] + MIN_GAIN:
            notes.append(f"repair {attempt} rejected: {score['score']} -> {after['score']}" + (f" ({after['gated']})" if after["gated"] else ""))
            break
        notes.append(f"repair {attempt} kept: {score['score']} -> {after['score']} ({len(reqs)} requirement(s))"
                     + (f"; naturalness {before_rating:g} -> {last['rating']:g}" if before_rating is not None and last["rating"] is not None else ""))
        current, score = new, after
    return current, notes
