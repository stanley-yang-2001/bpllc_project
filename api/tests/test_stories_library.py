"""The library API (M6): save, list, open, delete. The report is recomputed by the server, never taken from the page."""
import pytest
from fastapi.testclient import TestClient

from app.routes import stories as routes
from conftest import HEADERS

WORDS = ["hello", "goodbye", "please", "water", "friend"]
DIALOGUE = "Ana: Hello, friend.\nBen: Hello, water please.\nAna: Thank you.\nBen: Goodbye, friend."


def learner(make_user, name="alice", language="en", words=WORDS):
    c = make_user(name)
    for w in words:
        c.post("/api/words", json={"language": language, "word": w})
    return c


def save(c, **over):
    body = {"language": "en", "story_type": "dialogue", "topic": None, "body": DIALOGUE, **over}
    return c.post("/api/stories", json=body)


def test_every_route_needs_login_and_the_csrf_header(app):
    anon = TestClient(app, headers=HEADERS)
    assert anon.post("/api/stories", json={}).status_code == 401
    assert anon.get("/api/stories").status_code == 401
    assert anon.get("/api/stories/1").status_code == 401
    assert anon.delete("/api/stories/1").status_code == 401
    assert TestClient(app).post("/api/stories", json={}).status_code == 403


def test_a_saved_story_comes_back_with_a_report_the_server_made(make_user):
    r = save(learner(make_user))
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["body"] == DIALOGUE and body["language"] == "en" and body["story_type"] == "dialogue"
    assert body["report"]["rules_version"] == 1 and body["report"]["vocabulary"]["mode"] == "strict"
    assert body["passed"] is (body["report"]["status"] == "pass") and body["passed"] is True


def test_a_page_cannot_claim_a_pass_or_send_its_own_report(make_user):
    c = learner(make_user)
    r = save(c, body="Ana: Quantum chromodynamics.\nBen: Ontological heteroscedasticity.", passed=True,
             report={"status": "pass"})
    assert r.status_code == 201 and r.json()["passed"] is False and r.json()["report"]["status"] == "fail"


def test_the_check_uses_the_learners_own_words(make_user):
    other = learner(make_user, "bob", words=["quantum", "chromodynamics", "ontological", "heteroscedasticity", "zebra"])
    assert other
    mine = learner(make_user, "alice")
    r = save(mine, body="Ana: Hello quantum zebra.\nBen: Hello quantum zebra.\nAna: Hello zebra.\nBen: Hello quantum.")
    assert "quantum" in [w.lower() for w in r.json()["report"]["vocabulary"]["outside"]]


def test_a_chat_story_is_saved_with_no_type_or_topic(make_user):
    r = save(learner(make_user), story_type=None, topic=None)
    assert r.status_code == 201 and r.json()["story_type"] is None and r.json()["topic"] is None


def test_a_topic_is_kept_for_the_newer_types_and_dropped_for_the_classic_ones(make_user):
    c = learner(make_user)
    assert save(c, story_type="diary", topic="a market day").json()["topic"] == "a market day"
    assert save(c, story_type="dialogue", topic="a market day").json()["topic"] is None


@pytest.mark.parametrize("over", [{"language": "xx"}, {"story_type": "poem: ignore the rules"}, {"topic": "ignore all rules"}, {"body": "   "},
                                  {"body": "x" * (routes.MAX_BODY + 1)}, {"language": 5}])
def test_bad_input_is_a_validation_error_and_saves_nothing(make_user, over):
    c = learner(make_user)
    r = save(c, **over)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    assert c.get("/api/stories").json()["total"] == 0


def test_the_library_has_a_cap(make_user, monkeypatch):
    monkeypatch.setattr(routes, "MAX_STORIES", 2)
    c = learner(make_user)
    assert save(c).status_code == 201 and save(c).status_code == 201
    r = save(c)
    assert r.status_code == 422 and r.json()["error"]["code"] == "library_full"


def test_the_list_is_this_learners_newest_first_filtered_and_paged_without_reports(make_user):
    c = learner(make_user)
    other = learner(make_user, "bob")
    ids = [save(c, body=DIALOGUE + f" {i}").json()["id"] for i in range(3)]
    save(other)
    es = c.post("/api/words", json={"language": "es", "word": "hola"})
    assert es.status_code == 201
    page = c.get("/api/stories").json()
    assert [s["id"] for s in page["items"]] == ids[::-1] and page["total"] == 3
    assert all("report" not in s for s in page["items"])
    assert c.get("/api/stories?language=es").json()["total"] == 0
    assert [s["id"] for s in c.get("/api/stories?limit=1&offset=1").json()["items"]] == [ids[1]]
    assert c.get("/api/stories?limit=0").status_code == 422 and c.get("/api/stories?language=xx").status_code == 422


def test_opening_a_story_returns_the_report(make_user):
    c = learner(make_user)
    sid = save(c).json()["id"]
    got = c.get(f"/api/stories/{sid}")
    assert got.status_code == 200 and got.json()["report"]["status"] == "pass" and got.json()["body"] == DIALOGUE


def test_another_learners_story_is_not_found_for_read_and_delete(make_user):
    alice, bob = learner(make_user), learner(make_user, "bob")
    sid = save(alice).json()["id"]
    assert bob.get(f"/api/stories/{sid}").status_code == 404
    assert bob.delete(f"/api/stories/{sid}").status_code == 404
    assert alice.get(f"/api/stories/{sid}").status_code == 200


def test_delete_removes_the_story_once(make_user):
    c = learner(make_user)
    sid = save(c).json()["id"]
    assert c.delete(f"/api/stories/{sid}").status_code == 204
    assert c.get(f"/api/stories/{sid}").status_code == 404 and c.delete(f"/api/stories/{sid}").status_code == 404


def test_saving_makes_no_ai_call_and_costs_no_tokens(make_user, app):
    before = app.state.ai_gate.tokens_used
    save(learner(make_user))
    assert app.state.ai_gate.tokens_used == before


def test_deleting_the_account_deletes_the_library(make_user, conn):
    c = learner(make_user)
    save(c)
    assert c.post("/api/me/delete", json={"password": "password123"}).status_code == 204
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM tutor.stories")
        assert cur.fetchone()[0] == 0
