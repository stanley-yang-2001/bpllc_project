"""Meanings check: does the tutor write meanings in the language the learner chose?

It signs up a throwaway learner (an address ending @meanings-check.invalid, English as their own language), adds a few words, and
asks the real route (POST /api/words/define) to write meanings in each way a learner can choose:

  1. their own language (English)             -> the meanings are English
  2. the studied language (Spanish)           -> the meanings are Spanish
  3. both                                     -> "English / Spanish" with both halves present
  4. one exact language chosen for this click -> French, for Spanish words
  5. the same for Japanese words, whose script is easy to tell from English

The model decides what it writes, so this is a heuristic: it looks for the right script, and for common function words of the
right language. A failure means "look at the meanings printed above it", not necessarily a bug. Needs the stack up with
AI_MODE=live and a Groq key (a handful of model calls; --delay pauses between them). Exit code 0 only if every check passed.

Run from the project folder:

    docker compose exec api python scripts/meanings_check.py
"""
import argparse
import http.cookiejar
import json
import re
import secrets
import sys
import time
import urllib.error
import urllib.request

PASSWORD = "Meanings-check-" + secrets.token_hex(6)
CJK = re.compile(r"[぀-ヿ㐀-鿿]")
SPANISH_MARKERS = {"de", "la", "el", "los", "las", "un", "una", "que", "para", "se", "en", "con", "es", "por", "del", "y", "lo"}
ENGLISH_MARKERS = {"the", "a", "an", "of", "to", "and", "is", "used", "for", "that", "in", "with", "or", "on", "you", "it", "your", "from"}
FRENCH_MARKERS = {"de", "le", "la", "les", "un", "une", "qui", "pour", "est", "du", "des", "que", "dans", "et", "en", "au", "avec"}

SPANISH_BY_MODE = {"native": ["agua", "pan", "casa"], "study": ["leche", "libro", "perro"], "both": ["gato", "mesa", "puerta"], "french": ["árbol", "ventana", "camino"]}
JAPANESE_BY_MODE = {"native": ["水", "犬"], "study": ["本", "家"]}


def tokens(text):
    return re.findall(r"[^\W\d_]+", text.casefold())


def looks_english(text):
    """ASCII letters only (no accents, no CJK) and at least one common English word."""
    return bool(text) and not CJK.search(text) and all(ord(c) < 128 for c in text) and bool(set(tokens(text)) & ENGLISH_MARKERS)


def looks_spanish(text):
    return bool(text) and not CJK.search(text) and bool(set(tokens(text)) & SPANISH_MARKERS) and not (set(tokens(text)) & ENGLISH_MARKERS - SPANISH_MARKERS and not re.search(r"[áéíóúñ¿¡]", text))


def looks_french(text):
    return bool(text) and not CJK.search(text) and bool(set(tokens(text)) & FRENCH_MARKERS) and not (set(tokens(text)) & ENGLISH_MARKERS - FRENCH_MARKERS)


def looks_japanese(text):
    return bool(CJK.search(text))


def both_halves(text, first, second):
    """"first / second": two non-empty parts, the first passing `first` and the second passing `second`."""
    parts = [p.strip() for p in text.split(" / ")]
    return len(parts) == 2 and all(parts) and first(parts[0]) and second(parts[1])


class Client:
    def __init__(self, base):
        self.base = base.rstrip("/")
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def call(self, method, path, body=None, timeout=180):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method,
                                     headers={"Content-Type": "application/json", "X-Requested-With": "tutor"})
        try:
            with self.opener.open(req, timeout=timeout) as r:
                raw = r.read()
                return r.status, (json.loads(raw) if raw else None)
        except urllib.error.HTTPError as e:
            raw = e.read()
            try:
                return e.code, json.loads(raw)
            except Exception:
                return e.code, {"message": raw.decode("utf-8", "replace")[:300]}


class Report:
    def __init__(self):
        self.rows = []

    def check(self, name, ok, detail=""):
        self.rows.append((name, ok))
        print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  ({detail})" if detail else ""))
        return ok

    @property
    def failed(self):
        return [n for n, ok in self.rows if not ok]


def with_retry(call, delay):
    status, body = call()
    if status == 429:
        time.sleep(max(delay, 15))
        status, body = call()
    return status, body


def add_words(c, language, words):
    ids = {}
    for w in words:
        s, b = c.call("POST", "/api/words", {"language": language, "word": w})
        if s != 201:
            sys.exit(f"could not add {w!r} ({s}): {b}")
        ids[w] = b["id"]
    return ids


def meanings_of(c, language, ids):
    s, b = c.call("GET", f"/api/words?language={language}&limit=200")
    by_id = {w["id"]: w["meaning"] or "" for w in b["items"]}
    return {w: by_id.get(i, "") for w, i in ids.items()}


def define(c, language, ids, delay, **extra):
    time.sleep(delay)
    return with_retry(lambda: c.call("POST", "/api/words/define", {"language": language, "ids": list(ids.values()), **extra}), delay)


def run_case(c, rep, delay, label, language, words, passes, **extra):
    ids = add_words(c, language, words)
    status, body = define(c, language, ids, delay, **extra)
    if status != 200:
        rep.check(f"{label}: request", False, f"HTTP {status} {body.get('error') or body}")
        return
    if body.get("defined", 0) == 0:
        print("  SKIP  nothing was defined; the API answers with its stand-in (AI_MODE=stub)? set AI_MODE=live")
    got = meanings_of(c, language, ids)
    print(f"        {label}: {got}")
    rep.check(f"{label}: every word got a meaning", all(got.values()), f"defined={body.get('defined')} failed={body.get('failed')}")
    rep.check(f"{label}: meanings are in the chosen language", all(passes(m) for m in got.values() if m), "")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://localhost:8000", help="API address as seen from where the script runs")
    ap.add_argument("--delay", type=float, default=10, help="seconds between model calls (Groq's free tier is rate limited)")
    ap.add_argument("--keep", action="store_true", help="do not delete the throwaway learner afterwards")
    a = ap.parse_args()

    c = Client(a.base)
    email = f"check-{secrets.token_hex(5)}@meanings-check.invalid"
    status, body = c.call("POST", "/api/auth/register", {"email": email, "password": PASSWORD, "display_name": "Meanings check",
                                                         "language": "en", "accept_privacy": True})
    if status != 201:
        sys.exit(f"could not create the throwaway learner ({status}): {body}")
    print(f"throwaway learner {email} (own language: English)")
    rep = Report()
    try:
        run_case(c, rep, a.delay, "es words, own language", "es", SPANISH_BY_MODE["native"], looks_english, meaning_mode="native")
        run_case(c, rep, a.delay, "es words, studied language", "es", SPANISH_BY_MODE["study"], looks_spanish, meaning_mode="study")
        run_case(c, rep, a.delay, "es words, both", "es", SPANISH_BY_MODE["both"], lambda m: both_halves(m, looks_english, looks_spanish), meaning_mode="both")
        run_case(c, rep, a.delay, "es words, French chosen for this click", "es", SPANISH_BY_MODE["french"], looks_french, meaning_language="fr")
        run_case(c, rep, a.delay, "ja words, own language", "ja", JAPANESE_BY_MODE["native"], lambda m: not looks_japanese(m), meaning_mode="native")
        run_case(c, rep, a.delay, "ja words, studied language", "ja", JAPANESE_BY_MODE["study"], looks_japanese, meaning_mode="study")
        # the saved account choice is what a click with no choice uses
        s, _ = c.call("PATCH", "/api/me/preferences", {"meaning_mode": "study"})
        rep.check("the account's meaning language can be saved", s == 200, f"HTTP {s}")
        run_case(c, rep, a.delay, "es words, saved choice (studied language)", "es", ["pared", "silla", "mano"], looks_spanish)
    finally:
        if not a.keep:
            s, _ = c.call("POST", "/api/me/delete", {"password": PASSWORD})
            print("throwaway learner deleted" if s == 204 else f"could not delete the throwaway learner ({s}); delete {email} by hand")
    print(f"\n{len(rep.rows) - len(rep.failed)} of {len(rep.rows)} checks passed")
    for name in rep.failed:
        print(f"  FAILED: {name}")
    return 0 if not rep.failed else 1


if __name__ == "__main__":
    sys.exit(main())
