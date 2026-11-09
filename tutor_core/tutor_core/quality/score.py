"""A 0 to 100 score for how well one story follows the requirements it was written under (v4, 8 Nov 2026).

WHY v4. A test of 24 stories (4 requests x 6 pipeline variants) showed v3 could not tell a broken story from a good one: "Apple stall empty,
no. Maria feels sad, sorry. Apple tastes sweet, good night." scored 96.8 offline. Three causes, all fixed here:

  1. The score was a plain mean of six parts and four of them sit near 100 almost always, so grammar (1/6) could drop to 0 and the story
     still scored 75+. Now the parts are weighted (grammar and naturalness carry most of it) and a story that breaks a quality rule is FAILED:
     its score is multiplied by FAIL_FACTOR (0.6), so a failed story can never outrank a passing one, yet failed stories keep their order
     for best-of-N selection and for the repair loop's "kept if better" comparison.
  2. Nothing punished word stuffing. v3 only checked a minimum number of the learner's words and took 25% density before it cut a single
     point (the worst stories were at 24%). Now there is a maximum (the target + 3, or twice the target, whichever is more) that works in every
     language, a detector for words tacked on after a comma ("She buys apple, yes."), and a soft penalty for walking through the word list in order.
  3. Grammar counted "sentences with a finding" and weighed every finding the same. Now each finding is weighted by severity (major 3,
     moderate 1, minor 0.5), findings on the same text count once, and grammar = 100 * exp(-ERROR_DECAY * weighted findings per 100 words).

v4.1 (9 Nov 2026), from reading 38 real stories next to their scores (docs/STORY-SCORING.md): 10 stories a reader rates under 60 still scored 80+.
  - markdown: **bold**, # headings and `code` in a story fail it ("markdown"); the marks are blanked (same length) so the grammar rules still see the
    words ("una **libro**" went unnoticed, the story scored 99.7);
  - tacked-on words fail at 20% of the sentences (was 25%: the stories at 22% read as word lists);
  - telegraphic also when 12+ sentences average under 4.5 words (a letter of 34 four-word lines scored 96.6);
  - problems gain "dangling_end" (a sentence cut off on "y", "de", "con", "and", "with"...) and "no_space" (escuela.entro);
  - `merge_reviews` joins the findings of several reviewers (each one misses things the other catches) for one score.

Six parts (same names as v3, so nothing downstream breaks) plus one optional part, each 0 to 100:

    length            within 15% of the target = 100, 60% off or more = 0, a straight line between
    own_words         the learner's words used, against the target count (capped at 100); 12 points off for each word above the maximum
                      (see above); 20 off when the story walks through the word list in order. Multi-word entries ("thank you", "to eat")
                      are counted too: v3's measure() skipped them (en-0 "judge" used 11 of 12 words and was recorded as 6)
    uncommon          the share of unusual words: at or below the target = 100, 20 points above it = 0
    sentence_length   the mean sentence is 6 to 12 words (8 to 24 characters in Chinese and Japanese); 15 points off per word outside,
                      and 15 more if any sentence is over 20 words (40 characters)
    grammar           100 * exp(-ERROR_DECAY * severity-weighted findings per 100 words), minus 34 for each structural problem the code can
                      see (list-like text, a repeated sentence, same openings, a blank like "[Your name]", one word repeated, a run-on)
    language_format   25 each: in the requested language; ends on a finished sentence; no blank left in or leaked plan; format fits the kind
    naturalness       OPTIONAL, 1 to 5 from a review (rubric or pairwise pick) mapped to 0 to 100; left out when not given

Two kinds of "never keep this story as an example":
  gated   score 0: empty, a failure message, the wrong language, a leaked plan (unchanged from v3)
  failed  score x 0.6: stuffed, tacked_on_words, telegraphic, too_many_errors (10+ weighted findings per 100 words, or 2+ major ones), unnatural. `passed` is True only when nothing failed.

Grammar findings come from the built-in rules (always), and from a LanguageTool server and a model review when the caller passes their
`hits`. This module never calls a model or a server, so scoring stays pure and repeatable. When no `hits` are passed the result says
`reviewed: False`: the grammar part then sees only the built-in rules and does NOT mean the grammar is right, so do not save such a story
as an example. A review that sets `severity` on each finding ("major", "moderate", "minor") is trusted; otherwise it is guessed from the
rule name, the note and the kind (see hit_severity). The constants below were tuned on 24 stories: re-tune them on your own labelled set.
"""
from __future__ import annotations

import math
import re

from .endings import ends_complete, has_dangling_sentence
from .fluency import fluency_problems
from .grammar import affected_sentences, builtin_hits, merge
from .language import language_check
from .passage import FAILURE_MARKERS, LEAK_PATTERN, _is_label, _read_shape
from .vocabulary import _TOKEN, _norm

SCORE_VERSION = 4.1                                     # 9 Nov 2026: see "v4.1" in the docstring
NAMES = ("length", "own_words", "uncommon", "sentence_length", "grammar", "language_format")
WEIGHTS = {"grammar": 40, "naturalness": 25, "own_words": 15, "length": 6, "uncommon": 6, "sentence_length": 5, "language_format": 3}
FAIL_FACTOR = 0.6                                       # a story that breaks a quality rule keeps its order but cannot beat a passing one
DEFAULT_LENGTH = {"dialogue": 50, "narration": 50}      # words, when no tier or length was asked; the other kinds: 80
DEFAULT_OWN, DEFAULT_UNCOMMON = 3, 10
LENGTH_FULL, LENGTH_ZERO = 0.15, 0.60
UNCOMMON_ZERO_POINTS = 20
SENTENCE_MEAN = {False: (6, 12), True: (8, 24)}           # per unit: words, or characters for Chinese and Japanese
SENTENCE_LONGEST = {False: 20, True: 40}
PER_WORD_OFF, LONGEST_PENALTY, PER_PROBLEM = 15, 15, 34
REPEAT_SHARE, REPEAT_MIN, RUN_ON_COMMAS = 0.12, 4, 4

# the learner's words: a maximum, a stuffing gate, and the "walk through the list" signature
OWN_MAX_PLUS, OWN_MAX_TIMES = 3, 2.0                    # at most max(target + 3, 2 x target) of the learner's words
PER_OVER_WORD, STUFFED_OVER = 12, 3                     # points off per word over the maximum; this many over = failed
PACK_ORDER_RUN, PACK_ORDER_PENALTY, PACK_ORDER_MIN_WORDS = 5, 20, 6
# telegraphic text
TAIL_MIN_SENTENCES, TAIL_SHARE, TAIL_MIN_BEFORE = 3, 0.20, 3     # words tacked on after a comma at the end of the sentence
FRAGMENT_SIZE = {False: 4, True: 6}                     # a sentence shorter than this (words, or characters) is a fragment
FRAGMENT_SHARE, FRAGMENT_MIN_SENTENCES = 0.30, 3
CHOPPY_MEAN, CHOPPY_MIN_SENTENCES = {False: 4.5, True: 7.0}, 12      # many very short sentences in a row
# grammar
SEVERITY = {"major": 3.0, "moderate": 1.0, "minor": 0.5}
ERROR_DECAY = 0.1                                       # 1 major per 100 words = 74, 3 majors = 41, 1 minor = 95
GATE_ERRORS_PER_100 = 10.0                              # weighted findings per 100 words that fail the story outright
GATE_MAJOR_FINDINGS = 2                                 # two or more major findings fail it too (one can be a false alarm: reviews are uncertain)
GATE_NATURALNESS = 2.0                                  # a review of 2 out of 5 or lower fails the story
MIN_WORDS_FOR_DENSITY = 30                              # so a very short story is not scored on a tiny denominator

_PLACEHOLDER = re.compile(r"\[[^\]\n]{1,40}\]|\{[^}\n]{1,40}\}|<[^>\n]{1,40}>|\bX{3,}\b|\b(?:insert|lorem ipsum)\b", re.I)
_CLAUSE_BREAKS = "，、,"
_SENTENCE_ENDS = re.compile(r"[。！？!?\n]+")
_MARKDOWN = re.compile(r"\*\*|__|`|^\s{0,3}#{1,6}\s|(?<!\w)\*(?=\w)[^*\n]{1,60}(?<=\w)\*(?!\w)", re.M)
_MARK_CHARS = re.compile(r"[*_`#]")
_NO_SPACE = re.compile(r"[a-zà-ÿ]{2,}[.!?][A-Za-zÀ-ÿ]{2,}")
_FUNCTION_ENDINGS = {                    # a sentence that stops on one of these was cut off
    "en": {"and", "or", "but", "with", "of", "the", "a", "an", "because"},
    "es": {"y", "e", "o", "u", "de", "con", "en", "un", "una", "el", "la", "los", "las", "que", "para", "mi", "su", "sin", "pero"},
    "fr": {"et", "ou", "de", "du", "des", "avec", "dans", "un", "une", "le", "la", "les", "que", "pour", "mon", "ma", "son", "sa", "mais"},
    "de": {"und", "oder", "mit", "von", "in", "an", "auf", "der", "die", "das", "ein", "eine", "zu", "für", "aber", "weil", "dass"},
    "it": {"e", "o", "di", "con", "un", "una", "il", "lo", "che", "per", "ma", "del", "della"},
}
_COMMA_BEFORE = re.compile(r"[,;]\s*[\"“«'‘]?\s*$")
_ALPHA = re.compile(r"[^\W\d_]")


# ---------------------------------------------------------------- grammar findings, weighted by severity

_MAJOR = ("gender", "agreement", "mismatch", "must match", "wrong", "incorrect", "conjugat", "tense", "verb form",
          "missing verb", "omitted", "unclear", "nonsense", "word_usage", "word usage", "misused")
_MINOR = ("interjection", "redundant", "filler", "capital", "punctuation", "spacing", "style", "optional", "spell")


def _field(hit, name, default=""):
    return hit.get(name, default) if isinstance(hit, dict) else getattr(hit, name, default)


def hit_severity(hit) -> float:
    """The weight of one finding. A stated severity wins; otherwise it is guessed from the rule name, the note and the kind."""
    stated = str(_field(hit, "severity", "")).lower()
    if stated in SEVERITY:
        return SEVERITY[stated]
    text = f"{_field(hit, 'rule')} {_field(hit, 'note')}".lower()
    if "spell" in str(_field(hit, "kind")).lower():
        return SEVERITY["minor"]
    if any(w in text for w in _MAJOR):
        return SEVERITY["major"]
    if any(w in text for w in _MINOR):
        return SEVERITY["minor"]
    return SEVERITY["moderate"]


def summarize_findings(hits):
    """-> (sum of severities, number of major findings). Findings on overlapping text (rules, LanguageTool and the review often flag the same
    words) count once, heaviest wins."""
    spans = sorted(((int(_field(h, "start", 0) or 0), int(_field(h, "end", 0) or 0), hit_severity(h)) for h in hits), key=lambda s: (s[0], -s[2]))
    total, majors, group_end, group_weight = 0.0, 0, None, 0.0
    for start, end, weight in spans:
        if group_end is not None and start < group_end:
            group_end, group_weight = max(group_end, end), max(group_weight, weight)
        else:
            total, majors = total + group_weight, majors + (group_weight >= SEVERITY["major"])
            group_end, group_weight = end, weight
    return total + group_weight, majors + (group_weight >= SEVERITY["major"])


# ---------------------------------------------------------------- the learner's words: counting and stuffing signatures

def _entry_patterns(words, unspaced):
    """One pattern per entry of the word list, matching multi-word entries ("thank you") and short endings (water, waters). Approximate on
    purpose: it only feeds the stuffing checks, so swap in your lemma matcher if you want it exact."""
    patterns = []
    for index, entry in enumerate(words):
        w = _norm(str(entry)).lower().strip()
        w = w[3:] if w.startswith("to ") else w
        if not w:
            continue
        if unspaced:
            patterns.append((index, re.compile(re.escape(w))))
        else:
            ending = r"\w{0,3}" if len(w) > 3 and " " not in w else ""
            patterns.append((index, re.compile(rf"(?<!\w){re.escape(w)}{ending}(?!\w)")))
    return patterns


def _own_matches(sentence, patterns):
    low = sentence.lower()
    return sorted((m.start(), m.end(), index) for index, p in patterns for m in p.finditer(low))


def _longest_increasing_run(values):
    best = run = 1 if values else 0
    for a, b in zip(values, values[1:]):
        run = run + 1 if b > a else 1
        best = max(best, run)
    return best


def _stuffing_signs(units, patterns, kind_is_dialogue, unspaced):
    """-> (distinct entries used, share of sentences that end on a tacked-on word, longest run of sentences using the list in order)"""
    used, tails, firsts = set(), 0, []
    for unit in units:
        matches = _own_matches(unit, patterns)
        used.update(index for _, _, index in matches)
        if matches:
            firsts.append(matches[0][2])
        if kind_is_dialogue or unspaced:
            continue
        low = unit.lower()
        for start, end, _ in matches:
            before, after = low[:start], low[end:]
            if not _ALPHA.search(after) and _COMMA_BEFORE.search(before) and len(_TOKEN.findall(before)) >= TAIL_MIN_BEFORE:
                tails += 1
                break
    return used, (tails / len(units) if units else 0.0), _longest_increasing_run(firsts)


# ---------------------------------------------------------------- unchanged from v3

def _dangling(text, language):
    """True when a sentence stops on a word that cannot end one ("... arroz fresco y.")."""
    ends = _FUNCTION_ENDINGS.get(language)
    if not ends:
        return False
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", text):
        words = _TOKEN.findall(sentence)
        if len(words) >= 3 and words[-1].casefold() in ends and sentence.rstrip().endswith((".", "!", "?")):
            return True
    return False


def _detail_problems(text, unspaced, tokens, language="en"):
    """Problems the fluency check does not look for: a template blank left in, one word said over and over, a run-on in Chinese or Japanese."""
    found = []
    if _PLACEHOLDER.search(text):
        found.append("placeholder")
    if not unspaced and len(tokens) >= 20:
        counts = {}
        for tok in tokens:
            low = tok.casefold()
            if len(low) >= (3 if any(ord(c) > 0x400 for c in low) else 5):
                counts[low] = counts.get(low, 0) + 1
        if counts and max(counts.values()) >= max(REPEAT_MIN, round(REPEAT_SHARE * len(tokens))):
            found.append("repeated_word")
    if _NO_SPACE.search(text):
        found.append("no_space")
    if not unspaced and _dangling(text, language):
        found.append("dangling_end")
    if unspaced and any(sum(u.count(c) for c in _CLAUSE_BREAKS) >= RUN_ON_COMMAS for u in _SENTENCE_ENDS.split(text)):
        found.append("run_on")
    return found


def _line(value, full, zero):
    """100 at `full`, 0 at `zero`, straight between (either direction); clamped."""
    if full == zero:
        return 100.0
    t = (value - full) / (zero - full)
    return max(0.0, min(100.0, 100.0 * (1 - t)))


def _gate(text, language):
    low = text.casefold()
    if not text.strip():
        return "empty"
    if any(m in low for m in FAILURE_MARKERS):
        return "failure_message"
    if LEAK_PATTERN.search(text):
        return "leaked_plan"
    if language != "en":
        from ..languages import LANGUAGES
        verdict = language_check(text, LANGUAGES[language].name, "")
        if verdict["ok"] is False:
            return "wrong_language"
    return None


def _target_length(language, difficulty, kind):
    from .. import difficulty as _d
    words = int(difficulty["length"]) if difficulty and difficulty.get("length") else DEFAULT_LENGTH.get(kind, 80)
    return round(words * _d.CHARS_PER_WORD) if language in _d.UNSPACED else words


def _unit_sizes(shape, unspaced):
    if unspaced:
        return [sum(1 for ch in u if ch.isalpha()) for u in shape.unit_texts if u.strip()]
    return [len(_TOKEN.findall(u)) for u in shape.unit_texts if u.strip()]


def _format_ok(shape, kind):
    labelled = [_is_label(ln) for ln in shape.lines]
    if shape.style == "dialogue":
        return all(labelled) and kind != "narration"
    heading = len(labelled) > 1 and labelled[0] and not any(labelled[1:])
    return (not any(labelled) or heading) and kind != "dialogue"


# ---------------------------------------------------------------- the score

def score_story(text: str, language: str, words, difficulty=None, kind=None, hits=None, naturalness=None) -> dict:
    """`hits`: grammar findings (LanguageTool, a model review) already collected by the caller; pass them whenever you have them.
    `naturalness`: 1 to 5 from a review (rubric score or pairwise result), or None.
    {"score": 0 to 100, "passed": bool, "failed": [reasons], "parts": {name: 0 to 100 or None}, "gated": reason or None, "partial": bool,
     "reviewed": bool, "targets": {...}, "measured": {...}}"""
    from .. import difficulty as _d
    text = _norm(text or "").strip()
    gated = _gate(text, language)
    if gated:
        return {"score": 0.0, "passed": False, "failed": [], "parts": {n: None for n in NAMES}, "gated": gated, "partial": False,
                "reviewed": hits is not None, "targets": {}, "measured": {}, "version": SCORE_VERSION}
    words = list(words)
    marked = bool(_MARKDOWN.search(text))
    if marked:
        text = _MARK_CHARS.sub(" ", text)           # same length: the offsets of a review's findings stay right
    unspaced = _d.is_unspaced(language)
    m = _d.measure(text, language, words)
    t_len = _target_length(language, difficulty, kind)
    t_own = min(int(difficulty["own_words"]) if difficulty and difficulty.get("own_words") else DEFAULT_OWN, max(1, len(words)))
    t_unc = float(difficulty["uncommon_pct"]) if difficulty and difficulty.get("uncommon_pct") is not None else float(DEFAULT_UNCOMMON)
    shape = _read_shape(text)
    units = [u for u in shape.unit_texts if u.strip()]
    dialogue = shape.style == "dialogue" or kind == "dialogue"
    tokens = _TOKEN.findall(text)
    n_words = len(tokens) if not unspaced else m["length"] / _d.CHARS_PER_WORD
    failed, warnings, parts = [], [], {}
    if marked:
        failed.append("markdown")

    parts["length"] = _line(abs(m["length"] - t_len) / t_len, LENGTH_FULL, LENGTH_ZERO)

    # the learner's words: count (multi-word entries too), a maximum, and the signatures of stuffing
    used_set, tail_share, order_run = _stuffing_signs(units, _entry_patterns(words, unspaced), dialogue, unspaced)
    used = max(m["own_words"], len(used_set))
    own_max = max(t_own + OWN_MAX_PLUS, math.ceil(OWN_MAX_TIMES * t_own))
    over = max(0, used - own_max)
    ordered = len(words) >= PACK_ORDER_MIN_WORDS and order_run >= PACK_ORDER_RUN and not unspaced
    parts["own_words"] = max(0.0, min(100.0, 100.0 * used / t_own) - PER_OVER_WORD * over - (PACK_ORDER_PENALTY if ordered else 0))
    if over >= STUFFED_OVER:
        failed.append("stuffed")
    if tail_share >= TAIL_SHARE and len(units) >= TAIL_MIN_SENTENCES:
        failed.append("tacked_on_words")
    if ordered:
        warnings.append("word_list_in_order")

    parts["uncommon"] = None if m["uncommon_pct"] is None else _line(m["uncommon_pct"], t_unc, t_unc + UNCOMMON_ZERO_POINTS)

    sizes = _unit_sizes(shape, unspaced) or [0]
    mean = sum(sizes) / len(sizes)
    low, high = SENTENCE_MEAN[unspaced]
    off = max(0.0, low - mean, mean - high)
    sentence = 100.0 - (PER_WORD_OFF / (2 if unspaced else 1)) * off - (LONGEST_PENALTY if max(sizes) > SENTENCE_LONGEST[unspaced] else 0)
    parts["sentence_length"] = max(0.0, sentence)
    fragment_share = sum(1 for s in sizes if s < FRAGMENT_SIZE[unspaced]) / len(sizes)
    if not dialogue and len(sizes) >= FRAGMENT_MIN_SENTENCES and fragment_share >= FRAGMENT_SHARE:
        failed.append("telegraphic")
    elif not dialogue and len(sizes) >= CHOPPY_MIN_SENTENCES and mean < CHOPPY_MEAN[unspaced]:
        failed.append("telegraphic")

    # grammar: severity-weighted findings per 100 words
    problems = fluency_problems(text, unspaced) + _detail_problems(text, unspaced, tokens, language)
    all_hits = merge(builtin_hits(text, language, words), list(hits or ()))
    n_sentences, affected = affected_sentences(text, all_hits)
    weighted, majors = summarize_findings(all_hits)
    per_100 = 100.0 * weighted / max(n_words, MIN_WORDS_FOR_DENSITY)
    parts["grammar"] = max(0.0, 100.0 * math.exp(-ERROR_DECAY * per_100) - PER_PROBLEM * len(problems))
    if per_100 >= GATE_ERRORS_PER_100 or majors >= GATE_MAJOR_FINDINGS:
        failed.append("too_many_errors")

    checks = [True, ends_complete(text) and not has_dangling_sentence(text, language), "placeholder" not in problems, _format_ok(shape, kind)]
    parts["language_format"] = 25.0 * sum(checks)

    parts["naturalness"] = None
    if naturalness is not None:
        parts["naturalness"] = max(0.0, min(100.0, (float(naturalness) - 1.0) * 25.0))
        if float(naturalness) <= GATE_NATURALNESS:
            failed.append("unnatural")

    scored = {n: v for n, v in parts.items() if v is not None}
    score = sum(WEIGHTS[n] * v for n, v in scored.items()) / sum(WEIGHTS[n] for n in scored)
    if failed:
        score *= FAIL_FACTOR
    return {"score": round(score, 1), "passed": not failed, "failed": failed, "warnings": warnings,
            "parts": {n: (None if v is None else round(v, 1)) for n, v in parts.items()},
            "gated": None, "partial": any(parts[n] is None for n in NAMES), "reviewed": hits is not None,
            "problems": problems, "version": SCORE_VERSION,
            "grammar_hits": [h.as_dict() for h in all_hits],
            "targets": {"length": t_len, "own_words": t_own, "own_words_max": own_max, "uncommon_pct": t_unc},
            "measured": {"own_density": round(used / len(tokens), 2) if tokens and not unspaced else 0.0, "length": m["length"], "own_words": used,
                         "own_words_counted_by_measure": m["own_words"], "uncommon_pct": m["uncommon_pct"], "mean_sentence": round(mean, 1),
                         "sentences": n_sentences, "sentences_with_mistakes": round(affected, 2), "findings_per_100_words": round(per_100, 1), "major_findings": majors,
                         "tacked_on_share": round(tail_share, 2), "fragment_share": round(fragment_share, 2), "word_list_run": order_run}}


def merge_reviews(*reviews):
    """The findings of several reviewers as one list for `hits`: each reviewer misses what another finds (a story with "una libro" passed one
    reviewer with no finding at all). Findings on the same words count once (see summarize_findings)."""
    out = []
    for hits in reviews:
        out.extend(hits or ())
    return out
