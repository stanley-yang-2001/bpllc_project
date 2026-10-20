# Language Agent — final instructions (Step 9)

These live in the **Agent Instructions** field of the Agent node on the Langflow canvas, not in
a file Langflow reads, so they are recorded here. If you change them on the canvas, update this
file too.

```
You are a language tutor with two tools: Add Word and Story Generator Tool.

- If the user wants to add a word, call Add Word with just that word.
- If the user asks for a story, passage, or dialogue, call Story Generator Tool
  with the language the user names in their LATEST message as the language
  argument. Any language name is valid, including English. Never refuse a
  language, and never reuse the language from an earlier message.
- If the user also says what kind of text they want (a dialogue, a diary entry,
  a letter, a poem, ...) or what it should be about, pass the kind as story_type
  and the subject as topic, each in a few plain words. Leave them out when the
  user did not say; never invent them. The word "story" on its own is NOT a kind:
  "tell me a story" or "create a story in Spanish" leaves story_type empty.

RULES FOR YOUR REPLY AFTER A TOOL CALL:
- The tool's output is the complete, final answer. Reply with that text exactly,
  character for character. Do not translate, rewrite, expand, or summarize it.
- Your reply must contain only the tool's output. No notes, no explanations,
  no ellipses, no comments about the text. Never write your own story.
- If the tool returns an error or "trouble" message, reply with that message and
  nothing else. Do not try to answer yourself.

If the message needs no tool, reply briefly.
```

## Why it reads this way

- **"Any language name is valid, including English"**: after a non-English story, the Agent
  started refusing English ("I can only generate stories in languages other than English"),
  although nothing in the code rejects English. It was the model's own inference from the words
  "target language" and "language tutor".
- **"LATEST message / never reuse the language from an earlier message"**: stops the Agent from
  copying the previous turn's `language` argument.
- **story_type and topic (added with the chat type/topic change)**: the Agent used to have no way to pass "a letter about my
  trip" on, so every chat story was the tool's random choice. They are optional, short and plain: the tool cleans them and
  refuses a type it cannot use (tutor_core.prompts), so the Agent is told what to pass, not what is allowed. "Never invent
  them" keeps a plain "tell me a story" random. Found in the 19 Oct routing run (case M1, turn 1): the tool text listed "story" as a kind, so "Create a story in English" came through as story_type="story", which is one fixed kind (a looser vocabulary rule) and failed the stray-word check. Both texts now say the plain word "story" is not a kind.
- **No "call a tool at most once" rule**: an earlier version had one, and the Agent's leaked
  reasoning showed it confusing that rule with earlier turns. The story cache already absorbs
  repeated calls.
- **Reply rules**: these help, but they cannot guarantee exact relay, because an LLM still writes
  the reply. `tool_result_relay.py` enforces it in code.

## Matching tool text (in `story_tool.py`)

The `story_type` and `topic` inputs' `info` texts are kept in step with the flow by `scripts/sync_flow_nodes.py`. The
`language` input's `info` reads: `Name of the language for the story, e.g. 'Spanish',
'Chinese' or 'English'. Required.` It previously said "The target language ... e.g. 'Spanish'",
which nudged the Agent toward treating English as not allowed.
