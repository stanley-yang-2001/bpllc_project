"""The command line: check passages pasted into a text file (scripts/vocab_adherence.py runs this)."""
from __future__ import annotations

from .passage import check_passage
from .reporting import summarize
from .variety import format_summary
import argparse
import re
import sys

def main(argv=None):
    parser = argparse.ArgumentParser(description="Check pasted passages against a vocabulary.")
    parser.add_argument("passages_file", help="text file; passages separated by a line with only ---")
    parser.add_argument("--words", help="comma-separated vocabulary")
    parser.add_argument("--words-file", help="file with one word (or phrase) per line")
    parser.add_argument("--max-oov", type=int, default=5, help="stray words tolerated per passage (0 = strict)")
    parser.add_argument("--strict-verbs", action="store_true")
    parser.add_argument("--max-unit-words", type=int, default=None, help="fail sentences/lines longer than this")
    args = parser.parse_args(argv)

    vocab = args.words or ""
    if args.words_file:
        with open(args.words_file, encoding="utf-8") as f:
            vocab += "," + f.read().replace("\n", ",")
    if not vocab.strip():
        parser.error("provide --words or --words-file")

    with open(args.passages_file, encoding="utf-8") as f:
        passages = [p.strip() for p in re.split(r"^\s*---\s*$", f.read(), flags=re.M) if p.strip()]

    results = []
    for i, passage in enumerate(passages, 1):
        r = check_passage(passage, vocab, max_oov=args.max_oov, strict_verbs=args.strict_verbs,
                          max_unit_words=args.max_unit_words)
        results.append(r)
        verdict = "PASS" if r["passed"] else "FAIL"
        extras = []
        if r["oov_words"]:
            extras.append(f"out-of-vocabulary: {r['oov_words']}")
        if not r["length_ok"]:
            extras.append(f"length {r['units']}")
        if not r["format_ok"]:
            extras.append("bad format")
        if r["leaked_plan"]:
            extras.append("leaked plan")
        print(f"#{i} [{verdict}] {r['style'] or 'failure'} {'; '.join(extras)}")
    print()
    print(format_summary(summarize(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())

