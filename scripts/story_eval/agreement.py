"""How well do the offline signals agree with my hand grades and with the model reviews? (10 Nov 2026). Pure Python, no model calls.

Pearson and Spearman are computed within each run (a grade from another day is a different scale) and pooled after z-scoring per language,
so a language that is simply harder does not look like a better or worse signal."""
from __future__ import annotations

import math


def _mean(v):
    return sum(v) / len(v)


def pearson(x, y):
    if len(x) < 3:
        return None
    mx, my = _mean(x), _mean(y)
    sx = math.sqrt(sum((a - mx) ** 2 for a in x))
    sy = math.sqrt(sum((b - my) ** 2 for b in y))
    return None if sx == 0 or sy == 0 else round(sum((a - mx) * (b - my) for a, b in zip(x, y)) / (sx * sy), 3)


def ranks(v):
    order = sorted(range(len(v)), key=lambda i: v[i])
    out, i = [0.0] * len(v), 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            out[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return out


def spearman(x, y):
    return pearson(ranks(x), ranks(y)) if len(x) >= 3 else None


def zscores(values):
    m = _mean(values)
    s = math.sqrt(sum((a - m) ** 2 for a in values) / len(values))
    return [0.0 if s == 0 else (a - m) / s for a in values]


def standardise(rows, key):
    """Z-score `key` within each language (rows are dicts with 'language'); returns {row index: z}. Languages with fewer than 3 stories get none."""
    out = {}
    for lang in {r["language"] for r in rows}:
        idx = [i for i, r in enumerate(rows) if r["language"] == lang and r.get(key) is not None]
        if len(idx) >= 3:
            out.update(zip(idx, zscores([rows[i][key] for i in idx])))
    return out


def correlate(rows, column, target="hand"):
    """Pooled correlation of one column with the target after z-scoring both within language. Returns {n, pearson, spearman}."""
    a, b = standardise(rows, column), standardise(rows, target)
    common = sorted(set(a) & set(b))
    x, y = [a[i] for i in common], [b[i] for i in common]
    return {"n": len(common), "pearson": pearson(x, y), "spearman": spearman(x, y)}


def meta_score(rows, columns, higher_is_better):
    """The mean of the signs-adjusted z-scores of several signals: no fitting, so nothing to overfit with 38 grades. Adds 'meta' to each row it can."""
    zs = {c: standardise(rows, c) for c in columns}
    for i, row in enumerate(rows):
        parts = [zs[c][i] * (1 if higher_is_better[c] else -1) for c in columns if i in zs[c]]
        row["meta"] = round(_mean(parts), 3) if parts and len(parts) == len(columns) else None
    return rows


def report(rows, columns, target="hand"):
    return {c: correlate(rows, c, target) for c in columns}
