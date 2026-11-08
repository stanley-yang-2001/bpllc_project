"""How well does each grammar layer find mistakes it is KNOWN to have missed or caught? (7 Nov 2026)

Takes scripts/data/grammar_probe.json: per language one clean text and a list of mistakes injected one at a time (right -> wrong). For
each layer it reports
    recall        injected mistakes found / injected (a hit must overlap the injected words)
    false alarms  hits on the CLEAN text (should be 0)
and, for the score, how far the grammar part drops for one injected mistake.

Layers: `rules` (built in, always), `languagetool` (when LANGUAGETOOL_URL is set), `audit` (when GROQ_API_KEY is set; uses GROQ_AUDIT_MODEL if
set, else the story model). The audit costs one call per text (about 60 calls for everything), spaced out so the free tier's token limit
holds; use --languages to run a few.

    python scripts/grammar_probe.py                      # built-in rules only (no network)
    python scripts/grammar_probe.py --audit --languages es,fr
    python scripts/grammar_probe.py --json probe.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path[:0] = [str(ROOT / "tutor_core"), str(ROOT / "scripts")]

from tutor_core.languages import LANGUAGES  # noqa: E402
from tutor_core.quality import score_story  # noqa: E402
from tutor_core.quality.grammar import builtin_hits  # noqa: E402
from tutor_core.quality.grammar.audit import AuditChecker  # noqa: E402
from tutor_core.quality.grammar import languagetool  # noqa: E402

DATA = ROOT / "scripts" / "data" / "grammar_probe.json"


def injected_span(clean: str, case: dict):
    text = clean.replace(case["right"], case["wrong"], 1)
    start = text.find(case["wrong"])
    return text, start, start + len(case["wrong"])


def caught(hits, start: int, end: int) -> bool:
    return any(h.start >= 0 and h.start < end and start < h.end for h in hits)


def probe(layers: dict, languages=None, words=()) -> dict:
    """{"layers": {name: {"recall", "false_alarms", "by_language": {code: [found, injected, false]}, "by_type": {...}}}, "score_drop": {...}}"""
    data = json.loads(DATA.read_text(encoding="utf-8"))["languages"]
    report = {"layers": {}, "score_drop": {}}
    for name, check in layers.items():
        found = total = false = 0
        per_lang, per_type = {}, {}
        for code, item in data.items():
            if languages and code not in languages:
                continue
            clean_false = len(check(item["clean"], code))
            f = 0
            for case in item["errors"]:
                text, start, end = injected_span(item["clean"], case)
                ok = caught(check(text, code), start, end)
                f += ok
                t = per_type.setdefault(case["type"], [0, 0])
                t[0] += ok
                t[1] += 1
            per_lang[code] = [f, len(item["errors"]), clean_false]
            found, total, false = found + f, total + len(item["errors"]), false + clean_false
        report["layers"][name] = {"recall": round(found / total, 3) if total else None, "found": found, "injected": total,
                                  "false_alarms": false, "by_language": per_lang, "by_type": per_type}
    drops = []
    for code, item in data.items():
        if languages and code not in languages:
            continue
        base = score_story(item["clean"], code, [], None, "story")["parts"]["grammar"]
        for case in item["errors"]:
            text, _, _ = injected_span(item["clean"], case)
            drops.append(base - score_story(text, code, [], None, "story")["parts"]["grammar"])
    report["score_drop"] = {"mean_points_per_injected_mistake": round(sum(drops) / len(drops), 1) if drops else None,
                            "share_that_lower_the_score": round(sum(1 for d in drops if d > 0) / len(drops), 3) if drops else None}
    return report


def build_layers(use_audit: bool):
    layers = {"rules": lambda text, code: builtin_hits(text, code)}
    lt = languagetool.from_env()
    if lt:
        layers["languagetool"] = lambda text, code: lt.check(text, code)
    if use_audit:
        from tutor_core import groq
        from tutor_core.patient import patient
        call = patient(groq.make_model_call("GROQ_AUDIT_MODEL", "GROQ_AUDIT_EFFORT") or groq.call_groq, say=print)
        checker = AuditChecker(call)
        layers["audit"] = lambda text, code: checker.check(text, code)
    return layers


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--audit", action="store_true", help="also run the model review (needs GROQ_API_KEY)")
    ap.add_argument("--languages", help="comma-separated codes, e.g. es,fr (default: all nine)")
    ap.add_argument("--json", help="write the full report to this file")
    args = ap.parse_args(argv)
    if args.audit and not os.environ.get("GROQ_API_KEY"):
        print("--audit needs GROQ_API_KEY")
        return 2
    report = probe(build_layers(args.audit), args.languages.split(",") if args.languages else None)
    for name, r in report["layers"].items():
        print(f"\n{name}: found {r['found']}/{r['injected']} injected mistakes (recall {r['recall']}), false alarms on clean text: {r['false_alarms']}")
        for code, (f, n, fa) in r["by_language"].items():
            print(f"   {LANGUAGES[code].name:<11} {f}/{n}   false alarms {fa}")
        print("   by type:", ", ".join(f"{t} {a}/{b}" for t, (a, b) in sorted(r["by_type"].items())))
    d = report["score_drop"]
    print(f"\nscore: one injected mistake lowers the grammar part by {d['mean_points_per_injected_mistake']} points on average; "
          f"{d['share_that_lower_the_score']:.0%} of them lower it at all (with the layers the score itself uses: built-in rules)")
    if args.json:
        Path(args.json).write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
