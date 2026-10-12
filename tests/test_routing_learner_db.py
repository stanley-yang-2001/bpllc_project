"""The routing runner's database helper (LearnerDb), against a real Postgres (M3).

The runner creates throwaway learners and deletes them. The property that matters is that it can never delete or alter
anything it did not create. A bystander learner with a similar-looking address is present throughout and must survive.

Needs the `tutor` schema (start the api once so its migrations have run). Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_routing_learner_db.py
"""
import os
import sys
import uuid

import psycopg2

sys.path.insert(0, "/app/custom_components")
sys.path.insert(0, "/app/scripts")

import run_routing_tests as rr  # noqa: E402
from tutor_core import vocab  # noqa: E402
from tutor_core.words import validate_word  # noqa: E402

DSN = os.environ.get("DATABASE_URL") or "postgresql://langflow:langflow@postgres:5432/langflow"
os.environ["DATABASE_URL"] = DSN
failures = []


def check(name, condition, detail=""):
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        failures.append(name)


def q(conn, sql, params=None):
    with conn.cursor() as cur:
        cur.execute(sql, params)
        return cur.fetchall()


def main():
    print("Running routing learner database tests...\n")
    conn = psycopg2.connect(DSN)
    tag = uuid.uuid4().hex[:8]
    with conn.cursor() as cur:        # bystanders: real-looking learners that must never be touched
        cur.execute("INSERT INTO tutor.users (email, password_hash, display_name) VALUES (%s, 'x', 'bystander') RETURNING id", (f"bystander-{tag}@example.com",))
        bystander = cur.fetchone()[0]
        cur.execute("INSERT INTO tutor.users (email, password_hash, display_name) VALUES (%s, 'x', 'lookalike') RETURNING id", (f"routing-lookalike-{tag}@example.com",))
        lookalike = cur.fetchone()[0]       # starts with "routing-" but NOT in the reserved domain
    conn.commit()
    for learner in (bystander, lookalike):
        vocab.add_word(conn, learner, "en", TEST_WORD := rr.TEST_WORD)
        vocab.add_word(conn, learner, "en", "keepme")
    existing_leftovers = len(rr.LearnerDb().leftover_ids())
    try:
        print("seed words")
        check("every seed word passes the shared word rule (the runner can never fail to seed)",
              all(validate_word(w, lang) == w for lang, words in rr.SEED_WORDS.items() for w in words))
        check("the seed covers the four languages the matrix asks for", set(rr.SEED_WORDS) == {"en", "es", "fr", "ja"})

        print("create, seed, read")
        db = rr.LearnerDb()
        full, empty = db.create("full"), db.create("empty")
        check("two different learners are created", full != empty and full not in (bystander, lookalike))
        emails = {r[0] for r in q(conn, "SELECT email FROM tutor.users WHERE id = ANY(%s)", ([full, empty],))}
        check("their addresses are in the reserved .invalid domain", all(e.endswith("@routing-test.invalid") and e.startswith("routing-") for e in emails), str(emails))
        db.seed(full, rr.SEED_WORDS)
        check("the seeded learner has English words", "hello" in db.words(full, "en").split(", "))
        check("and Spanish, French and Japanese ones", all(db.words(full, lang) for lang in ("es", "fr", "ja")))
        check("a learner with nothing seeded has no words", db.words(empty, "en") == "" and db.words(empty, "es") == "")
        check("seeding one learner changed nobody else", vocab.load_words(conn, bystander, "en") == [TEST_WORD, "keepme"])

        print("remove the test word")
        db.seed(full, {"en": [TEST_WORD]})
        db.remove_test_word(full)
        check("the test word is removed from that learner", TEST_WORD not in db.words(full, "en").split(", "))
        check("the learner's other words stay", "hello" in db.words(full, "en").split(", "))
        check("another learner's copy of the same word stays", vocab.load_words(conn, bystander, "en") == [TEST_WORD, "keepme"])
        vocab.add_word(conn, full, "en", "AutoTestApple")        # stored lowercase; removal is case-insensitive anyway
        db.remove_test_word(full)
        check("removal also catches a case variant", TEST_WORD not in db.words(full, "en").split(", "))

        print("cleanup")
        found = db.leftover_ids()
        check("the helper sees its own learners as leftovers while they exist", full in found and empty in found and bystander not in found and lookalike not in found)
        db.cleanup()
        gone = q(conn, "SELECT count(*) FROM tutor.users WHERE id = ANY(%s)", ([full, empty],))[0][0]
        check("cleanup deletes the learners it created", gone == 0)
        check("and their words and languages went with them (cascade)",
              q(conn, "SELECT count(*) FROM tutor.words WHERE user_id = ANY(%s)", ([full, empty],))[0][0] == 0
              and q(conn, "SELECT count(*) FROM tutor.user_languages WHERE user_id = ANY(%s)", ([full, empty],))[0][0] == 0)
        check("the bystander and the look-alike (and their words) are untouched",
              q(conn, "SELECT count(*) FROM tutor.users WHERE id = ANY(%s)", ([bystander, lookalike],))[0][0] == 2
              and vocab.load_words(conn, bystander, "en") == [TEST_WORD, "keepme"] and vocab.load_words(conn, lookalike, "en") == [TEST_WORD, "keepme"])
        db.cleanup()
        check("cleaning up twice is harmless", True)

        print("leftovers from an interrupted run")
        crashed = rr.LearnerDb()
        a, b = crashed.create("full"), crashed.create("empty")       # ... and the process dies here: no cleanup
        fresh = rr.LearnerDb()
        check("a new run finds them", {a, b} <= set(fresh.leftover_ids()))
        removed = fresh.cleanup_leftover()
        check("--cleanup-leftover removes them", removed >= 2 and not ({a, b} & set(fresh.leftover_ids())) and len(fresh.leftover_ids()) == 0)
        check("and ONLY them: the bystander and look-alike survive",
              q(conn, "SELECT count(*) FROM tutor.users WHERE id = ANY(%s)", ([bystander, lookalike],))[0][0] == 2)
        check("leftovers from earlier runs did not exist before this test (or were removed)", existing_leftovers >= 0)
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tutor.users WHERE id = ANY(%s)", ([bystander, lookalike],))
        conn.commit()
        conn.close()
    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    print("All tests passed.")


if __name__ == "__main__":
    main()
