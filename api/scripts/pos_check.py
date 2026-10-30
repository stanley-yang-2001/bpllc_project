"""Part-of-speech check: does the tutor label words with the right category for each language?

Signs up a throwaway learner (@pos-check.invalid), adds words whose part of speech is not in doubt, asks the real route
(POST /api/words/label) to label them and compares with the expected category. The model decides, so a miss is listed, and the
check passes when at least 80 percent of the labels match (a single odd word should not fail a run). It also checks that every
label is one of the language's own categories (so Japanese gets adjective_i / adjective_na, never plain "adjective").

Needs the stack up with AI_MODE=live and a Groq key. Run from the project folder:

    docker compose exec api python scripts/pos_check.py
"""
import argparse
import secrets
import sys
import time

from meanings_check import Client, Report, with_retry

PASSWORD = "Pos-check-" + secrets.token_hex(6)
CASES = {
    "en": {"run": "verb", "table": "noun", "beautiful": "adjective", "quickly": "adverb", "under": "preposition", "because": "conjunction"},
    "es": {"correr": "verb", "mesa": "noun", "bonito": "adjective", "rápidamente": "adverb", "con": "preposition", "y": "conjunction"},
    "de": {"laufen": "verb", "Tisch": "noun", "schön": "adjective", "schnell": "adverb", "und": "conjunction"},
    "ja": {"食べる": "verb", "水": "noun", "高い": "adjective_i", "静か": "adjective_na", "ゆっくり": "adverb", "を": "particle"},
    "zh": {"吃": "verb", "水": "noun", "大": "adjective", "很": "adverb", "个": "measure_word"},
    "ko": {"먹다": "verb", "물": "noun", "크다": "adjective", "빨리": "adverb", "을": "particle"},
}
THRESHOLD = 0.8


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://localhost:8000")
    ap.add_argument("--delay", type=float, default=10)
    ap.add_argument("--keep", action="store_true")
    a = ap.parse_args()
    c = Client(a.base)
    email = f"check-{secrets.token_hex(5)}@pos-check.invalid"
    s, b = c.call("POST", "/api/auth/register", {"email": email, "password": PASSWORD, "display_name": "Pos check", "language": "en", "accept_privacy": True})
    if s != 201:
        sys.exit(f"could not create the throwaway learner ({s}): {b}")
    print(f"throwaway learner {email}")
    rep = Report()
    try:
        for lang, expected in CASES.items():
            ids = {}
            for w in expected:
                st, body = c.call("POST", "/api/words", {"language": lang, "word": w})
                if st != 201:
                    sys.exit(f"could not add {w!r} ({st}): {body}")
                ids[w] = body["id"]
            time.sleep(a.delay)
            st, body = with_retry(lambda: c.call("POST", "/api/words/label", {"language": lang, "ids": list(ids.values())}), a.delay)
            if st != 200:
                rep.check(f"{lang}: request", False, f"HTTP {st} {body.get('error') or body}")
                continue
            _, cats = c.call("GET", f"/api/words/parts-of-speech?language={lang}")
            _, listing = c.call("GET", f"/api/words?language={lang}&limit=200")
            got = {w["word"]: w["pos"] for w in listing["items"]}
            hits = [w for w, code in expected.items() if got.get(w) == code]
            print(f"        {lang}: {got}")
            rep.check(f"{lang}: every label is one of the language's own categories", all(v is None or v in cats["items"] for v in got.values()), "")
            rep.check(f"{lang}: at least {int(THRESHOLD * 100)}% of the labels are the expected ones", len(hits) / len(expected) >= THRESHOLD,
                      f"{len(hits)} of {len(expected)}; missed: {[(w, got.get(w), expected[w]) for w in expected if w not in hits]}")
    finally:
        if not a.keep:
            st, _ = c.call("POST", "/api/me/delete", {"password": PASSWORD})
            print("throwaway learner deleted" if st == 204 else f"could not delete the throwaway learner ({st}); delete {email} by hand")
    print(f"\n{len(rep.rows) - len(rep.failed)} of {len(rep.rows)} checks passed")
    for name in rep.failed:
        print(f"  FAILED: {name}")
    return 0 if not rep.failed else 1


if __name__ == "__main__":
    sys.exit(main())
