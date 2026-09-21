# Workflow Diagram — Language Tutor with Langflow

```mermaid
flowchart TD
    A[Learner sends chat message] --> B[Language Agent receives message]
    B --> C{Agent decides intent}

    C -->|"add word" request| D[Call Add Word tool]
    C -->|"story" request| E[Call Story-generation tool]

    D --> D1[Add Word tool inserts word into Postgres words table]
    D1 --> D2[Return confirmation to Language Agent]
    D2 --> Z[Language Agent replies in chat]

    E --> E1[Word Loader queries Postgres for all known words]
    E1 --> E2{Vocabulary empty?}
    E2 -->|Yes| E3[Ask learner to add words first]
    E2 -->|No| E4[Fill Prompt Template with language + word list]
    E4 --> E5[Story-generation Agent calls open-source LLM via Ollama]
    E5 --> E6[Story returned to Language Agent]
    E6 --> Z
    E3 --> Z
```

**Notes**
- This traces one full round-trip of a chat message, matching Stories 3, 4, 5, and 6 from `OVERVIEW.md`.
- The `E2` branch is the "vocabulary empty" guard called out explicitly in Story 5's acceptance criteria.
