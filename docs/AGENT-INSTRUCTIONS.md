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
- **No "call a tool at most once" rule**: an earlier version had one, and the Agent's leaked
  reasoning showed it confusing that rule with earlier turns. The story cache already absorbs
  repeated calls.
- **Reply rules**: these help, but they cannot guarantee exact relay, because an LLM still writes
  the reply. `tool_result_relay.py` enforces it in code.

## Matching tool text (in `story_tool.py`)

The `language` input's `info` reads: `Name of the language for the story, e.g. 'Spanish',
'Chinese' or 'English'. Required.` It previously said "The target language ... e.g. 'Spanish'",
which nudged the Agent toward treating English as not allowed.
