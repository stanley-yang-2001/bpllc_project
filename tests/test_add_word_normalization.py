"""
Tests for Add Word input normalization (Step 10 edge cases).

Problem: the `words` column is UNIQUE but case-sensitive, and Add Word only stripped the ends,
so "Water", "water" and " water " could become three separate rows, and an Agent passing
'bread.' or '"bread"' stored the punctuation. A duplicate vocabulary entry silently skews
every story.

Written BEFORE the fix. Uses a fake connection, so no Postgres is needed.

Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_add_word_normalization.py
"""

import sys

sys.path.insert(0, "/app/custom_components")

from add_word import insert_word, normalize_word  # noqa: E402

PASS = "PASS"
FAIL = "FAIL"
failures = []


def check(label, condition):
    if condition:
        print(f"[{PASS}] {label}")
    else:
        print(f"[{FAIL}] {label}")
        failures.append(label)


class FakeCursor:
    def __init__(self, store):
        self.store = store
        self.rowcount = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def execute(self, sql, params=None):
        if "information_schema" in sql:
            self._fetch = (True,)
        elif sql.strip().upper().startswith("INSERT"):
            word = params[0]
            if word in self.store:  # ON CONFLICT (word) DO NOTHING (case-sensitive, like Postgres)
                self.rowcount = 0
            else:
                self.store.append(word)
                self.rowcount = 1

    def fetchone(self):
        return self._fetch


class FakeConnection:
    def __init__(self):
        self.words = []

    def cursor(self):
        return FakeCursor(self.words)

    def commit(self):
        pass


def test_normalize_word():
    check("plain word unchanged", normalize_word("water") == "water")
    check("surrounding whitespace removed", normalize_word("  water \n") == "water")
    check("case folded", normalize_word("Water") == "water")
    check("internal whitespace collapsed", normalize_word("thank   you") == "thank you")
    check("trailing punctuation removed", normalize_word("bread.") == "bread")
    check("surrounding quotes removed", normalize_word('"bread"') == "bread")
    check("curly quotes and brackets removed", normalize_word("“bread”") == "bread" and normalize_word("(bread)") == "bread")
    check("an inner apostrophe is kept", normalize_word("Don't") == "don't")
    check("a hyphenated word is kept", normalize_word("well-known") == "well-known")
    check("non-English letters are kept", normalize_word("Ñandú") == "ñandú" and normalize_word("日本語") == "日本語")


def test_empty_after_normalizing_is_rejected():
    for raw in ["", "   ", "...", '""', None]:
        try:
            insert_word(FakeConnection(), raw)
            check(f"{raw!r} is rejected", False)
        except ValueError:
            check(f"{raw!r} is rejected", True)


def test_case_variants_are_one_word():
    conn = FakeConnection()
    first = insert_word(conn, "Water")
    second = insert_word(conn, "water")
    third = insert_word(conn, "  WATER. ")
    check("first insert succeeds", first is True)
    check("a case/whitespace/punctuation variant is a duplicate", second is False and third is False)
    check("only one row is stored, in normalized form", conn.words == ["water"])


def test_phrase_is_stored_normalized():
    conn = FakeConnection()
    insert_word(conn, "Thank   You")
    check("a phrase is stored lowercased with single spaces", conn.words == ["thank you"])


def main():
    print("Running Add Word normalization tests...\n")
    test_normalize_word()
    test_empty_after_normalizing_is_rejected()
    test_case_variants_are_one_word()
    test_phrase_is_stored_normalized()
    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    print("All tests passed.")
    sys.exit(0)


if __name__ == "__main__":
    main()
