"""Make stories in every language with every method, side by side, scored and TIMED, without breaking the Groq rate limit (7 Nov 2026).

The methods (scripts/story_eval/variants.py), each adding one idea to the one before:
    baseline    today's one-call pipeline
    range       + the prompt asks for a word range and names the level
    two_pass    + draft without the word list, then adapt it to the words
    candidates  + three adaptations of the draft, the best score kept
    judge       + a model reviews the best two for grammar (GROQ_JUDGE_MODEL, a different model if you can)
    repair      + names every missed requirement and rewrites (up to 2 calls)
    proofread   (two passes + one grammar-fixing call on every story)       only with --variants all or by name
    examples    (everything + a saved example from the bank)                needs --db

The requests are fixed (scripts/story_eval/fixed_set.py: 2 per language + 2 extra = 20, from the starter packs, so no learner and no
database), so a later run compares with this one. Per story it records the score, the calls, the seconds inside the model, the seconds in all
(waiting for the rate limit included) and what each step did. The page has a Summary tab and a tab per language, a column per method.

Rate limit: calls are paced to stay under the free tier's tokens per minute (--tpm, default 7000 of 8000) and a 429 is waited out. If the
limit is a long (daily) one the run stops and saves; run it again with --resume FILE.json. The file is saved after every story.

    docker compose exec langflow python /app/scripts/run_story_methods.py --dry-run                      # how big is the run?
    docker compose exec langflow python /app/scripts/run_story_methods.py --limit 4                      # first 4 requests, default methods
    docker compose exec langflow python /app/scripts/run_story_methods.py --audit                        # + an independent grammar review of every story
    docker compose exec langflow python /app/scripts/run_story_methods.py --resume /app/scripts/methods_20261108_010000.json
    docker compose exec langflow python /app/scripts/run_story_methods.py --rescore /app/scripts/methods_20261108_010000.json   # no model calls

Optional models (environment): GROQ_JUDGE_MODEL / GROQ_JUDGE_EFFORT for the judge; GROQ_AUDIT_MODEL / GROQ_AUDIT_EFFORT for --audit (use a model
other than the story's: a model marks its own writing leniently, and the free tier counts tokens per model, so a second model also eases the limit).
"""
import argparse
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path[:0] = [str(HERE), str(HERE.parent / "tutor_core"), "/app/custom_components", "/app/scripts"]

from story_eval import fixed_set, report, runner, variants as variant_set  # noqa: E402


def _out_path(args) -> str:
    if args.out:
        return args.out
    base = args.resume or args.rescore
    if base and args.rescore:
        return base.rsplit(".", 1)[0] + "_rescored.html"
    return f"{HERE}/methods_{time.strftime('%Y%m%d_%H%M%S')}.html"


def write_outputs(data: dict, html_path: str) -> None:
    runner.save(data, html_path.rsplit(".", 1)[0] + ".json")
    Path(html_path).write_text(report.render(data), encoding="utf-8")


def pick_requests(args) -> list:
    from tutor_core.languages import normalize_language
    wanted = None
    if args.languages.strip().lower() != "all":
        wanted = [normalize_language(x.strip()) for x in args.languages.split(",") if x.strip()]
        wanted = [c for c in wanted if c]
    fixed = wanted is None and args.count == 2
    return fixed_set.build(wanted, per_language=args.count, extras=fixed)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--variants", default="default", help="'default' (baseline to repair), 'all', or names separated by commas")
    ap.add_argument("--languages", default="all", help="'all' or names or codes separated by commas")
    ap.add_argument("--count", type=int, default=2, help="requests per language (2 with all languages is the fixed set of 20)")
    ap.add_argument("--limit", type=int, default=None, help="only the first N requests")
    ap.add_argument("--audit", action="store_true", help="an independent model lists grammar mistakes in every final story (one more call each)")
    ap.add_argument("--gpt-model", default=None, help="model for the 'gpt' side of the mix methods (default: GROQ_MODEL)")
    ap.add_argument("--qwen-model", default=None, help="model for the 'qwen' side (default: GROQ_QWEN_MODEL, else qwen/qwen3.6-27b: check the id in the Groq console)")
    ap.add_argument("--audit-models", default=None, help="reviewers of every story, e.g. 'gpt,qwen' (implies --audit): compares their grammar findings")
    ap.add_argument("--no-naturalness", action="store_true", help="with --audit: skip the 1-5 naturalness rating (saves one call per story and reviewer)")
    ap.add_argument("--no-translate", action="store_true", help="no English translation under each story (saves one call per story)")
    ap.add_argument("--db", action="store_true", help="connect to the database (needed for the 'examples' method)")
    ap.add_argument("--key-budget", type=int, default=0, metavar="TOKENS", help="switch to the next key for the same model BEFORE a key has spent about this many tokens (0: switch only when Groq refuses). "
                    "Extra keys are GROQ_API_KEY_2, _3 ... (and GROQ_QWEN_API_KEY_2, GROQ_JUDGE_API_KEY_2, GROQ_AUDIT_API_KEY_2) in .env")
    ap.add_argument("--tpm", type=int, default=7000, help="tokens per minute to stay under (free tier: 8000)")
    ap.add_argument("--resume", default=None, metavar="FILE.json", help="continue an earlier run: only missing stories are made")
    ap.add_argument("--rescore", default=None, metavar="FILE.json", help="no model calls: score the saved stories again with the current score")
    ap.add_argument("--dry-run", action="store_true", help="print the size of the run and stop")
    ap.add_argument("--out", default=None, help="the .html file (the .json is written next to it)")
    args = ap.parse_args(argv)

    if args.rescore:
        data = report.rescore(runner.load(args.rescore))
        out = _out_path(args)
        write_outputs(data, out)
        print(f"Scored again with the current score: {out}")
        return 0

    try:
        chosen = variant_set.resolve(args.variants)
    except ValueError as exc:
        print(exc)
        return 2
    requests = pick_requests(args)
    if args.limit is not None:
        requests = requests[:args.limit]
    if not requests:
        print("No requests: check --languages.")
        return 2
    reviewers = [x.strip() for x in (args.audit_models or "").split(",") if x.strip()]
    if any(x not in ("gpt", "qwen") for x in reviewers):
        print("--audit-models takes gpt and/or qwen.")
        return 2
    args.audit = args.audit or bool(reviewers)
    size = runner.estimate(requests, chosen, args.audit, not args.no_translate, args.tpm)
    print(f"{size['requests']} requests x {size['variants']} methods: about {size['calls']} model calls, {size['tokens']:,} tokens, "
          f"at least {size['minutes']} minutes at {args.tpm} tokens a minute.")
    if size["tokens"] > 150_000:
        print("That is more than the free tier's daily token allowance for one model may cover. Run it in parts with --limit N, then --resume; "
              "a second model for the judge and the review (GROQ_JUDGE_MODEL, GROQ_AUDIT_MODEL) has its own allowance.")
    from tutor_core import groq as _g
    print("Keys: story/gpt = " + _g.key_label() + "; qwen = " + _g.key_label("GROQ_QWEN_API_KEY") + "; judge = " + _g.key_label("GROQ_JUDGE_API_KEY")
          + "; review = " + _g.key_label("GROQ_AUDIT_API_KEY"))
    from tutor_core import key_pool as _kp
    extra = {base or "GROQ_API_KEY": len(_kp.key_vars(base)) for base in (None, "GROQ_QWEN_API_KEY", "GROQ_JUDGE_API_KEY", "GROQ_AUDIT_API_KEY")}
    print("Keys per family (the next one is used when a key hits its limit): " + ", ".join(f"{k} x{n}" for k, n in extra.items()) +
          (f"; switching early at {args.key_budget:,} tokens a key" if args.key_budget else "; switching only when Groq refuses"))
    if args.dry_run:
        return 0
    if not os.environ.get("GROQ_API_KEY"):
        print("GROQ_API_KEY is not set.")
        return 2

    from tutor_core import groq
    from tutor_core.patient import patient
    from compare_story_versions import translator
    os.environ.setdefault("STORY_ALLOW_UNMEASURED", "1")

    def wrap(call):
        return patient(call, tpm=args.tpm, say=print)

    from tutor_core import key_pool
    pools = {}

    def pool_of(base, model=None):
        """One pool per key family AND model (Groq counts the limit per model), so channels that share both share their blocks and their spend."""
        tag = (base, model or os.environ.get("GROQ_MODEL") or groq.DEFAULT_MODEL)
        if tag not in pools:
            pools[tag] = key_pool.KeyPool(key_pool.key_vars(base), args.key_budget, say=print)
        return pools[tag]

    def rotating_default(base=None, **kw):
        pool = pool_of(base)
        return key_pool.rotating(lambda prompt, kv: groq.call_groq(prompt, key_var=kv, **kw), pool)

    story = runner.Channel(rotating_default(), wrap)
    judge_raw = groq.make_model_call("GROQ_JUDGE_MODEL", "GROQ_JUDGE_EFFORT", "GROQ_JUDGE_API_KEY", pool=pool_of("GROQ_JUDGE_API_KEY", os.environ.get("GROQ_JUDGE_MODEL")))
    audit_raw = (groq.make_model_call("GROQ_AUDIT_MODEL", "GROQ_AUDIT_EFFORT", "GROQ_AUDIT_API_KEY", pool=pool_of("GROQ_AUDIT_API_KEY", os.environ.get("GROQ_AUDIT_MODEL"))) or rotating_default()) if args.audit else None
    names = {"gpt": args.gpt_model or os.environ.get("GROQ_MODEL") or groq.DEFAULT_MODEL,
             "qwen": args.qwen_model or os.environ.get("GROQ_QWEN_MODEL") or "qwen/qwen3.6-27b"}
    channels = {}

    def model_channel(alias):
        """One Channel (so one pacing meter) per model: Groq limits each model on its own."""
        if alias not in channels:
            name = names[alias]
            base = "GROQ_QWEN_API_KEY" if alias == "qwen" else None
            raw = key_pool.rotating(lambda prompt, kv, _m=name, _a=alias: groq.call_groq(prompt, model=_m, effort="none" if _a == "qwen" else None, key_var=kv),
                                    pool_of(base, name))
            raw.model = name
            channels[alias] = runner.Channel(raw, wrap)
        return channels[alias]

    audits = {a: model_channel(a) for a in reviewers} or None
    calls = runner.Calls(story, runner.Channel(judge_raw, wrap) if judge_raw else None, runner.Channel(audit_raw, wrap) if audit_raw and not audits else None,
                         None if args.no_translate else translator(wrap(groq.call_groq)), models=model_channel, audits=audits, rate=not args.no_naturalness)
    meta = {"story model": os.environ.get("GROQ_MODEL") or groq.DEFAULT_MODEL, "judge model": getattr(judge_raw, "model", None) or ("(story model)" if any(v.judge for v in chosen) else None),
            "review model": ", ".join(f"{a}={names[a]}" for a in reviewers) or ((getattr(audit_raw, "model", None) or "(story model)") if audit_raw else None),
            "gpt model": names["gpt"], "qwen model": names["qwen"]}
    from tutor_core.quality.score import SCORE_VERSION
    meta["score_version"] = SCORE_VERSION

    if args.resume:
        data = runner.load(args.resume)
        have = {v["name"] for v in data["variants"]}
        data["variants"] += [v.as_dict() for v in chosen if v.name not in have]
        data["meta"].update({k: v for k, v in meta.items() if v})
        out = args.out or args.resume.rsplit(".", 1)[0] + ".html"
        chosen = [variant_set.BY_NAME[v["name"]] for v in data["variants"] if v["name"] in variant_set.BY_NAME]
    else:
        data = runner.new_data(requests, chosen, meta)
        out = _out_path(args)

    conn = None
    if args.db:
        from tutor_core import db
        conn = db.connect()
    try:
        done = runner.run(data, chosen, calls, conn=conn, on_saved=lambda d: write_outputs(d, out), limit=args.limit)
    finally:
        if conn:
            conn.close()
    switches = [e for pool in pools.values() for e in pool.events]
    if switches:
        data["meta"]["key switches"] = "; ".join(switches)
        data["meta"]["key events"] = [dict(r, model=tag[1]) for tag, pool in pools.items() for r in pool.records]
    write_outputs(data, out)
    print(f"\n{'Finished' if done else 'Saved so far'}: {out}  (the numbers are in the .json next to it)")
    return 0 if done else 1


if __name__ == "__main__":
    sys.exit(main())
