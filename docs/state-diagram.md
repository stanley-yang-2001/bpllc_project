# State Diagram — Story Request Lifecycle

```mermaid
stateDiagram-v2
    [*] --> Received: Learner asks for a story
    Received --> Routing: Language Agent evaluates intent
    Routing --> LoadingVocabulary: story intent confirmed
    LoadingVocabulary --> VocabularyEmpty: word list is empty
    LoadingVocabulary --> PromptBuilding: word list has entries
    VocabularyEmpty --> AwaitingWords: ask learner to add words
    AwaitingWords --> [*]
    PromptBuilding --> Generating: prompt sent to open-source LLM
    Generating --> Generated: story returned
    Generating --> Failed: LLM error / timeout
    Failed --> Retrying: automatic retry
    Retrying --> Generating
    Failed --> [*]: max retries exceeded
    Generated --> Delivered: story shown in chat
    Delivered --> [*]
```

**Notes**
- Chosen over the "Word" entity because a story request has the most non-trivial lifecycle in this project (branching on empty vocabulary, and a generation-failure/retry path that's more likely with a smaller open-source model than with a hosted frontier model).
- `Failed → Retrying → Generating` is worth implementing explicitly, since open-source models served locally are more prone to malformed or empty completions than GPT-4.1.
