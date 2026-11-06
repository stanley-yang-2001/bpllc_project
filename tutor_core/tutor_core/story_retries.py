"""When a story is not good enough the first time: at most one more try per problem, and the better text is kept.

Nothing is hidden: the report measures whichever story is returned. Each step costs a second model call only when its problem is
there. The three problems, in order:
  * another language than asked (the model answered in English, or mixed English in; seen 23 Oct, Chinese);
  * cut off mid-sentence, or far from the length a tier asked for (25 Oct: Chinese Medium and Hard came out at 50 to 70% of the
    length; a Korean story ended mid-word);
  * written in broken, list-like or repetitive sentences (6 Nov): one repair call that names the problems; and, when switched on
    (STORY_PROOFREAD=1), one proofreading call for grammar on every story. A rewrite is used only if it is still in the language, still
    complete, about as long and keeps the learner's words (see `_safe`); otherwise the first text stays;
  * English only: more words outside the learner's list than the prompt allows (the richer kinds failed this check every time in
    the 21 Oct batches).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from . import difficulty as _d
from .languages import LANGUAGES
from .prompts import build_proofread_prompt, build_repair_prompt, extract_final_passage
from .quality import check_passage, ends_complete, fluency_problems, has_dangling_sentence, language_check

STRAY_LIMIT = 5        # the prompt allows about this many words outside the learner's list (English)


@dataclass(frozen=True)
class RetryPolicy:
    language: str                       # ISO code
    prompt: str
    words: list
    difficulty: Optional[dict]
    call: Callable[[str], str]
    proofread: bool = False             # one grammar pass on every story (an extra model call)

    def improve(self, passage: str) -> str:
        passage = self._right_language(passage)
        passage = self._complete_and_sized(passage)
        passage = self._fewer_strays(passage)
        passage = self._natural(passage)
        return self._proofread(passage) if self.proofread else passage

    def _name(self) -> str:
        return LANGUAGES[self.language].name

    def _size(self, text: str) -> int:
        return _d.measure(text, self.language, self.words)["length"]

    def _used(self, text: str) -> int:
        low = text.casefold()
        return sum(1 for w in self.words if w.casefold() in low)

    def _safe(self, before: str, after: str, tolerance: float = 0.20) -> bool:
        """A rewrite replaces the first text only when it is still a good text of the same kind: right language, finished, about the
        same length (within 20%; a repair of list-like text may be up to 60% longer) and still using the learner's words."""
        if not after.strip() or not ends_complete(after) or has_dangling_sentence(after, self.language):
            return False
        if self.language != "en" and language_check(after, self._name(), "")["verdict"] not in ("ok", "not_checked"):
            return False
        was, now = self._size(before), self._size(after)
        if was and abs(now - was) / was > tolerance:
            return False
        return self._used(after) >= self._used(before) * 0.9

    def _rewrite(self, prompt: str) -> str:
        try:
            return extract_final_passage(self.call(prompt))
        except Exception:
            return ""

    def _natural(self, passage: str) -> str:
        """Broken, list-like or repetitive sentences: one repair that names what is wrong; kept only if it is safe and has fewer problems."""
        unspaced = _d.is_unspaced(self.language)
        problems = fluency_problems(passage, unspaced)
        if not problems:
            return passage
        second = self._rewrite(build_repair_prompt(self._name(), passage, problems, ", ".join(self.words)))
        if self._safe(passage, second, 0.60) and len(fluency_problems(second, unspaced)) < len(problems):
            return second
        return passage

    def _proofread(self, passage: str) -> str:
        second = self._rewrite(build_proofread_prompt(self._name(), passage, ", ".join(self.words)))
        return second if self._safe(passage, second) else passage

    def _again(self) -> str:
        try:
            return extract_final_passage(self.call(self.prompt))
        except Exception:
            return ""

    def _right_language(self, passage: str) -> str:
        if self.language == "en" or language_check(passage, LANGUAGES[self.language].name, "")["verdict"] in ("ok", "not_checked"):
            return passage
        second = self._again()
        return second if second.strip() else passage

    def _complete_and_sized(self, passage: str) -> str:
        diff, language, words = self.difficulty, self.language, self.words

        def gap(text):
            if not diff:
                return 0.0
            want = diff["length"] * (_d.CHARS_PER_WORD if _d.is_unspaced(language) else 1)
            return abs(_d.measure(text, language, words)["length"] - want) / want

        def bad(text):
            return (not ends_complete(text)) or has_dangling_sentence(text, language) or gap(text) > _d.LENGTH_TOLERANCE

        if not bad(passage):
            return passage
        second = self._again()
        if not second.strip():
            return passage

        def rank(text):
            return (not ends_complete(text), has_dangling_sentence(text, language), gap(text))
        return second if rank(second) < rank(passage) else passage

    def _fewer_strays(self, passage: str) -> str:
        if self.language != "en":
            return passage
        everyday = _d.everyday_words("en")
        vocab = ", ".join(self.words)

        def strays(text):
            return check_passage(text, vocab, check_vocab=True, max_oov=STRAY_LIMIT, everyday=lambda w: w in everyday)["oov_count"]

        first = strays(passage)
        if first <= STRAY_LIMIT:
            return passage
        second = self._again()
        if not second.strip() or strays(second) >= first:
            return passage
        return second
