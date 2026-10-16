"""Create a demo account with sample words. Safe to run repeatedly.

  docker compose exec api python -m app.seed [--import-legacy]

--import-legacy copies the old single-user table public.words into the demo user's English list
(the table is left in place as a backup).
"""
from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path

import psycopg2
from psycopg2.extras import Json
from tutor_core import quality
from tutor_core.words import WordError, validate_meaning, validate_word

from .db import SCHEMA
from .migrate import run_migrations
from .policy import POLICY_VERSION
from .security import hash_password, new_salt

_SAMPLES = Path(os.environ.get("SAMPLE_DIR", Path(__file__).resolve().parents[2] / "sample_data"))
# The starter list is tiny with almost no verbs, which made stories samey (Step 10 findings); the suggested list
# (verbs, nouns, adjectives) is the owner's remedy, so the demo account gets both.
SAMPLE_CSVS = [_SAMPLES / "starter_vocabulary.csv", _SAMPLES / "suggested_words.csv"]
SPANISH = [("hola", "hello"), ("gracias", "thank you"), ("agua", "water"), ("pan", "bread"), ("casa", "house"),
           ("amigo", "friend"), ("comer", "to eat"), ("beber", "to drink"), ("grande", "big"), ("pequeño", "small")]


# Two short saved stories, so Library and Practice have something to show on a clean checkout. They use only words from the
# sample lists; the quality report is made by the real checker, exactly as it is when a learner saves a story.
DEMO_STORIES = [
    ("en", "dialogue", "Ana: Hello, my friend.\nBen: Hello, do you want some water?\nAna: Yes, please. I want some food too.\nBen: Here you are. Goodbye, friend."),
    ("es", "dialogue", "Ana: Hola, amigo.\nLuis: Hola, ¿quieres agua?\nAna: Sí, gracias. Quiero pan en casa.\nLuis: Aquí tienes."),
]


def _stories(cur, user_id: int) -> int:
    made = 0
    for language, story_type, body in DEMO_STORIES:
        cur.execute(f"SELECT 1 FROM {SCHEMA}.stories WHERE user_id = %s AND language = %s AND body = %s", (user_id, language, body))
        if cur.fetchone():
            continue
        cur.execute(f"SELECT word FROM {SCHEMA}.words WHERE user_id = %s AND language = %s ORDER BY id", (user_id, language))
        report = quality.report(body, language, [w for (w,) in cur.fetchall()])
        cur.execute(f"INSERT INTO {SCHEMA}.stories (user_id, language, story_type, topic, body, passed, report) VALUES (%s, %s, %s, NULL, %s, %s, %s)",
                    (user_id, language, story_type, body, report["status"] == "pass", Json(report)))
        made += 1
    return made


def _insert(cur, user_id: int, language: str, pairs) -> int:
    n = 0
    for word, meaning in pairs:
        try:
            w, m = validate_word(word, language), validate_meaning(meaning)
        except WordError:
            continue
        cur.execute(f"INSERT INTO {SCHEMA}.words (user_id, language, word, meaning) VALUES (%s, %s, %s, %s) "
                    "ON CONFLICT (user_id, language, word) DO NOTHING RETURNING id", (user_id, language, w, m))
        n += 1 if cur.fetchone() else 0
    return n


def seed(database_url: str, email: str, password: str, import_legacy: bool = False, rounds: int = 12) -> dict:
    run_migrations(database_url)
    out = {"user_created": False, "english": 0, "spanish": 0, "legacy": 0, "stories": 0}
    with psycopg2.connect(database_url) as conn, conn.cursor() as cur:
        cur.execute(f"SELECT id FROM {SCHEMA}.users WHERE email = %s", (email,))
        row = cur.fetchone()
        if row:
            user_id = row[0]
        else:
            salt = new_salt()
            cur.execute(f"INSERT INTO {SCHEMA}.users (email, password_hash, password_salt, display_name, privacy_accepted_at, privacy_version) "
                        "VALUES (%s, %s, %s, %s, now(), %s) RETURNING id",
                        (email, hash_password(password, salt, rounds), salt, "Demo Learner", POLICY_VERSION))
            user_id = cur.fetchone()[0]
            out["user_created"] = True
        for lang in ("en", "es"):
            cur.execute(f"INSERT INTO {SCHEMA}.user_languages (user_id, language) VALUES (%s, %s) ON CONFLICT DO NOTHING", (user_id, lang))
        for sample in SAMPLE_CSVS:
            if sample.exists():
                with sample.open(encoding="utf-8-sig", newline="") as f:
                    out["english"] += _insert(cur, user_id, "en", ((r["word"], r.get("definition", "")) for r in csv.DictReader(f)))
        out["spanish"] = _insert(cur, user_id, "es", SPANISH)
        out["stories"] = _stories(cur, user_id)
        if import_legacy:
            cur.execute("SELECT to_regclass('public.words')")
            if cur.fetchone()[0]:
                cur.execute("SELECT word FROM public.words ORDER BY id")
                out["legacy"] = _insert(cur, user_id, "en", ((w, "") for (w,) in cur.fetchall()))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--import-legacy", action="store_true")
    args = ap.parse_args()
    url, user, pw = os.environ["DATABASE_URL"], os.environ.get("DEMO_EMAIL", "demo@example.com"), os.environ.get("DEMO_PASSWORD", "")
    if len(pw) < 8:
        raise SystemExit("Set DEMO_PASSWORD (at least 8 characters) in .env to create the demo account.")
    print(seed(url, user, pw, args.import_legacy))


if __name__ == "__main__":
    main()
