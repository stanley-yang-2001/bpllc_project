"""Grammar findings from several sources, in one shape (see base.py). `builtin_hits` is always available and free; the other
sources (languagetool.py, audit.py) are optional and are asked by whoever has the server or the model to ask."""
from .base import Checker, Hit, affected_sentences, apply_certain, locate, merge, sentence_spans
from .rules import BuiltinRules, builtin_hits

__all__ = ["BuiltinRules", "Checker", "Hit", "affected_sentences", "apply_certain", "builtin_hits", "locate", "merge", "sentence_spans"]
