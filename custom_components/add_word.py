"""
Add Word — Story 3.

Agent-callable tool: inserts a single new word into the vocabulary table. Requires the
`words` table to already exist (Upload Word File run at least once — Story 2, Step 4).

Core logic is a plain function (insert_word) so it's testable directly — see
tests/test_add_word.py — without running this inside Langflow.

To use as a tool: after adding this component to the canvas, enable "Tool Mode" on it, then
attach it to an Agent node's Tools input. The LLM fills in `word` based on the chat message.
"""

import unicodedata

import psycopg2
from langflow.custom import Component
from langflow.io import MessageTextInput, Output

DB_CONFIG = dict(
    dbname="langflow",
    user="langflow",
    password="langflow",
    host="postgres",
    port=5432,
)


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


# Punctuation an Agent may wrap around or trail after a word ('bread.', '"bread"', '(bread)').
_EDGE_CHARS = " \t\r\n.,!?;:\"'\u201c\u201d\u2018\u2019\u00ab\u00bb()[]{}\u2026" \
              "\u3002\uff01\uff1f\u3001\uff0c\uff1b\uff1a\u300c\u300d\u300e\u300f\uff08\uff09"


def normalize_word(word) -> str:
    """Canonical form stored in the vocabulary: no edge punctuation or whitespace, single
    spaces inside a phrase, lowercase. Without this, 'Water', 'water' and 'water.' became
    separate rows (the UNIQUE constraint is case-sensitive) and skewed every story."""
    text = unicodedata.normalize("NFC", word or "")
    text = " ".join(text.split()).strip(_EDGE_CHARS)
    return " ".join(text.split()).lower()


def insert_word(conn, word: str, table_name: str = "words") -> bool:
    """Insert a single word if not already present. Returns True if newly inserted."""
    word = normalize_word(word)
    if not word:
        raise ValueError("word must be a non-empty string")

    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s);",
            (table_name,),
        )
        if not cur.fetchone()[0]:
            raise RuntimeError(
                f"Table '{table_name}' does not exist. Run Upload Word File at least once first."
            )

        cur.execute(
            f"INSERT INTO {table_name} (word) VALUES (%s) ON CONFLICT (word) DO NOTHING;",
            (word,),
        )
        inserted = cur.rowcount == 1
    conn.commit()
    return inserted


class AddWord(Component):
    display_name = "Add Word"
    description = (
        "Adds a single new word to the vocabulary table. Enable Tool Mode and attach to an "
        "Agent so it can be called from chat."
    )
    icon = "Plus"
    name = "AddWord"

    inputs = [
        MessageTextInput(
            name="word",
            display_name="Word",
            info="The word to add to the learner's known vocabulary.",
            tool_mode=True,
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="run"),
    ]

    def run(self) -> str:
        try:
            conn = get_connection()
            try:
                added = insert_word(conn, self.word)
            finally:
                conn.close()

            shown = normalize_word(self.word)
            if added:
                return f"Added '{shown}' to your vocabulary."
            return f"'{shown}' is already in your vocabulary."
        except (ValueError, RuntimeError) as e:
            return f"Couldn't add word: {e}"
        except Exception as e:
            return f"Add word failed: {type(e).__name__}: {e}"