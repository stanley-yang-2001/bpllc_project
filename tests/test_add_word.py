"""
Tests for Add Word's core logic (Story 3 acceptance criteria).

Written BEFORE the implementation. Run this now and expect an ImportError, since
custom_components/add_word.py doesn't exist yet. Re-run after implementing to confirm green.

Uses a separate `words_test` table so it never touches real seeded vocabulary data.

Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_add_word.py
"""

import sys

import psycopg2

sys.path.insert(0, "/app/custom_components")

from add_word import insert_word  # noqa: E402

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


def word_count(conn, word):
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {TEST_TABLE} WHERE word = %s;", (word,))
        return cur.fetchone()[0]


def test_insert_word_adds_new_word():
    conn = get_connection()
    cleanup(conn)
    create_test_table(conn)
    result = insert_word(conn, "hello", table_name=TEST_TABLE)
    check("insert_word returns True for a new word", result is True)
    check("insert_word actually persists the word", word_count(conn, "hello") == 1)
    conn.close()


def test_insert_word_skips_duplicate():
    conn = get_connection()
    cleanup(conn)
    create_test_table(conn)
    insert_word(conn, "hello", table_name=TEST_TABLE)
    result = insert_word(conn, "hello", table_name=TEST_TABLE)
    check("insert_word returns False for an existing word", result is False)
    check("insert_word does not create a duplicate row", word_count(conn, "hello") == 1)
    conn.close()


def test_insert_word_strips_whitespace():
    conn = get_connection()
    cleanup(conn)
    create_test_table(conn)
    insert_word(conn, "  hello  ", table_name=TEST_TABLE)
    check("insert_word strips surrounding whitespace", word_count(conn, "hello") == 1)
    conn.close()


def test_insert_word_rejects_empty_string():
    conn = get_connection()
    cleanup(conn)
    create_test_table(conn)
    try:
        insert_word(conn, "   ", table_name=TEST_TABLE)
        check("insert_word raises on an empty/blank word", False)
    except ValueError:
        check("insert_word raises on an empty/blank word", True)
    conn.close()


def test_insert_word_requires_existing_table():
    conn = get_connection()
    cleanup(conn)  # table intentionally does NOT exist
    try:
        insert_word(conn, "hello", table_name=TEST_TABLE)
        check("insert_word raises a clear error if the table is missing", False)
    except RuntimeError as e:
        check(f"insert_word raises a clear error if the table is missing ({e})", True)
    conn.close()


def main():
    print("Running Add Word tests (Story 3 acceptance criteria)...\n")
    test_insert_word_adds_new_word()
    test_insert_word_skips_duplicate()
    test_insert_word_strips_whitespace()
    test_insert_word_rejects_empty_string()
    test_insert_word_requires_existing_table()

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