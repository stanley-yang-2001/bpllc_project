"""
Upload Word File — Story 2.

Standalone component (not agent-facing): run this once manually from the Langflow canvas
to create the `words` table and seed it from a CSV. Every later component that reads or
writes vocabulary (Add Word, Word Loader) depends on this having run first.

Core logic is split into plain functions (ensure_words_table, words_from_csv_text,
bulk_insert_words) so they can be tested directly — see tests/test_upload_word_file.py —
without needing to run this inside Langflow itself.
"""

import csv
import io

import psycopg2
from langflow.custom import Component
from langflow.io import FileInput, Output, StrInput

DB_CONFIG = dict(
    dbname="langflow",
    user="langflow",
    password="langflow",
    host="postgres",
    port=5432,
)


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def ensure_words_table(conn, table_name: str = "words") -> None:
    """Create the vocabulary table if it doesn't already exist. Safe to call repeatedly."""
    with conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id SERIAL PRIMARY KEY,
                word TEXT UNIQUE NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now()
            );
            """
        )
    conn.commit()


def words_from_csv_text(csv_text: str, column_name: str) -> list[str]:
    """Parse CSV text and return the non-blank values of one column, in order."""
    reader = csv.DictReader(io.StringIO(csv_text))
    if column_name not in (reader.fieldnames or []):
        raise ValueError(
            f"Column '{column_name}' not found in CSV headers: {reader.fieldnames}"
        )
    words: list[str] = []
    for row in reader:
        value = (row.get(column_name) or "").strip()
        if value:
            words.append(value)
    return words


def bulk_insert_words(conn, words: list[str], table_name: str = "words") -> int:
    """Insert words, silently skipping duplicates. Returns how many were actually inserted."""
    if not words:
        return 0
    inserted = 0
    with conn.cursor() as cur:
        for word in words:
            cur.execute(
                f"INSERT INTO {table_name} (word) VALUES (%s) ON CONFLICT (word) DO NOTHING;",
                (word,),
            )
            if cur.rowcount == 1:
                inserted += 1
    conn.commit()
    return inserted


class UploadWordFile(Component):
    display_name = "Upload Word File"
    description = (
        "Seeds the vocabulary table from a CSV file. Run once manually — not wired to any "
        "agent — to create and populate the `words` table."
    )
    icon = "Upload"
    name = "UploadWordFile"

    inputs = [
        FileInput(
            name="csv_file",
            display_name="CSV File",
            file_types=["csv"],
            info="A CSV file containing the starting vocabulary.",
        ),
        StrInput(
            name="column_name",
            display_name="Column Name",
            info="The CSV column that contains the words to import.",
            value="word",
        ),
    ]

    outputs = [
        Output(display_name="Result", name="result", method="run"),
    ]

    def run(self) -> str:
        try:
            with open(self.csv_file, "r", encoding="utf-8") as f:
                csv_text = f.read()

            words = words_from_csv_text(csv_text, self.column_name)

            conn = get_connection()
            try:
                ensure_words_table(conn)
                inserted = bulk_insert_words(conn, words)
            finally:
                conn.close()

            return f"Seeded {inserted} new word(s) out of {len(words)} found in the CSV."
        except Exception as e:
            return f"Upload failed: {type(e).__name__}: {e}"