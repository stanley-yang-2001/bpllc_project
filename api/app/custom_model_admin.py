"""Switch the "my own model" feature on or off for one account (decision 2 of docs/CUSTOM-MODEL-DESIGN.md).

    python -m app.custom_model_admin on you@example.com
    python -m app.custom_model_admin off you@example.com
    python -m app.custom_model_admin list

Needs DATABASE_URL (set in the api container). Turning an account off hides the feature but keeps the saved model."""
from __future__ import annotations

import os
import sys

import psycopg2


def run(argv, database_url: str) -> int:
    if not argv or argv[0] not in ("on", "off", "list") or (argv[0] != "list" and len(argv) != 2):
        print(__doc__)
        return 2
    with psycopg2.connect(database_url) as conn, conn.cursor() as cur:
        if argv[0] == "list":
            cur.execute("SELECT email FROM tutor.users WHERE custom_model_enabled ORDER BY email")
            rows = [r[0] for r in cur.fetchall()]
            print("\n".join(rows) if rows else "No account has it switched on.")
            return 0
        cur.execute("UPDATE tutor.users SET custom_model_enabled = %s WHERE lower(email) = lower(%s)", (argv[0] == "on", argv[1]))
        if cur.rowcount != 1:
            print(f"No account with the email {argv[1]}.")
            return 1
        print(f"Own model is now {argv[0]} for {argv[1]}.")
        return 0


if __name__ == "__main__":
    sys.exit(run(sys.argv[1:], os.environ["DATABASE_URL"]))
