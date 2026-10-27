"""What we send to Langflow (design section 3D): the learner's own message, a session id built here (never taken whole from the
browser) and, when the tweak keys are configured, the numeric learner id and language as hidden tool inputs. Nothing else: no email, no
display name, no password ever reaches Langflow or Groq."""
from __future__ import annotations

import re

from ...errors import validation_error

_SESSION_PART = re.compile(r"^[0-9a-f]{32}$")
STORY_TOOL_KEYS = ("Story Generator Tool", "StoryGeneratorTool")       # the tools that have a hidden `set_ids` field (a tweak for a field a tool lacks is dropped silently)


def build_session_id(user_id: int, client_part) -> str:
    """The browser supplies only 32 random hex characters; the user prefix is added here, so a learner can
    never address another learner's Langflow session."""
    if not isinstance(client_part, str) or not _SESSION_PART.match(client_part):
        raise validation_error("session_id must be 32 lowercase hex characters.")
    return f"u{int(user_id)}-{client_part}"


def build_tweaks(keys, user_id: int, language: str, set_ids=None) -> dict | None:
    """The hidden tool inputs are named `learner_id` and `active_language` (not `language`: the story tool already has a visible
    `language` argument that the Agent fills in, and the two must not be confused). NOT `user_id`: Langflow reserves that name on every
    component (it returns the Langflow account's UUID) and a tool input called user_id is silently shadowed by it.
    The id is sent as a STRING: Langflow's text-field handling accepts only strings, lists and Data objects and silently
    drops anything else, so an integer never reaches the tool (the tool then sees no learner and, by design, refuses).
    Both found by the M0 spike. The tool turns the string back into an integer and rejects anything else."""
    if not keys:
        return None
    tweaks = {key: {"learner_id": str(int(user_id)), "active_language": language} for key in keys}
    if set_ids:       # only the story tool has this field; a tweak for a field that does not exist is dropped silently by Langflow
        for key in tweaks:
            if key.startswith(STORY_TOOL_KEYS):
                tweaks[key]["set_ids"] = ",".join(str(int(i)) for i in set_ids)
    return tweaks


def with_reply_language(message: str, reply_language: str | None) -> str:
    """The Agent is asked to write ITS OWN sentences in the learner's study language when the learner chose that
    (Settings, "Chat replies in my study language"). The note names only the language, goes in front of the learner's message, and
    says tool names and arguments stay as they are. Fixed tool messages are relayed as the tool wrote them, so they are not affected.
    English gets the note too: a learner studying English who writes in another language still gets English back.
    It also says which language a story is in when the learner names none (24 Oct: with English active, "生成一个故事" came back as a
    Chinese story, because the Agent took the language from the message); a language the learner does name still wins."""
    if not reply_language or not reply_language.strip():
        return message
    return (f"[Note for the tutor: write your own sentences to the learner in {reply_language}. "
            f"If the learner asks for a story without naming a language in words, call the story tool with language \"{reply_language}\", "
            f"whatever language the message is written in. A language the learner does name wins. "
            f"Tool names and every other tool argument stay exactly as they are.]\n\n{message}")


def build_run_payload(message: str, session_id: str, tweaks: dict | None) -> dict:
    payload = {"input_value": message, "input_type": "chat", "output_type": "chat", "session_id": session_id}
    if tweaks:
        payload["tweaks"] = tweaks
    return payload
