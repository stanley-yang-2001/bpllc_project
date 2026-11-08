"""Refresh the example bank: write candidate stories from the starter-pack words, score them 0 to 100, and keep the best two per language.

A candidate replaces the lower of the two saved stories of its language only when it scores higher (the text and its score are replaced
together); a language with fewer than two saved stories takes whatever scores best until it has two. A story with score 0 (empty, wrong
language, leaked plan) never gets in. Candidates are written from the STARTER-PACK words of the language, never from a learner's list.

Run from the project folder (needs the stack up, a Groq key, and the 0016 migration, which the API applies on start):

    docker compose exec api python scripts/refresh_story_bank.py                       # every language, 2 rounds of 2 candidates
    docker compose exec api python scripts/refresh_story_bank.py --languages de,es --rounds 3 --per-round 3
    docker compose exec api python scripts/refresh_story_bank.py --two-pass            # candidates from the two-pass pipeline
    docker compose exec api python scripts/refresh_story_bank.py --status              # what is saved now; no model calls

Run it again whenever you like: it only ever improves what is saved. It stops with a failure code while any language has fewer than two.
"""
import argparse
import os
import random
import sys
import time

SEED_NOTE = "starter-pack words"


def starter_words(language):
    from tutor_core import starter
    seen, out = set(), []
    for pack in starter.pack_ids():
        for word, _gloss in starter.pack_words(pack, language):
            if word not in seen:
                seen.add(word)
                out.append(word)
    return out


def refresh_language(conn, language, *, rounds, per_round, call, two_pass=False, difficulty=None, delay=0.0, sleep=time.sleep, say=print,
                     words_for=starter_words, seed=None):
    """Candidates for one language; returns {"offered": n, "outcomes": [...]}. Stops early once two saved stories score GOOD_ENOUGH."""
    from tutor_core import example_bank as bank, story as tc_story
    from tutor_core.quality import score_story

    words = words_for(language)
    if not words:
        say(f"  {language}: no starter-pack words, skipped")
        return {"offered": 0, "outcomes": []}
    rng = random.Random(seed if seed is not None else time.time())
    outcomes = []
    for n in range(1, rounds * per_round + 1):
        result = tc_story.story_from_words(language, words, call, difficulty=difficulty, two_pass=two_pass, rng=rng)
        if not result.ok:
            outcomes.append("no story")
            say(f"  {language} #{n}: no story ({result.reason})")
        else:
            scored = score_story(result.text, language, words, difficulty, result.story_type)
            from tutor_core.story_gates import check as run_gates
            if difficulty and not run_gates(result.text, language, words, difficulty, result.story_type, score=scored)["passed"]:
                scored = dict(scored, passed=False)            # only stories that pass the free checks become few-shot examples
            outcome = bank.offer(conn, language, result.text, scored, story_type=result.story_type, topic=result.topic, two_pass=two_pass)
            outcomes.append(outcome)
            gate = f" (gate: {scored['gated']})" if scored["gated"] else ""
            say(f"  {language} #{n}: {result.story_type or '-'} / {result.topic or '-'}  score {scored['score']}{gate}  -> {outcome}")
        saved = bank.examples(conn, language)
        if len(saved) >= bank.SLOTS and all(not s["provisional"] for s in saved):
            break
        if n < rounds * per_round and delay:
            sleep(delay)
    return {"offered": len(outcomes), "outcomes": outcomes}


def status(conn, languages, say=print):
    """Prints what is saved; returns the languages that have fewer than two."""
    from tutor_core import example_bank as bank
    short = []
    for language in languages:
        saved = bank.examples(conn, language)
        scores = ", ".join(f"{s['score']}{' (provisional)' if s['provisional'] else ''}" for s in saved) or "nothing saved"
        say(f"{language}: {len(saved)} saved: {scores}")
        if len(saved) < bank.SLOTS:
            short.append(language)
    return short


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--languages", default="all", help="comma-separated codes, or 'all' (the default)")
    parser.add_argument("--rounds", type=int, default=2)
    parser.add_argument("--per-round", type=int, default=2, help="candidates per language in each round")
    parser.add_argument("--delay", type=float, default=20.0, help="seconds between model calls (rate limit)")
    parser.add_argument("--two-pass", action="store_true")
    parser.add_argument("--tier", default=None, choices=("easy", "medium", "hard"))
    parser.add_argument("--status", action="store_true", help="show what is saved; no model calls")
    args = parser.parse_args(argv)

    from tutor_core import db as tc_db, difficulty as d, groq as tc_groq
    from tutor_core.patient import patient
    from tutor_core.languages import LANGUAGES

    languages = list(LANGUAGES) if args.languages.strip().lower() == "all" else [c.strip() for c in args.languages.split(",") if c.strip()]
    bad = [c for c in languages if c not in LANGUAGES]
    if bad:
        print(f"Unknown language code(s): {', '.join(bad)}. Known: {', '.join(LANGUAGES)}")
        return 2
    os.environ.setdefault("STORY_ALLOW_UNMEASURED", "1")
    conn = tc_db.connect()
    try:
        if args.status:
            return 1 if status(conn, languages) else 0
        difficulty = d.resolve(args.tier) if args.tier else None
        for language in languages:
            print(f"{language} ({LANGUAGES[language].name}), {SEED_NOTE}:")
            refresh_language(conn, language, rounds=args.rounds, per_round=args.per_round, call=patient(tc_groq.call_groq, say=print), two_pass=args.two_pass,
                             difficulty=difficulty, delay=args.delay)
        print("\nSaved now:")
        short = status(conn, languages)
    finally:
        conn.close()
    if short:
        print(f"\nStill fewer than two stories: {', '.join(short)}. Run it again (a busy model service can fail a call).")
        return 1
    print("\nEvery language has two stories.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
