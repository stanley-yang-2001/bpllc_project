"""Small statistics for the story report and the rating lab (16 Nov 2026), plain Python so nothing has to be installed.

Why they exist: the 15 November runs had 10 requests per method and ratings that took only three values (2, 3 and 4). With so few stories a gap of a few
points is mostly the luck of which requests were drawn. These functions put a range next to a number, so the page can say "within noise" instead of
showing a gap as if it were a difference."""
from __future__ import annotations

import math
from typing import Optional, Sequence

# the two-sided 95% t value for 1 to 30 degrees of freedom
T95 = (12.706, 4.303, 3.182, 2.776, 2.571, 2.447, 2.365, 2.306, 2.262, 2.228, 2.201, 2.179, 2.160, 2.145, 2.131, 2.120, 2.110, 2.101, 2.093, 2.086,
       2.080, 2.074, 2.069, 2.064, 2.060, 2.056, 2.052, 2.048, 2.045, 2.042)

# with this few pairs the sign test cannot reach p < 0.05 even when every pair points the same way (5 of 5 gives p = 0.0625)
MIN_PAIRS = 6


def t95(df: int) -> float:
    if df < 1:
        raise ValueError("a t value needs at least one degree of freedom")
    return T95[df - 1] if df <= len(T95) else 1.96 + 2.4 / df          # 2.0 at 60, 1.98 at 120: within 0.01 of the table


def mean(values: Sequence[float]) -> Optional[float]:
    values = [v for v in values if v is not None]
    return sum(values) / len(values) if values else None


def sd(values: Sequence[float]) -> Optional[float]:
    """The sample standard deviation (n - 1). None with fewer than two values."""
    v = [x for x in values if x is not None]
    if len(v) < 2:
        return None
    m = sum(v) / len(v)
    return math.sqrt(sum((x - m) ** 2 for x in v) / (len(v) - 1))


def requests_needed(spread: Optional[float], gap: float, z: float = 2.8) -> Optional[int]:
    """About how many paired requests it takes to see a mean change of `gap` when the change of a single request spreads like `spread` (its standard deviation).
    ((1.96 + 0.84) x spread / gap) squared, plus two for the t distribution: the usual 80% chance of a clear result at the 5% level. 30 requests with a spread of 0.5
    resolve about 0.26, and a gap of 0.15 takes about 90. None when the spread is missing or zero or the gap is not above zero."""
    if not spread or not gap or gap <= 0:
        return None
    return math.ceil((z * spread / gap) ** 2) + 2


def wilson(k: int, n: int, z: float = 1.96) -> Optional[tuple]:
    """The 95% Wilson range of a share: k of n. 4 of 10 is 17% to 69%, which is what ten requests can tell. None when n is 0."""
    if n <= 0:
        return None
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, centre - half), min(1.0, centre + half)


def mean_range(values: Sequence[float]) -> Optional[tuple]:
    """(mean, low, high): the mean and the 95% range it could really have (t interval). None with fewer than two values."""
    v = [x for x in values if x is not None]
    n = len(v)
    if n < 2:
        return None
    m = sum(v) / n
    sd = math.sqrt(sum((x - m) ** 2 for x in v) / (n - 1))
    half = t95(n - 1) * sd / math.sqrt(n)
    return m, m - half, m + half


def sign_test(better: int, worse: int) -> float:
    """The exact two-sided p of `better` against `worse` pairs if each pair were a coin flip (pairs that did not change are left out)."""
    n = better + worse
    if n == 0:
        return 1.0
    tail = sum(math.comb(n, i) for i in range(min(better, worse) + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def variance_share(groups: dict) -> Optional[float]:
    """The share of the variation in the values that the grouping explains ({group: [values]}), adjusted for the number of groups: ten groups of a few values
    explain about a tenth of anything by chance, so that is taken off (epsilon squared). 0 when the grouping explains no more than chance would."""
    groups = {g: [v for v in vs if v is not None] for g, vs in groups.items()}
    groups = {g: vs for g, vs in groups.items() if vs}
    allv = [v for vs in groups.values() for v in vs]
    n, k = len(allv), len(groups)
    if n < 3 or k < 2 or k >= n:
        return None
    grand = sum(allv) / n
    total = sum((v - grand) ** 2 for v in allv)
    if total == 0:
        return None
    between = sum(len(vs) * (sum(vs) / len(vs) - grand) ** 2 for vs in groups.values())
    return max(0.0, 1 - (1 - between / total) * (n - 1) / (n - k))


def icc(groups: dict) -> Optional[float]:
    """The share of the variation that lies BETWEEN the groups ({story: [its ratings]}): 1 means every repeat of a story gets the same rating and stories differ,
    0 means a rating says nothing about which story it was. One-way intraclass correlation (unequal group sizes allowed). None when it cannot be told."""
    groups = [[v for v in vs if v is not None] for vs in groups.values()]
    groups = [vs for vs in groups if vs]
    a, n = len(groups), sum(len(vs) for vs in groups)
    if a < 2 or n <= a:
        return None
    grand = sum(v for vs in groups for v in vs) / n
    ssb = sum(len(vs) * (sum(vs) / len(vs) - grand) ** 2 for vs in groups)
    ssw = sum((v - sum(vs) / len(vs)) ** 2 for vs in groups for v in vs)
    msb, msw = ssb / (a - 1), ssw / (n - a)
    k0 = (n - sum(len(vs) ** 2 for vs in groups) / n) / (a - 1)
    if msb + (k0 - 1) * msw == 0:
        return None
    return max(-1.0, min(1.0, (msb - msw) / (msb + (k0 - 1) * msw)))


def percent(value: Optional[float]) -> str:
    return "–" if value is None else f"{value * 100:.0f}%"


def percent_range(k: int, n: int) -> str:
    """'4 of 10 (17–69%)': a count with the range the share could really have."""
    r = wilson(k, n)
    return "–" if r is None else f"{k} of {n} ({r[0] * 100:.0f}–{r[1] * 100:.0f}%)"


def ranks(values: Sequence[float]) -> list:
    """Ranks from 1, ties sharing the average rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def spearman(a: Sequence[float], b: Sequence[float]) -> Optional[float]:
    """Rank correlation of two equally long lists (-1 to 1); None for fewer than 3 pairs or when one side never changes."""
    if len(a) != len(b) or len(a) < 3:
        return None
    ra, rb = ranks(a), ranks(b)
    ma, mb = sum(ra) / len(ra), sum(rb) / len(rb)
    va, vb = sum((x - ma) ** 2 for x in ra), sum((y - mb) ** 2 for y in rb)
    if not va or not vb:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(ra, rb)) / (va * vb) ** 0.5
