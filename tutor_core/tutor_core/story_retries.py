"""When a story is not good enough the first time: at most one more try per problem, and the better text is kept.

Nothing is hidden: the report measures whichever story is returned. Each step costs a second model call only when its problem is
there. The three problems, in order:
  * another language than asked (the model answered in English, or mixed English in; seen 23 Oct, Chinese);
  * cut off mid-sentence, or far from the length a tier asked for (25 Oct: Chinese Medium and Hard came out at 50 to 70% of the
    length; a Korean story ended mid-word);
  * English only: more words outside the learner's list than the prompt allows (the richer kinds failed this check every time in
    the 21 Oct batches).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional

from . import difficulty as _d
from .languages import LANGUAGES
from .prompts import extract_final_passage
from .quality import check_passage, ends_complete, has_dangling_sentence, language_check

STRAY_LIMIT = 5        # the prompt allows about this many words outside the learner's list (English)


@dataclass(frozen=True)
class RetryPolicy:
    language: str                       # ISO code
    prompt: str
    words: list
    difficulty: Optional[dict]
    call: Callable[[str], str]

    def improve(self, passage: str) -> str:
        passage = self._right_language(passage)
        passage = self._complete_and_sized(passage)
        return self._fewer_strays(passage)

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
