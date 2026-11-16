"""The rating lab (16 Nov 2026): how far can the 1 to 5 naturalness rating be trusted? Re-rates SAVED stories again and again, with each reviewer and each rating prompt,
and measures the rating itself instead of the methods. No story is written, so a run costs only short rating calls.

Asked of every (reviewer, prompt): does the same reviewer give the same rating to the same text (identical share, pass/fail flips)? how much of the variation lies between
stories (intraclass correlation) and how much is noise? do two reviewers agree, and does the new prompt agree better than the old? A prompt is better only if flips go down and
agreement goes up WITHOUT the ratings collapsing onto one value; the default prompt is not changed until this says so."""
from __future__ import annotations

import time
from typing import Callable, Optional

from tutor_core.languages import LANGUAGES
from tutor_core.naturalness import rate

from . import health, stats

FORMAT = "rating-lab-1"
FAIL_AT = 2.0                       # a rating at or below this fails a story (tutor_core.quality.score.GATE_NATURALNESS)
STOP_KINDS = ("rate_limit_long", "key", "model")


def stories_from(data: dict, variants: Optional[list] = None, limit: Optional[int] = None) -> list:
    """The finished stories of a story-methods file: [{key, id, variant, code, tier, text}]. The same text twice (two methods that left a draft alone) is rated once."""
    by_id = {r["id"]: r for r in data["requests"]}
    out, seen = [], set()
    for rid, row in data["results"].items():
        for name, e in row.items():
            if (variants and name not in variants) or not e.get("ok") or not (e.get("text") or "").strip() or (rid, e["text"]) in seen:
                continue
            seen.add((rid, e["text"]))
            r = by_id.get(rid) or {}
            out.append({"key": f"{rid}|{name}", "id": rid, "variant": name, "code": r.get("code", "en"), "tier": r.get("tier", ""), "text": e["text"]})
    return out[:limit] if limit else out


def new_data(source: str, stories: list, reviewers: list, prompts: list, repeats: int) -> dict:
    return {"format": FORMAT, "created": time.strftime("%Y-%m-%d %H:%M:%S"), "source": source, "reviewers": reviewers, "prompts": prompts, "repeats": repeats,
            "stories": stories, "ratings": {}, "meta": {}}


def rating_key(story: dict, reviewer: str, prompt: str, repeat: int) -> str:
    return f"{story['key']}|{reviewer}|{prompt}|{repeat}"


def run(data: dict, channels: dict, *, on_saved: Callable = lambda d: None, say: Callable = print, deadline: Optional[float] = None, rater: Callable = rate) -> bool:
    """Make every rating that is missing: story by story, so a stop leaves whole stories. True when all are made. A daily limit, a refused key or a wrong model id stops the
    run and says why in data['meta']['stopped']; a single failed call is kept with its error and counted, not retried (a resume asks it again)."""
    meta = data.setdefault("meta", {})
    meta.pop("stopped", None)
    for n, story in enumerate(data["stories"], 1):
        for repeat in range(data["repeats"]):
            for prompt in data["prompts"]:
                for reviewer in data["reviewers"]:
                    key = rating_key(story, reviewer, prompt, repeat)
                    if key in data["ratings"] and data["ratings"][key]["ok"]:
                        continue
                    if deadline is not None and time.monotonic() >= deadline:
                        meta["stopped"] = "the time budget (--max-minutes) ran out; stopped cleanly between two ratings"
                        on_saved(data)
                        return False
                    channel = channels[reviewer]
                    channel.reset()
                    try:
                        got = rater(channel.call, story["text"], LANGUAGES[story["code"]].name, prompt=prompt, level=story["tier"])
                    except KeyboardInterrupt as stop:
                        meta["stopped"] = "interrupted" + (f" ({stop})" if str(stop) else "")
                        on_saved(data)
                        return False
                    data["ratings"][key] = got.as_dict()
                    if not got.ok and health.classify(got.error) in STOP_KINDS:
                        meta["stopped"] = f"{health.describe_error(got.error)} (at {story['key']}, {reviewer}, {prompt})"
                        on_saved(data)
                        say(f"\nStopped: {meta['stopped']}. Run again with --resume to continue.")
                        return False
        on_saved(data)
        say(f"[{n}/{len(data['stories'])}] {story['key']}: " + ", ".join(f"{p} {r} {_row(data, story, r, p)}" for p in data["prompts"] for r in data["reviewers"]))
    return True


def _row(data: dict, story: dict, reviewer: str, prompt: str) -> str:
    got = [data["ratings"].get(rating_key(story, reviewer, prompt, i)) for i in range(data["repeats"])]
    return "/".join(f"{g['score']:g}" if g and g["ok"] else "?" for g in got)


def _values(data: dict, reviewer: str, prompt: str) -> dict:
    """{story key: [its ratings that worked, in repeat order]}"""
    out = {}
    for story in data["stories"]:
        v = [(data["ratings"].get(rating_key(story, reviewer, prompt, i)) or {}) for i in range(data["repeats"])]
        out[story["key"]] = [x["score"] for x in v if x.get("ok") and x.get("score") is not None]
    return out


def _pair_stats(a: dict, b: dict) -> dict:
    """Ratings of the same story and repeat from two sources: how often identical, within one point, and disagreeing on pass or fail; the mean of b minus a."""
    pairs = [(x, y) for k in a for x, y in zip(a[k], b.get(k, []))]
    n = len(pairs)
    if not n:
        return {"n": 0}
    return {"n": n, "identical": sum(x == y for x, y in pairs) / n, "within_one": sum(abs(x - y) <= 1 for x, y in pairs) / n,
            "passfail": sum((x <= FAIL_AT) != (y <= FAIL_AT) for x, y in pairs) / n, "shift": sum(y - x for x, y in pairs) / n}


def summarize(data: dict) -> dict:
    """The numbers: per (reviewer, prompt) the values used, repeatability and ICC; per prompt the reviewers' agreement; per reviewer the two prompts' agreement."""
    out = {"each": {}, "between_reviewers": {}, "between_prompts": {}, "asked": len(data["ratings"]), "failed_calls": sum(1 for r in data["ratings"].values() if not r["ok"])}
    for prompt in data["prompts"]:
        for reviewer in data["reviewers"]:
            vals = _values(data, reviewer, prompt)
            allv = [x for v in vals.values() for x in v]
            repeated = {k: v for k, v in vals.items() if len(v) > 1}
            n = len(repeated)
            out["each"][(reviewer, prompt)] = {
                "ratings": len(allv), "histogram": {k: allv.count(k) for k in sorted(set(allv))}, "mean": stats.mean(allv),
                "fail_share": (sum(x <= FAIL_AT for x in allv) / len(allv)) if allv else None,
                "stories_repeated": n, "identical": sum(len(set(v)) == 1 for v in repeated.values()) / n if n else None,
                "within_one": sum(max(v) - min(v) <= 1 for v in repeated.values()) / n if n else None,
                "flips": sum(min(v) <= FAIL_AT < max(v) for v in repeated.values()) / n if n else None, "icc": stats.icc(vals)}
    for prompt in data["prompts"]:
        for i, a in enumerate(data["reviewers"]):
            for b in data["reviewers"][i + 1:]:
                out["between_reviewers"][(a, b, prompt)] = _pair_stats(_values(data, a, prompt), _values(data, b, prompt))
    for reviewer in data["reviewers"]:
        for i, p in enumerate(data["prompts"]):
            for q in data["prompts"][i + 1:]:
                out["between_prompts"][(reviewer, p, q)] = _pair_stats(_values(data, reviewer, p), _values(data, reviewer, q))
    return out


def _pct(v) -> str:
    return "–" if v is None else f"{v * 100:.0f}%"


def text_report(data: dict) -> str:
    s = summarize(data)
    lines = [f"Rating lab: {len(data['stories'])} stories x {len(data['reviewers'])} reviewers x {len(data['prompts'])} prompt(s) x {data['repeats']} repeats "
             f"({s['asked']} ratings asked, {s['failed_calls']} did not work). Source: {data.get('source')}.", ""]
    if data.get("meta", {}).get("stopped"):
        lines += [f"STOPPED: {data['meta']['stopped']}. Run again with --resume.", ""]
    lines += ["Each reviewer and prompt (the same story rated again: how steady is it?)",
              f"{'reviewer':<9}{'prompt':<7}{'ratings':>8}  {'values used':<34}{'mean':>5}{'fail':>6}{'same':>6}{'±1':>6}{'flips':>7}{'ICC':>6}"]
    for (rv, pr), e in s["each"].items():
        used = ", ".join(f"{k:g}×{v}" for k, v in e["histogram"].items())
        lines.append(f"{rv:<9}{pr:<7}{e['ratings']:>8}  {used:<34}{'–' if e['mean'] is None else format(e['mean'], '.2f'):>5}{_pct(e['fail_share']):>6}"
                     f"{_pct(e['identical']):>6}{_pct(e['within_one']):>6}{_pct(e['flips']):>7}{'–' if e['icc'] is None else format(e['icc'], '.2f'):>6}")
    lines += ["", "same = every repeat identical; ±1 = repeats within one point; flips = repeats on both sides of the pass line; ICC = share of the variation that lies between stories", ""]
    if s["between_reviewers"]:
        lines.append("Two reviewers on the same story and repeat")
        for (a, b, pr), e in s["between_reviewers"].items():
            lines.append(f"  {a} vs {b}, prompt {pr}: " + ("no pairs" if not e["n"] else f"identical {_pct(e['identical'])}, within one {_pct(e['within_one'])}, disagree on pass/fail {_pct(e['passfail'])}, {b} minus {a} {e['shift']:+.2f}"))
        lines.append("")
    if s["between_prompts"]:
        lines.append("The same reviewer under two prompts")
        for (rv, p, q), e in s["between_prompts"].items():
            lines.append(f"  {rv}, {p} vs {q}: " + ("no pairs" if not e["n"] else f"identical {_pct(e['identical'])}, within one {_pct(e['within_one'])}, disagree on pass/fail {_pct(e['passfail'])}, {q} minus {p} {e['shift']:+.2f}"))
        lines.append("")
    lines.append("A prompt is better only if flips fall and the reviewers agree more, with several values still in use.")
    return "\n".join(lines) + "\n"
