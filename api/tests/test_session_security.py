"""Beyond per-user query filters: sessions, caching, shared-browser and multi-tab behaviour."""
import psycopg2
import pytest
from fastapi.testclient import TestClient

from conftest import DB_URL, HEADERS, login_body, register

TOKEN = "tutor_session"


def clone_with_cookie(app, token):
    c = TestClient(app, headers=HEADERS)
    c.cookies.set(TOKEN, token)
    return c


def test_logout_revokes_the_session_on_the_server(app, client):
    register(client, "alice")
    stolen = client.cookies.get(TOKEN)                     # someone copied the cookie before logout
    assert clone_with_cookie(app, stolen).get("/api/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 204
    r = clone_with_cookie(app, stolen).get("/api/me")      # replaying the old token must fail
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"


def test_logging_in_over_another_session_revokes_the_old_one(app, client):
    register(client, "alice")
    register_other = TestClient(app, headers=HEADERS)
    register(register_other, "bob")
    alice_token = client.cookies.get(TOKEN)
    # the same browser (same cookie jar) now logs in as bob
    assert client.post("/api/auth/login", json=login_body("bob", "password123")).status_code == 200
    assert client.get("/api/me").json()["email"] == "bob@example.com"
    assert clone_with_cookie(app, alice_token).get("/api/me").status_code == 401     # alice's session is gone


def test_every_login_gets_a_new_session_id(app):
    a = TestClient(app, headers=HEADERS)
    register(a, "alice")
    first = a.cookies.get(TOKEN)
    b = TestClient(app, headers=HEADERS)
    b.post("/api/auth/login", json=login_body("alice", "password123"))
    assert b.cookies.get(TOKEN) != first
    assert a.get("/api/me").status_code == 200 and b.get("/api/me").status_code == 200   # separate devices both work


def test_logout_all_ends_every_device(app, client):
    register(client, "alice")
    phone = TestClient(app, headers=HEADERS)
    phone.post("/api/auth/login", json=login_body("alice", "password123"))
    assert phone.get("/api/me").status_code == 200
    assert client.post("/api/auth/logout-all").status_code == 204
    assert phone.get("/api/me").status_code == 401 and client.get("/api/me").status_code == 401


def test_logout_all_only_affects_the_caller(app, make_user):
    a, b = make_user("alice"), make_user("bob")
    a.post("/api/auth/logout-all")
    assert b.get("/api/me").status_code == 200


def test_logout_all_requires_login(client):
    assert client.post("/api/auth/logout-all").status_code == 401


def test_expired_session_row_is_rejected(app, client):
    register(client, "alice")
    with psycopg2.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute("UPDATE tutor.sessions SET expires_at = now() - interval '1 minute'")
    assert client.get("/api/me").status_code == 401


def test_token_for_a_user_id_not_matching_its_session_is_rejected(app, make_user):
    """A valid signature isn't enough: the session must belong to the user named in the token."""
    import jwt
    a, b = make_user("alice"), make_user("bob")
    session_of_bob = jwt.decode(b.cookies.get(TOKEN), options={"verify_signature": False})["jti"]
    forged = jwt.encode({"sub": "1", "jti": session_of_bob, "exp": 9999999999}, app.state.settings.jwt_secret, algorithm="HS256")
    assert clone_with_cookie(app, forged).get("/api/me").status_code == 401


def test_token_without_a_session_id_is_rejected(app, client):
    import jwt
    register(client, "alice")
    legacy = jwt.encode({"sub": "1", "exp": 9999999999}, app.state.settings.jwt_secret, algorithm="HS256")
    assert clone_with_cookie(app, legacy).get("/api/me").status_code == 401


def test_deleting_a_user_kills_their_sessions(app, client):
    register(client, "alice")
    with psycopg2.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute("DELETE FROM tutor.users")
        cur.execute("SELECT count(*) FROM tutor.sessions")
        assert cur.fetchone()[0] == 0
    assert client.get("/api/me").status_code == 401


def test_other_tab_logged_in_as_someone_else_is_refused_not_misrouted(app, make_user):
    """Tab 1 shows alice. Another tab logs in as bob, replacing the shared cookie. Tab 1 must not be able to
    write into bob's account while still displaying alice's page."""
    alice = make_user("alice")
    alice_id = alice.get("/api/me").json()["id"]
    bob = TestClient(app, headers=HEADERS)
    bob.cookies.update(alice.cookies)                                # same browser, same cookie jar
    bob.post("/api/auth/login", json=login_body("bob", "x"))   # fails: bob doesn't exist yet
    register(bob, "bob")                                             # now the shared cookie belongs to bob

    tab1 = {"X-Expected-User": str(alice_id)}                        # what alice's page sends
    r = bob.post("/api/words", json={"language": "en", "word": "leak"}, headers=tab1)
    assert r.status_code == 401 and r.json()["error"]["code"] == "session_changed"
    assert bob.get("/api/words", params={"language": "en"}, headers=tab1).status_code == 401
    assert bob.get("/api/words", params={"language": "en"}).json()["total"] == 0          # nothing leaked into bob's list
    bob_id = bob.get("/api/me").json()["id"]
    assert bob.get("/api/words", params={"language": "en"}, headers={"X-Expected-User": str(bob_id)}).status_code == 200


def test_responses_are_never_cacheable(client):
    register(client, "alice")
    for resp in (client.get("/api/me"), client.get("/api/words", params={"language": "en"}),
                 client.get("/api/languages"), client.get("/api/health/live"),
                 client.get("/api/nope"),                                          # an error response
                 TestClient(client.app).post("/api/auth/login", json={})):         # blocked by the CSRF guard
        assert resp.headers["cache-control"] == "no-store", resp.request.url
        assert "cookie" in resp.headers["vary"].lower()
        assert resp.headers["x-content-type-options"] == "nosniff"
        assert resp.headers["x-frame-options"] == "DENY"


PUBLIC = {("GET", "/api/meta"), ("POST", "/api/auth/register"), ("POST", "/api/auth/login"), ("POST", "/api/auth/logout"),
          ("GET", "/api/health/live"), ("GET", "/api/languages")}


def _routes(app):
    """Every (METHOD, path) the app serves, read from the OpenAPI schema (app.routes nests included routers)."""
    app.openapi_schema = None
    for path, ops in app.openapi()["paths"].items():
        for method in ops:
            if method.upper() in {"GET", "POST", "PUT", "PATCH", "DELETE"}:
                yield method.upper(), path


def test_every_route_requires_login_unless_explicitly_public(app):
    """Adds itself to every new endpoint: forgetting the login dependency on a route fails this test."""
    anon = TestClient(app, headers=HEADERS)
    checked = 0
    for method, path in _routes(app):
        if (method, path) in PUBLIC:
            continue
        url = path.replace("{word_id}", "1").replace("{story_id}", "1").replace("{id}", "1")
        assert "{" not in url, f"unhandled path parameter in {path}: extend this test"
        r = anon.request(method, url)
        assert r.status_code == 401, f"{method} {path} answered {r.status_code} without a login"
        checked += 1
    assert checked >= 10


def test_public_routes_are_only_the_ones_we_listed(app):
    assert {(m, p) for m, p in _routes(app)} >= PUBLIC          # the allowlist can't silently go stale


@pytest.mark.parametrize("path", ["/api/me", "/api/words?language=en", "/api/health"])
def test_logged_out_clients_get_nothing(client, path):
    r = client.get(path)
    assert r.status_code == 401 and "alice" not in r.text
