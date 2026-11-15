"""Run every request with every method, one story at a time, and save after each story (7 Nov 2026).

Rate limit: the story call is wrapped by `patient` (it keeps under the token limit and waits out a 429 hint), and the run goes request by
request, so an interrupted or limit-stopped run always has complete rows for the requests it reached. A story that failed ONLY because the limit
was too long to wait for (a daily limit) is not saved: stop, wait, run again with --resume and it is made then.

Time, per story (all in seconds):
    model_seconds  time spent inside model calls (the story's own calls, and the judge's)
    seconds        wall time from request to finished story, including waiting for the rate limit
    wait_seconds   seconds minus model_seconds: waiting for the limit plus the code's own time (tiny)
The review of grammar (--audit) and the translation are measured separately and never counted in the story's calls or seconds.

14 Nov 2026: a method that rewrites its own draft (refine) also has its FIRST DRAFT reviewed by the same reviewers (`entry["draft"]`), so "did refine help" compares a
text with its own repair instead of with another sample of the model (two drafts of the same request differ by far more than any repair did). A draft that refine left
unchanged is not reviewed again: it is the result, and a second review of the same text would only add the reviewer's noise. And a run that ends early says why in
`data["meta"]["stopped"]`: before, the JSON of a run that stopped on a daily limit looked the same as one that was cut by a crash.
"""
from __future__ import annotations

import contextlib
import json
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from tutor_core import difficulty as _d
from tutor_core.languages import LANGUAGES
from tutor_core.patient import is_rate_limit
from tutor_core.quality import score_story
from tutor_core.quality.grammar import Hit
from tutor_core.naturalness import combine as combine_ratings, rate as rate_naturalness
from tutor_core.quality.grammar.audit import run_audit
from tutor_core.quality.score import merge_reviews
from tutor_core.story import story_from_words

from .health import describe_error, scrub

FORMAT = "story-methods-1"


class Timer:
    """Wraps a model call: counts calls, the seconds spent in them, and keeps the last error."""

    def __init__(self, call):
        self.call, self.calls, self.seconds, self.error = call, 0, 0.0, None

    def __call__(self, prompt):
        started = time.monotonic()
        self.calls += 1
        try:
            return self.call(prompt)
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self.seconds += time.monotonic() - started


class StopRun(Exception):
    """The rate limit is too long to wait for: save what is done and stop."""


class Channel:
    """One model, as the runner uses it: `raw` is the plain call, `call` is what the story gets. The meter sits INSIDE the pacing wrapper, so
    it counts time in the model only, not time spent waiting for the rate limit. The pacing wrapper lives as long as the channel, so the
    token count carries over from one story to the next. `wrap` is `patient` in a real run and the identity in the tests."""

    def __init__(self, raw, wrap=lambda call: call):
        self.meter = Timer(raw)
        self.call = wrap(self.meter)

    def reset(self):
        self.meter.calls, self.meter.seconds, self.meter.error = 0, 0.0, None


@dataclass
class Calls:
    story: Channel
    judge: Optional[Channel] = None
    audit: Optional[Channel] = None
    translate: Optional[Callable] = None        # (text, code) -> English text or ""
    models: Optional[Callable] = None           # alias ("gpt", "qwen") -> Channel, for methods that name who writes and who judges
    rate: bool = True                           # also ask every reviewer for a 1-5 naturalness rating (one more call per story and reviewer)
    audits: Optional[dict] = None               # label -> Channel: several independent reviewers of every final story (else `audit`)


@contextlib.contextmanager
def _env(**values):
    old = {k: os.environ.get(k) for k in values}
    os.environ.update({k: v for k, v in values.items() if v is not None})
    try:
        yield
    finally:
        for k, v in old.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def _score(text, ok, request, hits=None, naturalness=None):
    if not ok:
        return None
    return score_story(text, request["code"], request["words"], _d.resolve(request["tier"]), request.get("story_type"), hits=hits, naturalness=naturalness)


def review_text(text: str, request: dict, reviewers: dict, rate: bool = True):
    """Every reviewer's findings and 1 to 5 rating of `text`, and the score each gives it: (audits, audit_scores, audit_union). The union is the findings of all
    reviewers together with their mean rating, None with fewer than two."""
    code = request["code"]
    audits, scores, union = {}, {}, None
    for label, channel in reviewers.items():
        channel.reset()
        review = run_audit(channel.call, text, LANGUAGES[code].name)
        rating = rate_naturalness(channel.call, text, LANGUAGES[code].name) if rate else None
        audits[label] = dict(review.as_dict(), seconds=round(channel.meter.seconds, 1), naturalness=rating.as_dict() if rating is not None else None)
        if review.ok or (rating is not None and rating.ok):
            scores[label] = _score(text, True, request, review.hits if review.ok else None, rating.score if rating is not None and rating.ok else None)
    if len(scores) > 1:
        union = _score(text, True, request, merge_reviews(*([Hit(**h) for h in r["hits"]] for r in audits.values() if r.get("ok"))),
                       combine_ratings([(r.get("naturalness") or {}).get("score") for r in audits.values()]))
    return audits, scores, union


def draft_entry(draft: str, final: str, request: dict, reviewers: dict, rate: bool = True) -> dict:
    """The refine loop's first draft next to its result. Reviewed only when the loop changed it and there are reviewers; an unchanged draft IS the result."""
    changed = draft.strip() != final.strip()
    out = {"text": draft, "changed": changed}
    if changed:
        out["score"] = _score(draft, True, request)
        if reviewers:
            out["audits"], out["audit_scores"], out["audit_union"] = review_text(draft, request, reviewers, rate)
    return out


def run_one(request: dict, variant, calls: Calls, conn=None) -> dict:
    """One story by one method: the entry saved in the results. Raises StopRun when the limit cannot be waited out."""
    code, difficulty = request["code"], _d.resolve(request["tier"])
    story_ch = calls.models(variant.story_model) if variant.story_model and calls.models else calls.story
    judge_ch = calls.models(variant.judge_model) if variant.judge_model and calls.models else calls.judge
    used = [story_ch] + ([judge_ch] if judge_ch is not None and judge_ch is not story_ch else [])
    for channel in used:
        channel.reset()
    started = time.monotonic()
    with _env(STORY_RANGE_PROMPT="1" if variant.range_prompt else "0"):
        result = story_from_words(code, request["words"], story_ch.call, story_type=request["story_type"], topic=request["topic"],
                                  difficulty=difficulty, two_pass=variant.two_pass, rng=random.Random(request["seed"]),
                                  with_example=variant.examples and conn is not None, conn=conn, options=variant.options(),
                                  judge_call=judge_ch.call if judge_ch is not None else None, proofread=variant.proofread)
    wall = time.monotonic() - started
    error = next((c.meter.error for c in used if c.meter.error), None)
    if result.reason == "failed" and error and is_rate_limit(error):
        raise StopRun(error)
    model = sum(c.meter.seconds for c in used)
    n_calls = sum(c.meter.calls for c in used)
    judged_by = judge_ch if judge_ch is not None else story_ch      # no judge model set (GROQ_JUDGE_MODEL): the story's own model judges
    entry = {"text": result.text, "ok": result.ok, "reason": result.reason, "story_type": result.story_type, "topic": result.topic,
             "calls": n_calls, "seconds": round(wall, 1), "model_seconds": round(model, 1),
             "wait_seconds": round(max(0.0, wall - model), 1), "error": error, "notes": list(result.notes), "translation": "",
             "audit": None, "audit_seconds": None, "audit_score": None, "audits": {}, "audit_scores": {}, "audit_union": None, "models": {
                 "story": getattr(story_ch.meter.call, "model", None) or variant.story_model or "default",
                 "judge": (getattr(judged_by.meter.call, "model", None) or variant.judge_model or "default") if variant.judge else None}}
    entry["gate"] = None
    entry["trace"] = list(getattr(result, "trace", ()) or [])
    entry["score"] = _score(result.text, result.ok, request)
    if result.ok:
        from tutor_core.story_gates import check as run_gates
        entry["gate"] = run_gates(result.text, code, request["words"], difficulty, request.get("story_type"))
    reviewers = calls.audits or ({"review": calls.audit} if calls.audit else {})
    if result.ok:
        entry["audits"], entry["audit_scores"], entry["audit_union"] = review_text(result.text, request, reviewers, calls.rate)
        if entry["audits"]:
            first = next(iter(entry["audits"]))
            entry["audit"], entry["audit_seconds"] = entry["audits"][first], entry["audits"][first]["seconds"]
            entry["audit_score"] = entry["audit_scores"].get(first)
        draft = (getattr(result, "draft", "") or "").strip()
        if draft:
            entry["draft"] = draft_entry(draft, result.text, request, reviewers, calls.rate)
    if result.ok and calls.translate:
        entry["translation"] = calls.translate(result.text, code)
    return entry


def new_data(requests: list, variants: list, meta: dict) -> dict:
    return {"format": FORMAT, "created": time.strftime("%Y-%m-%d %H:%M:%S"), "meta": meta, "variants": [v.as_dict() for v in variants],
            "requests": requests, "results": {}}


def save(data: dict, path: str) -> None:
    tmp = f"{path}.tmp"
    Path(tmp).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)


def load(path: str) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != FORMAT:
        raise ValueError(f"{path} is not a story-methods file")
    return data


def run(data: dict, variants: list, calls: Calls, *, conn=None, on_saved: Callable = lambda d: None,
        say: Callable = print, limit: Optional[int] = None, deadline: Optional[float] = None) -> bool:
    """Fill `data["results"]` for every request and variant that has no entry yet. True when everything was done, False when stopped
    (limit, Ctrl-C, a kill signal, the time budget `deadline` (time.monotonic) or `limit` requests reached). `on_saved(data)` is called after every story."""
    todo = [r for r in data["requests"]]
    if limit is not None:
        todo = todo[:limit]
    meta = data.setdefault("meta", {})
    meta.pop("stopped", None)                   # a resumed run starts clean: the reason below belongs to the run that wrote it

    def stopped(why: str, request: dict, variant) -> None:
        meta["stopped"] = f"{why} (at {request['id']}, {variant.name})"
        on_saved(data)
    skipped = [v.name for v in variants if v.examples and conn is None]
    if skipped:
        say(f"Skipping {', '.join(skipped)}: it needs the example bank (--db).")
    active = [v for v in variants if v.name not in skipped]
    for n, request in enumerate(todo, 1):
        row = data["results"].setdefault(request["id"], {})
        for variant in active:
            if variant.name in row:
                continue
            if deadline is not None and time.monotonic() >= deadline:
                stopped("the time budget (--max-minutes) ran out; stopped cleanly between two stories", request, variant)
                say("\nStopped: the time budget ran out. What is done is saved. Run again with --resume to continue.")
                return False
            try:
                entry = run_one(request, variant, calls, conn)
            except StopRun as stop:
                why = describe_error(stop)
                stopped(f"limit too long to wait for: {why}", request, variant)
                say(f"\nStopped: the limit is too long to wait for ({why}). Run again with --resume to continue.")
                return False
            except KeyboardInterrupt as stop:
                note = f" ({stop})" if str(stop) else ""
                stopped("interrupted" + note, request, variant)
                say(f"\nInterrupted{note}: what is done is saved. Run again with --resume to continue.")
                return False
            except Exception as exc:                # noqa: BLE001 - not caught: written down first, so the JSON says where and why it ended, then raised again
                stopped(f"crashed: {type(exc).__name__}: {scrub(exc)[:160]}", request, variant)
                raise
            row[variant.name] = entry
            on_saved(data)
            sc = (entry["score"] or {}).get("score")
            say(f"[{n}/{len(todo)}] {request['id']} {request['tier']:<6} {variant.name:<10} score {sc if sc is not None else '-':<5} "
                f"calls {entry['calls']:<2} {entry['seconds']:>6}s (model {entry['model_seconds']}s)" + ("" if entry["ok"] else f"  FAILED {entry['reason']}"))
    if limit is not None and limit < len(data["requests"]):
        meta["stopped"] = f"--limit {limit} reached (planned: {len(data['requests']) - limit} requests are left for --resume)"
        on_saved(data)
        return False
    return True


def estimate(requests: list, variants: list, audit: bool, translate: bool, tpm: int = 7000) -> dict:
    """Rough size of a run: model calls, tokens and minutes at the pacing limit (about 1800 tokens a call, a guess)."""
    from .variants import CALLS
    per = sum(CALLS.get(v.name, 3.0) + (2 if audit else 0) + (1 if translate else 0) for v in variants)
    calls = round(per * len(requests))
    tokens = calls * 1800
    return {"requests": len(requests), "variants": len(variants), "calls": calls, "tokens": tokens, "minutes": round(tokens / tpm)}
