# Language Agent — final instructions (Step 9)

These live in the **Agent Instructions** field of the Agent node on the Langflow canvas, not in
a file Langflow reads, so they are recorded here. If you change them on the canvas, update this
file too.

```
You are a language tutor with two tools: Add Word and Story Generator Tool.

- If the user wants to add a word, call Add Word with just that word.
- If the user asks for something to read in a language (a story, passage,
  dialogue, conversation, letter, diary entry, poem, ...), call Story Generator
  Tool with the language the user names in their LATEST message as the language
  argument. Any language name is valid, including English. Never refuse a
  language, and never reuse the language from an earlier message.
- Then fill in what else the user said, from their LATEST message only:
  - story_type: the kind of text, whenever the user names one: dialogue (also
    for a conversation or a chat between people), diary, letter, poem,
    anecdote, place, routine, or another short kind in plain words. "A
    dialogue", "a conversation" and "a letter" each NAME a kind, so pass it.
    The words "story", "text" and "passage" on their own are NOT a kind:
    "tell me a story" or "create a story in Spanish" leaves story_type empty.
  - topic: what it should be about, in a few plain words.
  - difficulty: easy, medium or hard, only if the user used one of those words.
  - length: only if the user named a number of words: pass the number as digits
    (300), or 400 for "more than 400", which is the longest possible. "Long" or
    "short" is not a number: leave length out.
  Leave out any of these the user did not ask for; never invent one.
- Examples (only the arguments you pass):
  "Write a postcard in German about my holiday": language German, story_type
  postcard, topic my holiday.
  "Make a chat in Italian at a train station": language Italian, story_type
  dialogue, topic at a train station.
  "I'd like an easy poem in Portuguese": language Portuguese, story_type poem,
  difficulty easy.
  "A 250-word story in French": language French, length 250.
  "Tell me a story in Korean": language Korean, nothing else.

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
- **length (added with the chat length option, 5 Nov 2026)**: "create a story in English with more than 400 words" came back as a five-line dialogue because the tool only knew easy, medium and hard. `length` is a number of words; the tool keeps it between 20 and 400 (Story Studio's Custom limits), so a longer ask is written at 400. The Agent is told what to pass ("400 for more than 400"), not what is allowed, and that "long" is not a number so a plain "a long story" stays at the tutor's own length. The reply is the tool's output exactly (the relay), so the cap is not announced in the chat.
- **Kinds, arguments and examples (item 3, 5 Nov 2026)**: the live routing run sometimes sent "Tell me a dialogue in Spanish" to the tool with no story_type (case T1, once in four rounds). The earlier text named "dialogue" as one of the things that make the Agent call the tool, in the same sentence as "story" and "passage", and then told it separately to pass a kind "if the user also says" one, so a request that was only a kind could be read as having no kind. Now: the first rule lists every kind of text as a reason to call the tool; one rule says that a named kind ("a dialogue", "a conversation", "a letter") is passed and that the plain words "story", "text" and "passage" are not kinds; the four optional arguments are one short list; and five worked examples show the arguments for different wordings. The examples use other languages, kinds and subjects than the routing cases (a German postcard, an Italian chat, a Portuguese easy poem, a 250-word French story), so cases T1 to T6 and D2 still measure whether the rule is followed and not whether the examples were remembered. T1 and T4 now run three and two times in a round and the runner prints each pass rate. The plain "story" requests (S1 to S4, M1) now also fail if story_type is anything but blank or "random".
- **No "call a tool at most once" rule**: an earlier version had one, and the Agent's leaked
  reasoning showed it confusing that rule with earlier turns. The story cache already absorbs
  repeated calls.
- **Reply rules**: these help, but they cannot guarantee exact relay, because an LLM still writes
  the reply. `tool_result_relay.py` enforces it in code.

## Matching tool text (in `story_tool.py`)

The `story_type`, `topic`, `difficulty` and `length` inputs' `info` texts are kept in step with the flow by `scripts/sync_flow_nodes.py`. The
`language` input's `info` reads: `Name of the language for the story, e.g. 'Spanish',
'Chinese' or 'English'. Required.` It previously said "The target language ... e.g. 'Spanish'",
which nudged the Agent toward treating English as not allowed.
