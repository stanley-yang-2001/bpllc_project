"""
Smoke test for the Language Tutor project's environment.

Not a unit test — this is an environment health check covering Stories 1 and 1b's
acceptance criteria (Postgres reachable, Groq API key valid). Run it any time you touch
docker-compose.yml or .env, before debugging a component as if it were broken.

Run from inside the langflow container (it needs the same network access the app has):

    docker compose exec langflow python /app/scripts/smoke_test.py
"""

import json
import os
import sys
import urllib.error
import urllib.request

import psycopg2

PASS = "PASS"
FAIL = "FAIL"


def check_postgres() -> bool:
    """Story 1: confirm Postgres is reachable from inside the app's network."""
    try:
        conn = psycopg2.connect(
            dbname="langflow",
            user="langflow",
            password="langflow",
            host="postgres",
            port=5432,
            connect_timeout=5,
        )
        cur = conn.cursor()
        cur.execute("SELECT 1;")
        result = cur.fetchone()
        cur.close()
        conn.close()
        assert result == (1,)
        print(f"[{PASS}] Postgres — connected and query returned expected result.")
        return True
    except Exception as e:
        print(f"[{FAIL}] Postgres — {type(e).__name__}: {e}")
        return False


def check_groq() -> bool:
    """Story 1b: confirm the Groq API key is set and actually accepted."""
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key or api_key == "your-groq-api-key-here":
        print(f"[{FAIL}] Groq — GROQ_API_KEY is missing or still the placeholder value.")
        return False

    url = "https://api.groq.com/openai/v1/chat/completions"
    payload = json.dumps(
        {
            "model": "openai/gpt-oss-20b",
            "messages": [{"role": "user", "content": "Reply with the single word: ok"}],
            "max_tokens": 5,
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "language-tutor-smoke-test/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            reply = body["choices"][0]["message"]["content"]
            print(f"[{PASS}] Groq — API key valid, model responded: {reply.strip()!r}")
            return True
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        print(f"[{FAIL}] Groq — HTTP {e.code}: {detail}")
        return False
    except Exception as e:
        print(f"[{FAIL}] Groq — {type(e).__name__}: {e}")
        return False


def main() -> int:
    print("Running environment smoke test...\n")
    results = [check_postgres(), check_groq()]
    print()
    if all(results):
        print("All checks passed. Environment is healthy.")
        return 0
    else:
        print("One or more checks failed — fix these before building/testing features.")
        return 1


if __name__ == "__main__":
    sys.exit(main())