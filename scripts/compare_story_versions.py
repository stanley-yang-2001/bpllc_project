"""Old story generation next to the new two-pass generation, side by side, scored 0 to 100 (6-7 Nov 2026).

For each sample the SAME request is made twice: the same learner words, the same kind and topic (one random generator per sample,
seeded the same way for both), once with the one-call pipeline (today's logic, untouched) and once with two-pass generation
(a draft without the word list, then a rewrite that uses the words; see tutor_core/two_pass.py). Both go through the same retry and
repair steps afterwards. Each story is scored with the story score (tutor_core/quality/score.py, docs/STORY-SCORING.md): six requirements
at equal weight, 0 to 100. The result is ONE HTML page with a tab per language (and a Summary tab first), plus the numbers in a JSON file.

Every language is covered by default. Because you may not read a language, each story also gets an English machine translation under
it, translated literally so that broken sentences show up as broken (--no-translate turns this off; a translation is a rough guide
only, and costs one more model call per story).

Costs Groq calls: about 1 (old) + 2 (new) per sample, plus retries and translations, so a full run takes a while. Keep --count small:

    docker compose exec langflow python /app/scripts/compare_story_versions.py --learner-id 197                       # every language, 2 samples each
    docker compose exec langflow python /app/scripts/compare_story_versions.py --learner-id 197 --languages de,ja --count 3 --delay 25

If the learner has no words in a language, 25 starter words are added first (the script only ever adds words; --no-seed turns that off).
The learner id must exist: it is the User ID shown in Settings. The page is written to ./scripts/compare_<time>.html (rewritten after
every language, so an interrupted run still leaves a page). The scores count only what code can count; judge the grammar by reading.
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


PART_LABELS = {"length": "Length", "own_words": "Your words", "uncommon": "Uncommon words", "sentence_length": "Sentence length",
               "grammar": "Grammar, fluency", "language_format": "Language, format"}


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


def score_of(version, words, code):
    """The story score of one version, or None when there is no story."""
    from tutor_core.quality import score_story
    if not version["ok"]:
        return None
    return score_story(version["text"], code, words, None, version["story_type"])


def make_pair(generate, conn, learner_id, code, call, seed, words=None, translate=None, **options):
    """Both versions of one request, scored when `words` is given and translated when `translate` is. `generate` is
    tutor_core.story.generate_story (or a stand-in in the tests); `translate(text, code)` returns English text or ""."""
    out = {}
    for label, two_pass in (("old", False), ("new", True)):
        counted = CountingCall(call)
        if label == "new" and out["old"]["story_type"] not in (None, "unknown"):
            options = {**options, "story_type": out["old"]["story_type"], "topic": out["old"]["topic"]}      # the same kind and topic as the old story
        result = generate(conn, learner_id, code, call_groq_fn=counted, use_cache=False, two_pass=two_pass, rng=random.Random(seed), **options)
        out[label] = {"text": result.text, "ok": result.ok, "reason": result.reason, "story_type": result.story_type, "topic": result.topic,
                      "calls": counted.calls, "seconds": round(counted.seconds, 1), "error": counted.error}
        out[label]["score"] = score_of(out[label], words, code) if words else None
        out[label]["translation"] = translate(result.text, code) if translate and result.ok else ""
    return out


def average(values):
    values = [v for v in values if v is not None]
    return round(sum(values) / len(values), 1) if values else None


def summarize(items):
    """Averages over a language's samples: score, calls and seconds per version, and how many samples each version won."""
    out = {}
    for label in ("old", "new"):
        versions = [i["pair"][label] for i in items]
        out[label] = {"score": average([v["score"]["score"] if v["score"] else None for v in versions]),
                      "calls": average([v["calls"] for v in versions]), "seconds": average([v["seconds"] for v in versions]),
                      "stories": sum(1 for v in versions if v["ok"])}
    wins = {"old": 0, "new": 0, "tie": 0}
    for i in items:
        a, b = (i["pair"][k]["score"] for k in ("old", "new"))
        if a and b:
            wins["tie" if a["score"] == b["score"] else ("new" if b["score"] > a["score"] else "old")] += 1
    out["wins"] = wins
    return out


def _bars(sc):
    if not sc:
        return ""
    rows = []
    for key, label in PART_LABELS.items():
        v = sc["parts"].get(key)
        shown = "not measured" if v is None else f"{v:g}"
        width = 0 if v is None else v
        rows.append(f"<tr><td>{label}</td><td class=bar><i style='width:{width}%'></i></td><td class=n>{shown}</td></tr>")
    t, m = sc.get("targets") or {}, sc.get("measured") or {}
    facts = ""
    if m:
        facts = (f"<p class=num>Length {m.get('length')} (target {t.get('length')}) · your words {m.get('own_words')} (target {t.get('own_words')}) · "
                 f"uncommon {m.get('uncommon_pct')}% (target {t.get('uncommon_pct')}%) · mean sentence {m.get('mean_sentence')}</p>")
    problems = "".join(f"<li>{html.escape(p)}</li>" for p in sc.get("problems") or [])
    return f"<table class=parts>{''.join(rows)}</table>{facts}" + (f"<ul class=prob>{problems}</ul>" if problems else "")


def _card(title, version, winner):
    sc = version["score"]
    if sc is None:
        big = "<div class=score>–</div>"
    elif sc["gated"]:
        big = f"<div class='score zero'>0 <small>gate: {html.escape(sc['gated'])}</small></div>"
    else:
        big = f"<div class=score>{sc['score']:g}<small> / 100{' · partly scored' if sc['partial'] else ''}</small></div>"
    badge = " <span class=win>higher score</span>" if winner else ""
    bad = "" if version["ok"] else f"<p class=bad>No story ({html.escape(str(version['reason']))}). {html.escape(version['error'] or '')}</p>"
    tr = f"<details><summary>English translation (machine, a rough guide)</summary><div class=text>{html.escape(version['translation'])}</div></details>" if version.get("translation") else ""
    return (f"<div class=card><h4>{html.escape(title)}{badge}</h4>{big}<div class=text>{html.escape(version['text'])}</div>{bad}{tr}"
            f"{_bars(sc)}<p class=num>{version['calls']} model call(s) · {version['seconds']} s</p></div>")


def _fmt(v):
    return "–" if v is None else f"{v:g}"


def render(samples, vocabularies, names=None):
    """One page: a Summary tab and one tab per language. `samples` is {language name: [{"code", "pair"}]}."""
    names = names or {}
    tabs, panels = [("summary", "Summary")], []
    rows = []
    for language, items in samples.items():
        sm = summarize(items)
        code = items[0]["code"] if items else language
        tabs.append((code, language))
        rows.append(f"<tr><td>{html.escape(language)}</td><td>{len(items)}</td><td>{_fmt(sm['old']['score'])}</td><td>{_fmt(sm['new']['score'])}</td>"
                    f"<td>{sm['wins']['new']} new · {sm['wins']['old']} old · {sm['wins']['tie']} tie</td>"
                    f"<td>{_fmt(sm['old']['calls'])} / {_fmt(sm['new']['calls'])}</td><td>{_fmt(sm['old']['seconds'])} / {_fmt(sm['new']['seconds'])}</td></tr>")
        body = [f"<h2>{html.escape(language)}</h2><p class=num>Your words: {html.escape(vocabularies.get(language, ''))}</p>",
                f"<p><b>Average score:</b> old {_fmt(sm['old']['score'])} · new {_fmt(sm['new']['score'])}. "
                f"<b>Higher score:</b> {sm['wins']['new']} new, {sm['wins']['old']} old, {sm['wins']['tie']} tie.</p>"]
        for n, item in enumerate(items, 1):
            old, new = item["pair"]["old"], item["pair"]["new"]
            so, sn = (old["score"] or {}).get("score"), (new["score"] or {}).get("score")
            label = f"{old['story_type'] or '-'} / {old['topic'] or '-'}"
            body.append(f"<h3>Sample {n}: {html.escape(label)}</h3><div class=row>"
                        f"{_card('Old: one call', old, so is not None and sn is not None and so > sn)}"
                        f"{_card('New: two passes', new, so is not None and sn is not None and sn > so)}</div>")
        panels.append((code, "".join(body)))
    summary = ("<h2>Summary</h2><p>Score 0 to 100 from six equally weighted requirements (see docs/STORY-SCORING.md). It counts length, your words, "
               "uncommon words, sentence length, grammar problems the code can see, and language and format. It cannot see a wrong verb ending: "
               "read the stories, using the translation if you do not read the language.</p>"
               "<table class=sum><tr><th>Language</th><th>Samples</th><th>Old score</th><th>New score</th><th>Higher score in</th><th>Calls old / new</th>"
               "<th>Seconds old / new</th></tr>" + "".join(rows) + "</table>")
    css = ("body{font:16px/1.5 system-ui,sans-serif;max-width:1200px;margin:1.5rem auto;padding:0 1rem;color:#1c1c1c}"
           "nav{display:flex;flex-wrap:wrap;gap:.4rem;margin:1rem 0;border-bottom:1px solid #ccc;padding-bottom:.6rem}"
           "nav button{font:inherit;padding:.4rem .9rem;border:1px solid #bbb;border-radius:6px;background:#f4f4f1;cursor:pointer}"
           "nav button[aria-selected=true]{background:#1c1c1c;color:#fff;border-color:#1c1c1c}"
           ".row{display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1.6rem}.card{border:1px solid #ccc;border-radius:8px;padding:1rem}"
           ".card h4{margin:.1rem 0 .3rem}.score{font-size:2rem;font-weight:700}.score small{font-size:.8rem;font-weight:400;color:#555}.score.zero{color:#a00}"
           ".text{white-space:pre-wrap;background:#f7f7f4;padding:.8rem;border-radius:6px;margin:.5rem 0}"
           ".num{font-size:.85rem;color:#555;margin:.4rem 0}.bad{color:#a00}.win{font-size:.75rem;background:#d9f0df;color:#145a2a;padding:.1rem .45rem;border-radius:99px;margin-left:.4rem}"
           "table.parts{width:100%;border-collapse:collapse;font-size:.85rem}.parts td{padding:.1rem .3rem}.parts .bar{width:50%;background:#ececE6;border-radius:4px}"
           ".parts .bar i{display:block;height:.6rem;background:#2f7d4f;border-radius:4px}.parts .n{text-align:right;width:6rem}"
           "table.sum{border-collapse:collapse;width:100%}.sum th,.sum td{border:1px solid #ccc;padding:.4rem .6rem;text-align:left}.prob{font-size:.85rem;color:#8a4b00}"
           "details summary{cursor:pointer;font-size:.85rem;color:#444}.panel[hidden]{display:none}@media(max-width:800px){.row{grid-template-columns:1fr}}")
    nav = "".join(f"<button role=tab aria-selected={'true' if i == 0 else 'false'} data-tab='{html.escape(c)}'>{html.escape(t)}</button>" for i, (c, t) in enumerate(tabs))
    panel_html = f"<section class=panel id='p-summary'>{summary}</section>" + "".join(f"<section class=panel id='p-{html.escape(c)}'>{b}</section>" for c, b in panels)
    js = ("<script>(function(){var b=document.querySelectorAll('nav button'),p=document.querySelectorAll('.panel');"
          "function show(k){b.forEach(function(x){x.setAttribute('aria-selected',x.dataset.tab===k?'true':'false')});"
          "p.forEach(function(x){x.hidden=x.id!=='p-'+k});history.replaceState(null,'','#'+k)}"
          "b.forEach(function(x){x.addEventListener('click',function(){show(x.dataset.tab)})});"
          "var h=location.hash.slice(1);show(document.getElementById('p-'+h)?h:'summary')})();</script>")
    return (f"<!doctype html><meta charset=utf-8><meta name=viewport content='width=device-width,initial-scale=1'><title>Old and new story generation</title>"
            f"<style>{css}</style><h1>Old and new story generation</h1><p>Left: today's one-call pipeline. Right: two-pass (draft, then adapt to your words). "
            f"Same words, kind and topic on both sides.</p><nav role=tablist>{nav}</nav>{panel_html}{js}")


def translator(call):
    """An English machine translation, literal on purpose so that broken sentences stay visibly broken. "" when it fails."""
    def translate(text, code):
        from tutor_core.languages import LANGUAGES
        if code == "en" or not text.strip():
            return ""
        prompt = (f"Translate this {LANGUAGES[code].name} text into English, line by line. Translate literally: keep every mistake, odd word or "
                  "broken sentence visible instead of fixing it. Answer with the translation only, no notes.\n\n<<<\n" + text + "\n>>>")
        try:
            return (call(prompt) or "").strip()
        except Exception:
            return ""
    return translate


def rescore(data):
    """The saved comparison with every story scored again by the current score. Offline: no database, no model. Returns the new data."""
    samples = {}
    for name, items in data["samples"].items():
        words = [w.strip() for w in (data["vocabularies"].get(name) or "").split(",") if w.strip()]
        samples[name] = []
        for item in items:
            pair = {}
            for label, version in item["pair"].items():
                version = dict(version)
                version["score"] = score_of(version, words, item["code"]) if words and version.get("text") and version.get("ok") else None
                pair[label] = version
            samples[name].append({"code": item["code"], "pair": pair})
    return {"learner_id": data.get("learner_id"), "vocabularies": data["vocabularies"], "samples": samples}


def save(samples, vocabularies, learner_id, out):
    with open(out, "w", encoding="utf-8") as f:
        f.write(render(samples, vocabularies))
    with open(out.rsplit(".", 1)[0] + ".json", "w", encoding="utf-8") as f:
        json.dump({"learner_id": learner_id, "vocabularies": vocabularies, "samples": samples}, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--learner-id", type=int, default=None)
    parser.add_argument("--languages", default="all", help="'all' (the default: every language), or names or codes separated by commas")
    parser.add_argument("--count", type=int, default=2, help="samples per language")
    parser.add_argument("--delay", type=float, default=20.0, help="seconds between samples (rate limit)")
    parser.add_argument("--story-type", default=None)
    parser.add_argument("--no-seed", action="store_true", help="do not add starter words when the learner has none in a language")
    parser.add_argument("--no-translate", action="store_true", help="no English translation under each story (saves one call per story)")
    parser.add_argument("--rescore", default=None, metavar="FILE.json", help="no model calls: score the stories saved in this earlier run again with the current score")
    parser.add_argument("--out", default=None, help="the .html file (default: /app/scripts/compare_<time>.html)")
    args = parser.parse_args()

    if args.rescore:
        with open(args.rescore, encoding="utf-8") as f:
            data = rescore(json.load(f))
        out = args.out or args.rescore.rsplit(".", 1)[0] + "_rescored.html"
        save(data["samples"], data["vocabularies"], data["learner_id"], out)
        print(f"Scored again with the current score: {out}")
        return 0
    from tutor_core import db as tc_db, groq as tc_groq, story as tc_story, vocab as tc_vocab
    from tutor_core.patient import patient
    call = patient(tc_groq.call_groq, say=print)       # waits out the 429 rate limit instead of failing the story
    from tutor_core.languages import LANGUAGES, normalize_language

    learner_id = args.learner_id
    if learner_id is None and (os.environ.get("TUTOR_DEV_USER_ID") or "").strip().isdigit():
        learner_id = int(os.environ["TUTOR_DEV_USER_ID"])
    if not learner_id:
        print("Say whose vocabulary to use: --learner-id N (or set TUTOR_DEV_USER_ID).")
        return 2
    os.environ.setdefault("STORY_ALLOW_UNMEASURED", "1")
    wanted = list(LANGUAGES) if args.languages.strip().lower() == "all" else [l.strip() for l in args.languages.split(",") if l.strip()]
    out = args.out or f"/app/scripts/compare_{time.strftime('%Y%m%d_%H%M%S')}.html"
    translate = None if args.no_translate else translator(call)
    conn, samples, vocabularies = tc_db.connect(), {}, {}
    try:
        for language in wanted:
            code = normalize_language(language)
            words = tc_vocab.load_words(conn, learner_id, code) if code else []
            if code and not words and not args.no_seed:
                words = seed_words(conn, learner_id, code)
            if not words:
                print(f"Skipping {language}: no words for learner {learner_id}.")
                continue
            name = LANGUAGES[code].name
            vocabularies[name], samples[name] = ", ".join(words), []
            for i in range(1, args.count + 1):
                pair = make_pair(tc_story.generate_story, conn, learner_id, code, call, seed=1000 + i, words=words,
                                 translate=translate, story_type=args.story_type)
                samples[name].append({"code": code, "pair": pair})
                a, b = (pair[k]["score"] for k in ("old", "new"))
                print(f"[{name} {i}/{args.count}] score old {a and a['score']} / new {b and b['score']} | calls {pair['old']['calls']} / {pair['new']['calls']}", flush=True)
                if i < args.count:
                    time.sleep(args.delay)
            save(samples, vocabularies, learner_id, out)
    except KeyboardInterrupt:
        print("\nInterrupted: writing what was collected so far.")
    finally:
        conn.close()
    if not samples:
        print("Nothing was compared.")
        return 1
    save(samples, vocabularies, learner_id, out)
    print(f"Saved: {out}  (open it in your browser; the same data is in the .json next to it)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
