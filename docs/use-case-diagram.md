# Use Case Diagram — Language Tutor

*Rewritten 27 October 2026. The first version had one learner chatting and one admin seeding a CSV; the site now
has accounts, a vocabulary manager, story tools and practice.*

```mermaid
flowchart LR
    Learner([Learner])
    Admin([Developer / Operator])
    Model([AI model: Groq or the learner's own])

    subgraph Account["Account and look"]
        A1([Sign up with consent to the privacy policy])
        A2([Sign in and out, sign out everywhere])
        A3([Change name, email, password])
        A4([Download my data])
        A5([Delete my account])
        A6([Choose theme, colours, site language])
        A7([Set up my own model])
    end
    subgraph Vocab["Vocabulary"]
        V1([Add a word])
        V2([Edit or delete words])
        V3([Upload words from CSV])
        V4([Group words into sets])
        V5([Write missing meanings])
        V6([Study another language])
    end
    subgraph Stories["Stories"]
        S1([Make a story in Story Studio])
        S2([Choose kind, topic, difficulty, sets])
        S3([Save a story to the Library])
        S4([Read, reopen, delete saved stories])
        S5([Read the quality report])
    end
    subgraph Practice["Practice"]
        P1([Flashcards])
        P2([Multiple choice])
        P3([Fill in the blank])
    end
    subgraph Chat["Chat with the tutor"]
        C1([Ask the tutor to add a word])
        C2([Ask the tutor for a story])
    end
    subgraph Text["On any word or story"]
        T1([Read aloud])
        T2([Show pronunciation])
        T3([Translate])
    end
    L0([Load known vocabulary])

    Learner --> A1 & A2 & A3 & A4 & A5 & A6 & A7
    Learner --> V1 & V2 & V3 & V4 & V5 & V6
    Learner --> S1 & S3 & S4
    Learner --> P1 & P2 & P3
    Learner --> C1 & C2
    Learner --> T1 & T2 & T3
    S1 -.include.-> S2
    S1 -.include.-> L0
    S1 -.include.-> S5
    S4 -.include.-> S5
    C1 -.include.-> L0
    C2 -.include.-> L0
    P1 -.include.-> L0
    V5 --> Model
    S1 --> Model
    C2 --> Model
    T2 --> Model
    T3 --> Model
    Admin --> O1([Start the stack, run migrations])
    Admin --> O2([Switch on the own-model option for an account])
    Admin --> O3([Seed the demo account])
    Admin --> O4([Run the checks: routing, difficulty, story batch])
    Admin --> O5([Sync the flow's component code])
```

**Notes**
- *Learner* is the day-to-day actor; *Operator* does the things the site does not expose (start-up, the own-model switch, seeding, live checks).
- The AI model is shown as a secondary actor: five use cases send text to it (meanings, stories, chat stories, IPA readings, translations). Chinese, Japanese and Korean readings come from libraries and do not.
- "Load known vocabulary" is an `<<include>>` because stories, flashcards and the chat all depend on the learner's own word list.
