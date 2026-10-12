"""A stand-in tutor for AI_MODE=stub: no Langflow, no Groq, no network.

It exists so the whole Chat path (page, API, gate, tool trace, the vocabulary list updating) can be developed
and tested without an AI. It answers a few fixed requests the way the real tutor's tools do:

    "add the word bread"            -> adds the word to THIS learner's list for the active language
    "tell me a story (in French)"   -> a fixed short dialogue, or the not-available-yet message
    anything else                   -> a short help message, no tool call

It is deterministic on purpose. It is not a model of the tutor's intelligence, only of its response shape.
"""
from __future__ import annotations

import re

from tutor_core.languages import LANGUAGES, normalize_language, stories_enabled

from ..db import connection
from ..errors import AppError
from . import vocab
from .langflow_client import ChatResult, ToolCall

_ADD = re.compile(r"\badd\s+(?:the\s+)?word\s+[\"']?([^\s\"'.,!?;:]+)", re.IGNORECASE)
_TOKEN = re.compile(r"\w+", re.UNICODE)

STORIES = {
    "en": "Ana: Hi! Do you have any bread?\nBen: Yes, here you are.\nAna: Thank you!",
    "es": "Ana: ¡Hola! ¿Tienes pan?\nBen: Sí, aquí tienes.\nAna: ¡Gracias!",
    "fr": "Ana : Bonjour ! Avez-vous du pain ?\nBen : Oui, voici.\nAna : Merci !",
    "ja": "アナ：こんにちは！パンはありますか。\nベン：はい、どうぞ。\nアナ：ありがとう！",
}
HELP = ('I can add words to your vocabulary (say "add the word bread") '
        'or write you a short story (say "tell me a story in Spanish").')


def _language_named_in(message: str) -> str | None:
    """A language the learner named ('in French'). Two-letter tokens are skipped: 'it' is English, not Italian."""
    for token in _TOKEN.findall(message):
        if len(token) > 2:
            code = normalize_language(token)
            if code:
                return code
    return None


class StubChat:
    def __init__(self, get_pool):
        self._get_pool = get_pool

    def run(self, *, user_id: int, language: str, message: str, session_id: str) -> ChatResult:
        match = _ADD.search(message)
        if match:
            return self._add_word(user_id, language, match.group(1))
        if "story" in message.lower() or "dialogue" in message.lower():
            return self._story(_language_named_in(message) or language)
        return ChatResult(reply=HELP)

    def _add_word(self, user_id: int, language: str, word: str) -> ChatResult:
        name = LANGUAGES[language].name
        args = {"word": word}
        try:
            with connection(self._get_pool()) as conn:
                row = vocab.add_word(conn, user_id, language, word, None)
            text, failed = f"Added '{row['word']}' to your {name} vocabulary.", False
        except AppError as e:
            if e.code == "conflict":
                text, failed = f"'{word}' is already in your {name} vocabulary.", False
            elif e.code == "validation_error":
                text, failed = f"Couldn't add word: {e.message}", True
            else:
                raise
        return ChatResult(reply=text, tool_calls=[ToolCall("Add Word", args, text, failed)])

    def _story(self, code: str) -> ChatResult:
        args = {"language": code}
        if not stories_enabled(code):
            text = f"Stories in {LANGUAGES[code].name} are not available yet."
            return ChatResult(reply=text, tool_calls=[ToolCall("Story Generator Tool", args, text, True)])
        text = STORIES.get(code, STORIES["en"])
        return ChatResult(reply=text, tool_calls=[ToolCall("Story Generator Tool", args, text, False)])
