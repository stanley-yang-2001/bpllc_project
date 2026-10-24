"""Practice material made from a learner's own words (M7). Nothing here is stored: a result is shown and forgotten."""
from __future__ import annotations

import random
import re

from tutor_core.languages import LANGUAGES
from tutor_core.quality import word_forms

from ..db import cursor

MAX_ITEMS = 8
CHOICES = 4                       # the answer plus up to three other words from the learner's own list
_TOKEN = re.compile(r"[^\W\d_]+(?:['’\-][^\W\d_]+)*")
_LABEL = re.compile(r"^\s*[^\W\d_][^\W\d_'\-]*(?:\s[^\W\d_][^\W\d_'\-]*)?\s*:\s+")       # "Ana: " at the start of a line
_SENTENCE = re.compile(r"(?<=[.!?…])\s+")
MIN_WORDS_IN_SENTENCE = 3


def flashcards(conn, user_id: int, language: str, limit: int) -> dict:
    """Shuffled words that have a meaning (a card with nothing on its back is no use)."""
    with cursor(conn) as cur:
        cur.execute("SELECT id, word, meaning FROM tutor.words WHERE user_id = %s AND language = %s "
                    "AND meaning IS NOT NULL AND btrim(meaning) <> '' ORDER BY random() LIMIT %s", (user_id, language, limit))
        items = cur.fetchall()
        cur.execute("SELECT count(*) AS n FROM tutor.words WHERE user_id = %s AND language = %s "
                    "AND meaning IS NOT NULL AND btrim(meaning) <> ''", (user_id, language))
        return {"items": items, "total": cur.fetchone()["n"]}


def can_cloze(language: str) -> bool:
    """Every listed language. Languages that put spaces between words (tier 1) blank a whole word. Chinese, Japanese and
    Korean (tier 2) have no word splitter here, so they blank the learner's OWN list words wherever they appear in the text."""
    return LANGUAGES.get(language) is not None


def _unspaced(language: str) -> bool:
    lang = LANGUAGES.get(language)
    return bool(lang and lang.tier == 2)


def _vocabulary(conn, user_id: int, language: str) -> dict[str, str]:
    """single-word entries only: word -> meaning. A phrase cannot be matched to one blank."""
    with cursor(conn) as cur:
        cur.execute("SELECT word, meaning FROM tutor.words WHERE user_id = %s AND language = %s ORDER BY id", (user_id, language))
        return {r["word"].lower(): (r["meaning"] or "") for r in cur.fetchall() if len(_TOKEN.findall(r["word"])) == 1}


def _units(body: str):
    for line in body.split("\n"):
        for part in _SENTENCE.split(line):
            if part.strip():
                yield part


_UNSPACED_SENTENCE = re.compile(r"(?<=[。！？!?….])\s*")
_UNSPACED_LABEL = re.compile(r"^\s*[^\W\d_][^\W\d_'\-]*(?:\s[^\W\d_][^\W\d_'\-]*)?\s*[:：]\s*")     # "Ana:" or "アナ：" at the start of a line
MIN_CHARS_IN_UNSPACED_SENTENCE = 4


def _boundaries(unit: str, language: str):
    """The character offsets where a word starts or ends according to the splitter (tutor_core.splitter), or None when there is
    no splitter or its pieces do not add up to the text. A word the learner listed only counts where it starts and ends on one."""
    from tutor_core import splitter
    tokens = splitter.split(unit, language)
    if not tokens:
        return None
    if "".join(t.surface for t in tokens) != unit.replace(" ", "").replace("\u3000", "") and "".join(t.surface for t in tokens) != unit:
        return None
    marks, pos = {0}, 0
    for t in tokens:
        pos = unit.find(t.surface, pos) if t.surface.strip() else pos
        if pos < 0:
            return None
        marks.add(pos)
        pos += len(t.surface)
        marks.add(pos)
    return marks


def _make_cloze_by_word(body: str, vocabulary: dict[str, str], rng: random.Random, language: str = "") -> list[dict]:
    """Chinese, Japanese and Korean: no splitter, so look for the learner's own words inside each sentence. The longest word
    wins where two overlap (学校 before 学), the earliest not-yet-used word in a sentence is blanked, and whatever is stuck to
    it (a Korean ending, a Japanese particle) stays in the text around the blank."""
    words = sorted((w for w in vocabulary if w), key=len, reverse=True)
    items, used = [], set()
    for line in body.split("\n"):
        for unit in _UNSPACED_SENTENCE.split(line):
            unit = unit.strip()
            label = _UNSPACED_LABEL.match(unit)
            start = label.end() if label else 0
            if len(unit) - start < MIN_CHARS_IN_UNSPACED_SENTENCE:
                continue
            covered, found = [False] * len(unit), []
            marks = _boundaries(unit[start:], language) if language else None
            for w in words:
                pos = start
                while (i := unit.find(w, pos)) >= 0:
                    pos = i + len(w)
                    if marks is not None and (i - start not in marks or i - start + len(w) not in marks):
                        continue              # inside a longer word the splitter found, such as 面 in 面包
                    if not any(covered[i:i + len(w)]):
                        covered[i:i + len(w)] = [True] * len(w)
                        found.append((i, w))
            choice = min(((i, w) for i, w in found if w not in used), default=None)
            if choice is None:
                continue
            i, w = choice
            used.add(w)
            picks = rng.sample([x for x in vocabulary if x != w], min(CHOICES - 1, len(vocabulary) - 1))
            choices = [w] + picks
            rng.shuffle(choices)
            items.append({"before": unit[:i], "after": unit[i + len(w):], "answer": w, "hint": vocabulary[w], "choices": choices})
            if len(items) == MAX_ITEMS:
                return items
    return items


def make_cloze(body: str, language: str, vocabulary: dict[str, str], rng: random.Random | None = None) -> list[dict]:
    rng = rng or random.Random()
    if _unspaced(language):
        return _make_cloze_by_word(body, vocabulary, rng, language)
    english = language == "en"
    base_of = {w: w for w in vocabulary}
    if english:
        for w in vocabulary:
            for form in word_forms(w):
                base_of.setdefault(form, w)          # an exact entry always wins over a guessed inflection
    items, used = [], set()
    for unit in _units(body):
        label = _LABEL.match(unit)
        start = label.end() if label else 0
        tokens = [m for m in _TOKEN.finditer(unit) if m.start() >= start]
        if len(tokens) < MIN_WORDS_IN_SENTENCE:
            continue
        for m in tokens:
            base = base_of.get(m.group(0).lower())
            if base and base not in used:
                used.add(base)
                others = [w for w in vocabulary if w != base]
                picks = rng.sample(others, min(CHOICES - 1, len(others)))
                choices = [m.group(0)] + picks
                rng.shuffle(choices)
                items.append({"before": unit[:m.start()], "after": unit[m.end():], "answer": m.group(0),
                              "hint": vocabulary[base], "choices": choices})
                break
        if len(items) == MAX_ITEMS:
            break
    return items
