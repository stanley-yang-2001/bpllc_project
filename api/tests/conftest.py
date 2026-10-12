import os

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

DB_URL = os.environ.get("TEST_DATABASE_URL", "postgresql://langflow:testpw@localhost:5432/langflow")
HEADERS = {"X-Requested-With": "tutor"}


@pytest.fixture(scope="session")
def app():
    settings = Settings(database_url=DB_URL, jwt_secret="x" * 40, bcrypt_rounds=4)
    with psycopg2.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute("DROP SCHEMA IF EXISTS tutor CASCADE")
    application = create_app(settings)
    with TestClient(application):           # runs lifespan: migrations + pool
        yield application


@pytest.fixture(autouse=True)
def clean(app):
    with psycopg2.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute("TRUNCATE tutor.users RESTART IDENTITY CASCADE")
    app.state.login_guard._fails.clear()


@pytest.fixture
def client(app):
    return TestClient(app, headers=HEADERS)


def email_of(name: str) -> str:
    return f"{name.lower()}@example.com"


def signup_body(name="alice", password="password123", **extra):
    """A valid sign-up request. `name` becomes both the display name and the part before @example.com."""
    body = {"email": email_of(name), "password": password, "display_name": name, "accept_privacy": True}
    body.update(extra)
    return body


def register(client, name="alice", password="password123", **extra):
    r = client.post("/api/auth/register", json=signup_body(name, password, **extra))
    assert r.status_code == 201, r.text
    return r.json()


def login_body(name="alice", password="password123"):
    return {"email": email_of(name), "password": password}


@pytest.fixture
def make_user(app):
    def _make(name="alice", **extra):
        c = TestClient(app, headers=HEADERS)
        register(c, name, **extra)
        return c
    return _make


# --- plain database access, for testing tutor_core (the code the Langflow tools share) ----------------------------

@pytest.fixture
def conn(app):
    c = psycopg2.connect(DB_URL)
    yield c
    c.close()


@pytest.fixture
def make_learner(conn):
    """Insert a learner straight into tutor.users (no HTTP) and return the id. Ids restart at 1 in every test, so a
    test that needs to tell learners apart creates at least two."""
    made = []

    def _make(name="learner"):
        with conn.cursor() as cur:
            cur.execute("INSERT INTO tutor.users (email, password_hash, display_name) VALUES (%s, 'x', %s) RETURNING id",
                        (f"{name}{len(made) + 1}@example.com", name))
            made.append(cur.fetchone()[0])
        conn.commit()
        return made[-1]
    return _make


def words_of(conn, learner_id, language=None):
    """What is stored for a learner (optionally one language), oldest first."""
    with conn.cursor() as cur:
        if language:
            cur.execute("SELECT word FROM tutor.words WHERE user_id = %s AND language = %s ORDER BY id", (learner_id, language))
        else:
            cur.execute("SELECT word FROM tutor.words WHERE user_id = %s ORDER BY id", (learner_id,))
        return [r[0] for r in cur.fetchall()]
