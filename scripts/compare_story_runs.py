"""Two saved story-method runs of the same requests, compared (19 Nov 2026). No model call, no key: it only reads the two JSON files.

    python scripts/compare_story_runs.py scripts/writer_kaggle_30.json scripts/cascade_30.json
        every method the two files share, each against itself: how much a method moves between two runs (the noise a gain has to beat)
    python scripts/compare_story_runs.py a.json b.json --a rules --b cascade
        one method of the first file against a different method of the second, on the requests that are the same in both

A request counts only when its id, language, level and learner words are the same in both files. The numbers are the passed-stories comparison of the report (a story every
reviewer passes is worth 1, a split 0.5, a fail 0) with each reviewer alone, and the settings that differ between the two runs are printed under it: a gap that comes from another
reviewer model or another score version is not a gap between methods."""
import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "tutor_core")]

from story_eval import repeat, runner  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("first", help="the first saved run (.json)")
    ap.add_argument("second", help="the second saved run (.json)")
    ap.add_argument("--a", default=None, metavar="METHOD", help="a method of the first file (with --b: compare it with a method of the second)")
    ap.add_argument("--b", default=None, metavar="METHOD", help="a method of the second file (default: the same as --a)")
    args = ap.parse_args(argv)
    try:
        first, second = runner.load(args.first), runner.load(args.second)
    except (OSError, ValueError) as exc:
        print(f"Cannot read the runs: {exc}", file=sys.stderr)
        return 2
    if args.a or args.b:
        a = args.a or args.b
        missing = [(name, path, m) for name, path, data, m in (("first", args.first, first, a), ("second", args.second, second, args.b or a)) if m not in repeat.methods_of(data)]
        if missing:
            for name, path, m in missing:
                print(f"The {name} file ({path}) has no method '{m}'; it has: {', '.join(repeat.methods_of(first if name == 'first' else second))}", file=sys.stderr)
            return 2
        rows = [repeat.compare(first, second, a, args.b)]
    else:
        rows = repeat.same_method_everywhere(first, second)
    print(f"{len(repeat.shared_requests(first, second))} requests are the same in both files.\n")
    print(repeat.text(rows))
    return 0


if __name__ == "__main__":
    sys.exit(main())
