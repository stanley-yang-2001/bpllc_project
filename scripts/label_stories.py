"""Human labels for the story tests (17 Nov 2026; scripts/story_eval/labels.py says why).

    # 1. pick stories from saved runs and make the blind sheets, the zip to send, and the private key
    python scripts/label_stories.py build --from writer_kaggle_30.json,overnight_kaggle.json --out labeling_round2 [--languages fr,de] [--method-requests 4] [--per-verdict 6]

    # 2. when the filled files come back (a folder, or the files), compare them with the reviewers
    python scripts/label_stories.py analyze --key labeling_round2/label_key_PRIVATE.csv --labels returned_folder [--out joined.csv]

Send only story_labeling_set.zip. Keep label_key_PRIVATE.csv: it says which method wrote each text. Needs openpyxl (pip install openpyxl). No model calls, no network."""
import argparse
import csv
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "tutor_core")]

from story_eval import labels  # noqa: E402


def build(args) -> int:
    stories = []
    for f in [x.strip() for x in args.source.split(",") if x.strip()]:
        data = json.loads(Path(f).read_text(encoding="utf-8"))
        stories += labels.stories_of(data, Path(f).name)
    if args.languages != "all":
        keep = {x.strip().lower() for x in args.languages.split(",")}
        stories = [s for s in stories if s["code"] in keep]
    if not stories:
        print("No finished stories in those files (check --from and --languages).")
        return 2
    chosen = labels.pick(stories, method_requests=args.method_requests, per_verdict=args.per_verdict, seed=args.seed)
    made = labels.build(chosen, args.out)
    print(f"{len(chosen)} stories: " + ", ".join(f"{labels.language_name(c)} {n}" for c, n in made["counts"].items()))
    print(f"Send this:  {made['zip']}")
    print(f"Keep this:  {made['key']}  (names the method behind each text)")
    return 0


def analyze(args) -> int:
    key = labels.read_key(args.key)
    given = labels.read_labels(args.labels)
    if not given:
        print("No filled sheets found in --labels.")
        return 2
    unknown = sorted({i for answers in given.values() for i in answers} - set(key))
    if unknown:
        print("These ids are not in the key (a different round?): " + ", ".join(unknown[:10]))
        return 2
    result = labels.compare(key, given, args.humans_only)
    print(labels.text_report(result))
    if args.out:
        rows = labels.joined_rows(key, given)
        with open(args.out, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        print(f"Every answer next to the key: {args.out}")
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="pick stories and write the blind sheets, the zip and the private key")
    b.add_argument("--from", dest="source", required=True, metavar="A.json,B.json", help="story-methods files (the .json next to a report)")
    b.add_argument("--out", required=True, help="a folder for the zip and the key")
    b.add_argument("--languages", default="all", help="'all' or codes separated by commas (en,es)")
    b.add_argument("--method-requests", type=int, default=4, help="requests per language shown with every method that wrote them, for comparing methods (default 4)")
    b.add_argument("--per-verdict", type=int, default=6, help="more stories per language for each model verdict: passed, split, failed by every reviewer (default 6)")
    b.add_argument("--seed", type=int, default=1)
    a = sub.add_parser("analyze", help="compare the filled sheets with the reviewers")
    a.add_argument("--key", required=True, help="label_key_PRIVATE.csv of the round")
    a.add_argument("--labels", required=True, nargs="+", help="the filled .xlsx files, or a folder of them")
    a.add_argument("--humans-only", action="store_true", help="leave out a labeler whose sheet says it is a model (ChatGPT, an AI-assisted benchmark ...)")
    a.add_argument("--out", default=None, help="write every answer next to the key as a .csv")
    args = ap.parse_args(argv)
    return build(args) if args.cmd == "build" else analyze(args)


if __name__ == "__main__":
    sys.exit(main())
