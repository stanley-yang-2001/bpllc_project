"""Language handling: the target language is written out (never left to English), and the templates are adapted for non-English stories."""
from __future__ import annotations

from .templates import VALID_STYLES

# --- language handling -------------------------------------------------------------------------
# Found in the first live routing run: only 5 of 15 non-English stories were actually written in
# the requested language. Two causes are addressed here:
#   1. The vocabulary list is English, and "use words from this list" keeps the model in English.
#      For other languages the prompt now says the list holds English MEANINGS to be expressed in
#      the target language, with no English left in.
#   2. The tone examples in the templates are written in English, which primes English output.
#      For other languages the English example is left out.
# The English prompt is untouched (the two templates above are used exactly as written).

_NATIVE_LANGUAGE_NAMES = {
    "\u65e5\u672c\u8a9e": "Japanese", "\u306b\u307b\u3093\u3054": "Japanese", "nihongo": "Japanese",
    "\u4e2d\u6587": "Chinese", "\u6c49\u8bed": "Chinese", "\u6f22\u8a9e": "Chinese",
    "\u666e\u901a\u8bdd": "Chinese", "\u56fd\u8bed": "Chinese", "\u570b\u8a9e": "Chinese",
    "\ud55c\uad6d\uc5b4": "Korean",
    "espa\u00f1ol": "Spanish", "espanol": "Spanish", "castellano": "Spanish",
    "fran\u00e7ais": "French", "francais": "French",
    "deutsch": "German", "italiano": "Italian",
    "portugu\u00eas": "Portuguese", "portugues": "Portuguese",
    "\u0440\u0443\u0441\u0441\u043a\u0438\u0439": "Russian",
    "\u0627\u0644\u0639\u0631\u0628\u064a\u0629": "Arabic",
    "\u0939\u093f\u0928\u094d\u0926\u0940": "Hindi",
    "\u03b5\u03bb\u03bb\u03b7\u03bd\u03b9\u03ba\u03ac": "Greek",
    "\u0e44\u0e17\u0e22": "Thai", "\u05e2\u05d1\u05e8\u05d9\u05ea": "Hebrew",
    "nederlands": "Dutch", "svenska": "Swedish", "t\u00fcrk\u00e7e": "Turkish", "polski": "Polish",
    "ti\u1ebfng vi\u1ec7t": "Vietnamese", "bahasa indonesia": "Indonesian",
    "ingl\u00e9s": "English", "ingles": "English", "anglais": "English", "englisch": "English",
    "\u82f1\u8a9e": "English", "\u82f1\u8bed": "English",
}


def normalize_language(language) -> str:
    """The English name of a language, whatever the learner typed: "\u65e5\u672c\u8a9e" -> "Japanese",
    "fran\u00e7ais" -> "French", " spanish " -> "Spanish". Unknown names are only tidied up."""
    text = " ".join((language or "").split())
    if not text:
        return ""
    known = _NATIVE_LANGUAGE_NAMES.get(text.casefold())
    if known:
        return known
    if text.isascii():
        return " ".join(word.capitalize() for word in text.split(" "))
    return text


def is_english(language) -> bool:
    return normalize_language(language) == "English"


_LANGUAGE_BLOCK = (
    "LANGUAGE RULE (most important): write the ENTIRE passage or dialogue (everything after "
    "the ===STORY=== line) in {language}, and nothing in English. The vocabulary list below is "
    "written in English: treat each entry as a MEANING and use its natural {language} word for "
    "it (if the list has \"water\", write the {language} word for water). Do not leave any "
    "English word in the story; only character names may stay as they are.\n\n"
)
_LANGUAGE_REMINDER = (
    "Final check before you write: every word of the story is in {language} \u2014 each one the "
    "{language} equivalent of a word from the list, or a basic grammar word or simple verb. "
    "No English.\n\n"
)

# The vocabulary variant: a learner's word list is stored PER LANGUAGE, so a Spanish learner's list is already
# Spanish. Telling the model those entries are English "meanings" to be translated is wrong for them and makes it hunt
# for translations of words that are already in the target language. This variant says the list is already in the
# target language and must be used as written (inflected for grammar), never translated.
_LANGUAGE_BLOCK_IN_TARGET = (
    "LANGUAGE RULE (most important): write the ENTIRE passage or dialogue (everything after "
    "the ===STORY=== line) in {language}, and nothing in English. The vocabulary list below is "
    "already written in {language}: use those words as they are (you may inflect them for "
    "grammar) and do not translate, replace or explain them. Do not leave any English word in "
    "the story; only character names may stay as they are.\n\n"
)
_LANGUAGE_REMINDER_IN_TARGET = (
    "Final check before you write: every word of the story is in {language} \u2014 each one a "
    "word from the list (as written or inflected), or a basic {language} grammar word or simple "
    "verb. No English.\n\n"
)


def _template_for_other_languages(template: str, vocab_in_target: bool = False) -> str:
    """The same template with the language rule added after the intro, the English tone example
    removed (if it has one), and a final reminder before 'Begin:'. `vocab_in_target` swaps in the
    wording for a word list that is already written in the target language."""
    block = _LANGUAGE_BLOCK_IN_TARGET if vocab_in_target else _LANGUAGE_BLOCK
    reminder = _LANGUAGE_REMINDER_IN_TARGET if vocab_in_target else _LANGUAGE_REMINDER
    intro_end = template.index("\n\n") + 2
    begin = template.index("Begin:")
    example_start = template.find("Tone example only")
    middle_end = example_start if example_start != -1 else begin
    return template[:intro_end] + block + template[intro_end:middle_end] + reminder + template[begin:]


_OTHER_LANGUAGE_STYLES = {style: _template_for_other_languages(t) for style, t in VALID_STYLES.items()}
_IN_TARGET_STYLES = {style: _template_for_other_languages(t, True) for style, t in VALID_STYLES.items()}


# --- story variety (Step 10, tuning change #2) ---------------------------------------------------
# Reading 48 generated stories showed 81% mentioned water and ~75% were somebody asking for or
# receiving something. The classic prompts define the story's "Event" as a question or request
# needing a response, offer only two forms (narration, dialogue), cap stories at 5-6 short
# sentences, and nothing in the code varies the topic. So, in addition to the two classic styles
# (left exactly as they were), there are more story TYPES, a TOPIC seed chosen in code without
# repeating recent topics, a looser word rule (the vocabulary stays central, a few very common
# everyday words are allowed) and longer, more flexible lengths.
