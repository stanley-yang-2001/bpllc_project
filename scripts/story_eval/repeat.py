"""Two saved runs of the same requests, compared (19 Nov 2026).

Why: the 16 and the 17 November runs made the same baseline on the same 30 English requests (the same words, levels and seeds) on two days. It passed 9 stories one day and 11 the
next, and 5 requests went up, 22 stayed and 3 went down: that spread is the noise any gain has to beat, and it came from comparing two files by hand. This module does it for any
two files, and it also compares a DIFFERENT method of one file with a method of the other (the rules prompt of 16 Nov against the cascade of 17 Nov), but only on requests that are
the same in both files (the same id, language, level and learner words; the story model samples, so the seed alone does not make the text the same).

Two runs are only comparable when their reviewers are: `meta_differences` lists what differs in how they were made (another reviewer model, another score version, a different number
of rating repeats), and the comparison page and the script print it next to the numbers, because a gap that comes from the reviewer is not a gap between the methods."""
from __future__ import annotations

from typing import Optional

from . import verdicts

# the settings of a run that change what a verdict means
COMPARABLE = ("story model", "judge model", "review model", "gpt model", "qwen model", "score_version", "rating repeats")


def same_request(a: dict, b: dict) -> bool:
    return all(a.get(k) == b.get(k) for k in ("id", "code", "tier", "words"))


def shared_requests(first: dict, second: dict) -> list:
    """The requests that are the same in both files, in the first file's order."""
    other = {r["id"]: r for r in second.get("requests") or []}
    return [r for r in first.get("requests") or [] if r["id"] in other and same_request(r, other[r["id"]])]


def meta_differences(first: dict, second: dict) -> list:
    """[(setting, in the first, in the second)] for the settings that differ and so may move a verdict. A setting missing from a file is shown as None."""
    a, b = first.get("meta") or {}, second.get("meta") or {}
    return [(k, a.get(k), b.get(k)) for k in COMPARABLE if a.get(k) != b.get(k)]


def _pairs(data: dict, method: str, requests: list) -> list:
    row = data.get("results") or {}
    return [(r, row[r["id"]][method]) for r in requests if method in (row.get(r["id"]) or {})]


def methods_of(data: dict) -> list:
    return [v["name"] for v in data.get("variants") or []]


def compare(first: dict, second: dict, method_a: str, method_b: Optional[str] = None) -> dict:
    """`method_a` of the first file against `method_b` (the same name by default) of the second, on the requests both files share: the paired comparison of passed stories, and
    how many requests are shared and what differs in how the files were made."""
    method_b = method_b or method_a
    shared = shared_requests(first, second)
    a, b = _pairs(first, method_a, shared), _pairs(second, method_b, shared)
    out = verdicts.paired_verdicts(a, b)
    out.update({"method_a": method_a, "method_b": method_b, "shared": len(shared), "differences": meta_differences(first, second),
                "passed_a": verdicts.decided(a)["pass"], "passed_b": verdicts.decided(b)["pass"],
                "reviewed_a": verdicts.decided(a)["stories"], "reviewed_b": verdicts.decided(b)["stories"]})
    return out


def same_method_everywhere(first: dict, second: dict) -> list:
    """Every method the two files have in common, each compared with itself: the run-to-run noise of each."""
    common = [m for m in methods_of(first) if m in methods_of(second)]
    return [compare(first, second, m) for m in common]


def text(rows: list) -> str:
    """The comparison as plain text for a terminal: one line per pair of methods."""
    if not rows:
        return "Nothing to compare: the two files have no request and method in common."
    out = []
    for c in rows:
        label = c["method_a"] if c["method_a"] == c["method_b"] else f"{c['method_a']} -> {c['method_b']}"
        if not c["requests"]:
            out.append(f"{label}: no request with a verdict in both files ({c['shared']} requests are the same in both).")
            continue
        own = ", ".join(f"{k} {v * 100:+.0f}" for k, v in c["by_reviewer"].items())
        out.append(f"{label}: {c['requests']} requests; passed {c['passed_a']} -> {c['passed_b']} of {c['reviewed_b']}; change {c['change'] * 100:+.0f} points "
                   f"({'–' if c['low'] is None else format(c['low'] * 100, '+.0f')} to {'–' if c['high'] is None else format(c['high'] * 100, '+.0f')}); "
                   f"{c['up']} better, {c['same']} same, {c['down']} worse; sign test p {c['p']:.3f}; each reviewer alone {own}; {c['reading']}"
                   + (f"; about {c['needed']} requests to see {c['wanted'] * 100:.0f} points" if c["needed"] else ""))
    diffs = rows[0]["differences"]
    if diffs:
        out.append("")
        out.append("The two files were made differently, so part of a gap may be the reviewers and not the methods:")
        out += [f"  {k}: {a} | {b}" for k, a, b in diffs]
    return "\n".join(out)
