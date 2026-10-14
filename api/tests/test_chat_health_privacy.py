"""M5 acceptance items beyond deletion: nothing personal reaches the AI service (design 12B), and /health
reports on Langflow without exposing its address or key."""
import json

from app.errors import AppError
from app.services.ai_gate import AiGate
from app.services.chat import NotReadyChat
from app.services.chat_stub import StubChat
from app.services.langflow_client import LangflowClient, TransportError
from conftest import register

PART = "c" * 32


def swap(app, tutor):
    saved = app.state.chat, app.state.ai_gate
    app.state.chat, app.state.ai_gate = tutor, AiGate(slots=2, wait_seconds=0.2)
    return saved


def restore(app, saved):
    app.state.chat, app.state.ai_gate = saved


# --- prompt privacy ------------------------------------------------------------------------------------

def test_a_learners_name_email_and_password_never_reach_langflow(app, client):
    sent = []

    def transport(method, url, payload, headers, timeout):
        sent.append(json.dumps([method, url, payload, headers]))
        if method == "GET":
            return []
        return {"outputs": [{"outputs": [{"results": {"message": {"text": "hola"}}}]}]}

    saved = swap(app, LangflowClient("http://lf:7860", "language-tutor", "api-key-1", tweak_keys=("Add Word",), transport=transport))
    try:
        register(client, "zebulon", password="quux-secret-77", display_name="Zebulon Quux")
        r = client.post("/api/chat", json={"message": "add the word bread", "language": "es", "session_id": PART})
        assert r.status_code == 200
        assert client.post("/api/me/delete", json={"password": "quux-secret-77"}).status_code == 204   # cleanup calls too
    finally:
        restore(app, saved)
    everything = " ".join(sent).lower()
    assert len(sent) >= 3
    for personal in ("zebulon", "quux", "@example.com", "quux-secret-77", "password"):
        assert personal not in everything, f"{personal!r} was sent to Langflow"
    assert '"learner_id": "1"' in everything and "u1-" + PART in everything


# --- /health -------------------------------------------------------------------------------------------

def langflow_health(client):
    return client.get("/api/health").json()["langflow"]


def test_health_says_the_stub_is_in_use(app, client):
    saved = swap(app, StubChat(lambda: app.state.pool))
    try:
        register(client, "alice")
        assert langflow_health(client) == {"ok": None, "status": "stub", "detail": None}
    finally:
        restore(app, saved)


def test_health_says_chat_is_off_until_the_tools_are_confirmed(app, client):
    saved = swap(app, NotReadyChat())
    try:
        register(client, "alice")
        check = langflow_health(client)
        assert check["ok"] is False and check["status"] == "off"
    finally:
        restore(app, saved)


def test_health_reports_a_reachable_langflow_as_ok(app, client):
    calls = []

    def transport(method, url, payload, headers, timeout):
        calls.append((method, url, timeout))
        return {"status": "ok"}

    saved = swap(app, LangflowClient("http://lf:7860", "f", "k", transport=transport))
    try:
        register(client, "alice")
        assert langflow_health(client)["ok"] is True
    finally:
        restore(app, saved)
    assert calls == [("GET", "http://lf:7860/health", 3)]


def test_health_reports_an_unreachable_langflow_without_leaking_its_address_or_key(app, client):
    def transport(*a):
        raise TransportError("unreachable", None, "connect to http://lf:7860 refused key=api-key-9")

    saved = swap(app, LangflowClient("http://lf:7860", "f", "api-key-9", transport=transport))
    try:
        register(client, "alice")
        check = langflow_health(client)
    finally:
        restore(app, saved)
    assert check["ok"] is False and check["detail"] == "unreachable"
    assert "lf:7860" not in json.dumps(check) and "api-key-9" not in json.dumps(check)


def test_health_still_needs_login(client):
    assert client.get("/api/health").status_code == 401
