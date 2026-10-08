"""Profile, email and password changes, data export, and permanent deletion."""
import psycopg2
from fastapi.testclient import TestClient

from conftest import DB_URL, HEADERS, login_body, register


def db(sql, *args):
    with psycopg2.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall() if cur.description else None


def tables_with_user_id():
    return [r[0] for r in db("SELECT table_name FROM information_schema.columns "
                             "WHERE table_schema = 'tutor' AND column_name = 'user_id' ORDER BY 1")]


# ------------------------------------------------------------------ email
def test_change_email_needs_the_password(client):
    register(client, "alice")
    r = client.post("/api/me/email", json={"email": "new@example.com", "password": "wrong-password"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "wrong_password"
    assert client.get("/api/me").json()["email"] == "alice@example.com"


def test_change_email_success_and_old_address_stops_working(client):
    register(client, "alice")
    r = client.post("/api/me/email", json={"email": " New@Example.com ", "password": "password123"})
    assert r.status_code == 200 and r.json()["email"] == "new@example.com"
    other = TestClient(client.app, headers=HEADERS)
    assert other.post("/api/auth/login", json=login_body("alice")).status_code == 401
    assert other.post("/api/auth/login", json={"email": "new@example.com", "password": "password123"}).status_code == 200


def test_change_email_rejects_taken_and_malformed(client, make_user):
    make_user("bob")
    register(client, "alice")
    assert client.post("/api/me/email", json={"email": "BOB@example.com", "password": "password123"}).status_code == 409
    assert client.post("/api/me/email", json={"email": "not-an-email", "password": "password123"}).status_code == 422
    assert client.get("/api/me").json()["email"] == "alice@example.com"


def test_wrong_passwords_on_sensitive_actions_share_the_login_lockout(client):
    register(client, "alice")
    for _ in range(5):
        assert client.post("/api/me/email", json={"email": "x@example.com", "password": "nope-nope"}).status_code == 403
    assert client.post("/api/me/email", json={"email": "x@example.com", "password": "password123"}).status_code == 429
    assert TestClient(client.app, headers=HEADERS).post("/api/auth/login", json=login_body("alice")).status_code == 429


# --------------------------------------------------------------- password
def test_change_password_ends_other_sessions_but_keeps_this_one(app, client):
    register(client, "alice")
    phone = TestClient(app, headers=HEADERS)
    phone.post("/api/auth/login", json=login_body("alice"))
    assert phone.get("/api/me").status_code == 200

    r = client.post("/api/me/password", json={"current_password": "password123", "new_password": "a-new-password"})
    assert r.status_code == 204
    assert client.get("/api/me").status_code == 200                 # this browser stays logged in
    assert phone.get("/api/me").status_code == 401                  # the other device is logged out
    fresh = TestClient(app, headers=HEADERS)
    assert fresh.post("/api/auth/login", json=login_body("alice", "password123")).status_code == 401
    assert fresh.post("/api/auth/login", json=login_body("alice", "a-new-password")).status_code == 200


def test_change_password_rules(client):
    register(client, "alice")
    bad = client.post("/api/me/password", json={"current_password": "wrong-password", "new_password": "a-new-password"})
    assert bad.status_code == 403 and bad.json()["error"]["code"] == "wrong_password"
    assert client.post("/api/me/password", json={"current_password": "password123", "new_password": "short"}).status_code == 422
    assert client.post("/api/me/password", json={"current_password": "password123", "new_password": "x" * 73}).status_code == 422
    assert TestClient(client.app, headers=HEADERS).post("/api/auth/login", json=login_body("alice")).status_code == 200  # unchanged


# ----------------------------------------------------------------- export
def test_export_contains_my_data_and_no_secrets(client, make_user):
    bob = make_user("bob")
    bob.post("/api/words", json={"language": "en", "word": "bobsecret"})
    register(client, "alice", display_name="Alice A")
    client.post("/api/words", json={"language": "es", "word": "agua", "meaning": "water"})
    r = client.get("/api/me/export")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"] and r.headers["cache-control"] == "no-store"
    data = r.json()
    assert data["profile"]["email"] == "alice@example.com" and data["profile"]["display_name"] == "Alice A"
    assert data["profile"]["privacy_version"] and data["profile"]["privacy_accepted_at"]
    assert [(w["language"], w["word"], w["meaning"]) for w in data["words"]] == [("es", "agua", "water")]
    assert len(data["sessions"]) == 1 and set(data["sessions"][0]) == {"created_at", "expires_at"}
    text = r.text
    assert "bobsecret" not in text and "bob@example.com" not in text           # only my own data
    assert "password" not in text.lower() and "tutor_session" not in text      # no hash, no tokens


def test_export_requires_login(client):
    assert client.get("/api/me/export").status_code == 401


def test_export_covers_every_table_that_holds_user_data(client):
    """If a feature adds a table with a user_id column, this fails until the export includes it."""
    register(client, "alice")
    keys = set(client.get("/api/me/export").json())
    missing = [t for t in tables_with_user_id() if t not in keys]
    assert not missing, f"export is missing: {missing}"
    assert "profile" in keys                                                    # the users table itself


# --------------------------------------------------------------- deletion
def test_delete_account_needs_the_right_password(client):
    register(client, "alice")
    r = client.post("/api/me/delete", json={"password": "wrong-password"})
    assert r.status_code == 403 and r.json()["error"]["code"] == "wrong_password"
    assert client.get("/api/me").status_code == 200
    assert db("SELECT count(*) FROM tutor.users")[0][0] == 1


def test_delete_account_removes_everything_and_ends_all_sessions(app, client):
    register(client, "alice")
    client.post("/api/words", json={"language": "en", "word": "bread"})
    client.post("/api/me/languages", json={"language": "fr"})
    phone = TestClient(app, headers=HEADERS)
    phone.post("/api/auth/login", json=login_body("alice"))

    r = client.post("/api/me/delete", json={"password": "password123"})
    assert r.status_code == 204
    assert 'tutor_session=""' in r.headers["set-cookie"] or "max-age=0" in r.headers["set-cookie"].lower()
    assert client.get("/api/me").status_code == 401 and phone.get("/api/me").status_code == 401
    for table in ["users"] + tables_with_user_id():
        assert db(f"SELECT count(*) FROM tutor.{table}")[0][0] == 0, f"rows left in {table}"


def test_deletion_leaves_other_people_untouched(client, make_user):
    bob = make_user("bob")
    bob.post("/api/words", json={"language": "en", "word": "keepme"})
    register(client, "alice")
    client.post("/api/words", json={"language": "en", "word": "bread"})
    client.post("/api/me/delete", json={"password": "password123"})
    assert bob.get("/api/me").status_code == 200
    assert [w["word"] for w in bob.get("/api/words", params={"language": "en"}).json()["items"]] == ["keepme"]


def test_email_can_be_used_again_after_deletion_with_a_clean_slate(client):
    register(client, "alice")
    client.post("/api/words", json={"language": "en", "word": "old"})
    client.post("/api/me/delete", json={"password": "password123"})
    fresh = TestClient(client.app, headers=HEADERS)
    register(fresh, "alice")
    assert fresh.get("/api/words", params={"language": "en"}).json()["total"] == 0


def test_every_reference_to_users_deletes_with_the_user(client):
    """A table that points at users without ON DELETE CASCADE would survive account deletion."""
    rows = db("""SELECT conrelid::regclass::text, confdeltype FROM pg_constraint
                 WHERE contype = 'f' AND confrelid = 'tutor.users'::regclass""")
    assert rows, "expected foreign keys to users"
    assert all(kind == "c" for _, kind in rows), f"not cascading: {[t for t, k in rows if k != 'c']}"
    assert {t.split(".")[-1] for t, _ in rows} >= set(tables_with_user_id())


def test_delete_requires_login(client):
    assert client.post("/api/me/delete", json={"password": "x"}).status_code == 401
