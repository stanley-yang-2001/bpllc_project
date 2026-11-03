"""Chat streaming (docs/CUSTOM-MODEL-DESIGN.md section 11 / the chat page): Langflow's event stream in, lines of JSON out, and the
notice that says why a call to the learner's own model failed during a turn that still ended with an answer."""
import json

import pytest

from app.errors import AppError
from app.services import langflow_client as lc
from app.services.ai_gate import AiGate
from app.services.langflow.transport import TransportError, urllib_stream_transport
from app.services.langflow_client import ChatResult
from app.services.turn_tokens import TurnTokens
from conftest import HEADERS

PART = "c" * 32


def run_response(text):
    return {"session_id": "s", "outputs": [{"outputs": [{"results": {"message": {"text": text, "content_blocks": []}}}]}]}


def token(chunk):
    return {"event": "token", "data": {"chunk": chunk, "id": "x", "timestamp": "t"}}


def end(text):
    return {"event": "end", "data": {"result": run_response(text)}}


def client(events=None, error=None, stream=True):
    seen = {}

    def stream_transport(method, url, payload, headers, timeout):
        seen.update(url=url, payload=payload)
        if error:
            raise error
        yield from (events or [])

    c = lc.LangflowClient("http://lf:7860", "flow", "k", stream=stream, stream_transport=stream_transport,
                          transport=lambda *a: run_response("whole"))
    return c, seen


def run(c, **kw):
    return c.run(user_id=1, language="es", message="hi", session_id="u1-" + PART, **kw)


# --- the client --------------------------------------------------------------------------------------

def test_tokens_go_to_the_callback_and_the_end_event_is_the_answer():
    c, seen = client([{"event": "add_message", "data": {}}, token("Ho"), token("la"), token(""), end("Hola")])
    got = []
    result = run(c, on_delta=got.append)
    assert got == ["Ho", "la"] and result.reply == "Hola" and seen["url"].endswith("?stream=true")


def test_a_stream_with_no_tokens_still_ends_with_the_answer():
    c, _ = client([end("Hola")])
    got = []
    assert run(c, on_delta=got.append).reply == "Hola" and got == []


def test_odd_events_are_ignored():
    c, _ = client([{"event": "token", "data": "no"}, {"event": "token", "data": {"chunk": 5}}, {"nonsense": 1}, {"event": "end", "data": {"result": "x"}}, end("ok")])
    assert run(c, on_delta=lambda t: None).reply == "ok"


@pytest.mark.parametrize("events", [[token("a")], [{"event": "error", "data": {"error": "boom"}}, end("late")]])
def test_an_error_event_or_a_missing_end_is_a_plain_failure(events):
    c, _ = client(events)
    with pytest.raises(AppError) as e:
        run(c, on_delta=lambda t: None)
    assert e.value.code == "ai_failed" and "boom" not in e.value.message


def test_transport_failures_use_the_usual_messages():
    c, _ = client(error=TransportError("timeout"))
    with pytest.raises(AppError, match="took too long"):
        run(c, on_delta=lambda t: None)


def test_without_a_callback_or_with_the_flag_off_the_old_call_is_used():
    for c, kw in (client([end("stream")])[0], {}), (client([end("stream")], stream=False)[0], {"on_delta": lambda t: None}):
        assert run(c, **kw).reply == "whole"


def test_the_stream_reader_yields_json_lines_and_skips_the_rest(monkeypatch):
    class Resp:
        def __init__(self, lines):
            self.lines = lines

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def __iter__(self):
            return iter(self.lines)
    lines = [b'{"event":"token","data":{"chunk":"a"}}\n', b"\n", b"not json\n", b"[1]\n", b'{"event":"end","data":{}}\n']
    monkeypatch.setattr("urllib.request.urlopen", lambda req, timeout: Resp(lines))
    assert [e["event"] for e in urllib_stream_transport("POST", "http://x", {}, {}, 5)] == ["token", "end"]


# --- the route -------------------------------------------------------------------------------------------

class Tutor:
    stores_chat = False
    calls_ai = False
    streams = True

    def __init__(self, error=None, notice=""):
        self.error, self.notice, self.calls = error, notice, []

    def run(self, **kw):
        self.calls.append(kw)
        if kw.get("on_delta"):
            kw["on_delta"]("Ho"), kw["on_delta"]("la")
        if self.error:
            raise self.error
        return ChatResult("Hola", notice=self.notice)


@pytest.fixture
def tutor(app, monkeypatch):
    saved = app.state.chat, app.state.ai_gate
    app.state.chat, app.state.ai_gate = Tutor(), AiGate(slots=2, wait_seconds=0.2)
    monkeypatch.setattr(app.state.settings, "chat_stream", True)
    yield app.state.chat
    app.state.chat, app.state.ai_gate = saved


def say(c, accept=None):
    h = {"Accept": accept} if accept else {}
    return c.post("/api/chat", json={"message": "hi", "language": "es", "session_id": PART}, headers=h)


def lines(r):
    return [json.loads(x) for x in r.text.splitlines() if x.strip()]


def test_the_page_that_asks_gets_deltas_then_the_final_answer(make_user, tutor):
    r = say(make_user("alice"), "application/x-ndjson, application/json")
    assert r.headers["content-type"].startswith("application/x-ndjson")
    ev = lines(r)
    assert [e["event"] for e in ev] == ["delta", "delta", "final"] and "".join(e["text"] for e in ev[:2]) == "Hola"
    assert ev[-1]["reply"] == "Hola" and ev[-1]["session_id"] == PART and tutor.calls[0]["session_id"].startswith("u1-") and ev[-1]["notice"] is None


def test_a_page_that_does_not_ask_or_a_switched_off_flag_gets_the_one_json_answer(make_user, tutor, monkeypatch, app):
    c = make_user("alice")
    r = say(c)
    assert r.headers["content-type"].startswith("application/json") and r.json()["reply"] == "Hola" and "on_delta" not in tutor.calls[0]
    monkeypatch.setattr(app.state.settings, "chat_stream", False)
    assert say(c, "application/x-ndjson").json()["reply"] == "Hola"


def test_a_tutor_that_cannot_stream_gets_the_one_json_answer(make_user, tutor):
    tutor.streams = False
    assert say(make_user("alice"), "application/x-ndjson").json()["reply"] == "Hola"


def test_a_failed_turn_ends_the_stream_with_the_usual_error(make_user, tutor):
    tutor.error = AppError("tutor_busy", "The tutor is busy.", 429, retry_after=15)
    ev = lines(say(make_user("alice"), "application/x-ndjson"))
    assert ev[-1] == {"event": "error", "status": 429, "error": {"code": "tutor_busy", "message": "The tutor is busy.", "retry_after": 15}}


def test_the_checks_before_the_stream_still_answer_with_http_errors(client, tutor):
    assert say(client, "application/x-ndjson").status_code == 401
    assert client.post("/api/chat", json={"message": "  ", "language": "es", "session_id": PART}, headers={"Accept": "application/x-ndjson"}).status_code in (401, 422)


def test_a_surprise_ends_the_stream_with_an_error_not_a_hang(make_user, tutor):
    tutor.error = RuntimeError("secret detail")
    ev = lines(say(make_user("alice"), "application/x-ndjson"))
    assert ev[-1]["event"] == "error" and "secret" not in json.dumps(ev[-1])


# --- the notice ------------------------------------------------------------------------------------------

def test_a_notice_reaches_the_page_in_both_shapes(make_user, tutor):
    tutor.notice = "The model server answered 401. Check the key."
    c = make_user("alice")
    assert say(c).json()["notice"] == tutor.notice
    assert lines(say(c, "application/x-ndjson"))[-1]["notice"] == tutor.notice


def test_the_tool_failure_notice_comes_from_the_token_and_a_later_success_clears_it():
    t = TurnTokens()
    tok = t.issue(1)
    t.note_error(tok, "The model server answered 401. Check the key.")
    assert t.last_error(tok)
    t.clear_error(tok)
    assert t.last_error(tok) == ""
