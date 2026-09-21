# System Architecture / Deployment Diagram — Language Tutor with Langflow

```mermaid
flowchart LR
    UD[User Device<br/>Browser - Langflow Chat UI]
    WS[Web Server<br/>Langflow - Docker Container]
    DB[(Database<br/>Postgres - Docker Container)]
    MS[Model Server<br/>Ollama - Docker Container]
    CS[Cloud Services<br/>Hugging Face Inference - fallback only]

    UD -- HTTP chat request --> WS
    WS -- SQL read/write --> DB
    DB -- vocabulary rows --> WS
    WS -- prompt --> MS
    MS -- generated text --> WS
    WS -. fallback prompt if local model unavailable .-> CS
    CS -. generated text .-> WS
    WS -- chat response --> UD
```

**Notes**
- All four boxes besides Cloud Services run locally via the same Docker Compose stack (Story 1 + Story 1b in `OVERVIEW.md`) — nothing here requires external hosting.
- The Cloud Services box is dashed/optional: it's only exercised if local hardware can't run the Ollama model, per Story 1b's fallback plan.
