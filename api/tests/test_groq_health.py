"""/health reports on Groq (M6): one light call, remembered for 60 seconds, never leaking the key."""
import json

from app.services.story_llm import GROQ_MODELS_URL, GroqHealth
from app.services.langflow_client import TransportError
from conftest import register


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def probe(transport, key="gsk-secret-1", clock=None, stub=False):
    return GroqHealth(stub, api_key_fn=lambda: key, transport=transport, clock=clock or Clock())


def ok(calls):
    def transport(method, url, payload, headers, timeout):
        calls.append((method, url, payload, headers, timeout))
        return {"data": []}
    return transport


def test_a_working_key_is_reported_up_with_one_light_call():
    calls = []
    assert probe(ok(calls)).check() == {"ok": True, "status": "up", "detail": None}
    method, url, payload, headers, timeout = calls[0]
    assert (method, url, payload, timeout) == ("GET", GROQ_MODELS_URL, None, 3.0)
    assert headers["Authorization"] == "Bearer gsk-secret-1" and headers["User-Agent"]


def test_the_answer_is_remembered_for_60_seconds_then_asked_again():
    calls, clock = [], Clock()
    p = probe(ok(calls), clock=clock)
    p.check()
    clock.now += 59.9
    p.check()
    assert len(calls) == 1
    clock.now += 0.2
    p.check()
    assert len(calls) == 2


def test_a_failure_is_remembered_too_so_a_down_service_is_not_hammered():
    calls = []

    def transport(*a):
        calls.append(a)
        raise TransportError("unreachable", None, "x")
    p = probe(transport)
    assert p.check()["ok"] is False and p.check()["ok"] is False and len(calls) == 1


def test_a_missing_key_is_off_and_makes_no_call():
    calls = []
    assert probe(ok(calls), key="  ").check() == {"ok": False, "status": "off", "detail": "no key"}
    assert calls == []


def test_a_refused_key_is_called_rejected_and_other_failures_name_only_their_kind():
    def refuse(code):
        def transport(*a):
            raise TransportError("http", code, "bad key gsk-secret-1")
        return transport
    assert probe(refuse(401)).check() == {"ok": False, "status": "down", "detail": "rejected"}
    assert probe(refuse(503)).check()["detail"] == "http"

    def slow(*a):
        raise TransportError("timeout")
    assert probe(slow).check()["detail"] == "timeout"


def test_the_report_never_holds_the_key_or_the_services_reply():
    def transport(*a):
        raise TransportError("http", 401, "Invalid API key gsk-secret-1")
    assert "gsk-secret-1" not in json.dumps(probe(transport).check())


def test_stub_mode_makes_no_call_and_says_so():
    calls = []
    assert probe(ok(calls), stub=True).check() == {"ok": None, "status": "stub", "detail": None}
    assert calls == []


def test_the_health_route_reports_groq_and_still_needs_login(app, client):
    assert client.get("/api/health").status_code == 401
    saved = app.state.groq_health
    app.state.groq_health = probe(ok([]))
    try:
        register(client, "alice")
        assert client.get("/api/health").json()["groq"] == {"ok": True, "status": "up", "detail": None}
    finally:
        app.state.groq_health = saved
