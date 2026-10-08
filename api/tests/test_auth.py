import jwt
import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.emails import validate_email
from conftest import DB_URL, HEADERS, login_body, register, signup_body


def test_register_login_me_logout(client):
    data = register(client, "Alice", display_name="  Al  ", language="es")
    assert data["email"] == "alice@example.com" and data["display_name"] == "Al" and data["languages"] == ["es"]
    assert "password_hash" not in data and "username" not in data
    assert client.get("/api/me").json()["email"] == "alice@example.com"       # register set the cookie
    assert client.post("/api/auth/logout").status_code == 204
    assert client.get("/api/me").status_code == 401
    r = client.post("/api/auth/login", json={"email": "  ALICE@Example.COM ", "password": "password123"})   # case/space tolerant
    assert r.status_code == 200 and client.get("/api/me").status_code == 200


def test_cookie_is_httponly_lax(client):
    r = client.post("/api/auth/register", json=signup_body("bob"))
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie


def test_signup_requires_accepting_the_privacy_policy(client):
    for extra in ({"accept_privacy": False}, {"accept_privacy": None}):
        r = client.post("/api/auth/register", json=signup_body("carol", **extra))
        assert r.status_code == 422 and "privacy" in r.json()["error"]["message"].lower()
    body = signup_body("carol"); del body["accept_privacy"]
    assert client.post("/api/auth/register", json=body).status_code == 422          # missing counts as not accepted
    assert client.get("/api/me").status_code == 401                                   # nothing was created


def test_consent_is_recorded_with_the_policy_version(client):
    from app.policy import POLICY_VERSION
    register(client, "alice")
    with psycopg2.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute("SELECT privacy_version, privacy_accepted_at IS NOT NULL FROM tutor.users")
        assert cur.fetchone() == (POLICY_VERSION, True)


def test_duplicate_email_conflict_ignores_case(client):
    register(client, "alice")
    r = client.post("/api/auth/register", json=signup_body("alice", email="ALICE@example.com"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "conflict"


def test_login_failures_are_generic(client):
    register(client, "alice")
    wrong_pw = client.post("/api/auth/login", json=login_body("alice", "nope-nope"))
    no_user = client.post("/api/auth/login", json=login_body("ghost", "nope-nope"))
    assert wrong_pw.status_code == no_user.status_code == 401
    assert wrong_pw.json() == no_user.json()


def test_lockout_after_five_failures(client):
    register(client, "alice")
    for _ in range(5):
        assert client.post("/api/auth/login", json=login_body("alice", "bad-password")).status_code == 401
    r = client.post("/api/auth/login", json=login_body("alice", "password123"))   # even the right one
    assert r.status_code == 429 and r.json()["error"]["code"] == "login_locked"
    assert r.json()["error"]["retry_after"] > 0 and "retry-after" in r.headers


def test_password_rules(client):
    short = client.post("/api/auth/register", json=signup_body("carol", "short"))
    assert short.status_code == 422 and short.json()["error"]["code"] == "validation_error"
    assert client.post("/api/auth/register", json=signup_body("carol", "x" * 73)).status_code == 422
    assert client.post("/api/auth/register", json=signup_body("carol", "x" * 72)).status_code == 201


@pytest.mark.parametrize("bad", ["", "plain", "a@b", "a@@b.com", "@example.com", "a b@example.com", "a@exa mple.com",
                                 "a@-example.com", "a@example..com", ".a@example.com", "a.@example.com",
                                 "a@example.c", "a@example.123", "x" * 65 + "@example.com", "a@" + "b" * 250 + ".com"])
def test_bad_emails_rejected(client, bad):
    assert client.post("/api/auth/register", json=signup_body("dave", email=bad)).status_code == 422
    with pytest.raises(ValueError):
        validate_email(bad)


@pytest.mark.parametrize("good", ["a@example.com", "First.Last+tag@Sub.Example.co.uk", "o'brien@example.org", "x@xn--bcher-kva.example"])
def test_good_emails_accepted(good):
    assert validate_email(good) == good.lower()


def test_name_and_language_rules(client):
    assert client.post("/api/auth/register", json=signup_body("dave", display_name="")).status_code == 422
    assert client.post("/api/auth/register", json=signup_body("dave", display_name="x" * 41)).status_code == 422
    assert client.post("/api/auth/register", json=signup_body("dave", language="xx")).status_code == 422


def test_expired_and_forged_tokens_rejected(app, client):
    register(client, "alice")
    secret = app.state.settings.jwt_secret
    expired = jwt.encode({"sub": "1", "exp": 1}, secret, algorithm="HS256")
    forged = jwt.encode({"sub": "1", "exp": 9999999999}, "y" * 40, algorithm="HS256")
    for token in (expired, forged, "garbage"):
        c = TestClient(app, headers=HEADERS)
        c.cookies.set("tutor_session", token)
        assert c.get("/api/me").status_code == 401


def test_token_for_deleted_user_rejected(app, client):
    register(client, "alice")
    with psycopg2.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute("DELETE FROM tutor.users")
    assert client.get("/api/me").status_code == 401


def test_csrf_header_and_origin(app):
    bare = TestClient(app)                                           # no X-Requested-With
    r = bare.post("/api/auth/register", json=signup_body("eve"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "forbidden"
    evil = TestClient(app, headers={**HEADERS, "Origin": "http://evil.example"})
    assert evil.post("/api/auth/register", json=signup_body("eve")).status_code == 403
    ok = TestClient(app, headers={**HEADERS, "Origin": "http://localhost:8080"})
    assert ok.post("/api/auth/register", json=signup_body("eve")).status_code == 201
    assert bare.get("/api/health/live").status_code == 200           # GET needs no header


def test_languages_list_is_public(client):
    r = client.get("/api/languages")
    assert r.status_code == 200 and {l["code"] for l in r.json()} >= {"en", "es", "ja"}


def test_meta_is_public_and_carries_the_policy_version(app, client):
    from app.policy import POLICY_VERSION
    r = client.get("/api/meta")
    assert r.status_code == 200 and r.json() == {"policy_version": POLICY_VERSION, "privacy_contact": None}
    app.state.settings.privacy_contact = "privacy@school.example"
    try:
        assert client.get("/api/meta").json()["privacy_contact"] == "privacy@school.example"
    finally:
        app.state.settings.privacy_contact = None


def test_profile_and_languages(client):
    register(client, "alice")
    assert client.patch("/api/me", json={"display_name": "Alice A", "native_language": "fr"}).json()["display_name"] == "Alice A"
    assert client.patch("/api/me", json={"native_language": "zz"}).status_code == 422
    assert client.patch("/api/me", json={"display_name": "  "}).status_code == 422
    assert client.post("/api/me/languages", json={"language": "de"}).json()["languages"] == ["en", "de"]
    assert client.post("/api/me/languages", json={"language": "de"}).json()["languages"] == ["en", "de"]   # idempotent
    langs = {l["code"]: l for l in client.get("/api/languages").json()}
    assert langs["en"]["stories_enabled"] and langs["es"]["stories_enabled"] and langs["ja"]["stories_enabled"]
    assert not langs["de"]["stories_enabled"] and not langs["ko"]["stories_enabled"]


def test_health(client):
    assert client.get("/api/health/live").json() == {"status": "ok"}
    assert client.get("/api/health").status_code == 401              # full health needs login
    register(client, "alice")
    assert client.get("/api/health").json()["postgres"]["ok"] is True


def test_unknown_route_uses_error_body(client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"
