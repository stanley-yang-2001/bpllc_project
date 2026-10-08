import psycopg2
from fastapi.testclient import TestClient

from app.seed import seed
from conftest import DB_URL, HEADERS


def test_seed_creates_demo_user_who_can_log_in(app):
    out = seed(DB_URL, "demo@example.com", "demo-password", rounds=4)
    assert out["user_created"] and out["english"] >= 60 and out["spanish"] == 10     # starter list + suggested words
    c = TestClient(app, headers=HEADERS)
    assert c.post("/api/auth/login", json={"email": "demo@example.com", "password": "demo-password"}).json()["languages"] == ["en", "es"]
    assert c.get("/api/words", params={"language": "es"}).json()["total"] == 10


def test_seed_is_idempotent(app):
    seed(DB_URL, "demo@example.com", "demo-password", rounds=4)
    again = seed(DB_URL, "demo@example.com", "demo-password", rounds=4)
    assert again == {"user_created": False, "english": 0, "spanish": 0, "legacy": 0}


def test_import_legacy_words_then_leaves_the_table(app):
    with psycopg2.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute("DROP TABLE IF EXISTS public.words")
        cur.execute("CREATE TABLE public.words (id SERIAL PRIMARY KEY, word TEXT UNIQUE NOT NULL, created_at TIMESTAMPTZ DEFAULT now())")
        cur.execute("INSERT INTO public.words (word) VALUES ('zebra'), ('hello'), ('x9')")
    try:
        out = seed(DB_URL, "demo@example.com", "demo-password", import_legacy=True, rounds=4)
        assert out["legacy"] == 1                       # 'hello' already came from the sample CSV; 'x9' is invalid
        c = TestClient(app, headers=HEADERS)
        c.post("/api/auth/login", json={"email": "demo@example.com", "password": "demo-password"})
        words = {w["word"] for w in c.get("/api/words", params={"language": "en", "limit": 200}).json()["items"]}
        assert "zebra" in words and "x9" not in words
        with psycopg2.connect(DB_URL) as c2, c2.cursor() as cur:
            cur.execute("SELECT count(*) FROM public.words")
            assert cur.fetchone()[0] == 3                # legacy table untouched
    finally:
        with psycopg2.connect(DB_URL) as c3, c3.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS public.words")
