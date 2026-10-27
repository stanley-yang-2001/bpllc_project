# Class Diagrams — Index, and the Langflow Components

*Updated 27 October 2026. The first version ("rough, by design") covered only the Langflow side. The site now has a
Python back end and a React front end, so the class diagrams are split into three files:*

| File | Covers |
|---|---|
| [`class-diagram-backend.md`](class-diagram-backend.md) | the FastAPI service, `tutor_core`, the model-choice classes, the chat client, security, the database, and the list of further back-end splits |
| [`class-diagram-frontend.md`](class-diagram-frontend.md) | the React shell, contexts, the API layer, pages and their parts, shared components, and the list of further front-end splits |
| this file | the Langflow components and how they reach `tutor_core` |

## Langflow components (`custom_components/`)

```mermaid
classDiagram
    class LanguageAgent {
        <<Langflow built-in Agent>>
        +tools: AddWord, StoryGeneratorTool
        +model: GroqLanguageModel
        +chat_input: str
        +route_and_respond() str
    }
    class GroqLanguageModel {
        <<custom component>>
        +api_key: str
        +model_name: str
        +build_model() LanguageModel
    }
    class AddWord {
        <<custom component>>
        +word: str
        +learner_id: str hidden
        +active_language: str hidden
        +run() Message
    }
    class StoryGeneratorTool {
        <<custom component>>
        +language: str
        +story_type: str
        +topic: str
        +difficulty: str
        +learner_id: str hidden
        +active_language: str hidden
        +set_ids: str hidden
        +run() Message
    }
    class ToolResultRelay {
        <<custom component>>
        +agent_response: Message
        +relay() Message
        -extract_last_tool_output()
    }
    class WordLoader {
        <<custom component, unwired>>
        +run() Message
    }
    class SpikeWhoAmI {
        <<custom component, test only>>
        +run() Message
    }
    class AgentTools {
        <<module tutor_core.tools>>
        +add_word_for_agent(...)
        +story_for_agent(...)
        +vocabulary_for_agent(...)
    }
    class TutorCore {
        <<package tutor_core>>
        story, vocab, words, prompts, quality, difficulty
    }
    class GroqAPI {
        <<external>>
        +chat_completions() str
    }
    class WordsTable {
        <<table tutor.words>>
        +id, user_id, language, word, meaning, set_id
    }

    LanguageAgent --> AddWord : tool
    LanguageAgent --> StoryGeneratorTool : tool
    LanguageAgent --> GroqLanguageModel : model
    LanguageAgent --> ToolResultRelay : reply passes through
    GroqLanguageModel --> GroqAPI
    AddWord --> AgentTools : add_word_for_agent
    StoryGeneratorTool --> AgentTools : story_for_agent
    WordLoader --> AgentTools : vocabulary_for_agent
    AgentTools --> TutorCore
    TutorCore --> GroqAPI : story prompt
    TutorCore --> WordsTable : as tutor_tools role
```

**Notes**
- Each component is thin: Langflow's component code only collects inputs and calls one `tutor_core.tools` function, so the same rules run in chat and on the site. The component code is copied into `flows/language-tutor.json`; `scripts/sync_flow_nodes.py --check` must print "in step".
- `StoryGeneratorTool` is one component because Langflow's Tool Mode returns only a component's own output.
- The hidden inputs (`learner_id`, `active_language`, `set_ids`) are set by the API per request through the run's tweaks; the Agent cannot see or change them.
- The old Step 8 canvas pipeline was deleted on 18 October 2026. `WordLoader` remains, unwired, for debugging; `SpikeWhoAmI` is the M0 spike that proved per-request inputs stay separate.
- Known duplication: `ToolResultRelay` and `api/app/services/langflow/reply.py` each parse a tool's recorded output (card B11).
