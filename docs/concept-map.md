# High-Level Concept Map — Language Tutor

*Rewritten 27 October 2026 to include accounts, word sets, difficulty, the quality report and the text tools.*

```mermaid
flowchart TD
    Learner((Learner))
    Account[Account<br/>email, preferences, own model]
    Vocabulary[Known Vocabulary]
    Word[Word and its meaning]
    Set[Word Set<br/>General is always there]
    Language[Target Language<br/>nine, stories switched on after measuring]
    Story[Story or Dialogue<br/>kind, topic]
    Difficulty[Difficulty<br/>length, own words, unusual words]
    Report[Quality Report<br/>language, structure, vocabulary, difficulty]
    Library[Library of saved stories]
    Practice[Practice<br/>flashcards, choices, blanks]
    Reading[Reading aids<br/>read aloud, pronunciation, translation]
    Agent[Language Agent in chat]
    Tools[Add Word and Story tools]
    LLM[Language Model<br/>Groq, or the learner's own]
    DB[(Postgres)]

    Learner -- owns --> Account
    Learner -- builds --> Vocabulary
    Vocabulary -- made of --> Word
    Word -- grouped in --> Set
    Word -- belongs to --> Language
    Vocabulary -- persisted in --> DB
    Learner -- asks for --> Story
    Story -- written from --> Set
    Story -- shaped by --> Difficulty
    Story -- in --> Language
    Story -- written by --> LLM
    Story -- judged by --> Report
    Report -- measures --> Difficulty
    Story -- saved to --> Library
    Library -- feeds --> Practice
    Vocabulary -- feeds --> Practice
    Story -- explained by --> Reading
    Word -- explained by --> Reading
    Reading -- uses --> LLM
    Learner -- chats with --> Agent
    Agent -- routes to --> Tools
    Tools -- write --> Word
    Tools -- read --> Vocabulary
    Agent -- orchestrated by --> LLM
    Account -- may choose --> LLM
```

**Notes**
- A concept view, not a component view: it shows how the *ideas* relate, independent of code.
- The recurring theme is still the learner's own vocabulary: stories, practice, readings and the chat all start from it, and the **set** lets the learner narrow it.
- The language model appears in three roles: orchestrating the chat, writing stories and text aids, and (optionally) the learner's own model replacing the shared one.
- The **quality report** is what separates this site from "ask a chatbot for a story": every story is measured against the learner's own words and the difficulty asked for, and shown honestly.
