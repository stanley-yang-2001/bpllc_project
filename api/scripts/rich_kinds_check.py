"""Richer English kinds check: do diary, letter, place, routine, anecdote and story texts stay near the learner's own words?

Backlog card "Richer English kinds back into random picks". In the 21 Oct 2026 batches these kinds failed the stray-word check
every time, so a random English story is narration or dialogue only. Stories now get one more try when they have too many words
outside the list (tutor_core/story.py). This signs up a throwaway learner (@rich-kinds-check.invalid), adds 12 English words,
asks for each richer kind --count times through the running API and counts how many pass the site's own report.

It passes when at least 70 percent pass. If it does, put TUTOR_RICH_RANDOM=1 in .env and rebuild: a random English story may
then be any kind. If it fails, nothing changes for learners; send the table to Claude.

Needs the stack up with AI_MODE=live and a Groq key:

    docker compose exec api python scripts/rich_kinds_check.py
"""
import argparse
import secrets
import sys
import time

from meanings_check import Client, Report, with_retry

PASSWORD = "Rich-check-" + secrets.token_hex(6)
WORDS = ["water", "bread", "friend", "house", "morning", "market", "river", "window", "garden", "letter", "chair", "rain"]
KINDS = ["story", "diary", "letter", "place", "routine", "anecdote"]
THRESHOLD = 0.7


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--count", type=int, default=2, help="stories per kind")
    ap.add_argument("--delay", type=float, default=10)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    c = Client(a.base)
    email = f"check-{secrets.token_hex(5)}@rich-kinds-check.invalid"
    s, b = c.call("POST", "/api/auth/register", {"email": email, "password": PASSWORD, "display_name": "Rich kinds check", "language": "en", "accept_privacy": True})
    if s != 201:
        sys.exit(f"could not create the throwaway learner ({s}): {b}")
    print(f"throwaway learner {email}")
    rep, passed, total = Report(), 0, 0
    rows = []
    try:
        for w in WORDS:
            st, body = c.call("POST", "/api/words", {"language": "en", "word": w})
            if st != 201:
                sys.exit(f"could not add {w!r} ({st}): {body}")
        for kind in KINDS:
            ok_here = 0
            for _ in range(a.count):
                time.sleep(a.delay)
                st, body = with_retry(lambda: c.call("POST", "/api/stories/generate", {"language": "en", "story_type": kind}), a.delay)
                total += 1
                if st == 200 and body["report"].get("status") == "pass":
                    ok_here += 1
                    passed += 1
            rows.append((kind, ok_here, a.count))
            print(f"        {kind:<9} {ok_here} of {a.count} passed")
        share = passed / total if total else 0
        rep.check(f"at least {int(THRESHOLD * 100)}% of the richer-kind stories pass the site's own report", share >= THRESHOLD, f"{passed} of {total}")
    finally:
        if not a.keep:
            st, _ = c.call("POST", "/api/me/delete", {"password": PASSWORD})
            print("throwaway learner deleted" if st == 204 else f"could not delete the throwaway learner ({st}); delete {email} by hand")
    if not rep.failed:
        print("\nThe richer kinds hold up. To let a random English story be any kind: add TUTOR_RICH_RANDOM=1 to .env, then docker compose up -d --build.")
    return 0 if not rep.failed else 1


if __name__ == "__main__":
    sys.exit(main())
