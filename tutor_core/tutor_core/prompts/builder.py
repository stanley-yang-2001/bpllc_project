"""Building the story prompt, and recognising what kind and topic a built prompt asked for."""
from __future__ import annotations

from .kinds import ALL_STORY_TYPES, CUSTOM_TYPE_MAX_CHARS, CUSTOM_TYPE_MAX_WORDS, STORY_TYPES, TOPICS, _CUSTOM_FORM, _CUSTOM_SPEC_LENGTH, _CUSTOM_SPEC_RULE, _CUSTOM_TOPIC, _IN_TARGET_VARIETY, _OTHER_LANGUAGE_VARIETY, _RECENT_TOPICS, _VARIETY_TEMPLATE, choose_story_type, choose_topic, clean_free_text, clean_topic, is_custom_type
from .language_blocks import _IN_TARGET_STYLES, _OTHER_LANGUAGE_STYLES, is_english, normalize_language
from .templates import VALID_STYLES
from typing import Optional
import re

_LENGTH_PHRASE = re.compile(r"([Aa])im for \d+ to \d+ (?:short )?(sentences|lines)(?: of back-and-forth conversation)?(?: \((?:up to )?[\d-]+ words each\))?")


_FINISH_RULE = ("The passage ends with the story itself: no thanks, goodbye, notes or translation after the last sentence. "
                "Before you answer, re-read it once for grammar: articles, verb endings, and gender and number agreement.")
_BEGIN = "Begin: planning, then delimiter, then passage."


def _with_finish_rule(prompt: str) -> str:
    """25 Oct: a Korean story ended with a stray \"thank you\" line, and German and Portuguese stories had article and
    agreement slips. A short rule before the final instruction, for target-language stories only."""
    i = prompt.rfind(_BEGIN)
    return prompt if i < 0 else prompt[:i] + _FINISH_RULE + "\n\n" + prompt[i:]


def build_story_prompt(language: str, words: str, style: Optional[str] = None,
                       topic: Optional[str] = None, rng=None, *, vocab_in_target: bool = False,
                       difficulty: Optional[dict] = None) -> str:
    """style: one of ALL_STORY_TYPES, or None/"random" for a weighted random choice. topic only
    applies to the new story types; when omitted it is chosen at random, avoiding recent topics.
    vocab_in_target: the word list is already written in `language` (a learner's per-language list),
    so the prompt says to use the words as written instead of translating English meanings. It has
    no effect for English, whose prompts are unchanged.
    A RANDOM choice of kind is limited to the classic styles for English (see choose_story_type); a named kind is always honoured.
    difficulty: targets from tutor_core.difficulty.resolve (or None); a note stating them goes at the top of the prompt."""
    prompt = _build_story_prompt(language, words, style, topic, rng, vocab_in_target)
    if vocab_in_target and not is_english(normalize_language(language)):
        prompt = _with_finish_rule(prompt)
    if difficulty:
        # The built-in templates ask for 5 to 9 sentences; with a tier that sentence count is replaced by the tier's own.
        from ..difficulty import CHARS_PER_WORD, ask_size, prompt_note
        from ..languages import LANGUAGES
        name = (normalize_language(language) or "").casefold()
        code = next((c for c, lang in LANGUAGES.items() if lang.name.casefold() == name or c == name), "en")
        asked = ask_size(code, difficulty["length"])
        count = max(2, round(asked / 10))
        if code in ("zh", "ja"):       # 24 Oct: Chinese came out at 40 to 65% of the length asked; say the characters per sentence and in all
            each = f"about {round(10 * CHARS_PER_WORD)} characters each, about {round(asked * CHARS_PER_WORD)} characters in all"
        elif code == "ko":
            each = f"about 10 words each, about {asked} words in all"
        else:
            each = "about 10 words each"
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
        style = choose_story_type(rng, classic_only=english)

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


