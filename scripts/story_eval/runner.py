"""Run every request with every method, one story at a time, and save after each story (7 Nov 2026).

Rate limit: the story call is wrapped by `patient` (it keeps under the token limit and waits out a 429 hint), and the run goes request by
request, so an interrupted or limit-stopped run always has complete rows for the requests it reached. A story that failed ONLY because the limit
was too long to wait for (a daily limit) is not saved: stop, wait, run again with --resume and it is made then.

Time, per story (all in seconds):
    model_seconds  time spent inside model calls (the story's own calls, and the judge's)
    seconds        wall time from request to finished story, including waiting for the rate limit
    wait_seconds   seconds minus model_seconds: waiting for the limit plus the code's own time (tiny)
The review of grammar (--audit) and the translation are measured separately and never counted in the story's calls or seconds.
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
from tutor_core.story import story_from_words

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
    entry = {"text": result.text, "ok": result.ok, "reason": result.reason, "story_type": result.story_type, "topic": result.topic,
             "calls": n_calls, "seconds": round(wall, 1), "model_seconds": round(model, 1),
             "wait_seconds": round(max(0.0, wall - model), 1), "error": error, "notes": list(result.notes), "translation": "",
             "audit": None, "audit_seconds": None, "audit_score": None, "audits": {}, "audit_scores": {}, "audit_union": None, "models": {
                 "story": getattr(story_ch.meter.call, "model", None) or variant.story_model or "default",
                 "judge": (getattr(judge_ch.meter.call, "model", None) or variant.judge_model or "default") if variant.judge else None}}
    entry["gate"] = None
    entry["trace"] = list(getattr(result, "trace", ()) or [])
    entry["score"] = _score(result.text, result.ok, request)
    if result.ok:
        from tutor_core.story_gates import check as run_gates
        entry["gate"] = run_gates(result.text, code, request["words"], difficulty, request.get("story_type"))
    reviewers = calls.audits or ({"review": calls.audit} if calls.audit else {})
    if result.ok:
        for label, channel in reviewers.items():
            channel.reset()
            review = run_audit(channel.call, result.text, LANGUAGES[code].name)
            rating = rate_naturalness(channel.call, result.text, LANGUAGES[code].name) if calls.rate else None
            entry["audits"][label] = dict(review.as_dict(), seconds=round(channel.meter.seconds, 1),
                                          naturalness=rating.as_dict() if rating is not None else None)
            if review.ok or (rating is not None and rating.ok):
                entry["audit_scores"][label] = _score(result.text, True, request, review.hits if review.ok else None,
                                                      rating.score if rating is not None and rating.ok else None)
        if len(entry["audit_scores"]) > 1:
            from tutor_core.quality.score import merge_reviews
            entry["audit_union"] = _score(result.text, True, request, merge_reviews(*(
                [Hit(**h) for h in r["hits"]] for r in entry["audits"].values() if r.get("ok"))),
                combine_ratings([(r.get("naturalness") or {}).get("score") for r in entry["audits"].values()]))
        if entry["audits"]:
            first = next(iter(entry["audits"]))
            entry["audit"], entry["audit_seconds"] = entry["audits"][first], entry["audits"][first]["seconds"]
            entry["audit_score"] = entry["audit_scores"].get(first)
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
        say: Callable = print, limit: Optional[int] = None) -> bool:
    """Fill `data["results"]` for every request and variant that has no entry yet. True when everything was done, False when stopped
    (limit, Ctrl-C or `limit` requests reached). `on_saved(data)` is called after every story."""
    todo = [r for r in data["requests"]]
    if limit is not None:
        todo = todo[:limit]
    skipped = [v.name for v in variants if v.examples and conn is None]
    if skipped:
        say(f"Skipping {', '.join(skipped)}: it needs the example bank (--db).")
    active = [v for v in variants if v.name not in skipped]
    for n, request in enumerate(todo, 1):
        row = data["results"].setdefault(request["id"], {})
        for variant in active:
            if variant.name in row:
                continue
            try:
                entry = run_one(request, variant, calls, conn)
            except StopRun as stop:
                say(f"\nStopped: the rate limit is too long to wait for ({str(stop)[:160]}). Run again with --resume to continue.")
                return False
            except KeyboardInterrupt:
                say("\nInterrupted: what is done is saved. Run again with --resume to continue.")
                return False
            row[variant.name] = entry
            on_saved(data)
            sc = (entry["score"] or {}).get("score")
            say(f"[{n}/{len(todo)}] {request['id']} {request['tier']:<6} {variant.name:<10} score {sc if sc is not None else '-':<5} "
                f"calls {entry['calls']:<2} {entry['seconds']:>6}s (model {entry['model_seconds']}s)" + ("" if entry["ok"] else f"  FAILED {entry['reason']}"))
    return not (limit is not None and limit < len(data["requests"]))


def estimate(requests: list, variants: list, audit: bool, translate: bool, tpm: int = 7000) -> dict:
    """Rough size of a run: model calls, tokens and minutes at the pacing limit (about 1800 tokens a call, a guess)."""
    from .variants import CALLS
    per = sum(CALLS.get(v.name, 3.0) + (2 if audit else 0) + (1 if translate else 0) for v in variants)
    calls = round(per * len(requests))
    tokens = calls * 1800
    return {"requests": len(requests), "variants": len(variants), "calls": calls, "tokens": tokens, "minutes": round(tokens / tpm)}
