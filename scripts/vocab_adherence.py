"""
Vocabulary adherence checker — Step 10 (LO 7: write and iterate on a constrained prompt).

Scores a generated story/dialogue against the learner's vocabulary so that prompt changes can
be measured instead of guessed at. It encodes the rules the story prompt itself states:

  * words must come from the vocabulary (inflections of a word are fine: same root),
  * basic grammar words and simple verbs are allowed ("is, have, want, like, go, see"),
  * character names are allowed,
  * 5-6 short sentences (narration) or lines (dialogue), dialogue lines as "Name: line",
  * no leaked planning text, and never an empty passage.

The vocabulary check only makes sense for English passages, because the stored vocabulary is
English. For other languages call check_passage(..., check_vocab=False): structure is still
checked and the vocabulary check is skipped.

Pure functions only (no database, no network) so they can be tested directly — see
tests/test_vocab_adherence.py. The CLI at the bottom checks passages pasted into a text file:

    python scripts/vocab_adherence.py passages.txt --words "hello, water, friend"

(passages are separated by a line containing only ---).
"""

import argparse
import itertools
import math
import re
import sys
from collections import Counter

# Messages the story tool returns instead of a story. Matched loosely, after apostrophe
# normalization, so small wording changes in story_tool.py don't break the checker.
FAILURE_MARKERS = (
    "having trouble generating a story",
    "don't have any vocabulary yet",
)

LEAK_PATTERN = re.compile(r"===\s*story\s*===|^\s*(character|characters|want|event|resolution)\s*:", re.I | re.M)

# --- allowed non-vocabulary words ------------------------------------------------------------

GRAMMAR_WORDS = set(
    """
    a an the
    i me my mine myself you your yours yourself he him his she her hers it its we us our ours
    they them their theirs this that these those who whom whose what which
    someone something anyone anything everyone everything nothing nobody
    in on at to of for with without from by about near under over into out up down after before
    between behind through around next beside inside outside
    and but or so because then if than as
    is am are was were be been being have has had having do does did done doing
    can could will would should may might must shall not
    here there now very too also just some any much many more most all each every again still
    where when why how
    """.split()
)

# The prompt names six simple verbs; the prompt's own tone example also uses "say" and the
# like, so a few very basic verbs are allowed by default. strict_verbs=True keeps only the six.
PROMPT_VERBS = ("want", "like", "go", "see")  # is/have are in GRAMMAR_WORDS
EXTRA_BASIC_VERBS = ("say", "give", "get", "take", "come", "need", "ask")

IRREGULAR = {
    "go": {"goes", "went", "gone", "going"},
    "see": {"sees", "saw", "seen", "seeing"},
    "say": {"says", "said", "saying"},
    "give": {"gives", "gave", "given", "giving"},
    "get": {"gets", "got", "gotten", "getting"},
    "take": {"takes", "took", "taken", "taking"},
    "come": {"comes", "came", "coming"},
}

CONTRACTIONS = {
    "i'm", "i'll", "i'd", "i've", "you're", "you'll", "you've", "you'd", "he's", "she's", "it's",
    "we're", "we'll", "we've", "they're", "they'll", "they've", "that's", "there's", "here's",
    "what's", "who's", "let's", "don't", "doesn't", "didn't", "can't", "won't", "isn't",
    "aren't", "wasn't", "weren't", "haven't", "hasn't", "couldn't", "wouldn't", "shouldn't",
}

_TOKEN = re.compile(r"[^\W\d_]+(?:['\-][^\W\d_]+)*")
_LABEL = re.compile(r"^\s*([^\W\d_][^\W\d_'\-]*(?:\s[^\W\d_][^\W\d_'\-]*)?)\s*:\s+\S")
# Japanese/Chinese sentences end in 。！？ with no space after them, so those split without whitespace.
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?…])\s+|(?<=[。！？])\s*|\n+")

_VOWELS = set("aeiou")


def _norm(text):
    return (text or "").replace("\u2019", "'").replace("\u2018", "'").replace("\u02bc", "'")


def word_forms(word):
    """The word plus its regular inflections (plural, -ed, -ing, ...). Same root only."""
    w = _norm(word).strip().lower()
    if not w:
        return set()
    forms = {w, w + "s", w + "es", w + "ed", w + "d", w + "ing"}
    if len(w) > 1 and w.endswith("y") and w[-2] not in _VOWELS:
        forms |= {w[:-1] + "ies", w[:-1] + "ied"}
    if w.endswith("e"):
        forms.add(w[:-1] + "ing")
    if len(w) >= 2 and w[-1] not in _VOWELS | {"w", "x", "y"} and w[-2] in _VOWELS:
        forms |= {w + w[-1] + "ed", w + w[-1] + "ing"}
    forms |= IRREGULAR.get(w, set())
    return forms


def _allowed_words(strict_verbs=False, extra=()):
    allowed = set(GRAMMAR_WORDS) | set(CONTRACTIONS)
    verbs = list(PROMPT_VERBS) + ([] if strict_verbs else list(EXTRA_BASIC_VERBS))
    for verb in verbs:
        allowed |= word_forms(verb)
    for w in extra:
        allowed |= word_forms(w)
    for w in ("is", "have", "do", "be"):
        allowed |= word_forms(w)
    return allowed


def parse_vocabulary(vocab):
    """Accepts 'a, b, thank you' or a list. Returns the set of single lowercase words
    (a phrase contributes each of its words)."""
    if vocab is None:
        return set()
    items = re.split(r"[,\n]", vocab) if isinstance(vocab, str) else list(vocab)
    words = set()
    for item in items:
        for token in _TOKEN.findall(_norm(str(item)).lower()):
            words.add(token)
    return words


def _vocab_forms(vocab_words):
    forms = set()
    for w in vocab_words:
        forms |= word_forms(w)
    return forms


def _is_known(token, vocab_forms, allowed):
    """token is lowercase."""
    if token in allowed or token in vocab_forms:
        return True
    if token.endswith("'s") and (token[:-2] in vocab_forms or token[:-2] in allowed):
        return True
    if "-" in token:
        return all(_is_known(part, vocab_forms, allowed) for part in token.split("-") if part)
    return False


# --- is the passage actually written in the requested language? --------------------------------
# Found in the first automated run: a "Spanish" story written in English, a "Japanese" story in
# English, French with English words left in. Checking structure alone passed all of them.

_SCRIPT_RANGES = {
    "kana": "\u3040-\u30ff", "cjk": "\u3400-\u4dbf\u4e00-\u9fff", "hangul": "\uac00-\ud7af\u1100-\u11ff",
    "cyrillic": "\u0400-\u04ff", "arabic": "\u0600-\u06ff", "devanagari": "\u0900-\u097f",
    "greek": "\u0370-\u03ff", "thai": "\u0e00-\u0e7f", "hebrew": "\u0590-\u05ff",
}
_LANGUAGE_SCRIPTS = {}
for _names, _scripts in (
    (("japanese", "nihongo", "\u65e5\u672c\u8a9e"), ("kana", "cjk")),
    (("chinese", "mandarin", "cantonese", "\u4e2d\u6587", "\u6c49\u8bed", "\u6f22\u8a9e", "\u666e\u901a\u8bdd"), ("cjk",)),
    (("korean", "\ud55c\uad6d\uc5b4"), ("hangul",)),
    (("russian", "ukrainian", "bulgarian", "\u0440\u0443\u0441\u0441\u043a\u0438\u0439"), ("cyrillic",)),
    (("arabic", "\u0627\u0644\u0639\u0631\u0628\u064a\u0629"), ("arabic",)),
    (("hindi", "\u0939\u093f\u0928\u094d\u0926\u0940"), ("devanagari",)),
    (("greek", "\u03b5\u03bb\u03bb\u03b7\u03bd\u03b9\u03ba\u03ac"), ("greek",)),
    (("thai", "\u0e44\u0e17\u0e22"), ("thai",)),
    (("hebrew", "\u05e2\u05d1\u05e8\u05d9\u05ea"), ("hebrew",)),
):
    for _n in _names:
        _LANGUAGE_SCRIPTS[_n] = _scripts

# Short English words that are also ordinary words in Spanish/French/Italian/Portuguese/German
# ("no", "a", "me", "on"...) must not make a Romance-language story look English.
_AMBIGUOUS_WITH_ENGLISH = {"a", "as", "me", "no", "on", "do", "in", "an", "he", "so", "all", "here",
                           "is", "be", "was", "had", "son", "des", "the", "per"}
_ENGLISH_MARKERS = GRAMMAR_WORDS - _AMBIGUOUS_WITH_ENGLISH

ENGLISH_VERDICT_RATIO = 0.5  # at least this share of English words: the story is in English
MIXED_VERDICT_RATIO = 0.2    # at least this share: English words left in a story in another language
SCRIPT_MIN_RATIO = 0.5       # at least this share of letters must be in the language's own script


def language_check(text, language, vocab=""):
    """Is `text` plausibly written in `language`? English is never checked here.

    Non-Latin languages (Japanese, Chinese, Korean, Russian, ...): most letters must be in the
    language's own script. Other languages: the share of English words (grammar words plus the
    learner's English vocabulary) must be low; a story in English, or with English words left in
    ("je veux water"), fails. A heuristic, not a language detector: ok/verdict only."""
    name = _norm(language).strip().lower()
    base = {"ok": True, "verdict": "not_checked", "english_ratio": None, "script_ratio": None}
    if not name or name in ("english", "en", "ingles", "inglés", "anglais", "englisch"):
        return base

    letters = [ch for ch in _norm(text) if ch.isalpha()]
    scripts = _LANGUAGE_SCRIPTS.get(name)
    if scripts:
        pattern = re.compile("[" + "".join(_SCRIPT_RANGES[sc] for sc in scripts) + "]")
        ratio = (sum(1 for ch in letters if pattern.match(ch)) / len(letters)) if letters else 0.0
        ok = ratio >= SCRIPT_MIN_RATIO
        return {"ok": ok, "verdict": "ok" if ok else "wrong_script", "english_ratio": None, "script_ratio": ratio}

    markers = _ENGLISH_MARKERS | (parse_vocabulary(vocab) - _AMBIGUOUS_WITH_ENGLISH)
    markers |= {f for w in parse_vocabulary(vocab) for f in word_forms(w)} - _AMBIGUOUS_WITH_ENGLISH
    tokens = [t.lower() for t in _TOKEN.findall(_norm(text))]
    if not tokens:
        return {"ok": False, "verdict": "no_text", "english_ratio": 0.0, "script_ratio": None}
    ratio = sum(1 for t in tokens if t in markers) / len(tokens)
    if ratio >= ENGLISH_VERDICT_RATIO:
        verdict = "english"
    elif ratio >= MIXED_VERDICT_RATIO:
        verdict = "mixed"
    else:
        verdict = "ok"
    return {"ok": verdict == "ok", "verdict": verdict, "english_ratio": ratio, "script_ratio": None}


def _is_label(line):
    """A speaker label: 'Name:' or 'Name :' with 1-2 words, none starting with a lower-case letter.
    ('Marc dit : ...' inside a narration is not a label; names in scripts without case still are.)"""
    match = _LABEL.match(line)
    return bool(match) and all(not word[0].islower() for word in match.group(1).split())


def _failure_result(reason):
    return {
        "failure": True, "failure_reason": reason, "passed": False, "style": None, "units": 0,
        "length_ok": False, "format_ok": False, "leaked_plan": False, "vocab_checked": False,
        "oov_words": None, "oov_count": 0, "word_count": 0, "oov_rate": 0.0, "names": [],
        "longest_unit_words": 0, "mean_unit_words": 0.0, "language_check": None,
    }


def check_passage(text, vocab, check_vocab=True, max_oov=0, length_range=(4, 10),
                  strict_verbs=False, extra_allowed=(), names=(), max_unit_words=None, language=None):
    """Score one passage. Returns a dict; `passed` is the overall verdict.

    max_oov: words outside the vocabulary tolerated (0 = strict; the batch runner defaults to 2
    so ordinary everyday words such as "eat" or "drink" don't fail a story).
    max_unit_words: optional cap on the words in any one sentence/line (beginner readability);
    the longest and mean lengths are always reported either way.
    language: the language the story was requested in. For anything other than English the
    passage must actually be written in it (see language_check); None skips that check."""
    text = _norm(text).strip()
    if not text:
        return _failure_result("empty")
    lowered = text.lower()
    for marker in FAILURE_MARKERS:
        if marker in lowered:
            return _failure_result("fallback or guard message")

    leaked = bool(LEAK_PATTERN.search(text))
    lines = [ln for ln in text.splitlines() if ln.strip()]
    labelled = [_is_label(ln) for ln in lines]
    style = "dialogue" if sum(labelled) * 2 >= len(lines) and any(labelled) else "narration"
    format_ok = all(labelled) if style == "dialogue" else not any(labelled)

    body_segments = []  # text with speaker labels removed
    label_names = set()
    for ln, is_label in zip(lines, labelled):
        if is_label:
            label, _, rest = ln.partition(":")
            label_names.update(t.lower() for t in _TOKEN.findall(label))
            body_segments.append(rest.strip())
        else:
            body_segments.append(ln.strip())

    if style == "dialogue":
        units = len(lines)
        unit_texts = body_segments
    else:
        unit_texts = [s for s in _SENTENCE_SPLIT.split(text) if re.search(r"[^\W\d_]", s)]
        units = len(unit_texts)
    length_ok = length_range[0] <= units <= length_range[1]
    unit_lengths = [len(_TOKEN.findall(u)) for u in unit_texts] or [0]

    result = {
        "failure": False, "failure_reason": None, "style": style, "units": units,
        "length_ok": length_ok, "format_ok": format_ok, "leaked_plan": leaked,
        "vocab_checked": bool(check_vocab), "oov_words": None, "oov_count": 0,
        "word_count": 0, "oov_rate": 0.0, "names": [],
        "longest_unit_words": max(unit_lengths),
        "mean_unit_words": sum(unit_lengths) / len(unit_lengths),
    }

    if check_vocab:
        allowed = _allowed_words(strict_verbs, extra_allowed)
        vocab_forms = _vocab_forms(parse_vocabulary(vocab))
        known_names = set(label_names) | {n.lower() for n in names}

        # Capitalised words in the middle of a sentence that are neither vocabulary nor
        # grammar are character names ("I am Sam").
        for segment in body_segments:
            for sentence in _SENTENCE_SPLIT.split(segment):
                tokens = _TOKEN.findall(sentence)
                for token in tokens[1:]:
                    low = token.lower()
                    if token[0].isupper() and token != "I" and not _is_known(low, vocab_forms, allowed):
                        known_names.add(low)

        # A capitalised word that appears at least twice, never in lower case, and is neither
        # vocabulary nor grammar is a name even if it only ever starts sentences ("Sam wakes up. Sam
        # looks out."). Sentence-initial "Soon," twice would also be taken for one: a rare,
        # harmless under-count.
        cap_counts, lower_seen = Counter(), set()
        for segment in body_segments:
            for sentence in _SENTENCE_SPLIT.split(segment):
                for token in _TOKEN.findall(sentence):
                    if token[0].isupper() and token != "I":
                        cap_counts[token.lower()] += 1
                    else:
                        lower_seen.add(token.lower())
        for low, count in cap_counts.items():
            if count >= 2 and low not in lower_seen and not _is_known(low, vocab_forms, allowed):
                known_names.add(low)

        word_count = 0
        oov_occurrences = []
        for segment in body_segments:
            for token in _TOKEN.findall(segment):
                low = token.lower()
                if low in known_names:
                    continue
                word_count += 1
                if not _is_known(low, vocab_forms, allowed):
                    oov_occurrences.append(low)

        result["oov_words"] = list(dict.fromkeys(oov_occurrences))
        result["oov_count"] = len(oov_occurrences)
        result["word_count"] = word_count
        result["oov_rate"] = len(oov_occurrences) / word_count if word_count else 0.0
        result["names"] = sorted(known_names)

    vocab_ok = (not check_vocab) or result["oov_count"] <= max_oov
    unit_ok = max_unit_words is None or result["longest_unit_words"] <= max_unit_words
    language_ok = True
    if language:
        result["language_check"] = language_check(text, language, vocab)
        language_ok = result["language_check"]["ok"]
    else:
        result["language_check"] = None
    result["passed"] = (not leaked) and length_ok and format_ok and vocab_ok and unit_ok and language_ok
    return result


def rescore_results(data, max_oov=0, strict_verbs=False, max_unit_words=None):
    """Re-score a saved batch (the JSON written by run_story_batch.py) under different rules,
    without generating anything new. Returns {language: [result, ...]}."""
    vocab = data.get("vocabulary", "")
    rescored = {}
    for language, items in data["results"].items():
        rescored[language] = []
        for item in items:
            r = check_passage(
                item.get("text", ""), vocab, check_vocab=(language.strip().lower() == "english"),
                max_oov=max_oov, strict_verbs=strict_verbs, max_unit_words=max_unit_words,
                language=language,
            )
            r.update(language=language, latency=item.get("latency"),
                     style_requested=item.get("style_requested"), text=item.get("text"),
                     story_type=item.get("story_type"), topic=item.get("topic"))
            rescored[language].append(r)
    return rescored


def summarize(results):
    """Aggregate a list of check_passage() results (optionally with a 'latency' key)."""
    total = len(results)
    failures = sum(1 for r in results if r["failure"])
    scored = [r for r in results if not r["failure"]]
    passes = sum(1 for r in results if r["passed"])
    vocab_scored = [r for r in scored if r["oov_words"] is not None]
    latencies = sorted(r["latency"] for r in results if r.get("latency") is not None)

    def percentile(p):
        if not latencies:
            return None
        return latencies[min(len(latencies) - 1, math.ceil(p * len(latencies)) - 1)]

    return {
        "total": total,
        "failures": failures,
        "passes": passes,
        "pass_rate": passes / total if total else 0.0,
        "mean_oov_per_passage": (sum(r["oov_count"] for r in vocab_scored) / len(vocab_scored)) if vocab_scored else None,
        "top_oov": Counter(w for r in vocab_scored for w in r["oov_words"]).most_common(10),
        "styles": dict(Counter(r["style"] for r in scored)),
        "leaks": sum(1 for r in scored if r["leaked_plan"]),
        "length_off": sum(1 for r in scored if not r["length_ok"]),
        "format_bad": sum(1 for r in scored if not r["format_ok"]),
        "latency_p50": percentile(0.5),
        "latency_p90": percentile(0.9),
        "language_bad": sum(1 for r in scored if r.get("language_check") and not r["language_check"]["ok"]),
        "language_verdicts": dict(Counter(r["language_check"]["verdict"] for r in scored if r.get("language_check"))),
        "language_checked": sum(1 for r in scored if r.get("language_check") and r["language_check"]["verdict"] != "not_checked"),
        "mean_unit_words": (sum(r["mean_unit_words"] for r in scored) / len(scored)) if scored else None,
        "longest_unit_words": max((r["longest_unit_words"] for r in scored), default=None),
    }


# --- variety: are the stories different from one another? ---------------------------------------
# Reading 48 generated stories showed 81% mentioned water and ~75% were somebody asking for or
# receiving something. A pass rate cannot see that, so variety gets its own numbers.

# Greetings and politeness words open nearly every beginner text; they are not "the repeated word".
SOCIAL_WORDS = {"hello", "hi", "goodbye", "bye", "please", "thank", "thanks", "you", "yes", "no",
                "sorry", "welcome"}
_OPENING_LABEL = re.compile(r"^\s*[^\W\d_][^\W\d_'\-]*(?:\s[^\W\d_][^\W\d_'\-]*)?\s*:\s+")


def _all_tokens(text):
    return {t.lower() for t in _TOKEN.findall(_norm(text))}


def _content_tokens(text):
    return {t for t in _all_tokens(text) if t not in GRAMMAR_WORDS and t not in CONTRACTIONS}


def variety_report(results, vocab="", english=True):
    """How different are these stories from each other? `results` are check_passage() results with
    a "text" (and optionally "story_type"), as saved by run_story_batch.py. Failed generations are
    left out. top_vocab_word needs the English vocabulary, so it is skipped when english=False."""
    kept = [r for r in results if r.get("text") and not r.get("failure")]
    n = len(kept)
    types = Counter(r["story_type"] for r in kept if r.get("story_type"))
    report = {"n": n, "types": dict(types), "distinct_types": len(types),
              "mean_overlap": None, "top_vocab_word": None, "top_opening": None}
    if n == 0:
        return report

    content = [_content_tokens(r["text"]) for r in kept]
    if n >= 2:
        overlaps = [len(a & b) / len(a | b) for a, b in itertools.combinations(content, 2) if a | b]
        report["mean_overlap"] = sum(overlaps) / len(overlaps) if overlaps else 0.0

    openings = Counter()
    for r in kept:
        first = next((ln for ln in r["text"].splitlines() if ln.strip()), "")
        words = _TOKEN.findall(_norm(_OPENING_LABEL.sub("", first)).lower())[:3]
        openings[" ".join(words)] += 1
    opening, count = openings.most_common(1)[0]
    report["top_opening"] = (opening, count / n)

    if english:
        everything = [_all_tokens(r["text"]) for r in kept]
        best = None
        for word in sorted(parse_vocabulary(vocab) - SOCIAL_WORDS):
            forms = word_forms(word)
            share = sum(1 for tokens in everything if forms & tokens) / n
            if best is None or share > best[1]:
                best = (word, share)
        report["top_vocab_word"] = best
    return report


def format_variety(report):
    if not report["n"]:
        return "Variety: no stories to compare."
    parts = [f"Variety over {report['n']} stories: {report['distinct_types']} distinct types {report['types']}"]
    if report["mean_overlap"] is not None:
        parts.append(f"mean overlap between stories {report['mean_overlap']:.2f}")
    if report["top_vocab_word"]:
        word, share = report["top_vocab_word"]
        parts.append(f"most repeated vocabulary word '{word}' in {share:.0%} of stories")
    if report["top_opening"]:
        opening, share = report["top_opening"]
        parts.append(f"most common opening '{opening}' in {share:.0%}")
    return "; ".join(parts)


def format_summary(s):
    lines = [
        f"Attempts: {s['total']}   Passed: {s['passes']} ({s['pass_rate']:.0%})   Failures (no story): {s['failures']}",
        f"Styles: {s['styles']}   Leaked plan: {s['leaks']}   Off-length: {s['length_off']}   Bad format: {s['format_bad']}",
    ]
    if s["mean_oov_per_passage"] is not None:
        lines.append(f"Mean out-of-vocabulary words per passage: {s['mean_oov_per_passage']:.2f}")
        lines.append(f"Most common out-of-vocabulary words: {s['top_oov']}")
    if s["language_checked"]:  # English passages are not language-checked, so they are not counted
        lines.append(f"Written in the requested language: {s['language_checked'] - s['language_bad']}/{s['language_checked']}"
                     f"   Language verdicts: { {k: v for k, v in s['language_verdicts'].items() if k != 'not_checked'} }")
    if s["mean_unit_words"] is not None:
        lines.append(f"Words per sentence/line: mean {s['mean_unit_words']:.1f}, longest {s['longest_unit_words']}")
    if s["latency_p50"] is not None:
        lines.append(f"Latency p50 / p90: {s['latency_p50']:.1f}s / {s['latency_p90']:.1f}s")
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description="Check pasted passages against a vocabulary.")
    parser.add_argument("passages_file", help="text file; passages separated by a line with only ---")
    parser.add_argument("--words", help="comma-separated vocabulary")
    parser.add_argument("--words-file", help="file with one word (or phrase) per line")
    parser.add_argument("--max-oov", type=int, default=5, help="stray words tolerated per passage (0 = strict)")
    parser.add_argument("--strict-verbs", action="store_true")
    parser.add_argument("--max-unit-words", type=int, default=None, help="fail sentences/lines longer than this")
    args = parser.parse_args(argv)

    vocab = args.words or ""
    if args.words_file:
        with open(args.words_file, encoding="utf-8") as f:
            vocab += "," + f.read().replace("\n", ",")
    if not vocab.strip():
        parser.error("provide --words or --words-file")

    with open(args.passages_file, encoding="utf-8") as f:
        passages = [p.strip() for p in re.split(r"^\s*---\s*$", f.read(), flags=re.M) if p.strip()]

    results = []
    for i, passage in enumerate(passages, 1):
        r = check_passage(passage, vocab, max_oov=args.max_oov, strict_verbs=args.strict_verbs,
                          max_unit_words=args.max_unit_words)
        results.append(r)
        verdict = "PASS" if r["passed"] else "FAIL"
        extras = []
        if r["oov_words"]:
            extras.append(f"out-of-vocabulary: {r['oov_words']}")
        if not r["length_ok"]:
            extras.append(f"length {r['units']}")
        if not r["format_ok"]:
            extras.append("bad format")
        if r["leaked_plan"]:
            extras.append("leaked plan")
        print(f"#{i} [{verdict}] {r['style'] or 'failure'} {'; '.join(extras)}")
    print()
    print(format_summary(summarize(results)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
