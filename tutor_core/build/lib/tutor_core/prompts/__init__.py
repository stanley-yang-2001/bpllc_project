"""Story prompts: templates, language handling, story kinds and topics, prompt building, and reading the model's answer.
Pure Python (no Langflow, no database, no network). Moved from custom_components/story_tool.py (M3), split here by what each part decides:

    templates.py        the classic narration and dialogue templates, the delimiter
    language_blocks.py  writing the target language out; adapting templates for non-English stories
    kinds.py            built-in and free-text kinds and topics (cleaned hard), and the weighted choosers
    builder.py          building the prompt, and recognising what kind and topic a built prompt asked for
    extract.py          reading the passage out of the model's answer

The package keeps the one import path callers have always used (`tutor_core.prompts.build_story_prompt`, `.TOPICS`, ...), including the
underscore names tests reach for, by re-exporting every module-level name of its parts. Shared mutable state (`_RECENT_TOPICS`) is the same
object everywhere, so clearing it from here clears it for the code that uses it.
"""
from . import builder, extract, kinds, language_blocks, templates

for _part in (templates, language_blocks, kinds, builder, extract):
    globals().update({k: v for k, v in vars(_part).items() if not k.startswith("__") and k != "annotations"})
del _part
