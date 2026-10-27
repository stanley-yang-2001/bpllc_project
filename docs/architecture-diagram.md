# System Architecture / Deployment Diagram — Language Tutor

*Rewritten 27 October 2026. The first version showed only Langflow, Postgres and Groq; the site now has its own
web server and API, and Langflow is one path among two.*

## 1. Containers and who talks to whom

```mermaid
flowchart LR
    subgraph Device["Learner's device"]
        BR["Browser: React single-page app"]
        SP["Browser speech engine<br/>(read aloud; some browsers use an online voice)"]
    end
    subgraph Compose["Docker Compose on the learner's or host's machine"]
        WEB["web: nginx<br/>serves the React build, proxies /api<br/>127.0.0.1:8080"]
        API["api: FastAPI<br/>routes, services, tutor_core"]
        LF["langflow 1.12.2<br/>Agent, Add Word, Story Generator Tool,<br/>Tool Result Relay<br/>127.0.0.1:7860 (flow editing only)"]
        PG[("postgres 16<br/>schema tutor<br/>not published")]
    end
    GQ["Groq API<br/>gpt-oss-120b (shared key)"]
    OM["Learner's own model<br/>(OpenAI-compatible address, optional)"]

    BR -- "HTTPS-style REST, same origin /api<br/>cookie session + CSRF header" --> WEB
    WEB --> API
    BR -.-> SP
    API -- "SQL (api role)" --> PG
    API -- "chat turns: HTTP run + hidden inputs" --> LF
    LF -- "SQL via tutor_core (tutor_tools role)" --> PG
    LF -- "Agent and story calls" --> GQ
    API -- "stories, meanings, readings, translations" --> GQ
    API -- "same calls when the learner set one up<br/>(address checked, no redirects)" --> OM
```

**Two backend paths on purpose**
- **Agent path** (`POST /api/chat`): the API calls the Langflow flow; the Agent picks a tool; the Tool Result Relay returns the tool's exact output. Used only by the Chat page.
- **Direct path** (vocabulary, sets, stories, practice, readings, translations): the API calls `tutor_core` itself. Faster, deterministic, and it offers controls the Agent tool lacks (kind, topic, difficulty, sets, regenerate).

**Network rules.** Only `web` is reachable from the browser. `api` and `postgres` are not published. Langflow is published on `127.0.0.1:7860` only, because its tools trust the learner id they are given; reaching Langflow's API means reading anyone's words. Langflow's tools connect as the limited role `tutor_tools`.

## 2. Inside the API container

```mermaid
flowchart TB
    REQ["Request"] --> MW["Guard middleware<br/>CSRF header, origin check, no-store headers"]
    MW --> RT["routes/ (13 modules): parse, call one service, answer"]
    RT --> DEP["deps: current_user from the session cookie, require_language"]
    RT --> SV["services/ (use cases, SQL)"]
    SV --> AIR["AiRunner<br/>StubSource, OwnModelSource, SharedSource"]
    AIR --> GATE["AiGate: slots, one AI call per user,<br/>shared tokens-per-minute budget"]
    GATE --> TC["tutor_core: prompts, quality, difficulty,<br/>pronunciation, translation, definitions"]
    SV --> LFC["langflow/ client (chat path)"]
    SV --> DBL["db: connection pool"]
    TC --> GQ["Groq or the learner's own model"]
    LFC --> LF["Langflow"]
    DBL --> PG[("Postgres")]
    ERR["errors: AppError to {error: {code, message}}"] -.-> RT
```

## 3. Notes

- `tutor_core` is a pip package installed in both the `api` and the `langflow` images, so the chat tools and the site run the same rules (word cleaning, story prompts, the quality report).
- `AI_MODE=stub` replaces Groq and Langflow with fixed stand-ins so the whole stack runs offline for tests and demos; `AI_MODE=live` calls them.
- Groq's free-tier rate limit is shared by every learner and by both paths; `AiGate` queues calls (2 slots, 5 s wait) and reserves tokens per minute before a call. A learner's own model skips the shared token budget and has its own limit (10 a minute).
- Passwords are salted and bcrypt-hashed; sessions are JWTs in an httpOnly cookie backed by a `sessions` row that can be revoked; the own-model key is encrypted at rest with `MODEL_KEY_SECRET` and never returned.
- The original design used a local Ollama container with a Hugging Face fallback; it was dropped because local hardware could not run the model. There is no automatic provider fallback.
