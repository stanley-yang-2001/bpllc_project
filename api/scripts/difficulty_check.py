"""Difficulty check: makes real stories at each difficulty, in each language, through the running API, and prints what was
asked for against what was measured (the same report the site shows). Replaces trying each case by hand in Story Studio.

It signs up a throwaway learner (an address ending @difficulty-check.invalid), adds a small word list per language, generates
the stories, then deletes the learner. Needs the stack up with AI_MODE=live. Groq's free tier is slow, so there is a pause
between stories (--delay).

Run from the project folder:

    docker compose exec api python scripts/difficulty_check.py
    docker compose exec api python scripts/difficulty_check.py --languages zh,ja,ko --tiers easy,hard --count 2
    docker compose exec api python scripts/difficulty_check.py --languages es --tiers easy --show

Add --out /tmp/difficulty.json to keep every story and report in a file (inside the container). The summary table is
printed at the end; send it to Claude as it is.
"""
import argparse
import http.cookiejar
import json
import secrets
import sys
import time
import urllib.error
import urllib.request

WORDS = {   # small starter lists, one per language; stories must use at least the tier's number of these
    "en": ["water", "bread", "friend", "house", "morning", "market", "river", "window", "garden", "letter"],
    "es": ["agua", "pan", "amigo", "casa", "mañana", "mercado", "río", "ventana", "jardín", "carta"],
    "fr": ["eau", "pain", "ami", "maison", "matin", "marché", "rivière", "fenêtre", "jardin", "lettre"],
    "de": ["Wasser", "Brot", "Freund", "Haus", "Morgen", "Markt", "Fluss", "Fenster", "Garten", "Brief"],
    "it": ["acqua", "pane", "amico", "casa", "mattina", "mercato", "fiume", "finestra", "giardino", "lettera"],
    "pt": ["água", "pão", "amigo", "casa", "manhã", "mercado", "rio", "janela", "jardim", "carta"],
    "zh": ["水", "面包", "朋友", "房子", "早上", "市场", "河", "窗户", "花园", "信"],
    "ja": ["水", "パン", "友達", "家", "朝", "市場", "川", "窓", "庭", "手紙"],
    "ko": ["물", "빵", "친구", "집", "아침", "시장", "강", "창문", "정원", "편지"],
}
PASSWORD = "Difficulty-check-" + secrets.token_hex(6)


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


def row(language, tier, r):
    rep = r["report"]
    d = rep.get("difficulty") or {}
    m, req, met = d.get("measured", {}), d.get("requested", {}), d.get("met", {})
    mark = lambda v: "?" if v is None else ("ok" if v else "MISS")
    unc = m.get("uncommon_pct")
    return {
        "language": language, "tier": tier, "status": rep.get("status"),
        "length": f'{m.get("length")}/{round(req.get("length", 0) * (1.6 if m.get("length_unit") == "characters" else 1))} {mark(met.get("length"))}',
        "own": f'{m.get("own_words")}/{min(req.get("own_words", 0), d.get("list_size", 0))} {mark(met.get("own_words"))}',
        "uncommon": f'{"n/a" if unc is None else str(unc) + "%"}/{req.get("uncommon_pct")}% {mark(met.get("uncommon_pct"))}',
        "language_ok": (rep.get("language") or {}).get("verdict"),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://localhost:8000", help="API address as seen from where the script runs")
    ap.add_argument("--languages", default="en,es,fr,zh,ja,ko")
    ap.add_argument("--tiers", default="easy,medium,hard")
    ap.add_argument("--count", type=int, default=1, help="stories per language and tier")
    ap.add_argument("--delay", type=float, default=20, help="seconds between stories (Groq's free tier is rate limited)")
    ap.add_argument("--show", action="store_true", help="print every story as well")
    ap.add_argument("--out", help="write every story and report to this JSON file")
    ap.add_argument("--keep", action="store_true", help="do not delete the throwaway learner afterwards")
    a = ap.parse_args()
    languages = [x.strip() for x in a.languages.split(",") if x.strip()]
    tiers = [x.strip() for x in a.tiers.split(",") if x.strip()]
    bad = [x for x in languages if x not in WORDS]
    if bad:
        sys.exit(f"unknown language code(s) {bad}; choose from {', '.join(WORDS)}")

    c = Client(a.base)
    email = f"check-{secrets.token_hex(5)}@difficulty-check.invalid"
    status, body = c.call("POST", "/api/auth/register", {"email": email, "password": PASSWORD, "display_name": "Difficulty check",
                                                         "language": languages[0], "accept_privacy": True})
    if status != 201:
        sys.exit(f"could not create the throwaway learner ({status}): {body}")
    print(f"throwaway learner {email}")
    results, rows = [], []
    try:
        for lang in languages:
            for w in WORDS[lang]:
                s, b = c.call("POST", "/api/words", {"language": lang, "word": w})
                if s not in (200, 201):
                    print(f"  could not add {w!r} ({lang}): {s} {b}")
        n, total = 0, len(languages) * len(tiers) * a.count
        for lang in languages:
            for tier in tiers:
                for i in range(a.count):
                    n += 1
                    started = time.time()
                    s, b = c.call("POST", "/api/stories/generate", {"language": lang, "difficulty": tier})
                    if s == 429:
                        time.sleep(30)
                        s, b = c.call("POST", "/api/stories/generate", {"language": lang, "difficulty": tier})
                    if s != 200:
                        print(f"[{n}/{total}] {lang} {tier}: FAILED {s} {b.get('message') or b}")
                        rows.append({"language": lang, "tier": tier, "status": f"error {s}", "length": "", "own": "", "uncommon": "", "language_ok": ""})
                        results.append({"language": lang, "tier": tier, "error": b})
                    else:
                        r = row(lang, tier, b)
                        rows.append(r)
                        results.append({"language": lang, "tier": tier, "story": b["story"], "report": b["report"]})
                        print(f"[{n}/{total}] {lang} {tier}: {r['status']}  length {r['length']}  own {r['own']}  uncommon {r['uncommon']}  ({time.time() - started:.0f}s)")
                        if a.show:
                            print("-" * 60 + "\n" + b["story"].strip() + "\n" + "-" * 60)
                    if n < total:
                        time.sleep(a.delay)
    finally:
        if not a.keep:
            s, _ = c.call("POST", "/api/me/delete", {"password": PASSWORD})
            print("throwaway learner deleted" if s == 204 else f"could not delete the throwaway learner ({s}); delete {email} by hand")
    if a.out:
        with open(a.out, "w", encoding="utf-8") as f:
            json.dump(results, f, ensure_ascii=False, indent=1)
        print(f"written to {a.out}")

    cols = ["language", "tier", "status", "length", "own", "uncommon", "language_ok"]
    print("\nSUMMARY (measured/asked; MISS = target not met, ? = cannot be measured)")
    widths = [max(len(c_), *(len(str(r[c_])) for r in rows)) for c_ in cols]
    print("  ".join(c_.ljust(w) for c_, w in zip(cols, widths)))
    for r in rows:
        print("  ".join(str(r[c_]).ljust(w) for c_, w in zip(cols, widths)))
    good = sum(1 for r in rows if r["status"] == "pass")
    print(f"\n{good} of {len(rows)} stories passed their tier")
    return 0 if good == len(rows) else 1        # lets a test runner see a miss; reading the table is still the real check


if __name__ == "__main__":
    sys.exit(main())
