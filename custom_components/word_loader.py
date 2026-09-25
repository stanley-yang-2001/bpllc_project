"""
Word Loader — Story 4.

Reads every word from the vocabulary table and returns them as a single comma-separated
string. Feeds the {words} variable in the story prompt template (Step 7) and is used by
Add Word's dependency chain — requires the `words` table to already exist (Story 2, Step 4).

Core logic is a plain function (load_words) so it's testable directly — see
tests/test_word_loader.py — without running this inside Langflow.
"""

import psycopg2
from langflow.custom import Component
from langflow.io import Output
from langflow.schema.message import Message

DB_CONFIG = dict(
    dbname="langflow",
    user="langflow",
    password="langflow",
    host="postgres",
    port=5432,
)


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def load_words(conn, table_name: str = "words") -> str:
    """Return every word in the table as a comma-separated string, in insertion order.

    Returns an empty string if the vocabulary is empty. Raises RuntimeError if the table
    doesn't exist yet.
    """
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s);",
            (table_name,),
        )
        if not cur.fetchone()[0]:
            raise RuntimeError(
                f"Table '{table_name}' does not exist. Run Upload Word File at least once first."
            )

        cur.execute(f"SELECT word FROM {table_name} ORDER BY id;")
        rows = cur.fetchall()

    return ", ".join(row[0] for row in rows)


class WordLoader(Component):
    display_name = "Word Loader"
    description = (
        "Reads all known vocabulary and returns it as a comma-separated string, for use as "
        "the {words} variable in the story prompt template."
    )
    icon = "BookOpen"
    name = "WordLoader"

    inputs = []

    outputs = [
        Output(display_name="Words", name="words", method="run"),
    ]

    def run(self) -> Message:
        conn = get_connection()
        try:
            result = load_words(conn)
        finally:
            conn.close()

        message = Message(text=result)
        self.status = message  # shows the returned value in the node's UI preview
        return message