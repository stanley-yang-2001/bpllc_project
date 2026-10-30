"""Practice material made from a learner's own words (M7). The material is made on the spot and never stored; what the learner
got right or wrong is remembered by services/progress.py so that words come back when they are due.

One module per mode, so a new mode is a new file: flashcards.py (flashcards, dictation, parts of speech), choices.py, cloze.py."""
from .choices import choice_cards
from .cloze import MIN_CHARS_IN_UNSPACED_SENTENCE, MIN_WORDS_IN_SENTENCE, can_cloze, make_cloze, vocabulary_of, word_ids_of
from .flashcards import dictation, flashcards, pos_cards
from .limits import CHOICES, MAX_ITEMS

__all__ = ["CHOICES", "MAX_ITEMS", "MIN_CHARS_IN_UNSPACED_SENTENCE", "MIN_WORDS_IN_SENTENCE", "can_cloze", "choice_cards", "dictation",
           "flashcards", "make_cloze", "pos_cards", "vocabulary_of", "word_ids_of"]
