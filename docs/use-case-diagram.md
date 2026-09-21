# Use Case Diagram — Language Tutor with Langflow

```mermaid
flowchart LR
    Learner([👤 Learner])
    Admin([👤 Developer / Admin])

    UC1([Seed vocabulary from CSV])
    UC2([Add new word via chat])
    UC3([Request story in target language])
    UC4([Read generated story])
    UC5([Load known vocabulary])

    Admin --> UC1
    Learner --> UC2
    Learner --> UC3
    UC3 --> UC4
    UC2 -.include.-> UC5
    UC3 -.include.-> UC5
```

**Notes**
- *Learner* is the day-to-day actor, interacting entirely through chat.
- *Developer / Admin* is a separate actor for the one-off CSV seeding step (Story 2), which isn't exposed through the chat agent.
- "Load known vocabulary" is modeled as an `<<include>>` use case since both "Add new word" (to check for duplicates) and "Request story" depend on it.
