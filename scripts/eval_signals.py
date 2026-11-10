#!/usr/bin/env python3
"""Do offline, non-LLM signals judge a story the way I do? (10 Nov 2026). No Groq calls.

  docker run -d -p 8010:8010 erikvl87/languagetool                       # once; any LanguageTool server works
  pip install torch transformers                                          # only for --signals perplexity / worst_sentence
  PYTHONPATH=tutor_core:scripts python scripts/eval_signals.py scripts/*methods_*.json --signals languagetool,perplexity,worst_sentence

Reads saved story-methods runs, measures every story, and prints how strongly each signal (and the story score, and the model review's score)
agrees with the hand grades in scripts/data/hand_grades.json. Writes <out>.json with every number. Run it after the overnight run, so it
does not compete for Docker."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "tutor_core")]

from story_eval import agreement  # noqa: E402
from story_eval.signals import default_signals  # noqa: E402


def load_grades(path: Path) -> dict:
    """{(created, request id, variant): grade}"""
    raw = json.loads(path.read_text(encoding="utf-8"))["runs"]
    return {(c, rid, v): g for c, reqs in raw.items() for rid, row in reqs.items() for v, g in row.items()}


def collect(files, grades, signals, log=print):
    rows = []
    for f in files:
        data = json.loads(Path(f).read_text(encoding="utf-8"))
        by_id = {r["id"]: r for r in data["requests"]}
        for rid, row in data["results"].items():
            language = by_id[rid]["code"]
            for variant, e in row.items():
                if not e.get("ok") or not e.get("text"):
                    continue
                review = e.get("audit_union") or e.get("audit_score") or {}
                out = {"run": data["created"], "id": rid, "variant": variant, "language": language,
                       "hand": grades.get((data["created"], rid, variant)),
                       "score": (e.get("score") or {}).get("score"), "review": review.get("score")}
                for s in signals:
                    try:
                        out[s.name] = s.measure(e["text"], language)
                    except Exception as err:                       # one unreachable server must not lose the other signals
                        log(f"  {s.name} failed on {rid}/{variant}: {err}")
                        out[s.name] = None
                rows.append(out)
    return rows


def build(rows, signals):
    names = [s.name for s in signals]
    direction = {s.name: s.higher_is_better for s in signals} | {"score": True, "review": True}
    columns = ["score", "review"] + names
    graded = [r for r in rows if r["hand"] is not None]
    meta_cols = names
    agreement.meta_score(rows, meta_cols, direction)
    result = {c: agreement.correlate(graded, c) for c in columns + ["meta"]}
    for c in names:                                               # lower is better for most signals: say so in the sign
        if not direction[c] and result[c]["pearson"] is not None:
            result[c]["pearson_if_flipped"] = -result[c]["pearson"]
            result[c]["spearman_if_flipped"] = -result[c]["spearman"] if result[c]["spearman"] is not None else None
    return result


def table(result) -> str:
    lines = [f"{'signal':28} {'n':>3} {'pearson':>8} {'spearman':>9}   (signals where lower is better show the flipped value)"]
    for c, v in result.items():
        p = v.get("pearson_if_flipped", v["pearson"])
        s = v.get("spearman_if_flipped", v["spearman"])
        lines.append(f"{c:28} {v['n']:>3} {p if p is not None else '-':>8} {s if s is not None else '-':>9}")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="+", help="story-methods run JSON files")
    ap.add_argument("--signals", default="languagetool", help="comma list of: languagetool, perplexity, worst_sentence")
    ap.add_argument("--grades", default=str(HERE / "data" / "hand_grades.json"))
    ap.add_argument("--out", default="signals_report.json")
    args = ap.parse_args(argv)
    signals = default_signals([n.strip() for n in args.signals.split(",") if n.strip()])
    rows = collect(args.files, load_grades(Path(args.grades)), signals)
    result = build(rows, signals)
    Path(args.out).write_text(json.dumps({"rows": rows, "agreement": result}, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"{len(rows)} stories, {sum(1 for r in rows if r['hand'] is not None)} with a hand grade\n")
    print(table(result))
    print(f"\nwritten to {args.out}")


if __name__ == "__main__":
    main()
