"""Text tools check: do pronunciation guides and translations work through the running API?

It signs up a throwaway learner (an address ending @text-tools-check.invalid), then asks the real routes for:

  1. Pronunciation of Chinese, Japanese and Korean words. These come from libraries on the server, so they need no model:
     pinyin with tone marks, romaji, Revised Romanization. Same answer every time. (Always checked.)
  2. Pronunciation of English words (IPA). The model writes these, so they are a guide, not a dictionary: the check
     wants one reading per word and `approximate` set to true. (Skipped with --no-model.)
  3. Translation of a short list of words, and of the lines of a story, from English into Spanish and into Chinese. The
     check wants one translation per line, none empty, and the target script for Chinese. (Skipped with --no-model.)

Needs the stack up. Parts 2 and 3 need AI_MODE=live and a Groq key (a few model calls; --delay pauses between them for
Groq's free-tier rate limit). Exit code 0 only if every check passed.

Run from the project folder:

    docker compose exec api python scripts/text_tools_check.py
    docker compose exec api python scripts/text_tools_check.py --no-model
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

PASSWORD = "Text-tools-check-" + secrets.token_hex(6)
HAN = re.compile(r"[一-鿿]")
TONE_MARKS = re.compile(r"[āáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜ]")

LIBRARY_CASES = [   # (language, words, expected kind, a check on one reading, what the check means)
    ("zh", ["你好", "谢谢", "朋友"], "pinyin", lambda r: bool(TONE_MARKS.search(r)), "pinyin with tone marks"),
    ("ja", ["ありがとう", "友達", "水"], "romaji", lambda r: bool(re.fullmatch(r"[A-Za-z' \-āīūēō]+", r)), "romaji in Latin letters"),
    ("ko", ["안녕하세요", "친구", "물"], "romanization", lambda r: bool(re.fullmatch(r"[A-Za-z' \-]+", r)), "Latin letters"),
]
ENGLISH_WORDS = ["water", "bread", "friend", "through", "island"]
STORY_LINES = ["Ana: Good morning, friend.", "Ben: Good morning. Do you want some bread?", "Ana: Yes, please. And some water."]


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
    """One retry after a pause when the shared model is busy (HTTP 429)."""
    status, body = call()
    if status == 429:
        time.sleep(max(delay, 15))
        status, body = call()
    return status, body


def check_libraries(c, rep):
    print("Pronunciation from libraries (no model)")
    for lang, words, kind, looks_right, meaning in LIBRARY_CASES:
        status, body = c.call("POST", "/api/pronounce", {"language": lang, "texts": words})
        if status != 200:
            rep.check(f"{lang}: request", False, f"HTTP {status} {body}")
            continue
        items = body.get("items", [])
        readings = [i.get("reading") or "" for i in items]
        rep.check(f"{lang}: kind is {kind}", body.get("kind") == kind, f"got {body.get('kind')}")
        rep.check(f"{lang}: not marked approximate (it is not model-written)", body.get("approximate") is False)
        rep.check(f"{lang}: one reading per word", len(items) == len(words) and all(readings), f"{readings}")
        rep.check(f"{lang}: readings look like {meaning}", all(looks_right(r) for r in readings if r), f"{readings}")
        status2, body2 = c.call("POST", "/api/pronounce", {"language": lang, "texts": words})
        rep.check(f"{lang}: same answer when asked again", status2 == 200 and body2.get("items") == items)


def check_ipa(c, rep, delay):
    print("English IPA (written by the model)")
    status, body = with_retry(lambda: c.call("POST", "/api/pronounce", {"language": "en", "texts": ENGLISH_WORDS}), delay)
    if status != 200:
        rep.check("en: request", False, f"HTTP {status} {body.get('error') or body}")
        return False
    items = body.get("items", [])
    readings = [i.get("reading") or "" for i in items]
    if any("stub reading" in r for r in readings):
        print("  SKIP  the API answers with its built-in stand-in (AI_MODE=stub), so the model checks mean nothing; set AI_MODE=live")
        return False
    rep.check("en: kind is ipa", body.get("kind") == "ipa", f"got {body.get('kind')}")
    rep.check("en: marked approximate (a guide, not a dictionary)", body.get("approximate") is True)
    rep.check("en: one reading per word", len(items) == len(ENGLISH_WORDS) and all(readings), f"{readings}")
    rep.check("en: readings are IPA-like (not the plain word, not a sentence)",
              all(r and r.lower() != w and len(r) < 40 for r, w in zip(readings, ENGLISH_WORDS)), f"{readings}")
    return True


def check_translation(c, rep, delay):
    print("Translation (written by the model)")
    for target, is_target_script in (("es", None), ("zh", lambda t: bool(HAN.search(t)))):
        for label, words, texts in (("words", True, ENGLISH_WORDS), ("story lines", False, STORY_LINES)):
            time.sleep(delay)
            status, body = with_retry(lambda: c.call("POST", "/api/translate", {"language": "en", "target_language": target, "texts": texts, "words": words}), delay)
            name = f"en to {target}, {label}"
            if status != 200:
                rep.check(name + ": request", False, f"HTTP {status} {body.get('error') or body}")
                continue
            items = body.get("items", [])
            out = [i.get("translation") or "" for i in items]
            rep.check(name + ": one translation per line", len(items) == len(texts) and all(out), f"{out}")
            rep.check(name + ": the original text is returned with each", [i.get("text") for i in items] == texts)
            if is_target_script:
                rep.check(name + ": written in the target script", all(is_target_script(t) for t in out), f"{out}")
            else:
                rep.check(name + ": not just the English back", all(t.strip().lower() != s.strip().lower() for t, s in zip(out, texts)), f"{out}")
    status, body = c.call("POST", "/api/translate", {"language": "en", "target_language": "en", "texts": ["hello"]})
    rep.check("same source and target language is refused", status in (400, 422), f"HTTP {status}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://localhost:8000", help="API address as seen from where the script runs")
    ap.add_argument("--no-model", action="store_true", help="only the library readings (zh, ja, ko); makes no model call")
    ap.add_argument("--delay", type=float, default=10, help="seconds between model calls (Groq's free tier is rate limited)")
    ap.add_argument("--keep", action="store_true", help="do not delete the throwaway learner afterwards")
    a = ap.parse_args()

    c = Client(a.base)
    email = f"check-{secrets.token_hex(5)}@text-tools-check.invalid"
    status, body = c.call("POST", "/api/auth/register", {"email": email, "password": PASSWORD, "display_name": "Text tools check",
                                                         "language": "en", "accept_privacy": True})
    if status != 201:
        sys.exit(f"could not create the throwaway learner ({status}): {body}")
    print(f"throwaway learner {email}")
    rep = Report()
    try:
        check_libraries(c, rep)
        if not a.no_model:
            if check_ipa(c, rep, a.delay):
                check_translation(c, rep, a.delay)
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
