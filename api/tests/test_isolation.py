"""User A must never read or change user B's data, and must not be able to tell it exists."""
from conftest import register


def test_words_are_private(make_user):
    a, b = make_user("alice"), make_user("bob")
    wid = a.post("/api/words", json={"language": "en", "word": "secret", "meaning": "mine"}).json()["id"]

    assert b.get("/api/words", params={"language": "en"}).json()["total"] == 0
    assert b.get("/api/words", params={"language": "en", "q": "secret"}).json()["items"] == []
    assert b.patch(f"/api/words/{wid}", json={"meaning": "hacked"}).status_code == 404       # 404, never 403
    assert b.post("/api/words/delete", json={"ids": [wid]}).json() == {"deleted": 0}

    mine = a.get("/api/words", params={"language": "en"}).json()["items"]
    assert [(w["word"], w["meaning"]) for w in mine] == [("secret", "mine")]


def test_same_word_allowed_for_different_users(make_user):
    a, b = make_user("alice"), make_user("bob")
    assert a.post("/api/words", json={"language": "en", "word": "bread"}).status_code == 201
    assert b.post("/api/words", json={"language": "en", "word": "bread"}).status_code == 201


def test_csv_upload_is_private(make_user):
    import io
    a, b = make_user("alice"), make_user("bob")
    a.post("/api/words/upload", data={"language": "en"}, files={"file": ("w.csv", io.BytesIO(b"word\nbread\n"), "text/csv")})
    assert b.get("/api/words", params={"language": "en"}).json()["total"] == 0
    assert b.get("/api/me").json()["email"] == "bob@example.com"


def test_languages_are_private(make_user):
    a, b = make_user("alice"), make_user("bob")
    a.post("/api/me/languages", json={"language": "ja"})
    assert "ja" not in b.get("/api/me").json()["languages"]


def test_unauthenticated_access_blocked(client):
    for method, path, kw in [("get", "/api/words?language=en", {}), ("post", "/api/words", {"json": {"language": "en", "word": "x"}}),
                             ("post", "/api/words/delete", {"json": {"ids": [1]}}), ("get", "/api/me", {})]:
        r = getattr(client, method)(path, **kw)
        assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized", path


def test_deleting_a_user_cascades(make_user, app):
    import psycopg2
    from conftest import DB_URL
    a = make_user("alice")
    a.post("/api/words", json={"language": "en", "word": "bread"})
    with psycopg2.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute("DELETE FROM tutor.users")
        cur.execute("SELECT (SELECT count(*) FROM tutor.words), (SELECT count(*) FROM tutor.user_languages)")
        assert cur.fetchone() == (0, 0)
