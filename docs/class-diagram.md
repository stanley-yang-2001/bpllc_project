# Rough Class Diagram — Language Tutor with Langflow

```mermaid
classDiagram
    class UploadWordFileComponent {
        +csv_file: File
        +column_name: str
        +run() str
        -create_table_if_missing()
        -bulk_insert_words()
    }

    class AddWordTool {
        +word: str
        +run() str
        -insert_word()
    }

    class WordLoader {
        +run() str
        -query_all_words() List~str~
    }

    class StoryPromptTemplate {
        +language: str
        +words: str
        +build_prompt() str
    }

    class StoryGenerationAgent {
        +prompt: str
        +model: OllamaModel
        +generate_story() str
    }

    class LanguageAgent {
        +tools: List~Tool~
        +model: OllamaModel
        +chat_input: str
        +route_and_respond() str
    }

    class OllamaModel {
        +model_name: str
        +endpoint: str
        +invoke(prompt: str) str
    }

    class WordsTable {
        +id: int
        +word: str
        +user_id: str
        +created_at: datetime
    }

    LanguageAgent --> AddWordTool : uses as tool
    LanguageAgent --> StoryGenerationAgent : uses as tool
    StoryGenerationAgent --> StoryPromptTemplate : fills
    StoryGenerationAgent --> WordLoader : reads vocabulary via
    StoryGenerationAgent --> OllamaModel : invokes
    LanguageAgent --> OllamaModel : invokes
    AddWordTool --> WordsTable : inserts into
    WordLoader --> WordsTable : queries
    UploadWordFileComponent --> WordsTable : seeds
```

**Notes**
- "Rough" by design — this mirrors the 9 components from `OVERVIEW.md` section 4, not a full implementation-ready class model.
- `OllamaModel` stands in for whichever model component is active (Ollama primary, Hugging Face Inference fallback) — swap the class name/attributes if you standardize on the fallback instead.
