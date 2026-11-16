"""Re-rate saved stories to measure the 1 to 5 naturalness rating itself (16 Nov 2026; scripts/story_eval/ratinglab.py explains what is measured).

    python scripts/rate_texts.py --from writer_kaggle_30.json --reviewers gpt,qwen --prompts v1,v2 --repeats 3 --out rating_lab.json
    python scripts/rate_texts.py --resume rating_lab.json              # go on after a stop (a daily limit, a time budget)
    python scripts/rate_texts.py --report rating_lab.json              # the table again, no model calls

No story is written; each rating is one short call. 40 stories x 2 reviewers x 2 prompts x 3 repeats is 480 calls, which a free-tier day may not allow on one key: use --limit, --max-minutes
and --resume, or extra keys (GROQ_API_KEY_2, GROQ_QWEN_API_KEY_2 ...). Models: GROQ_MODEL for gpt, GROQ_QWEN_MODEL for qwen, as in run_story_methods.py."""
import argparse
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "tutor_core"), "/app/custom_components", "/app/scripts"]

from story_eval import health, ratinglab, runner  # noqa: E402


def _save(data: dict, path: str) -> None:
    import json
    tmp = f"{path}.tmp"
    Path(tmp).write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, path)
    Path(path.rsplit(".", 1)[0] + ".txt").write_text(ratinglab.text_report(data), encoding="utf-8")


def _load(path: str) -> dict:
    import json
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("format") != ratinglab.FORMAT:
        raise ValueError(f"{path} is not a rating-lab file")
    return data


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--from", dest="source", default=None, metavar="FILE.json", help="a story-methods file whose finished stories are rated")
    ap.add_argument("--variants", default=None, help="only these methods' stories, names separated by commas")
    ap.add_argument("--limit", type=int, default=None, help="only the first N stories")
    ap.add_argument("--reviewers", default="gpt,qwen", help="gpt and/or qwen")
    ap.add_argument("--prompts", default="v1,v2", help="v1 (the one in use) and/or v2 (sense and wording apart, level named)")
    ap.add_argument("--repeats", type=int, default=3, help="how many times each story is rated by each reviewer and prompt")
    ap.add_argument("--resume", default=None, metavar="FILE.json", help="continue a rating-lab file: only missing ratings are asked")
    ap.add_argument("--report", default=None, metavar="FILE.json", help="print the table of a rating-lab file, no model calls")
    ap.add_argument("--gpt-model", default=None)
    ap.add_argument("--qwen-model", default=None)
    ap.add_argument("--key-budget", type=int, default=0, metavar="TOKENS")
    ap.add_argument("--tpm", type=int, default=7000)
    ap.add_argument("--max-minutes", type=float, default=None)
    ap.add_argument("--out", default=None, help="the .json (a .txt table is written next to it)")
    args = ap.parse_args(argv)
    log = health.RunLog()

    if args.report:
        print(ratinglab.text_report(_load(args.report)))
        return 0
    reviewers = [x.strip() for x in args.reviewers.split(",") if x.strip()]
    prompts = [x.strip() for x in args.prompts.split(",") if x.strip()]
    if not reviewers or any(x not in ("gpt", "qwen") for x in reviewers) or not prompts or any(x not in ("v1", "v2") for x in prompts) or args.repeats < 1:
        log("--reviewers takes gpt and/or qwen, --prompts takes v1 and/or v2, --repeats at least 1.")
        return 2
    if args.resume:
        data, out = _load(args.resume), args.out or args.resume
        reviewers, prompts = data["reviewers"], data["prompts"]
    else:
        if not args.source:
            log("Give --from FILE.json (a story-methods file) or --resume FILE.json.")
            return 2
        stories = ratinglab.stories_from(runner.load(args.source), [x.strip() for x in args.variants.split(",")] if args.variants else None, args.limit)
        if not stories:
            log("No finished stories in that file.")
            return 2
        data, out = ratinglab.new_data(args.source, stories, reviewers, prompts, args.repeats), args.out or f"{HERE}/rating_lab_{time.strftime('%Y%m%d_%H%M%S')}.json"
    asked = len(data["stories"]) * len(reviewers) * len(prompts) * data["repeats"]
    log(f"{len(data['stories'])} stories, {asked} ratings in all ({len(data['ratings'])} already made).")
    if not os.environ.get("GROQ_API_KEY"):
        log("GROQ_API_KEY is not set.")
        return 2

    from tutor_core import groq, key_pool
    from tutor_core.patient import patient
    pools = {}

    def pool_of(base, model):
        tag = (base, model)
        if tag not in pools:
            pools[tag] = key_pool.KeyPool(key_pool.key_vars(base), args.key_budget, say=log)
        return pools[tag]
    names = {"gpt": args.gpt_model or os.environ.get("GROQ_MODEL") or groq.DEFAULT_MODEL, "qwen": args.qwen_model or os.environ.get("GROQ_QWEN_MODEL") or "qwen/qwen3.6-27b"}
    channels = {}
    for alias in reviewers:
        base, name = ("GROQ_QWEN_API_KEY" if alias == "qwen" else None), names[alias]
        raw = key_pool.rotating(lambda prompt, kv, _m=name, _a=alias: groq.call_groq(prompt, model=_m, effort="none" if _a == "qwen" else None, key_var=kv), pool_of(base, name))
        raw.model = name
        channels[alias] = runner.Channel(raw, lambda call: patient(call, tpm=args.tpm, say=log))
    data["meta"]["models"] = {a: names[a] for a in reviewers}
    rows = health.preflight({f"review {a}": c for a, c in channels.items()}, say=log)
    bad = health.fatal(rows)
    if bad:
        data["meta"]["stopped"] = "preflight failed, nothing was rated: " + "; ".join(f"{r['channel']}: {r['why']}" for r in bad)
        _save(data, out)
        log(data["meta"]["stopped"])
        return 1
    deadline = time.monotonic() + args.max_minutes * 60 if args.max_minutes else None
    done = ratinglab.run(data, channels, on_saved=lambda d: _save(d, out), say=log, deadline=deadline)
    _save(data, out)
    log(("Finished" if done else "Saved so far") + f": {out}\n\n" + ratinglab.text_report(data))
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main())
