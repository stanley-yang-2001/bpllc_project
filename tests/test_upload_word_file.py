"""
Tests for Upload Word File's core logic (Story 2 acceptance criteria).

Written BEFORE the implementation, per the project's test-first workflow. Run this now and
you should see an ImportError — that's expected, since custom_components/upload_word_file.py
doesn't exist yet. Once it's implemented, re-run this to confirm everything passes (green).

Uses a separate `words_test` table so it never touches real seeded vocabulary data.

Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_upload_word_file.py
"""

import sys

import psycopg2

sys.path.insert(0, "/app/custom_components")

from upload_word_file import (  # noqa: E402
    bulk_insert_words,
    ensure_words_table,
    words_from_csv_text,
)

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


def test_ensure_words_table_creates_table():
    conn = get_connection()
    cleanup(conn)
    ensure_words_table(conn, table_name=TEST_TABLE)
    with conn.cursor() as cur:
        cur.execute(
            "SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = %s);",
            (TEST_TABLE,),
        )
        exists = cur.fetchone()[0]
    check("ensure_words_table creates the table if missing", exists is True)
    conn.close()


def test_ensure_words_table_is_idempotent():
    conn = get_connection()
    try:
        ensure_words_table(conn, table_name=TEST_TABLE)
        ensure_words_table(conn, table_name=TEST_TABLE)  # should not raise
        check("ensure_words_table can be called twice without error", True)
    except Exception as e:
        check(f"ensure_words_table can be called twice without error ({e})", False)
    conn.close()


def test_words_from_csv_text_parses_target_column():
    csv_text = "word,definition\nhello,a greeting\nworld,the earth\n"
    words = words_from_csv_text(csv_text, "word")
    check("words_from_csv_text extracts the right column", words == ["hello", "world"])


def test_words_from_csv_text_skips_blank_values():
    csv_text = "word\nhello\n\nworld\n"
    words = words_from_csv_text(csv_text, "word")
    check("words_from_csv_text skips blank rows", words == ["hello", "world"])


def test_words_from_csv_text_missing_column_raises():
    csv_text = "term\nhello\n"
    try:
        words_from_csv_text(csv_text, "word")
        check("words_from_csv_text raises on missing column", False)
    except ValueError:
        check("words_from_csv_text raises on missing column", True)


def test_bulk_insert_words_inserts_new_words():
    conn = get_connection()
    cleanup(conn)
    ensure_words_table(conn, table_name=TEST_TABLE)
    inserted = bulk_insert_words(conn, ["hello", "world"], table_name=TEST_TABLE)
    check("bulk_insert_words inserts all new words", inserted == 2)
    conn.close()


def test_bulk_insert_words_skips_duplicates():
    conn = get_connection()
    cleanup(conn)
    ensure_words_table(conn, table_name=TEST_TABLE)
    bulk_insert_words(conn, ["hello", "world"], table_name=TEST_TABLE)
    inserted_again = bulk_insert_words(conn, ["hello", "brand-new"], table_name=TEST_TABLE)
    check("bulk_insert_words skips existing duplicates", inserted_again == 1)
    conn.close()


def test_bulk_insert_words_handles_empty_list():
    conn = get_connection()
    cleanup(conn)
    ensure_words_table(conn, table_name=TEST_TABLE)
    inserted = bulk_insert_words(conn, [], table_name=TEST_TABLE)
    check("bulk_insert_words handles an empty word list", inserted == 0)
    conn.close()


def main():
    print("Running Upload Word File tests (Story 2 acceptance criteria)...\n")
    test_ensure_words_table_creates_table()
    test_ensure_words_table_is_idempotent()
    test_words_from_csv_text_parses_target_column()
    test_words_from_csv_text_skips_blank_values()
    test_words_from_csv_text_missing_column_raises()
    test_bulk_insert_words_inserts_new_words()
    test_bulk_insert_words_skips_duplicates()
    test_bulk_insert_words_handles_empty_list()

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