"""Old story generation next to the new two-pass generation, side by side (6 Nov 2026).

For each sample the SAME request is made twice: the same learner words, the same kind and topic (one random generator per sample,
seeded the same way for both), once with the one-call pipeline (today's logic, untouched) and once with two-pass generation
(a draft without the word list, then a rewrite that uses the words; see tutor_core/two_pass.py). Both go through the same retry and
repair steps afterwards. The result is one HTML page you open in a browser, plus the numbers in a JSON file.

Costs Groq calls: about 1 (old) + 2 (new) per sample, plus any retries, so keep --count small and the delay as in run_story_batch.py.

    docker compose exec langflow python /app/scripts/compare_story_versions.py --learner-id 1 --languages German,Spanish --count 2
    docker compose exec langflow python /app/scripts/compare_story_versions.py --learner-id 1 --languages Japanese --count 3 --delay 25

If the learner has no words in a language, 25 starter words are added first (the script only ever adds words; --no-seed turns that off).
The learner id must exist: it is the User ID shown in Settings. The page is written to ./scripts/compare_<time>.html. Read the stories yourself: the numbers below each text only count things that can
be counted (length, how many of your words appear, sentence problems the code can see); grammar and naturalness need a reader.
"""
import argparse
import html
import json
import os
import random
import sys
import time

sys.path.insert(0, "/app/custom_components")
sys.path.insert(0, "/app/scripts")


class CountingCall:
    """Wraps the model call: counts the calls and the seconds spent in them."""

    def __init__(self, call):
        self.call, self.calls, self.seconds, self.error = call, 0, 0.0, None

    def __call__(self, prompt):
        started = time.time()
        self.calls += 1
        try:
            return self.call(prompt)
        except Exception as exc:
            self.error = f"{type(exc).__name__}: {exc}"
            raise
        finally:
            self.seconds += time.time() - started


def stats(text, words, language, ok):
    from tutor_core import difficulty as d
    from tutor_core.quality import fluency_problems
    low = (text or "").casefold()
    present = [w for w in words if w.casefold() in low]
    return {"length": d.measure(text or "", language, words)["length"] if text else 0,
            "unit": "characters" if d.is_unspaced(language) else "words",
            "words_used": len(present), "words_total": len(words), "problems": fluency_problems(text or "", d.is_unspaced(language)) if ok else []}


def seed_words(conn, learner_id, code):
    """The learner has no words in this language: add the 25 starter words of scripts/seed_batch_words.py (it only ever ADDS words) and
    return the list. An unknown learner id, or a language with no starter list, gives []."""
    from tutor_core import vocab as tc_vocab
    import seed_batch_words
    if code not in seed_batch_words.WORDS:
        return []
    try:
        added = seed_batch_words.seed(conn, learner_id, [code])[code][0]
    except Exception as exc:
        conn.rollback()
        print(f"Could not add starter words for learner {learner_id} ({type(exc).__name__}). Is {learner_id} the User ID shown in Settings?")
        return []
    print(f"Added {added} starter words in {code} to learner {learner_id}.")
    return tc_vocab.load_words(conn, learner_id, code)


def make_pair(generate, conn, learner_id, code, call, seed, **options):
    """Both versions of one request. `generate` is tutor_core.story.generate_story (or a stand-in in the tests)."""
    out = {}
    for label, two_pass in (("old", False), ("new", True)):
        counted = CountingCall(call)
        if label == "new" and out["old"]["story_type"] not in (None, "unknown"):
            options = {**options, "story_type": out["old"]["story_type"], "topic": out["old"]["topic"]}      # the same kind and topic as the old story
        result = generate(conn, learner_id, code, call_groq_fn=counted, use_cache=False, two_pass=two_pass, rng=random.Random(seed), **options)
        out[label] = {"text": result.text, "ok": result.ok, "reason": result.reason, "story_type": result.story_type, "topic": result.topic,
                      "calls": counted.calls, "seconds": round(counted.seconds, 1), "error": counted.error}
    return out


def _card(title, version, words, language):
    s = stats(version["text"], words, language, version["ok"])
    problems = "".join(f"<li>{html.escape(p)}</li>" for p in s["problems"]) or "<li class=good>none found</li>"
    bad = "" if version["ok"] else f"<p class=bad>No story ({html.escape(str(version['reason']))}). {html.escape(version['error'] or '')}</p>"
    return (f"<div class=card><h3>{html.escape(title)}</h3><div class=text>{html.escape(version['text'])}</div>{bad}"
            f"<p class=num>{s['length']} {s['unit']} · your words used {s['words_used']} of {s['words_total']} · "
            f"{version['calls']} model call(s) · {version['seconds']} s</p><p class=num>Sentence problems the code can see:</p><ul>{problems}</ul></div>")


def render(samples, vocabularies):
    parts = ["<!doctype html><meta charset=utf-8><title>Old and new story generation</title><style>"
             "body{font:16px/1.5 system-ui,sans-serif;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#1c1c1c}"
             ".row{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:2rem}.card{border:1px solid #ccc;border-radius:8px;padding:1rem}"
             ".card h3{margin:.2rem 0 .6rem}.text{white-space:pre-wrap;font-size:1.05rem;background:#f7f7f4;padding:.8rem;border-radius:6px}"
             ".num{font-size:.85rem;color:#555;margin:.5rem 0 .2rem}.bad{color:#a00}.good{color:#276}h2{margin-top:2.2rem}"
             "@media(max-width:800px){.row{grid-template-columns:1fr}}</style>",
             "<h1>Old and new story generation</h1><p>Left: today's one-call pipeline. Right: two-pass (draft, then adapt to your words). "
             "Same words, kind and topic on both sides. The numbers count only what code can count; judge the grammar by reading.</p>"]
    for language, items in samples.items():
        parts.append(f"<h2>{html.escape(language)}</h2><p class=num>Your words: {html.escape(vocabularies.get(language, ''))}</p>")
        words = [w.strip() for w in vocabularies.get(language, "").split(",") if w.strip()]
        code = items[0]["code"] if items else ""
        for n, item in enumerate(items, 1):
            old, new = item["pair"]["old"], item["pair"]["new"]
            label = f"{old['story_type'] or '-'} / {old['topic'] or '-'}"
            parts.append(f"<h3>Sample {n}: {html.escape(label)}</h3><div class=row>{_card('Old: one call', old, words, code)}{_card('New: two passes', new, words, code)}</div>")
    return "".join(parts)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--learner-id", type=int, default=None)
    parser.add_argument("--languages", default="Spanish")
    parser.add_argument("--count", type=int, default=2, help="samples per language")
    parser.add_argument("--delay", type=float, default=20.0, help="seconds between model calls' groups (rate limit)")
    parser.add_argument("--story-type", default=None)
    parser.add_argument("--no-seed", action="store_true", help="do not add starter words when the learner has none in a language")
    parser.add_argument("--out", default=None, help="the .html file (default: /app/scripts/compare_<time>.html)")
    args = parser.parse_args()

    from tutor_core import db as tc_db, groq as tc_groq, story as tc_story, vocab as tc_vocab
    from tutor_core.languages import normalize_language

    learner_id = args.learner_id
    if learner_id is None and (os.environ.get("TUTOR_DEV_USER_ID") or "").strip().isdigit():
        learner_id = int(os.environ["TUTOR_DEV_USER_ID"])
    if not learner_id:
        print("Say whose vocabulary to use: --learner-id N (or set TUTOR_DEV_USER_ID).")
        return 2
    os.environ.setdefault("STORY_ALLOW_UNMEASURED", "1")
    conn, samples, vocabularies = tc_db.connect(), {}, {}
    try:
        for language in [l.strip() for l in args.languages.split(",") if l.strip()]:
            code = normalize_language(language)
            words = tc_vocab.load_words(conn, learner_id, code) if code else []
            if code and not words and not args.no_seed:
                words = seed_words(conn, learner_id, code)
            if not words:
                print(f"Skipping {language}: no words for learner {learner_id}.")
                continue
            vocabularies[language], samples[language] = ", ".join(words), []
            for i in range(1, args.count + 1):
                pair = make_pair(tc_story.generate_story, conn, learner_id, code, tc_groq.call_groq, seed=1000 + i, story_type=args.story_type)
                samples[language].append({"code": code, "pair": pair})
                print(f"[{language} {i}/{args.count}] old {pair['old']['calls']} call(s) {pair['old']['seconds']}s | new {pair['new']['calls']} call(s) {pair['new']['seconds']}s", flush=True)
                if i < args.count:
                    time.sleep(args.delay)
    except KeyboardInterrupt:
        print("\nInterrupted: writing what was collected so far.")
    finally:
        conn.close()
    if not samples:
        print("Nothing was compared.")
        return 1
    stamp = time.strftime("%Y%m%d_%H%M%S")
    out = args.out or f"/app/scripts/compare_{stamp}.html"
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(samples, vocabularies))
    with open(out.rsplit(".", 1)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump({"learner_id": learner_id, "vocabularies": vocabularies, "samples": samples}, f, ensure_ascii=False, indent=2)
    print(f"Saved: {out}  (open it in your browser; the same data is in the .json next to it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
