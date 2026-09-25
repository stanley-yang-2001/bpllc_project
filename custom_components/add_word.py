"""
Add Word — Story 3.

Agent-callable tool: inserts a single new word into the vocabulary table. Requires the
`words` table to already exist (Upload Word File run at least once — Story 2, Step 4).

Core logic is a plain function (insert_word) so it's testable directly — see
tests/test_add_word.py — without running this inside Langflow.

To use as a tool: after adding this component to the canvas, enable "Tool Mode" on it, then
attach it to an Agent node's Tools input. The LLM fills in `word` based on the chat message.
"""

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


def insert_word(conn, word: str, table_name: str = "words") -> bool:
    """Insert a single word if not already present. Returns True if newly inserted."""
    word = (word or "").strip()
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

            if added:
                return f"Added '{self.word.strip()}' to your vocabulary."
            return f"'{self.word.strip()}' is already in your vocabulary."
        except (ValueError, RuntimeError) as e:
            return f"Couldn't add word: {e}"
        except Exception as e:
            return f"Add word failed: {type(e).__name__}: {e}"