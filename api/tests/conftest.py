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
