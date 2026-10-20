from __future__ import annotations

from pathlib import Path

import psycopg2
from alembic import command
from alembic.config import Config
from psycopg2 import sql

ROOT = Path(__file__).resolve().parent.parent
TOOLS_ROLE = "tutor_tools"           # created by migration 0008, with no login


def run_migrations(database_url: str) -> None:
    cfg = Config(str(ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(ROOT / "migrations"))
    cfg.attributes["database_url"] = database_url      # not set_main_option: '%' in passwords breaks configparser
    command.upgrade(cfg, "head")


def set_tools_password(database_url: str, password: str) -> None:
    """Lets the Langflow tools' role log in with `password`, or (empty password) stops it logging in at all. Runs at every
    startup, after the migrations, so changing TOOLS_DB_PASSWORD and restarting the API is how the password is changed.
    The password is sent as a quoted literal built by psycopg2, never pasted into the statement by hand."""
    conn = psycopg2.connect(database_url)
    try:
        with conn.cursor() as cur:
            if password:
                cur.execute(sql.SQL("ALTER ROLE {} WITH LOGIN PASSWORD {}").format(sql.Identifier(TOOLS_ROLE), sql.Literal(password)))
            else:
                cur.execute(sql.SQL("ALTER ROLE {} WITH NOLOGIN PASSWORD NULL").format(sql.Identifier(TOOLS_ROLE)))
        conn.commit()
    finally:
        conn.close()
