"""
Step 10 story batch runner — measures the story prompt, with the Agent out of the loop.

Calls the SAME pipeline the Story Generator Tool uses (tutor_core.story.generate_story:
load the learner's words in that language -> guard -> build prompt -> Groq -> extract passage), N times per language
with the cache off, for ONE learner (--learner-id, default $TUTOR_DEV_USER_ID) using that learner's own list for each language, then scores every result with vocab_adherence.py and records latency.

Why: a prompt change is only an improvement if a number moves. Run this before and after each
change to the story templates and compare the summaries.

Groq's free tier is rate limited (~8K tokens/minute per model, shared with the Language Agent),
so calls are spaced out by --delay seconds. Don't use the Playground at the same time.

Run from the project folder (Windows or Linux):

    docker compose exec langflow python /app/scripts/run_story_batch.py --learner-id 1 --count 15
    docker compose exec langflow python /app/scripts/run_story_batch.py --learner-id 1 --languages English,Spanish --count 8

Re-score a saved run under different rules (instant, no Groq calls):

    docker compose exec langflow python /app/scripts/run_story_batch.py --rescore /app/scripts/step10_results_<time>.json --max-oov 0

The vocabulary check only applies to English (the stored vocabulary is English); other
languages are checked for structure and latency only, and should also be read by a human.
Results are written to /app/scripts/step10_results_<timestamp>.json (visible in ./scripts).
"""

import argparse
import json
import sys
import time

sys.path.insert(0, "/app/custom_components")
sys.path.insert(0, "/app/scripts")

from vocab_adherence import (  # noqa: E402
    check_passage,
    format_summary,
    format_variety,
    rescore_results,
    summarize,
    variety_report,
)


def run_language(language, count, delay, conn, learner_id, words, max_oov, strict_verbs, max_unit_words=None, story_type=None):
    from tutor_core import groq as tc_groq, prompts as tc_prompts, story as tc_story  # imported here so --rescore needs neither Langflow nor a database
    from tutor_core.languages import normalize_language

    code = normalize_language(language)
    if code is None:
        raise ValueError(f"unknown language {language!r}")

    results = []
    for i in range(1, count + 1):
        seen = {}

        def timed_call_groq(prompt):
            started = time.time()
            try:
                out = tc_groq.call_groq(prompt)
                if not (out or "").strip():
                    seen["error"] = "empty response from the model"
                return out
            except Exception as exc:  # the story pipeline turns this into the fallback message
                seen["error"] = f"{type(exc).__name__}: {exc}"
                raise
            finally:
                seen["latency"] = time.time() - started
                seen["story_type"], seen["topic"] = tc_prompts.describe_prompt(prompt)

        text = tc_story.generate_story(
            conn, learner_id, code, call_groq_fn=timed_call_groq, use_cache=False, story_type=story_type
        ).text
        result = check_passage(
            text, words, check_vocab=(language.strip().lower() == "english"),
            max_oov=max_oov, strict_verbs=strict_verbs, max_unit_words=max_unit_words,
            language=language, vocab_in_target=(language.strip().lower() != "english"),
        )
        result.update(language=language, latency=seen.get("latency"), style_requested=seen.get("story_type"),
                      story_type=seen.get("story_type"), topic=seen.get("topic"), text=text,
                      error=seen.get("error"))
        results.append(result)

        status = "PASS" if result["passed"] else "FAIL"
        detail = result["oov_words"] if result["oov_words"] else ""
        latency = f"{result['latency']:.1f}s" if result["latency"] is not None else "n/a"
        kind = result.get("story_type") or result["style"] or "failure"
        why = f"  <- {result['error'][:90]}" if result.get("error") else ""
        print(f"[{language} {i}/{count}] {status} {kind} / {result.get('topic') or '-'} {latency} {detail}{why}", flush=True)
        if i < count:
            time.sleep(delay)
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--learner-id", type=int, default=None,
                        help="whose vocabulary to use (default: $TUTOR_DEV_USER_ID). Each language uses that learner's own list for it")
    parser.add_argument("--languages", default="English", help="comma-separated names or codes, e.g. English,Spanish or en,es")
    parser.add_argument("--count", type=int, default=15, help="stories per language")
    parser.add_argument("--delay", type=float, default=20.0, help="seconds between calls (rate limit)")
    parser.add_argument("--max-oov", type=int, default=5,
                        help="stray words tolerated per story (default 5, matching the prompt's 'at most 5 everyday "
                             "words'; earlier runs used 2; 0 = strict)")
    parser.add_argument("--story-type", default=None,
                        help="force one type (narration, dialogue, story, diary, letter, place, routine, anecdote); default random")
    parser.add_argument("--strict-verbs", action="store_true", help="only the prompt's six simple verbs are allowed")
    parser.add_argument("--max-unit-words", type=int, default=None, help="fail any sentence/line longer than this")
    parser.add_argument("--rescore", metavar="RESULTS_JSON",
                        help="re-score a saved results file under the current rules; no generation, no Groq calls")
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    if args.rescore:
        with open(args.rescore, encoding="utf-8") as f:
            data = json.load(f)
        rescored = rescore_results(data, max_oov=args.max_oov, strict_verbs=args.strict_verbs,
                                   max_unit_words=args.max_unit_words)
        print(f"Re-scored {args.rescore} with max_oov={args.max_oov}, strict_verbs={args.strict_verbs}, "
              f"max_unit_words={args.max_unit_words}\n")
        for language, results in rescored.items():
            print(f"=== {language} ===")
            print(format_summary(summarize(results)))
            print(format_variety(variety_report(results, (data.get("vocabularies") or {}).get(language) or data.get("vocabulary", ""), english=language.strip().lower() == "english")))
            print()
        return 0

    import os

    from tutor_core import db as tc_db, vocab as tc_vocab
    from tutor_core.languages import normalize_language

    learner_id = args.learner_id
    if learner_id is None and (os.environ.get("TUTOR_DEV_USER_ID") or "").strip().isdigit():
        learner_id = int(os.environ["TUTOR_DEV_USER_ID"])
    if not learner_id:
        print("Say whose vocabulary to use: --learner-id N (or set TUTOR_DEV_USER_ID).")
        return 2
    os.environ.setdefault("STORY_ALLOW_UNMEASURED", "1")        # this is the measurement script: it may test any language

    conn = tc_db.connect()
    all_results, vocabularies = {}, {}
    try:
        try:
            for language in [l.strip() for l in args.languages.split(",") if l.strip()]:
                code = normalize_language(language)
                if code is None:
                    print(f"Skipping {language!r}: not a supported language.")
                    continue
                words_list = tc_vocab.load_words(conn, learner_id, code)
                if not words_list:
                    print(f"Skipping {language}: learner {learner_id} has no {code} words yet (add some in the app, or through the Add Word tool).")
                    continue
                words = ", ".join(words_list)
                vocabularies[language] = words
                print(f"{language} vocabulary ({len(words_list)} entries): {words}\n")
                all_results[language] = run_language(
                    language, args.count, args.delay, conn, learner_id, words, args.max_oov, args.strict_verbs,
                    args.max_unit_words, args.story_type,
                )
        except KeyboardInterrupt:
            print("\nInterrupted: summarizing what was collected so far.")
    finally:
        conn.close()
    if not all_results:
        print("Nothing was measured.")
        return 1

    print()
    for language, results in all_results.items():
        print(f"=== {language} ===")
        print(format_summary(summarize(results)))
        print(format_variety(variety_report(results, vocabularies.get(language, ""), english=language.strip().lower() == "english")))
        print()

    out = args.out or f"/app/scripts/step10_results_{time.strftime('%Y%m%d_%H%M%S')}.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(
            {"vocabularies": vocabularies, "vocabulary": next(iter(vocabularies.values()), ""), "learner_id": learner_id, "max_oov": args.max_oov, "strict_verbs": args.strict_verbs, "results": all_results},
            f, ensure_ascii=False, indent=2,
        )
    print(f"Saved: {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
