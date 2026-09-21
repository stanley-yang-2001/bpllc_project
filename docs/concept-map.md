# High-Level Concept Map — Language Tutor with Langflow

```mermaid
flowchart TD
    Learner((Learner))
    Vocabulary[Known Vocabulary]
    Word[Word]
    Language[Target Language]
    Story[Generated Story]
    Agent[Language Agent]
    Tool1[Add Word Tool]
    Tool2[Story-Generation Agent / Tool]
    LLM[Open-Source LLM - Ollama]
    DB[(Postgres Database)]

    Learner -- chats with --> Agent
    Agent -- routes to --> Tool1
    Agent -- routes to --> Tool2
    Tool1 -- writes --> Word
    Word -- stored in --> Vocabulary
    Vocabulary -- persisted in --> DB
    Tool2 -- reads --> Vocabulary
    Tool2 -- constrained by --> Language
    Tool2 -- generates --> Story
    Tool2 -- powered by --> LLM
    Story -- delivered to --> Learner
```

**Notes**
- This is a concept-level view (not a component/class view) — it shows how the *ideas* of learner, vocabulary, language, story, and model relate to each other, independent of implementation details.
- The recurring theme: the *Vocabulary* concept is the shared constraint that both the "add word" and "generate story" paths revolve around.
