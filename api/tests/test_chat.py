"""POST /api/chat: the learner's door to the tutor.

The tutor behind it is swapped per test: the built-in stub (no Langflow needed), a recording fake, or the
real LangflowClient over a fake transport. What is under test here is everything the API owns: login,
validation, who the request is made as, the session id, the gate, error shapes and privacy.
"""
import json
import threading

import pytest
from fastapi.testclient import TestClient

from app.errors import AppError
from app.services.ai_gate import AiGate
from app.services.chat_stub import StubChat
from app.services.langflow_client import ChatResult, LangflowClient, ToolCall
from conftest import HEADERS, register

PART = "a" * 32


@pytest.fixture
def stub(app):
    saved = app.state.chat, app.state.ai_gate
    app.state.chat = StubChat(lambda: app.state.pool)
    app.state.ai_gate = AiGate(slots=2, wait_seconds=0.2)
    yield
    app.state.chat, app.state.ai_gate = saved


class Recorder:
    """A tutor that records exactly what the route asked of it."""

    def __init__(self, result=None, error=None):
        self.calls, self.result, self.error = [], result or ChatResult("ok"), error

    def run(self, **kwargs):
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return self.result


@pytest.fixture
def recorder(app):
    saved = app.state.chat, app.state.ai_gate
    app.state.chat, app.state.ai_gate = Recorder(), AiGate(slots=2, wait_seconds=0.2)
    yield app.state.chat
    app.state.chat, app.state.ai_gate = saved


def say(client, message, language="es", session=PART, **extra):
    return client.post("/api/chat", json={"message": message, "language": language, "session_id": session, **extra})


# --- access ------------------------------------------------------------------------------------------

def test_chat_requires_login(client, stub):
    r = say(client, "hi")
    assert r.status_code == 401 and r.json()["error"]["code"] == "unauthorized"


def test_chat_is_refused_without_the_csrf_header(app, stub):
    c = TestClient(app)                      # no X-Requested-With
    assert c.post("/api/chat", json={"message": "hi", "language": "es", "session_id": PART}).status_code == 403


def test_a_stale_tab_cannot_chat_as_someone_else(make_user, stub):
    a = make_user("alice")
    r = a.post("/api/chat", json={"message": "hi", "language": "es", "session_id": PART}, headers={"X-Expected-User": "999"})
    assert r.status_code == 401 and r.json()["error"]["code"] == "session_changed"


def test_live_mode_is_off_until_the_tools_are_per_user(make_user):
    """Default settings: live AI, LANGFLOW_PER_USER_TOOLS unset. The flow's tools would still use one shared word
    list, so chat must refuse rather than mix learners' vocabulary."""
    r = say(make_user("alice"), "add the word bread")
    assert r.status_code == 503 and r.json()["error"]["code"] == "langflow_unavailable"


# --- the stub tutor ----------------------------------------------------------------------------------

def test_stub_adds_a_word_to_the_callers_own_list(make_user, stub):
    a, b = make_user("alice"), make_user("bob")      # ids restart at 1 per test: bob is NOT user 1
    r = say(b, "Please add the word bread")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["reply"] == "Added 'bread' to your Spanish vocabulary."
    assert [(c["name"], c["args"], c["failed"]) for c in body["tool_calls"]] == [("Add Word", {"word": "bread"}, False)]
    assert body["session_id"] == PART
    assert [w["word"] for w in b.get("/api/words", params={"language": "es"}).json()["items"]] == ["bread"]
    assert a.get("/api/words", params={"language": "es"}).json()["total"] == 0          # never alice's list


def test_stub_reports_a_duplicate_word(make_user, stub):
    a = make_user("alice")
    say(a, "add the word bread")
    r = say(a, "add the word bread")
    assert r.status_code == 200 and r.json()["reply"] == "'bread' is already in your Spanish vocabulary."


def test_stub_story_in_a_supported_language(make_user, stub):
    r = say(make_user("alice"), "Tell me a story in French", language="es")
    body = r.json()
    assert r.status_code == 200 and body["tool_calls"][0]["name"] == "Story Generator Tool"
    assert body["tool_calls"][0]["args"] == {"language": "fr"} and body["reply"] == body["tool_calls"][0]["output"]


def test_stub_story_uses_the_active_language_when_none_is_named(make_user, stub):
    r = say(make_user("alice"), "tell me a story", language="ja")
    assert r.json()["tool_calls"][0]["args"] == {"language": "ja"}


def test_stub_story_in_a_language_that_is_not_enabled_is_declined_not_faked(make_user, stub, de_off):
    body = say(make_user("alice"), "tell me a story in German").json()
    assert "not available yet" in body["reply"] and body["tool_calls"][0]["failed"] is True


def test_stub_smalltalk_has_no_tool_calls(make_user, stub):
    body = say(make_user("alice"), "hello there").json()
    assert body["tool_calls"] == [] and "add the word" in body["reply"].lower()


def test_stub_rejects_a_bad_word_politely(make_user, stub):
    body = say(make_user("alice"), "add the word " + "x" * 200).json()
    assert body["reply"].startswith("Couldn't add word") and body["tool_calls"][0]["failed"] is True


# --- validation --------------------------------------------------------------------------------------

@pytest.mark.parametrize("body", [
    {"message": "", "language": "es", "session_id": PART},
    {"message": "   ", "language": "es", "session_id": PART},
    {"message": "x" * 2001, "language": "es", "session_id": PART},
    {"message": "hi", "language": "xx", "session_id": PART},
    {"message": "hi", "language": "es", "session_id": "u2-" + "a" * 29},
    {"message": "hi", "language": "es", "session_id": "short"},
    {"message": "hi", "language": "es"},
    {"language": "es", "session_id": PART},
    {"message": 5, "language": "es", "session_id": PART},
])
def test_bad_requests_are_validation_errors_and_never_reach_the_tutor(make_user, recorder, body):
    r = make_user("alice").post("/api/chat", json=body)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validation_error"
    assert recorder.calls == []


def test_the_message_is_trimmed_but_otherwise_passed_on_unchanged(make_user, recorder):
    say(make_user("alice"), "  Cómo estás?  ")
    assert recorder.calls[0]["message"] == "Cómo estás?"


# --- who the request is made as ----------------------------------------------------------------------

def test_the_tutor_is_called_as_the_logged_in_user_not_as_the_body_says(make_user, recorder):
    a = make_user("alice")
    uid = a.get("/api/me").json()["id"]
    say(a, "hi", user_id=999, language_override="xx")          # extra fields are ignored
    call = recorder.calls[0]
    assert call["user_id"] == uid and call["language"] == "es"


def test_the_session_id_is_built_on_the_server_from_the_user_id(make_user, recorder):
    a, b = make_user("alice"), make_user("bob")
    say(a, "hi")
    say(b, "hi")                                                # the same browser-supplied part
    ids = [c["session_id"] for c in recorder.calls]
    a_id, b_id = a.get("/api/me").json()["id"], b.get("/api/me").json()["id"]
    assert ids == [f"u{a_id}-{PART}", f"u{b_id}-{PART}"] and ids[0] != ids[1]


# --- errors ------------------------------------------------------------------------------------------

@pytest.mark.parametrize("error, status, code", [
    (AppError("tutor_busy", "The tutor is busy.", 429, retry_after=15), 429, "tutor_busy"),
    (AppError("langflow_unavailable", "Down.", 503), 503, "langflow_unavailable"),
    (AppError("ai_failed", "Failed.", 502), 502, "ai_failed"),
])
def test_tutor_errors_keep_their_status_and_code(make_user, app, error, status, code):
    saved = app.state.chat
    app.state.chat = Recorder(error=error)
    try:
        r = say(make_user("alice"), "hi")
    finally:
        app.state.chat = saved
    assert r.status_code == status and r.json()["error"]["code"] == code
    if error.retry_after:
        assert r.headers["Retry-After"] == "15" and r.json()["error"]["retry_after"] == 15


def test_an_unexpected_crash_in_the_tutor_is_a_clean_500(make_user, app):
    class Boom:
        def run(self, **kw):
            raise RuntimeError("secret internals")

    saved = app.state.chat
    app.state.chat = Boom()
    try:
        r = TestClient(app, headers=HEADERS, raise_server_exceptions=False)
        register(r, "carol")
        resp = say(r, "hi")
    finally:
        app.state.chat = saved
    assert resp.status_code == 500 and "secret internals" not in resp.text


# --- the gate ----------------------------------------------------------------------------------------

def test_a_second_request_from_the_same_learner_is_refused_while_the_first_runs(app, make_user):
    started, release = threading.Event(), threading.Event()

    class Slow:
        def run(self, **kw):
            started.set()
            release.wait(5)
            return ChatResult("done")

    saved = app.state.chat, app.state.ai_gate
    app.state.chat, app.state.ai_gate = Slow(), AiGate(slots=2, wait_seconds=0.2)
    try:
        a = make_user("alice")
        first = {}
        t = threading.Thread(target=lambda: first.update(r=say(a, "one")))
        t.start()
        assert started.wait(5)
        second = say(a, "two")
        assert second.status_code == 429 and second.json()["error"]["code"] == "tutor_busy"
        release.set()
        t.join(5)
        assert first["r"].status_code == 200
        assert say(a, "three").status_code == 200              # and the slot is free again afterwards
    finally:
        release.set()
        app.state.chat, app.state.ai_gate = saved


def test_a_full_gate_answers_busy_with_retry_after(app, make_user):
    saved = app.state.chat, app.state.ai_gate
    app.state.chat, app.state.ai_gate = Recorder(), AiGate(slots=1, wait_seconds=0.1, retry_after=9)
    try:
        with app.state.ai_gate.slot(12345):                    # somebody else holds the only slot
            r = say(make_user("alice"), "hi")
        assert r.status_code == 429 and r.headers["Retry-After"] == "9"
        assert app.state.chat.calls == []                      # refused before any AI work
    finally:
        app.state.chat, app.state.ai_gate = saved


def test_validation_errors_do_not_use_up_a_slot(make_user, app, recorder):
    a = make_user("alice")
    say(a, "", session=PART)
    assert app.state.ai_gate.in_flight == 0 and app.state.ai_gate.active_users == set()


# --- privacy, end to end -----------------------------------------------------------------------------

def test_nothing_personal_leaves_the_api_when_chatting_through_the_real_client(app, make_user):
    sent = []

    def transport(method, url, payload, headers, timeout):
        sent.append(json.dumps([method, url, payload]))
        return {"outputs": [{"outputs": [{"results": {"message": {"text": "Hola!"}}}]}]}

    saved = app.state.chat, app.state.ai_gate
    app.state.chat = LangflowClient("http://lf:7860", "language-tutor", "k", 30, ("Add Word", "Story Generator Tool"), transport)
    app.state.ai_gate = AiGate(slots=2, wait_seconds=0.2)
    try:
        c = TestClient(app, headers=HEADERS)
        register(c, "Zebulon", display_name="Zebulon Quux")
        uid = c.get("/api/me").json()["id"]
        r = say(c, "hello")
    finally:
        app.state.chat, app.state.ai_gate = saved
    assert r.status_code == 200 and r.json()["reply"] == "Hola!"
    blob = " ".join(sent).lower()
    assert "zebulon" not in blob and "quux" not in blob and "@example.com" not in blob and "password" not in blob
    assert f'"learner_id": "{uid}"' in blob and f"u{uid}-{PART}" in blob


# --- chat replies in the study language (Settings checkbox) ------------------------------------------------

def test_the_chat_asks_for_the_study_language_only_when_the_learner_chose_it(make_user, recorder):
    c = make_user("alice")
    c.post("/api/me/languages", json={"language": "es"})
    say(c, "hola", language="es")
    assert recorder.calls[-1]["reply_language"] is None
    assert c.patch("/api/me/preferences", json={"chat_in_study_language": True}).status_code == 200
    say(c, "hola", language="es")
    assert recorder.calls[-1]["reply_language"] == "Spanish"
    say(c, "hello", language="en")
    assert recorder.calls[-1]["reply_language"] == "English"
    c.patch("/api/me/preferences", json={"chat_in_study_language": False})
    say(c, "hola", language="es")
    assert recorder.calls[-1]["reply_language"] is None


# --- word sets -----------------------------------------------------------------------------------------

def test_the_chosen_sets_are_passed_to_the_tutor_and_bad_ones_are_refused(client, recorder):
    register(client)
    assert say(client, "a story", set_ids=[0, 3]).status_code == 200
    assert recorder.calls[-1]["set_ids"] == [0, 3]
    assert say(client, "a story").status_code == 200 and recorder.calls[-1]["set_ids"] is None
    assert say(client, "a story", set_ids=[-1]).status_code == 422
    assert say(client, "a story", set_ids=["x"]).status_code == 422
