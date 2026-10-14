"""Deleting an account also deletes the learner's chat history held by Langflow (design 19.4 item 5).

Three layers: the client's `delete_sessions` over a fake transport, the route that records which Langflow
sessions a learner has, and account deletion itself. A final test wires the real client to a fake Langflow
that really stores and forgets messages, so "the chat is gone" is checked end to end, not assumed.
"""
import re
from urllib.parse import parse_qs, unquote, urlparse

import psycopg2
import pytest

from app.errors import AppError
from app.services import chat_sessions
from app.services.ai_gate import AiGate
from app.services.chat_stub import StubChat
from app.services.langflow_client import ChatResult, LangflowClient, TransportError
from conftest import DB_URL, register

PART = "a" * 32
OTHER = "b" * 32


def db(sql, *args):
    with psycopg2.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute(sql, args)
        return cur.fetchall() if cur.description else None


def sid(user_id, part=PART):
    return f"u{user_id}-{part}"


# --- the client --------------------------------------------------------------------------------------

class Script:
    """A fake transport: answers by (method, kind of url) from a table of values or exceptions."""

    def __init__(self, delete=None, listing=None):
        self.calls = []
        self.delete = delete if delete is not None else {}
        self.listing = listing if listing is not None else {}

    def __call__(self, method, url, payload, headers, timeout):
        self.calls.append((method, url, headers, timeout))
        parsed = urlparse(url)
        if method == "DELETE":
            session = unquote(parsed.path.rsplit("/", 1)[1])
            outcome = self.delete.get(session, {"deleted": True})
        else:
            session = parse_qs(parsed.query)["session_id"][0]
            outcome = self.listing.get(session, [])
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


def client(transport):
    return LangflowClient("http://lf:7860/", "flow", "k3y", transport=transport, fallback_timeout=7)


def test_each_session_is_deleted_then_checked_empty():
    t = Script()
    client(t).delete_sessions(["u1-x", "u1-y"])
    assert [(m, urlparse(u).path.rsplit("/", 1)[1] if m == "DELETE" else parse_qs(urlparse(u).query)["session_id"][0])
            for m, u, _, _ in t.calls] == [("DELETE", "u1-x"), ("GET", "u1-x"), ("DELETE", "u1-y"), ("GET", "u1-y")]
    assert all(h == {"x-api-key": "k3y"} and to == 7 for _, _, h, to in t.calls)
    assert t.calls[0][1] == "http://lf:7860/api/v1/monitor/messages/session/u1-x"


def test_the_session_id_is_quoted_into_the_url():
    t = Script()
    client(t).delete_sessions(["u1-a/b c"])
    assert t.calls[0][1].endswith("/session/u1-a%2Fb%20c")


def test_nothing_to_delete_makes_no_call():
    t = Script()
    client(t).delete_sessions([])
    assert t.calls == []


def test_a_session_that_still_has_messages_is_a_failure():
    t = Script(listing={"u1-x": [{"id": "m1"}]})
    with pytest.raises(AppError) as err:
        client(t).delete_sessions(["u1-x"])
    assert err.value.code == "chat_cleanup_failed" and err.value.status == 503 and err.value.retry_after


@pytest.mark.parametrize("answer", [{"detail": "x"}, "nope", None])
def test_a_check_that_does_not_return_a_list_is_a_failure(answer):
    t = Script(listing={"u1-x": answer})
    with pytest.raises(AppError) as err:
        client(t).delete_sessions(["u1-x"])
    assert err.value.code == "chat_cleanup_failed"


def test_a_check_that_cannot_be_made_is_a_failure():
    t = Script(listing={"u1-x": TransportError("unreachable")})
    with pytest.raises(AppError):
        client(t).delete_sessions(["u1-x"])


def test_langflow_unreachable_blocks_and_the_message_never_names_it():
    t = Script(delete={"u1-x": TransportError("unreachable", None, "refused")})
    with pytest.raises(AppError) as err:
        client(t).delete_sessions(["u1-x"])
    assert err.value.code == "chat_cleanup_failed" and err.value.status == 503
    assert "langflow" not in err.value.message.lower() and "groq" not in err.value.message.lower()
    assert "account has not been deleted" in err.value.message


def test_a_404_with_nothing_stored_counts_as_already_gone():
    t = Script(delete={"u1-x": TransportError("http", 404, "no messages")}, listing={"u1-x": []})
    client(t).delete_sessions(["u1-x"])


def test_a_404_with_messages_still_stored_is_a_failure():
    t = Script(delete={"u1-x": TransportError("http", 404, "")}, listing={"u1-x": [{"id": "m"}]})
    with pytest.raises(AppError):
        client(t).delete_sessions(["u1-x"])


def test_a_non_json_success_body_is_settled_by_the_check():
    t = Script(delete={"u1-x": TransportError("badjson", 200, "OK")})
    client(t).delete_sessions(["u1-x"])


def test_an_auth_error_is_a_failure_even_if_the_check_would_pass():
    t = Script(delete={"u1-x": TransportError("http", 403, "")})
    with pytest.raises(AppError):
        client(t).delete_sessions(["u1-x"])


def test_every_session_is_tried_before_the_error_is_raised():
    t = Script(delete={"u1-x": TransportError("timeout")})
    with pytest.raises(AppError):
        client(t).delete_sessions(["u1-x", "u1-y", "u1-z"])
    deleted = [urlparse(u).path.rsplit("/", 1)[1] for m, u, _, _ in t.calls if m == "DELETE"]
    assert deleted == ["u1-x", "u1-y", "u1-z"]


def test_clients_that_hold_no_chat_refuse_when_there_is_something_to_delete():
    for tutor in (StubChat(lambda: None),):
        tutor.delete_sessions([])
        with pytest.raises(AppError) as err:
            tutor.delete_sessions(["u1-x"])
        assert err.value.code == "chat_cleanup_failed"
    assert StubChat(lambda: None).stores_chat is False and client(Script()).stores_chat is True


# --- recording which sessions a learner has -----------------------------------------------------------

class Recorder:
    stores_chat = True

    def __init__(self, error=None):
        self.calls, self.error, self.deleted = [], error, []

    def run(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return ChatResult("ok")

    def delete_sessions(self, ids):
        self.deleted.append(list(ids))


@pytest.fixture
def tutor(app):
    saved = app.state.chat, app.state.ai_gate
    app.state.chat, app.state.ai_gate = Recorder(), AiGate(slots=2, wait_seconds=0.2)
    yield app.state.chat
    app.state.chat, app.state.ai_gate = saved


def say(c, part=PART):
    return c.post("/api/chat", json={"message": "hi", "language": "es", "session_id": part})


def test_a_chat_turn_records_the_full_session_id(client, tutor):
    register(client, "alice")
    assert say(client).status_code == 200
    uid = db("SELECT id FROM tutor.users")[0][0]
    assert db("SELECT user_id, session_id FROM tutor.chat_sessions") == [(uid, sid(uid))]


def test_recording_is_idempotent_and_keeps_each_session(client, tutor):
    register(client, "alice")
    say(client), say(client), say(client, OTHER)
    uid = db("SELECT id FROM tutor.users")[0][0]
    assert sorted(r[0] for r in db("SELECT session_id FROM tutor.chat_sessions")) == sorted([sid(uid), sid(uid, OTHER)])


def test_each_learner_has_their_own_sessions(make_user, tutor):
    a, b = make_user("alice"), make_user("bob")
    say(a), say(b)
    rows = db("SELECT user_id, session_id FROM tutor.chat_sessions ORDER BY user_id")
    assert [r[0] for r in rows] == [1, 2] and [r[1] for r in rows] == [sid(1), sid(2)]


def test_a_session_is_recorded_even_when_the_run_fails(client, tutor):
    register(client, "alice")
    tutor.error = AppError("ai_failed", "no", 502)
    assert say(client).status_code == 502
    assert len(db("SELECT 1 FROM tutor.chat_sessions")) == 1       # Langflow may have stored the question already


def test_nothing_is_recorded_for_a_tutor_that_stores_no_chat(app, client):
    saved = app.state.chat, app.state.ai_gate
    app.state.chat, app.state.ai_gate = StubChat(lambda: app.state.pool), AiGate(slots=2, wait_seconds=0.2)
    try:
        register(client, "alice")
        assert say(client).status_code == 200
        assert db("SELECT 1 FROM tutor.chat_sessions") == []
    finally:
        app.state.chat, app.state.ai_gate = saved


def test_nothing_is_recorded_when_the_gate_refuses(client, tutor, app):
    register(client, "alice")
    uid = db("SELECT id FROM tutor.users")[0][0]
    with app.state.ai_gate.slot(uid):
        assert say(client).status_code == 429
    assert db("SELECT 1 FROM tutor.chat_sessions") == [] and tutor.calls == []


def test_the_list_helper_returns_only_that_learners_ids(conn, make_learner):
    a, b = make_learner("a"), make_learner("b")
    chat_sessions.record(conn, a, "u1-x"), chat_sessions.record(conn, a, "u1-x"), chat_sessions.record(conn, b, "u2-y")
    conn.commit()
    assert chat_sessions.list_ids(conn, a) == ["u1-x"] and chat_sessions.list_ids(conn, b) == ["u2-y"]


# --- account deletion --------------------------------------------------------------------------------

def test_deleting_the_account_deletes_exactly_that_learners_sessions_first(make_user, tutor, app):
    a, b = make_user("alice"), make_user("bob")
    say(a), say(a, OTHER), say(b)
    seen = {}
    tutor.delete_sessions = lambda ids: seen.update(ids=sorted(ids),
                                                    user_still_there=db("SELECT count(*) FROM tutor.users WHERE id = 1")[0][0])
    assert a.post("/api/me/delete", json={"password": "password123"}).status_code == 204
    assert seen == {"ids": sorted([sid(1), sid(1, OTHER)]), "user_still_there": 1}
    assert db("SELECT user_id FROM tutor.chat_sessions") == [(2,)]


def test_a_failed_cleanup_keeps_the_account_and_the_login(client, tutor):
    register(client, "alice")
    say(client)

    def boom(ids):
        raise AppError("chat_cleanup_failed", "We couldn't remove your chat history just now, so your account has not been deleted.", 503, retry_after=15)
    tutor.delete_sessions = boom
    r = client.post("/api/me/delete", json={"password": "password123"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "chat_cleanup_failed" and r.headers["retry-after"]
    assert client.get("/api/me").status_code == 200
    assert db("SELECT count(*) FROM tutor.users")[0][0] == 1 and db("SELECT count(*) FROM tutor.chat_sessions")[0][0] == 1


def test_a_wrong_password_does_no_cleanup(client, tutor):
    register(client, "alice")
    say(client)
    assert client.post("/api/me/delete", json={"password": "wrong-password"}).status_code == 403
    assert tutor.deleted == []


def test_a_learner_who_never_chatted_is_deleted_without_calling_langflow(client, tutor):
    register(client, "alice")
    assert client.post("/api/me/delete", json={"password": "password123"}).status_code == 204
    assert tutor.deleted == []


def test_deletion_is_refused_while_a_chat_request_is_in_flight(client, tutor, app):
    register(client, "alice")
    uid = db("SELECT id FROM tutor.users")[0][0]
    say(client)
    with app.state.ai_gate.slot(uid):
        r = client.post("/api/me/delete", json={"password": "password123"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "tutor_busy"
    assert db("SELECT count(*) FROM tutor.users")[0][0] == 1 and tutor.deleted == []


def test_a_stub_deployment_deletes_normally(app, client):
    saved = app.state.chat, app.state.ai_gate
    app.state.chat, app.state.ai_gate = StubChat(lambda: app.state.pool), AiGate()
    try:
        register(client, "alice")
        say(client)
        assert client.post("/api/me/delete", json={"password": "password123"}).status_code == 204
    finally:
        app.state.chat, app.state.ai_gate = saved


def test_the_export_lists_chat_sessions_but_never_their_content(client, tutor):
    register(client, "alice")
    say(client)
    data = client.get("/api/me/export").json()
    assert len(data["chat_sessions"]) == 1 and set(data["chat_sessions"][0]) == {"session_id", "created_at"}


# --- end to end against a fake Langflow that really stores and forgets ------------------------------------

class FakeLangflow:
    def __init__(self):
        self.messages = {}                      # session id -> list of messages

    def __call__(self, method, url, payload, headers, timeout):
        parsed = urlparse(url)
        if method == "POST":
            session = payload["session_id"]
            self.messages.setdefault(session, []).extend([{"sender": "User", "text": payload["input_value"]},
                                                          {"sender": "Machine", "text": "hola"}])
            return {"outputs": [{"outputs": [{"results": {"message": {"text": "hola"}}}]}]}
        if method == "GET":
            return list(self.messages.get(parse_qs(parsed.query)["session_id"][0], []))
        session = unquote(parsed.path.rsplit("/", 1)[1])
        if not self.messages.pop(session, None):
            raise TransportError("http", 404, "no messages")
        return {"message": "Messages deleted successfully"}


def test_account_deletion_empties_only_that_learners_langflow_chat(app, make_user):
    saved = app.state.chat, app.state.ai_gate
    fake = FakeLangflow()
    app.state.chat, app.state.ai_gate = LangflowClient("http://lf", "flow", "k", transport=fake), AiGate()
    try:
        a, b = make_user("alice"), make_user("bob")
        say(a), say(a, OTHER), say(b)
        assert len(fake.messages) == 3
        assert a.post("/api/me/delete", json={"password": "password123"}).status_code == 204
        assert list(fake.messages) == [sid(2)]                    # bob's chat is untouched
        assert db("SELECT count(*) FROM tutor.chat_sessions")[0][0] == 1
    finally:
        app.state.chat, app.state.ai_gate = saved
