"""scripts/run_story_batch.py, run as a command against the real database (M3).

The unit test calls run_language() directly; this one runs main() through a subprocess, the way a person does, so the
argument parser, the learner and language handling, the per-language vocabularies and the saved file are all exercised.
Groq is made unavailable (no key), so every generation is a recorded failure and no network is needed.

Needs the `tutor` schema (start the api once so its migrations have run). Run from inside the langflow container:
    docker compose exec langflow python /app/tests/test_run_story_batch_cli.py
"""
import json
import os
import subprocess
import sys
import tempfile
import uuid

import psycopg2

sys.path.insert(0, "/app/custom_components")
from tutor_core import vocab  # noqa: E402

DSN = os.environ.get("ADMIN_DATABASE_URL") or os.environ.get("DATABASE_URL") or "postgresql://langflow:langflow@postgres:5432/langflow"   # these create and delete learners
SCRIPT = "/app/scripts/run_story_batch.py"
failures = []


def check(name, condition, detail=""):
    if condition:
        print(f"  PASS  {name}")
    else:
        print(f"  FAIL  {name} {detail}")
        failures.append(name)


def run(*args, env_extra=None):
    env = {k: v for k, v in os.environ.items() if k not in ("GROQ_API_KEY", "TUTOR_DEV_USER_ID")}
    env["DATABASE_URL"] = DSN
    env.update(env_extra or {})
    return subprocess.run([sys.executable, SCRIPT, *args], capture_output=True, text=True, timeout=120, env=env)


def main():
    print("Running story batch CLI tests...\n")
    conn = psycopg2.connect(DSN)
    with conn.cursor() as cur:
        cur.execute("INSERT INTO tutor.users (email, password_hash, display_name) VALUES (%s, 'x', 'batch test') RETURNING id",
                    (f"batch-{uuid.uuid4().hex[:8]}@example.com",))
        learner = cur.fetchone()[0]
    conn.commit()
    try:
        for w in ("hello", "water", "friend"):
            vocab.add_word(conn, learner, "en", w)
        vocab.add_word(conn, learner, "es", "pan")
        with tempfile.TemporaryDirectory() as tmp:
            out = os.path.join(tmp, "results.json")

            r = run("--learner-id", str(learner), "--languages", "English,Spanish,French,Klingon", "--count", "1",
                    "--delay", "0", "--out", out)
            check("it runs and exits 0", r.returncode == 0, r.stdout[-400:] + r.stderr[-400:])
            check("English uses the learner's English words", "English vocabulary (3 entries): hello, water, friend" in r.stdout, r.stdout[:300])
            check("Spanish uses the learner's own Spanish list, not the English one", "Spanish vocabulary (1 entries): pan" in r.stdout)
            check("a language the learner has no words in is skipped, with a reason", "Skipping French: learner" in r.stdout)
            check("an unknown language is skipped, not a crash", "Skipping 'Klingon'" in r.stdout)
            check("failures are recorded with their reason (no Groq key)", "GROQ_API_KEY" in r.stdout, r.stdout[-500:])
            data = json.load(open(out, encoding="utf-8"))
            check("the saved file has one vocabulary per language", data["vocabularies"] == {"English": "hello, water, friend", "Spanish": "pan"}, str(data.get("vocabularies")))
            check("the saved file names the learner", data["learner_id"] == learner)
            check("the old single 'vocabulary' key is still written (for older readers)", data["vocabulary"] == "hello, water, friend")
            check("both languages have results", set(data["results"]) == {"English", "Spanish"})

            r = run("--rescore", out)
            check("a saved file can be re-scored", r.returncode == 0 and "=== English ===" in r.stdout and "=== Spanish ===" in r.stdout, r.stdout[-300:] + r.stderr[-300:])

            old = os.path.join(tmp, "old.json")                  # the shape written before M3: one shared vocabulary
            json.dump({"vocabulary": "hello, water", "max_oov": 5, "strict_verbs": False, "results": data["results"]}, open(old, "w"))
            check("a results file from before M3 can still be re-scored", run("--rescore", old).returncode == 0)

            r = run("--languages", "English", "--count", "1")
            check("without a learner it refuses, saying how to give one", r.returncode == 2 and "--learner-id" in r.stdout, r.stdout + r.stderr)
            r = run("--languages", "English", "--count", "1", "--delay", "0", "--out", out, env_extra={"TUTOR_DEV_USER_ID": str(learner)})
            check("TUTOR_DEV_USER_ID is the default learner", r.returncode == 0 and "English vocabulary (3 entries)" in r.stdout, r.stdout[-300:])
            r = run("--learner-id", str(learner), "--languages", "French", "--count", "1")
            check("when no language has words it says so and exits 1", r.returncode == 1 and "Nothing was measured." in r.stdout, r.stdout)
            check("--help works", "--learner-id" in run("--help").stdout)
    finally:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM tutor.users WHERE id = %s", (learner,))
        conn.commit()
        conn.close()
    print()
    if failures:
        print(f"{len(failures)} test(s) failed: {failures}")
        sys.exit(1)
    print("All tests passed.")


if __name__ == "__main__":
    main()
