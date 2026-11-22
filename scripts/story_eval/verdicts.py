"""What the model reviewers decided, as numbers (16 Nov 2026): one verdict per story, the methods compared request by request, results by word pack and level, and
what moves a rating. Works from the saved JSON alone, like the report; the page in report.py only draws what is computed here.

Why the report leads with these and not with the free score (the 15 November runs, 10 English requests, 4 methods, 2 reviewers):
  - the free score checks the brief (words, length, level) and is 91 to 100 on stories the reviewers failed, so it cannot tell a good story from a bad one;
  - a reviewed score has a cliff: a story a reviewer fails is multiplied by 0.6, so a coin-flip between a rating of 2 and 3 moves it by about 40 points;
  - the request (its word pack above all) moved the ratings far more than the method did, and ten requests are few, so a gap between two methods needs a range
    next to it before it can be read as a difference."""
from __future__ import annotations

import math
from typing import Iterable, Optional

from . import stats

PASS, SPLIT, FAIL = "pass", "split", "fail"
MIN_CHANGE = 0.2              # a reviewer's own mean change smaller than this does not count as a direction (ratings, 1 to 5)
MIN_PASS_CHANGE = 0.1         # the same for a reviewer's own change in the share of stories it passes (0 to 1): 3 stories of 30
VALUE = {PASS: 1.0, SPLIT: 0.5, FAIL: 0.0}      # what a verdict is worth in the comparison of passed stories
WANTED_GAP = 0.15             # the gain in passed stories that "requests needed" is asked about: 4 or 5 stories more of 30
MIN_RATINGS_FOR_FACTORS = 20


def failed(score) -> bool:
    """A review that fails the story: a rule failed it (unnatural, stuffed, too many mistakes, tacked-on words ...) or a free gate zeroed it."""
    return bool(score) and bool(score.get("failed") or score.get("gated"))


def verdict(entry) -> Optional[dict]:
    """One story's verdict from its reviews: 'pass' (no reviewer failed it), 'split' (some did) or 'fail' (every reviewer did). None when it was not made or no review
    worked, so a story nobody reviewed is never counted as a pass."""
    if not entry or not entry.get("ok"):
        return None
    scores = entry.get("audit_scores") or {}
    if not scores:
        return None
    bad = [label for label, sc in scores.items() if failed(sc)]
    kind = FAIL if len(bad) == len(scores) else PASS if not bad else SPLIT
    return {"kind": kind, "failed": bad, "reviewers": list(scores)}


def ratings(entry) -> dict:
    """{reviewer: 1 to 5 rating} for the reviewers whose rating worked."""
    out = {}
    for label, review in ((entry or {}).get("audits") or {}).items():
        value = (review.get("naturalness") or {}).get("score")
        if value is not None:
            out[label] = value
    return out


def reviewed_score(entry) -> Optional[float]:
    """One 0 to 100 score for a reviewed story: both reviewers together when there are two, else the only one. None when nobody reviewed it."""
    union = ((entry or {}).get("audit_union") or {}).get("score")
    if union is not None:
        return union
    values = [sc["score"] for sc in ((entry or {}).get("audit_scores") or {}).values() if sc.get("score") is not None]
    return round(sum(values) / len(values), 1) if values else None


def free_score(entry) -> Optional[float]:
    return ((entry or {}).get("score") or {}).get("score")


def decided(pairs: Iterable) -> dict:
    """For one method, from its (request, entry) pairs: how many stories every reviewer passed, split on, or every reviewer failed; the failed reviews, in all and
    for each reviewer; the mean rating of each reviewer; the 95% range of the share of stories every reviewer passed."""
    kinds = {PASS: 0, SPLIT: 0, FAIL: 0}
    reviews = bad_reviews = 0
    per_reviewer, rated = {}, {}
    for _, entry in pairs:
        v = verdict(entry)
        if v is None:
            continue
        kinds[v["kind"]] += 1
        for label, sc in entry["audit_scores"].items():
            slot = per_reviewer.setdefault(label, [0, 0])
            slot[0] += 1
            slot[1] += failed(sc)
            reviews += 1
            bad_reviews += failed(sc)
        for label, value in ratings(entry).items():
            rated.setdefault(label, []).append(value)
    n = sum(kinds.values())
    return {"stories": n, **kinds, "reviews": reviews, "failed_reviews": bad_reviews, "passed_range": stats.wilson(kinds[PASS], n),
            "failed_by": {label: tuple(slot) for label, slot in per_reviewer.items()}, "rating": {label: stats.mean(v) for label, v in rated.items()}}


def paired(base_pairs: Iterable, other_pairs: Iterable) -> dict:
    """Two methods compared request by request on the reviewers' 1 to 5 ratings (the same request, so the same words and level: that is what makes it fair).
    A request counts when both methods have a rating from at least one common reviewer. Returns the mean change with its 95% range, how many requests went
    up, stayed or went down, the sign test, each reviewer's own mean change and a reading in a few words that does not say more than the data can."""
    base = {r["id"]: e for r, e in base_pairs if e.get("ok")}
    changes, per_reviewer = [], {}
    up = down = same = 0
    for r, entry in other_pairs:
        before = base.get(r["id"])
        if before is None or not entry.get("ok"):
            continue
        x, y = ratings(before), ratings(entry)
        common = [label for label in x if label in y]
        if not common:
            continue
        change = round(stats.mean([y[label] - x[label] for label in common]), 6)
        changes.append(change)
        up, down, same = up + (change > 0), down + (change < 0), same + (change == 0)
        for label in common:
            per_reviewer.setdefault(label, []).append(y[label] - x[label])
    n = len(changes)
    span = stats.mean_range(changes)
    mean_change = stats.mean(changes)
    own = {label: stats.mean(v) for label, v in per_reviewer.items()}
    p = stats.sign_test(up, down)
    return {"requests": n, "change": mean_change, "low": span[1] if span else None, "high": span[2] if span else None, "up": up, "same": same, "down": down,
            "p": p, "by_reviewer": own, "reading": reading(n, span, p, own)}


def reading(n: int, span: Optional[tuple], p: float, own: dict, min_change: float = MIN_CHANGE) -> str:
    """'too few requests', 'reviewers disagree', 'clear gain', 'clear loss' or 'within noise'. A clear change needs the range to leave zero AND the sign test to
    agree AND no reviewer to go the other way: a model may rate its own kind of writing higher, so a gain only one reviewer sees is not counted.
    `min_change` is the size of a reviewer's own change that counts as a direction (0.2 of a rating point, or 0.1 of the stories it passes)."""
    if n < stats.MIN_PAIRS or span is None:
        return "too few requests"
    signs = {(v > 0) - (v < 0) for v in own.values() if abs(round(v, 2)) >= min_change}
    if len(own) > 1 and {1, -1} <= signs:
        return "reviewers disagree"
    if span[1] > 0 and p < 0.05:
        return "clear gain"
    if span[2] < 0 and p < 0.05:
        return "clear loss"
    return "within noise"


def paired_verdicts(base_pairs: Iterable, other_pairs: Iterable, wanted: float = WANTED_GAP) -> dict:
    """Two methods compared request by request on what the reviewers DECIDED: a story every reviewer passed is worth 1, a split 0.5, a failed one 0 (19 Nov 2026).
    The ratings comparison (`paired`) moves by a tenth of a point and read 'within noise' where this one separates the methods: the verdict is what the app cares about
    (is there a mistake or an unnatural passage a reader would see) and a rating of 2 or less is the line. A request counts when both methods have a verdict.
    Returns the mean change with its 95% range, requests that went up, stayed or went down, the sign test, each reviewer ALONE (the change in the share of stories it
    passed: the one from another model family is the one that cannot favour the writer), the spread of the changes, how many requests it would take to see a change of
    `wanted` at that spread, and a reading."""
    base = {r["id"]: e for r, e in base_pairs}
    changes, per_reviewer = [], {}
    up = down = same = 0
    for request, entry in other_pairs:
        after, before = verdict(entry), verdict(base.get(request["id"]))
        if after is None or before is None:
            continue
        change = VALUE[after["kind"]] - VALUE[before["kind"]]
        changes.append(change)
        up, down, same = up + (change > 0), down + (change < 0), same + (change == 0)
        for label in set(after["reviewers"]) & set(before["reviewers"]):
            per_reviewer.setdefault(label, []).append((label not in after["failed"]) - (label not in before["failed"]))
    n = len(changes)
    span = stats.mean_range(changes)
    spread = stats.sd(changes)
    own = {label: stats.mean(v) for label, v in per_reviewer.items()}
    p = stats.sign_test(up, down)
    return {"requests": n, "change": stats.mean(changes), "low": span[1] if span else None, "high": span[2] if span else None, "up": up, "same": same, "down": down,
            "p": p, "by_reviewer": own, "spread": spread, "needed": stats.requests_needed(spread, wanted), "wanted": wanted,
            "reading": reading(n, span, p, own, MIN_PASS_CHANGE)}


def by_group(pairs_by_method: dict, key: str) -> dict:
    """{group: {method: (failed reviews, reviews)}} for a request field such as 'pack' or 'tier'. Empty when the requests carry no such field or all share one value
    (a table of one row says nothing)."""
    out = {}
    for method, pairs in pairs_by_method.items():
        for request, entry in pairs:
            group = request.get(key)
            if group is None or not entry.get("ok") or not entry.get("audit_scores"):
                continue
            slot = out.setdefault(group, {}).setdefault(method, [0, 0])
            for sc in entry["audit_scores"].values():
                slot[0] += failed(sc)
                slot[1] += 1
    return {g: {m: tuple(v) for m, v in row.items()} for g, row in out.items()} if len(out) > 1 else {}


def rating_counts(all_pairs: Iterable) -> dict:
    """{rating: how many times it was given} over every reviewed story and reviewer. Shows how few of the five values are used (2, 3 and 4 on 15 Nov)."""
    out = {}
    for _, _, entry in all_pairs:
        for value in ratings(entry).values():
            out[value] = out.get(value, 0) + 1
    return dict(sorted(out.items()))


LINE = 2.0       # a naturalness rating of this or less fails a story (tutor_core.quality.score.GATE_NATURALNESS; a test keeps the two equal)


def _repeats(entry, label) -> list:
    """The ratings a reviewer gave one story when it was rated more than once (only then are they saved)."""
    nat = (((entry or {}).get("audits") or {}).get(label) or {}).get("naturalness") or {}
    return [x for x in (nat.get("repeats") or []) if x is not None]


def crossing(all_pairs: Iterable) -> dict:
    """{reviewer: (stories it rated more than once, of those the stories whose ratings fall on both sides of the pass line)} (21 Nov 2026, round 8: 42% of qwen's stories and 15% of gpt's).
    A story rated 2, 3, 3 passes and one rated 2, 2, 3 fails, so for these stories the verdict is the median of a coin flip and a new set of ratings can turn it over."""
    seen, crossed = {}, {}
    for _, _, entry in all_pairs:
        if not entry or not entry.get("ok"):
            continue
        for label in entry.get("audits") or {}:
            ratings_ = _repeats(entry, label)
            if len(ratings_) > 1:
                seen[label] = seen.get(label, 0) + 1
                crossed[label] = crossed.get(label, 0) + (min(ratings_) <= LINE < max(ratings_))
    return {label: (n, crossed.get(label, 0)) for label, n in seen.items()}


def _fails(n: int, p: float) -> float:
    """The chance that the median of n ratings (n odd) is on the failing side when each rating is, on its own, with chance p: more than half of them are."""
    return sum(math.comb(n, k) * p ** k * (1 - p) ** (n - k) for k in range(n // 2 + 1, n + 1))


def rerating(pairs: Iterable) -> Optional[dict]:
    """How far one method's passed-story count would move if the reviewers rated the same stories again (21 Nov 2026): {stories, passed, expected, sd}.
    Each reviewer's ratings of a story are taken as its own distribution (the share at 2 or less is the chance that one rating fails; the median of three fails with
    3p^2(1-p)+p^3), and a story another rule fails stays failed. Exact, no random draw. It is the reviewers' noise only: a new story for the same request would add the writer's.
    None unless most stories were rated three or more times (an odd number, so the median is one of the ratings)."""
    chances, repeated, passed = [], 0, 0
    for _, entry in pairs:
        if verdict(entry) is None:
            continue
        passed += verdict(entry)["kind"] == PASS
        scores = entry.get("audit_scores") or {}
        repeated += any(len(_repeats(entry, label)) >= 3 for label in scores)
        chance = 1.0
        for label, score in scores.items():
            if set(score.get("failed") or []) - {"unnatural"} or score.get("gated"):
                chance = 0.0
                break
            ratings_ = _repeats(entry, label)
            if len(ratings_) >= 3 and len(ratings_) % 2:
                chance *= 1.0 - _fails(len(ratings_), sum(x <= LINE for x in ratings_) / len(ratings_))
            else:                                       # one rating, or an even number: the result as it was
                chance *= 0.0 if "unnatural" in (score.get("failed") or []) else 1.0
        chances.append(chance)
    if not chances or repeated * 2 < len(chances):      # most stories were rated once: nothing to say about how the ratings vary
        return None
    return {"stories": len(chances), "passed": passed, "expected": sum(chances), "sd": math.sqrt(sum(c * (1 - c) for c in chances))}


def what_moves(all_pairs: Iterable) -> dict:
    """The share of the variation in all ratings that each of these explains, adjusted for how many groups it has: the request, its word pack, its level, the
    reviewer and the method. {} with fewer than 20 ratings. all_pairs holds (request, method, entry)."""
    rows = [(r, method, label, value) for r, method, e in all_pairs for label, value in ratings(e).items()]
    if len(rows) < MIN_RATINGS_FOR_FACTORS:
        return {}
    keys = {"request": lambda r, m, l: r["id"], "word pack": lambda r, m, l: r.get("pack"), "level": lambda r, m, l: r.get("tier"),
            "reviewer": lambda r, m, l: l, "method": lambda r, m, l: m}
    out = {}
    for name, key in keys.items():
        groups = {}
        for r, m, l, value in rows:
            g = key(r, m, l)
            if g is not None:
                groups.setdefault(g, []).append(value)
        share = stats.variance_share(groups)
        if share is not None:
            out[name] = share
    return out


def free_score_by_verdict(all_pairs: Iterable) -> dict:
    """{'pass'|'split'|'fail': {n, low, high, mean}} of the FREE score, to show what it cannot see: on 15 Nov it was 91 to 100 for stories every reviewer failed."""
    seen = {}
    for _, _, entry in all_pairs:
        v, score = verdict(entry), free_score(entry)
        if v is not None and score is not None:
            seen.setdefault(v["kind"], []).append(score)
    return {k: {"n": len(v), "low": min(v), "high": max(v), "mean": sum(v) / len(v)} for k, v in seen.items()}


def agreement(all_pairs: Iterable) -> tuple:
    """(stories two or more reviewers judged the same way, stories two or more reviewers judged): pass or fail, not the mistakes they listed."""
    both = same = 0
    for _, _, entry in all_pairs:
        scores = (entry.get("audit_scores") or {}) if entry.get("ok") else {}
        if len(scores) > 1:
            both += 1
            same += len({failed(sc) for sc in scores.values()}) == 1
    return same, both
