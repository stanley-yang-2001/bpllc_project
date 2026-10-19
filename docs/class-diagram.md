# Rough Class Diagram — Language Tutor with Langflow

```mermaid
classDiagram
    class WordLoader {
        +run() Message
        -load_words()
    }

    class LanguageAgent {
        +tools: List~Tool~
        +model: GroqLanguageModel
        +chat_input: str
        +route_and_respond() str
    }

    class ToolResultRelay {
        +agent_response: Message
        +relay() Message
        -extract_last_tool_output()
    }

    class GroqLanguageModel {
        +api_key: str
        +model_name: str
        +build_model() LanguageModel
    }

    class GroqAPI {
        +model: gpt-oss-120b
        +chat_completions() str
    }

    class WordsTable {
        +id: int
        +word: str
        +user_id: str
        +created_at: datetime
    }

    LanguageAgent --> AddWordTool : uses as tool
    LanguageAgent --> StoryGeneratorTool : uses as tool
    LanguageAgent --> GroqLanguageModel : model (120b)
    LanguageAgent --> ToolResultRelay : reply passes through
    GroqLanguageModel --> GroqAPI : invokes
    StoryGeneratorTool --> GroqAPI : calls directly (120b)
    StoryGeneratorTool --> WordsTable : queries
    AddWordTool --> WordsTable : inserts into
    WordLoader --> WordsTable : queries
```

**Notes**
- "Rough" by design — not a full implementation-ready class model.
- `StoryGeneratorTool` is one component because Langflow's Tool Mode returns only a component's own
  output. It takes the language and, optionally, a story type and a topic. The old Step 8 canvas
  pipeline (`UploadWordFile`, `StoryPromptBuilder`, `story_guard`, `FinalPassageExtractor`) was deleted
  on 18 October 2026; `WordLoader` remains, unwired, for debugging.
