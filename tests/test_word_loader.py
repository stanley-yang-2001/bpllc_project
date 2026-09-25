"""
Tests for Word Loader's core logic (Story 4 acceptance criteria).

Written BEFORE the implementation. Run this now and expect an ImportError, since
custom_components/word_loader.py doesn't exist yet. Re-run after implementing to confirm green.

Uses a separate `words_test` table so it never touches real seeded vocabulary data.

Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_word_loader.py
"""

import sys

import psycopg2

sys.path.insert(0, "/app/custom_components")

from word_loader import load_words  # noqa: E402

DB_CONFIG = dict(dbname="langflow", user="langflow", password="langflow", host="postgres", port=5432)
TEST_TABLE = "words_test"

PASS = "PASS"
FAIL = "FAIL"
failures = []


def check(label, condition):
    if condition:
        print(f"[{PASS}] {label}")
    else:
        print(f"[{FAIL}] {label}")
        failures.append(label)


def get_connection():
    return psycopg2.connect(**DB_CONFIG)


def cleanup(conn):
    with conn.cursor() as cur:
        cur.execute(f"DROP TABLE IF EXISTS {TEST_TABLE};")
    conn.commit()


def create_test_table(conn):
    with conn.cursor() as cur:
        cur.execute(
            f"""
            CREATE TABLE IF NOT EXISTS {TEST_TABLE} (
                id SERIAL PRIMARY KEY,
                word TEXT UNIQUE NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now()
            );
            """
        )
    conn.commit()


def seed_words(conn, words):
    with conn.cursor() as cur:
        for word in words:
            cur.execute(f"INSERT INTO {TEST_TABLE} (word) VALUES (%s);", (word,))
    conn.commit()


def test_load_words_returns_comma_separated_string():
    conn = get_connection()
    cleanup(conn)
    create_test_table(conn)
    seed_words(conn, ["hello", "world", "friend"])
    result = load_words(conn, table_name=TEST_TABLE)
    check(
        "load_words returns all words as a comma-separated string, in insertion order",
        result == "hello, world, friend",
    )
    conn.close()


def test_load_words_single_word_no_trailing_comma():
    conn = get_connection()
    cleanup(conn)
    create_test_table(conn)
    seed_words(conn, ["hello"])
    result = load_words(conn, table_name=TEST_TABLE)
    check("load_words handles a single word with no trailing comma", result == "hello")
    conn.close()


def test_load_words_empty_table_returns_empty_string():
    conn = get_connection()
    cleanup(conn)
    create_test_table(conn)
    result = load_words(conn, table_name=TEST_TABLE)
    check("load_words returns an empty string for an empty vocabulary", result == "")
    conn.close()


def test_load_words_missing_table_raises():
    conn = get_connection()
    cleanup(conn)  # table intentionally does NOT exist
    try:
        load_words(conn, table_name=TEST_TABLE)
        check("load_words raises a clear error if the table is missing", False)
    except RuntimeError as e:
        check(f"load_words raises a clear error if the table is missing ({e})", True)
    conn.close()


def main():
    print("Running Word Loader tests (Story 4 acceptance criteria)...\n")
    test_load_words_returns_comma_separated_string()
    test_load_words_single_word_no_trailing_comma()
    test_load_words_empty_table_returns_empty_string()
    test_load_words_missing_table_raises()

    conn = get_connection()
    cleanup(conn)
    conn.close()

    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    else:
        print("All tests passed.")
        sys.exit(0)


if __name__ == "__main__":
    main()