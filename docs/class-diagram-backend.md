# Class Diagrams — Back End (API, `tutor_core`, Langflow components)

*Updated 27 October 2026, after the SOLID refactor (patch 0030). The diagrams follow the code in `api/app/`,
`tutor_core/tutor_core/` and `custom_components/`. Python has many module-level functions, so a module that is
only functions is drawn as a class with the stereotype `<<module>>`.*

Reading order: 1 layers, 2 model choice (the main design pattern), 3 the chat client, 4 the AI limits and
security, 5 `tutor_core`, 6 who calls what, 7 database. Section 8 records what the diagrams show about where to
split further; each item there is a card in `docs/kanban/cards.json`.

## 1. Layers and the rule between them

```mermaid
flowchart TB
    subgraph R["routes/ (HTTP only: parse, call one service, shape the answer)"]
        direction LR
        r1[auth] --- r2[me] --- r3[account] --- r4[public] --- r5[words] --- r6[sets] --- r7[definitions]
        r8[text_tools] --- r9[stories] --- r10[practice] --- r11[chat] --- r12[model] --- r13[health]
    end
    subgraph S["services/ (use cases and data access; no FastAPI imports)"]
        direction LR
        s1[users, sessions, reauth] --- s2[vocab, word_sets, meanings] --- s3[stories, practice]
        s4[text_tools, ai_runner, ai_gate] --- s5[langflow/, chat, chat_stub] --- s6[user_model, user_models, model_secrets]
        s7[preferences, export, chat_sessions]
    end
    subgraph C["tutor_core (pure Python, shared with Langflow)"]
        direction LR
        c1[words, vocab, languages] --- c2[story, prompts/, quality/, difficulty] --- c3[pronunciation, translation, definitions, numbered] --- c4[groq, tools, splitter]
    end
    subgraph F["cross-cutting (app/)"]
        direction LR
        f1[deps: current_user, require_language] --- f2[security, errors, config] --- f3[db: pool, connection, cursor]
    end
    R --> S
    S --> C
    R -.-> F
    S -.-> F
    DB[("Postgres, schema tutor")]
    S --> DB
    C --> DB
```

**The rule:** a route never touches SQL or a model; a service never imports FastAPI; `tutor_core` never imports
from `api`. `main.py` is the composition root: it builds the `AiGate`, the chat client, the story model and the
limiters once and stores them on `app.state`; routes receive a per-request object built from that state
(`ai_runner_for`, `own_models_for`), which is why tests can swap a part by assigning to `app.state`.

## 2. Choosing which model answers (open/closed, dependency inversion)

```mermaid
classDiagram
    class AiRunner {
        -sources: list~ModelSource~
        -gate: AiGate
        +choose(user_id, stub) Chosen
        +slot(user_id, chosen, tokens) ContextManager
        +failure(chosen, message, own_hint) AppError$
        +run(user_id, prompt, tokens, failed_message, stub) str
    }
    class ModelSource {
        <<Protocol>>
        +pick(user_id, stub) Chosen
    }
    class StubSource {
        -ai_mode: str
        +pick(user_id, stub) Chosen
    }
    class OwnModelSource {
        -own_models: OwnModels
        -limiter: RequestLimiter
        -allow_private: bool
        +pick(user_id, stub) Chosen
    }
    class SharedSource {
        -llm: Callable
        +pick(user_id, stub) Chosen
    }
    class Chosen {
        <<frozen dataclass>>
        +call: Callable
        +own_model: str
        +metered() bool
        +last_error() str
    }
    class OwnModels {
        -pool
        -secret: str
        +find(user_id, conn) dict
    }
    class AiGate {
        +slot(user_id, tokens) Ticket
        +exclusive(user_id)
        +in_flight() int
        +tokens_used() int
    }
    class TokenBudget {
        +reserve(tokens) Ticket
        +used() int
    }
    class Ticket {
        +settle(actual)
    }
    class RequestLimiter {
        +allow(user_id) bool
    }
    class UserModelClient {
        <<module user_model>>
        +check_base_url(url, allow_private) tuple
        +call_model(model, base_url, key, prompt) str
        +make_call_fn(model, base_url, key) Callable
    }
    class ModelSecrets {
        <<module>>
        +encrypt(secret, key) str
        +decrypt(secret, token) str
        +last4(key) str
    }

    ModelSource <|.. StubSource
    ModelSource <|.. OwnModelSource
    ModelSource <|.. SharedSource
    AiRunner o-- ModelSource : tries in order
    AiRunner --> AiGate : holds a slot
    AiRunner ..> Chosen : returns
    AiGate *-- TokenBudget
    AiGate ..> Ticket : issues
    TokenBudget ..> Ticket : issues
    OwnModelSource --> OwnModels : finds the learner's model
    OwnModelSource --> RequestLimiter : 10 a minute
    OwnModelSource ..> UserModelClient : builds the call
    OwnModels ..> ModelSecrets : decrypts the key
```

The order built by `ai_runner_for` is `StubSource`, `OwnModelSource`, `SharedSource(state.story_llm)`. A new
source (for example a second shared provider) is a new class in that list. The stories route, `meanings.write_missing`
and `text_tools` all go through `AiRunner`; **`routes/chat.py` and `routes/model.py` do not** (see section 8, items B3 and B4).

## 3. The chat path (Agent in Langflow, or a stand-in)

```mermaid
classDiagram
    class ChatClient {
        <<duck type, no interface yet>>
        +calls_ai: bool
        +stores_chat: bool
        +run(user_id, language, message, session_id, reply_language, set_ids) ChatResult
        +health() dict
        +delete_sessions(session_ids)
    }
    class NoStoredChat {
        +health() dict
        +delete_sessions(session_ids)
    }
    class LangflowClient {
        -base_url: str
        -flow: str
        -transport: Transport
        +run(...) ChatResult
        +health() dict
        +delete_sessions(session_ids)
        -headers() dict
        -stored_messages(session_id)
    }
    class StubChat {
        -get_pool
        +run(...) ChatResult
        -add_word(user_id, language, word) ChatResult
        -story(code) ChatResult
    }
    class NotReadyChat {
        +health() dict
        +run() raises
    }
    class ChatResult {
        <<dataclass>>
        +reply: str
        +tool_calls: list~ToolCall~
        +tokens: int
    }
    class ToolCall {
        <<dataclass>>
        +name: str
        +args: dict
        +output: str
        +failed: bool
    }
    class Payload {
        <<module langflow/payload>>
        +build_session_id(user_id, client_part) str
        +build_tweaks(keys, user_id, language, set_ids) dict
        +with_reply_language(message, reply_language) str
        +build_run_payload(message, session_id, tweaks) dict
    }
    class Reply {
        <<module langflow/reply>>
        +parse_run_response(body) ChatResult
        +find_tool_calls(obj) list~ToolCall~
        +walk_tool_blocks(obj)
        +output_to_text(output) str
    }
    class Transport {
        <<module langflow/transport>>
        +urllib_transport(...)
        +map_transport_error(exc) AppError
    }
    class MakeChatClient {
        <<module chat>>
        +make_chat_client(settings, get_pool) ChatClient
    }

    ChatClient <|.. NoStoredChat
    NoStoredChat <|-- LangflowClient
    NoStoredChat <|-- StubChat
    NoStoredChat <|-- NotReadyChat
    LangflowClient --> Payload : builds the request
    LangflowClient --> Transport : sends it
    LangflowClient --> Reply : reads the answer
    Reply ..> ChatResult
    ChatResult o-- ToolCall
    MakeChatClient ..> LangflowClient : AI_MODE live
    MakeChatClient ..> StubChat : AI_MODE stub
    MakeChatClient ..> NotReadyChat : no flow id yet
```

`services/langflow_client.py` is a facade that re-exports the names of the `langflow/` package, so old imports
keep working. The learner's id is never read from the request body: `routes/chat.py` builds the Langflow session
id from the session cookie's user.

## 4. Security, errors and settings

```mermaid
classDiagram
    class Settings {
        <<frozen dataclass>>
        +database_url: str
        +jwt_secret: str
        +ai_mode: str
        +langflow_url: str
        +ai_gate_slots: int
        +ai_tokens_per_minute: int
        +allowed_origins: set
        +validate()
    }
    class LoginGuard {
        +check(key)
        +failure(key)
        +success(key)
    }
    class Security {
        <<module>>
        +hash_password(password, salt, rounds) str
        +verify_password(password, hash, salt) bool
        +new_salt() str
        +check_password_rules(pw) str
        +create_token(user_id, session_id, secret, hours) str
        +decode_token(token, secret) tuple
        +new_session_id() str
    }
    class AppError {
        +code: str
        +message: str
        +status: int
    }
    class Deps {
        <<module>>
        +current_user(request) dict
        +require_language(code) str
        +session_from_cookie(request)
        +pool_of(request)
    }
    class Sessions {
        <<module services/sessions>>
        +create(conn, user_id, hours) str
        +user_for(conn, session_id, user_id) dict
        +revoke(conn, session_id)
        +revoke_others(conn, user_id, keep) int
        +revoke_all(conn, user_id) int
    }
    class Reauth {
        <<module services/reauth>>
        +reauthenticate(state, user, password)
    }
    class Users {
        <<module services/users>>
        +create_user(...)
        +get_by_email(...)
        +set_password(...)
        +delete_user(...)
        +profile(conn, user) dict
    }

    Deps ..> Sessions : cookie to user
    Deps ..> Security : decode_token
    Reauth ..> Security : verify_password
    Reauth ..> LoginGuard : state.login_guard counts wrong guesses
    Sessions ..> Security
    Users ..> AppError : raises
    Deps ..> AppError : raises
    Settings <.. Deps : app.state.settings
```

Only the guard middleware in `main.py` (CSRF header, origin check, no-store headers) and `install_error_handlers`
(`AppError` to the `{error: {code, message}}` shape) are applied to every route.

## 5. `tutor_core` (shared by the API and the Langflow tools)

```mermaid
classDiagram
    class Language {
        <<frozen dataclass>>
        +code: str
        +name: str
        +native: str
        +tier: int
        +stories_enabled: bool
    }
    class StoryResult {
        <<frozen dataclass>>
        +text: str
        +ok: bool
        +reason: str
        +story_type: str
        +topic: str
        +words_total: int
        +words_used: int
        +difficulty: dict
    }
    class AddResult {
        <<dataclass>>
        +word: str
        +language: str
        +added: bool
    }
    class Story {
        <<module story>>
        +generate_story(conn, learner_id, language, call_groq_fn, story_type, topic, difficulty, set_ids) StoryResult
        -better_try(...) str
    }
    class Vocab {
        <<module vocab>>
        +add_word(conn, ...) AddResult
        +load_words(conn, learner_id, language, set_ids) list
        +sample_words(words, cap) list
        +clean_set_ids(set_ids) list
    }
    class Words {
        <<module words>>
        +normalize_word(w, language) str
        +validate_word(w) str
        +validate_meaning(m) str
    }
    class Prompts {
        <<package prompts>>
        +build_story_prompt(...) str
        +resolve_story_type(text) str
        +clean_topic(text) str
        +choose_story_type(...) str
        +extract_final_passage(raw) str
    }
    class Quality {
        <<package quality>>
        +report(text, language, words, targets) dict
        +check_passage(...) dict
        +language_check(text, name, ...) dict
        +ends_complete(text) bool
        +has_dangling_sentence(text, language) bool
    }
    class Difficulty {
        <<module>>
        +resolve(name, length, own_words, pct) dict
        +prompt_note(targets, language) str
        +measure(text, language, words) dict
        +evaluate(targets, measured) dict
    }
    class TextTools {
        <<modules>>
        pronunciation: romanize, build_prompt, parse
        translation: build_prompt, parse
        definitions: build_prompt, parse
        numbered: flatten, block, parse
    }
    class Groq {
        <<module groq>>
        +call_groq(prompt) str
    }
    class Splitter {
        <<module splitter>>
        +available(language) bool
        +split(text, language) list~Token~
    }
    class AgentTools {
        <<module tools>>
        +add_word_for_agent(...) str
        +story_for_agent(...) str
        +vocabulary_for_agent(...) str
    }

    Story --> Vocab : load_words, sample_words
    Story --> Prompts : build prompt
    Story --> Quality : language check, ends
    Story --> Difficulty : length gap
    Story --> Groq : default model call
    Story ..> StoryResult
    Vocab --> Words
    Vocab --> Language
    Vocab ..> AddResult
    Quality --> Difficulty
    Quality --> Splitter
    Prompts --> Language
    Difficulty --> Language
    AgentTools --> Story
    AgentTools --> Vocab
    AgentTools --> Words
```

## 6. Which route uses which service

| Route module | Services and helpers it calls |
|---|---|
| `auth` | users, sessions, security, emails, policy |
| `me` | users, preferences |
| `account` | users, sessions, reauth, export, chat_sessions, security, emails |
| `public` | policy, languages |
| `words` | vocab, word_sets |
| `sets` | word_sets |
| `definitions` | meanings, `AiRunner` |
| `text_tools` | text_tools, `AiRunner` |
| `stories` | stories, `AiRunner`, `OwnModels`; `tutor_core` story and quality (**inside the route**) |
| `practice` | practice, stories |
| `chat` | chat client, chat_sessions, preferences, `AiGate` (**inside the route**) |
| `model` | user_models, model_secrets, user_model (**inside the route**) |
| `health` | db, `app.state` health objects |

## 7. Database (schema `tutor`)

```mermaid
erDiagram
    users ||--o{ user_languages : studies
    users ||--o{ words : owns
    users ||--o{ word_sets : owns
    users ||--o{ stories : saves
    users ||--o{ sessions : "signed in"
    users ||--o{ chat_sessions : "has Langflow chats"
    users ||--o| user_preferences : sets
    users ||--o| user_models : "own model"
    word_sets |o--o{ words : groups

    users {
        int id PK
        text email
        text password_hash
        text password_salt
        text display_name
        text native_language
        bool custom_model_enabled
        text privacy_version
    }
    words {
        int id PK
        int user_id FK
        text language
        text word
        text meaning
        int set_id FK "null = General"
    }
    word_sets {
        int id PK
        int user_id FK
        text language
        text name
    }
    stories {
        int id PK
        int user_id FK
        text language
        text story_type
        text topic
        text body
        bool passed
        jsonb report
    }
    user_preferences {
        int user_id PK
        text active_language
        bool ui_follows_study_language
        bool chat_in_study_language
        text theme
        jsonb custom_colors
    }
    user_models {
        int user_id PK
        text model
        text base_url
        text api_key_encrypted
        text key_last4
    }
    sessions {
        text id PK
        int user_id FK
        timestamptz expires_at
    }
    chat_sessions {
        int user_id FK
        text session_id
    }
    user_languages {
        int user_id FK
        text language
    }
```

Deleting a user cascades to every table above; deleting a set sets `words.set_id` to null (the words move to
General). The Langflow tools connect as the limited role `tutor_tools`: SELECT and INSERT on `words`, INSERT on
`user_languages`, nothing else.

## 8. What these diagrams show about further splits

Findings are ranked by value for easier maintenance. Each has a kanban card (cards "B1" to "B12" in
`docs/kanban/cards.json`). None is built yet; each keeps behaviour unchanged and starts with the existing tests.

| # | Where | What the diagram shows | Proposed split | Principle |
|---|---|---|---|---|
| B1 | `routes/stories.py` (174 lines) | The route holds the whole "make a story" use case (load words, check the minimum, choose the model, generate, report) and also the request models with validators | `services/story_generation.py` for the use case; request models to `schemas`; the route only calls it | S, D |
| B2 | Set filter SQL | The same "all, general or a set id" clause is written three times: `vocab.list_words`, `vocab.words_without_meaning`, `practice._set_clause` | One `word_sets.filter_clause(set_filter)` used by all three | DRY, S |
| B3 | `routes/chat.py` | Holds the chat turn: gate slot, session record, preferences, reply language. The chat client is a duck type read with `getattr(state.chat, "calls_ai")` | `services/chat_turn.py` plus a `ChatClient` Protocol with `calls_ai` and `stores_chat` as real attributes | S, D, L |
| B4 | `routes/model.py` | Holds test, save and remove for the learner's own model, with encryption and the address check inline | `services/model_settings.py`; the route validates the body only | S |
| B5 | `services/user_model.py` (160 lines) | Four jobs in one file: the address guard (SSRF), the pinned connections, the HTTP call, the request limiter | Split into `model_address.py`, `pinned_http.py`, `model_client.py`, `rate_limit.py` | S |
| B6 | `services/vocab.py` (172 lines) | Word CRUD, meaning filling and CSV parsing and bulk insert in one module | `vocab.py` (CRUD), `csv_import.py`; `fill_meanings` and `words_without_meaning` move into `meanings.py` | S, cohesion |
| B7 | `services/practice.py` (192 lines) | Three practice modes in one module | A `practice/` package: `flashcards.py`, `choices.py`, `cloze.py` | S, O |
| B8 | `schemas.py` (204 lines, 29 models) | One file for every response model | A `schemas/` package by area (`user`, `words`, `stories`, `practice`, `system`) with a re-exporting `__init__` | S, I |
| B9 | `tutor_core/story.py` `generate_story` (82 lines, 12 parameters) | Gate, cache, load, prompt, model call, two retry policies in one function; `_better_try` reads the private `difficulty._UNSPACED` | A `StoryCache` class, a `RetryPolicy` for the language and length retries, a `StoryRequest` dataclass for the parameters; make the unspaced-language fact public | S, O, encapsulation |
| B10 | `tutor_core/quality/passage.py` `check_passage` (118 lines, 12 parameters) | The longest function in the repo; one function runs every rule | A list of small rule functions (structure, format, length, vocabulary) combined by a runner | O, S |
| B11 | `custom_components/tool_result_relay.py` and `services/langflow/reply.py` | Both parse a Langflow tool output (`output_to_text`, walking the content blocks), with two slightly different copies | One `tutor_core/tool_output.py` used by both (the other three Langflow components already import `tutor_core`, so the image has it); re-sync the flow | DRY |
| B12 | `security.py` (110 lines) and `difficulty.py` (252 lines) | `security` mixes password hashing, tokens and the login guard; `difficulty` mixes presets, prompt note and measuring | `security/` package (`passwords`, `tokens`, `login_guard`); `difficulty/` package (`presets`, `measure`, `evaluate`) | S |

Not worth splitting (checked): `ai_gate.py` (three small classes that share one lock, one concern),
`main.py` (a composition root should know every part), `policy/` and `emails.py`.
