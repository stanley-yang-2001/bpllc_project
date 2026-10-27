# Workflow Diagram — Language Tutor

*Rewritten 27 October 2026. Two workflows now exist: a chat message through the Langflow Agent, and the direct
requests the pages make.*

## 1. A chat message (Agent path)

```mermaid
flowchart TD
    A[Learner sends a chat message<br/>Chat page, optional set choice] --> B[POST /api/chat<br/>cookie gives the learner id, never the body]
    B --> B1[AiGate slot: reserve tokens]
    B1 --> B2[Record the Langflow session id in chat_sessions]
    B2 --> B3[Read the chat-language preference]
    B3 --> C[LangflowClient runs the flow<br/>hidden inputs: user id, language, set ids]
    C --> D{Agent decides intent}
    D -->|add a word| E[Add Word tool: insert into words, tutor_tools role]
    D -->|story| F[Story Generator Tool: tutor_core generate_story]
    D -->|other| G[Agent answers itself]
    E --> Z
    F --> Z
    G --> Z[Tool Result Relay returns the tool output exactly,<br/>or the Agent's own text]
    Z --> H[API parses reply and tool calls, settles the token count]
    H --> I[Chat page shows the reply, a tool chip, and for a story:<br/>Save, Listen, Pronunciation, Translate]
```

## 2. A story from Story Studio (direct path)

```mermaid
flowchart TD
    A[Learner picks kind, topic, difficulty, sets] --> B[POST /api/stories/generate]
    B --> C{Language on? Kind and topic valid? 5 words or more?}
    C -->|no| X[Error shown on the page]
    C -->|yes| D[AiRunner chooses: stub, own model, shared model]
    D --> E[AiGate slot and token reservation]
    E --> F[tutor_core generate_story:<br/>prompt, model call, language retry, length retry]
    F --> G[quality.report on the learner's whole list]
    G --> H[Page shows the story and the report]
    H --> I{Save?}
    I -->|yes| J[POST /api/stories: report rebuilt on the server, saved to the Library]
    I -->|no| K[Nothing stored]
    H --> T[Listen, Pronunciation, Translate: optional, nothing stored]
```

## 3. Words, practice and text tools (direct path)

```mermaid
flowchart LR
    V[Vocabulary page] -->|add, edit, delete, move, upload CSV| W["/api/words, /api/sets"]
    V -->|Write missing meanings, 25 per call| D["/api/words/define"]
    D --> AR[AiRunner and AiGate] --> M[Model]
    P[Practice page] -->|flashcards, choices, blanks| PR["/api/practice/*"]
    PR --> DB[(Postgres)]
    W --> DB
    T[Pronunciation and Translate buttons] --> TX["/api/pronounce, /api/translate"]
    TX -->|zh, ja, ko readings| LIB[pypinyin, pykakasi, korean-romanizer]
    TX -->|IPA, translation| AR
    S[Read aloud] --> BE[Browser speech engine, no server call]
```

**Notes**
- The Agent path exists so the chat can add words and write stories in conversation; every other feature uses the direct path because it is faster and gives exact controls.
- The "vocabulary empty" guard (Story 5) and the Tool Result Relay (Step 9 fix) still apply on the chat path; the Studio has its own 5-word minimum.
- Nothing from reading, pronunciation or translation is stored; meanings are stored only when the learner asks for them to be written.
