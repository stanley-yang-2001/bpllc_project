"""Building the story prompt, and recognising what kind and topic a built prompt asked for."""
from __future__ import annotations

from .kinds import ALL_STORY_TYPES, CUSTOM_TYPE_MAX_CHARS, CUSTOM_TYPE_MAX_WORDS, STORY_TYPES, TOPICS, _CUSTOM_FORM, _CUSTOM_SPEC_LENGTH, _CUSTOM_SPEC_RULE, _CUSTOM_TOPIC, _IN_TARGET_VARIETY, _OTHER_LANGUAGE_VARIETY, _RECENT_TOPICS, _VARIETY_TEMPLATE, choose_story_type, rich_kinds_in_random, choose_topic, clean_free_text, clean_topic, is_custom_type
from .language_blocks import _IN_TARGET_STYLES, _OTHER_LANGUAGE_STYLES, is_english, normalize_language
from .templates import VALID_STYLES
from typing import Optional
import re

_LENGTH_PHRASE = re.compile(r"([Aa])im for \d+ to \d+ (?:short )?(sentences|lines)(?: of back-and-forth conversation)?(?: \((?:up to )?[\d-]+ words each\))?")


_FINISH_RULE = ("The passage ends with the story itself: no thanks, goodbye, notes or translation after the last sentence. "
                "Before you answer, re-read it once for grammar: articles, verb endings, and gender and number agreement.")
_NATURAL_RULE = ("Write complete, natural sentences: every sentence has a subject and a verb, with correct grammar. Do not just list words. "
                 "The text has a beginning, a middle and an end.")
# 14 Nov 2026 (writer rules, OFF unless StoryOptions.rules): the 13 Nov Kaggle run's ten English first drafts had 25 reviewer findings; 10 were a missing article or
# possessive ("to kitchen", "in house"), 4 an unneeded word or phrase stuck on ("please", "goodbye today") and 4 an adverb in the wrong form or place. The prompts ask for
# "short sentences" and "no rare words" and never say that short is not telegraphic. The text is what the reviewers' naturalness rating punishes, said to the writer.
_WRITER_RULES = ("Small words stay: a short sentence is still a complete one, so never drop an article, possessive, preposition, particle or verb ending that the language needs{example}. "
                 "Use a listed word only where it belongs: if it does not fit a sentence, leave it out instead of attaching it after a comma or adding a sentence just to use it. "
                 "Do not end sentences with filler such as {filler} to make the text longer.")
_WRITER_EXAMPLE = {True: " (\"the drawer\", not \"drawer\"; \"to the park\", not \"to park\")", False: ""}
_WRITER_FILLER = {True: "\"today\", \"now\", \"still\" or \"indeed\"", False: "the words for \"today\", \"now\", \"still\" or \"indeed\""}
# 20 Nov 2026 (writer v2, OFF unless StoryOptions.writer_v2): after review and repair what the reviewers still fail is how the text reads: every sentence the same length, the same
# opener, "today" on the end, one sentence per line, the same name in 22 of 150 stories. The block asks for a scene decided before writing (the model's own reasoning does it; no plan
# is written out, so no plan can leak into the text), words placed where an event needs them, a mix of short and long sentences, and one or two paragraphs; the name, place and time come
# from code (story_seed.py). The level stays set by the level note's sentence range (it fits 29 of 30 stories); this block adds spread around that range, never a longer average.
_WRITER_V2 = ("{seed} Make it read like something a native speaker would really write, not like a textbook drill. Before you write, decide where and when it happens, three or "
              "four events where each one causes the next, and one concrete detail of sight, sound, smell or touch; put each listed word where its event needs it, and leave out a word "
              "that does not fit. Mix short sentences (3 to 5 words) with longer ones joined by words like {connectors}; never three sentences in a row of about the same length. "
              "Do not start more than two sentences in a row with the same word. Do not end a sentence on a time word such as {filler} unless the reader needs it. "
              "Keep it easy with common words and simple grammar, not with sentences that are all very short; no sentence over 20 words.{layout}")
_V2_LAYOUT = " Write one or two paragraphs, with no line break between the sentences of a paragraph."
_BEGIN = "Begin:"          # every template ends with a line that starts like this (the rest of the line differs)


def _with_finish_rule(prompt: str) -> str:
    """25 Oct: a Korean story ended with a stray \"thank you\" line, and German and Portuguese stories had article and
    agreement slips. A short rule before the final instruction, for target-language stories only."""
    i = prompt.rfind(_BEGIN)
    return prompt if i < 0 else prompt[:i] + _FINISH_RULE + "\n\n" + prompt[i:]


def _with_natural_rule(prompt: str) -> str:
    """6 Nov: telegraphic, list-like sentences came out of tight length caps. One short rule for every language but English, before the final instruction."""
    i = prompt.rfind(_BEGIN)
    return prompt if i < 0 else prompt[:i] + _NATURAL_RULE + "\n\n" + prompt[i:]


def writer_rules(english: bool) -> str:
    """The text of the writer rules; the example is English only, because an English example in a French prompt would be copied."""
    return _WRITER_RULES.format(example=_WRITER_EXAMPLE[english], filler=_WRITER_FILLER[english])


def _with_writer_rules(prompt: str, english: bool) -> str:
    """Before the final instruction like the other rules; appended when the prompt has none, so the option never silently does nothing."""
    rules = writer_rules(english)
    i = prompt.rfind(_BEGIN)
    return prompt.rstrip() + "\n\n" + rules if i < 0 else prompt[:i] + rules + "\n\n" + prompt[i:]


def _language_code(language: str) -> str:
    from ..languages import LANGUAGES
    name = (normalize_language(language) or "").casefold()
    return next((c for c, lang in LANGUAGES.items() if lang.name.casefold() == name or c == name), "en")


def writer_v2_block(code: str, kind: Optional[str], rng=None) -> str:
    """The writer v2 text for a language code and a story kind, with the name, place and time drawn by code (story_seed.py)."""
    from ..story_diagnose import CONNECTORS, FILLER
    from ..story_seed import note
    filler = ", ".join(f'"{w}"' for w in sorted(FILLER.get(code, FILLER["en"]))[:5])
    return _WRITER_V2.format(seed=note(code, kind, rng), connectors=CONNECTORS.get(code, CONNECTORS["en"]), filler=filler,
                             layout="" if kind == "dialogue" else _V2_LAYOUT)


def _with_writer_v2(prompt: str, code: str, kind: Optional[str], rng=None) -> str:
    """Before the final instruction like the other rules; appended when the prompt has none, so the option never silently does nothing."""
    block = writer_v2_block(code, kind, rng)
    i = prompt.rfind(_BEGIN)
    return prompt.rstrip() + "\n\n" + block if i < 0 else prompt[:i] + block + "\n\n" + prompt[i:]


def build_story_prompt(language: str, words: str, style: Optional[str] = None,
                       topic: Optional[str] = None, rng=None, *, vocab_in_target: bool = False,
                       difficulty: Optional[dict] = None, rules: bool = False, writer_v2: bool = False) -> str:
    """style: one of ALL_STORY_TYPES, or None/"random" for a weighted random choice. topic only
    applies to the new story types; when omitted it is chosen at random, avoiding recent topics.
    vocab_in_target: the word list is already written in `language` (a learner's per-language list),
    so the prompt says to use the words as written instead of translating English meanings. It has
    no effect for English, whose prompts are unchanged.
    A RANDOM choice of kind is limited to the classic styles for English (see choose_story_type); a named kind is always honoured.
    difficulty: targets from tutor_core.difficulty.resolve (or None); a note stating them goes at the top of the prompt.
    rules: add the writer rules (small words stay, no tacked-on words, no filler) before the final instruction; off, the prompt is exactly what it was.
    writer_v2: add the writer v2 block (a scene decided first, mixed sentence length, varied openers, paragraphs, a name, place and time drawn by code); off, nothing changes."""
    prompt = _build_story_prompt(language, words, style, topic, rng, vocab_in_target)
    if not is_english(normalize_language(language)):       # the English prompts stay exactly as they were (pinned by tests); English grammar is handled by the repair and proofreading calls
        prompt = _with_natural_rule(prompt)
    if vocab_in_target and not is_english(normalize_language(language)):
        prompt = _with_finish_rule(prompt)
    if rules:
        prompt = _with_writer_rules(prompt, is_english(normalize_language(language)))
    if writer_v2:
        prompt = _with_writer_v2(prompt, _language_code(language), describe_prompt(prompt)[0], rng)
    if difficulty:
        # The built-in templates ask for 5 to 9 sentences; with a tier that sentence count is replaced by the tier's own.
        from ..difficulty import CHARS_PER_WORD, ask_size, prompt_note
        from ..languages import LANGUAGES
        name = (normalize_language(language) or "").casefold()
        code = next((c for c, lang in LANGUAGES.items() if lang.name.casefold() == name or c == name), "en")
        asked = ask_size(code, difficulty["length"])
        from ..difficulty.note import SENTENCE_WORDS, range_prompt_on
        per = SENTENCE_WORDS.get(difficulty.get("tier") if difficulty.get("tier") in SENTENCE_WORDS else "medium", 10) if range_prompt_on() else 10
        count = max(2, round(asked / per))
        if code in ("zh", "ja"):       # 24 Oct: Chinese came out at 40 to 65% of the length asked; say the characters per sentence and in all
            each = f"about {round(per * CHARS_PER_WORD)} characters each, about {round(asked * CHARS_PER_WORD)} characters in all"
        elif code == "ko":
            each = f"about {per} words each, about {asked} words in all"
        else:
            each = f"about {per} words each"
        prompt = _LENGTH_PHRASE.sub(lambda m: f"{m.group(1)}im for about {count} {m.group(2)} ({each})", prompt)
        prompt = prompt_note(code, difficulty) + "\n\n" + prompt
    return prompt


def _build_story_prompt(language, words, style, topic, rng, vocab_in_target):
    language = normalize_language(language)
    words = (words or "").strip()
    if not language:
        raise ValueError("language must be a non-empty string")
    if not words:
        raise ValueError("words must be a non-empty string")
    english = is_english(language)
    if not style or style == "random":
        style = choose_story_type(rng, classic_only=english and not rich_kinds_in_random())

    if style in VALID_STYLES:  # the two classic prompts, unchanged
        templates = VALID_STYLES if english else (_IN_TARGET_STYLES if vocab_in_target else _OTHER_LANGUAGE_STYLES)
        return templates[style].format(language=language, words=words)
    if style in STORY_TYPES or is_custom_type(style):
        if is_custom_type(style):
            label = clean_free_text(style, CUSTOM_TYPE_MAX_CHARS, CUSTOM_TYPE_MAX_WORDS)
            if label is None:
                raise ValueError(f"style must be one of {list(ALL_STORY_TYPES)} or a short plain-text label, got {style!r}")
            spec = {"form": _CUSTOM_FORM.format(label=label), "length": _CUSTOM_SPEC_LENGTH, "rule": _CUSTOM_SPEC_RULE}
        else:
            spec = STORY_TYPES[style]
        if topic and topic not in TOPICS:
            clean = clean_topic(topic)
            if clean is None:
                raise ValueError("topic must be a short plain-text subject")
            topic = clean if clean in TOPICS else _CUSTOM_TOPIC.format(topic=clean)
        if not topic:
            topic = choose_topic(rng, recent=_RECENT_TOPICS)
            _RECENT_TOPICS.append(topic)
        template = _VARIETY_TEMPLATE if english else (_IN_TARGET_VARIETY if vocab_in_target else _OTHER_LANGUAGE_VARIETY)
        return template.format(language=language, words=words, topic=topic, **spec)
    raise ValueError(f"style must be one of {list(ALL_STORY_TYPES)}, got {style!r}")


def describe_prompt(prompt: str):
    """(story type, topic) of a prompt built by build_story_prompt; ("unknown", None) otherwise. A custom type comes back as
    its label."""
    prompt = prompt or ""
    if "short, simple dialogue" in prompt:
        return "dialogue", None
    if "simple reading passage" in prompt:
        return "narration", None
    story_type = None
    for known, spec in STORY_TYPES.items():
        if f"Form: {spec['form']}." in prompt:
            story_type = known
            break
    if story_type is None:
        custom = re.search(r'Form: a text of the kind "([^"]+)" \(', prompt)
        if not custom:
            return "unknown", None
        story_type = custom.group(1)
    free = re.search(r'Topic: "([^"]+)" \(a subject to write about', prompt)
    if free:
        return story_type, free.group(1)
    match = re.search(r"Topic: (.*?)\.\n", prompt)
    return story_type, (match.group(1) if match else None)


