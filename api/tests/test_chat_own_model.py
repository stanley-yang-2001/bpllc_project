"""Chat on a learner's own model (docs/CUSTOM-MODEL-DESIGN.md section 10, option B): the learner's key stays in the API.

Langflow gets the model name, the API's internal address and a throwaway token. The token comes back to /internal/v1/chat/completions,
where the API swaps in the stored key, runs the address guard, and forwards the request."""
import json
import socket

import psycopg2
import pytest
from fastapi.testclient import TestClient

from app.errors import AppError
from app.services import model_proxy
from app.services.ai_gate import AiGate
from app.services.langflow.payload import build_tweaks
from app.services.langflow_client import ChatResult
from app.services.model_proxy import ProxyError, open_upstream, prepare_body
from app.services.turn_tokens import TurnTokens
from app.services.user_model import RequestLimiter
from conftest import DB_URL, HEADERS

SECRET = "a-long-test-secret-for-model-keys"
KEY = "sk-real-key-9999"
PART = "b" * 32
OWN = {"node": "GroqLanguageModel-h5DsK", "model": "gpt-x", "url": "http://api:8000/internal/v1", "token": "tt-abc"}


def resolver(*ips):
    def fake(host, port, type=0):
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in ips]
    return fake


# --- the token ---------------------------------------------------------------------------------------------------------

def test_a_token_names_one_learner_expires_runs_out_and_can_be_revoked():
    now = [0.0]
    tokens = TurnTokens(clock=lambda: now[0], ttl=100, max_uses=2)
    t = tokens.issue(7)
    assert t.startswith("tt-") and tokens.issue(7) != t
    assert tokens.use(t) == 7 and tokens.use(t) == 7 and tokens.use(t) is None       # the third call is over the limit
    t2 = tokens.issue(8)
    now[0] = 101
    assert tokens.use(t2) is None                                                      # expired
    t3 = tokens.issue(9)
    tokens.revoke(t3)
    assert tokens.use(t3) is None and tokens.use("") is None and tokens.use("nope") is None


# --- what Langflow is told -----------------------------------------------------------------------------------------------

def test_the_tweaks_carry_a_token_never_a_key():
    tweaks = build_tweaks(("AddWord-WhP5g", "StoryGeneratorTool-RQpvc"), 5, "es", [1], own_model=OWN)
    assert tweaks[OWN["node"]] == {"model_name": "gpt-x", "base_url": OWN["url"], "api_key": "tt-abc"}
    assert tweaks["StoryGeneratorTool-RQpvc"]["own_model_token"] == "tt-abc" and tweaks["StoryGeneratorTool-RQpvc"]["learner_id"] == "5"
    assert "own_model_name" not in tweaks["AddWord-WhP5g"]
    assert KEY not in json.dumps(tweaks)


def test_no_own_model_means_the_tweaks_are_unchanged():
    assert build_tweaks(("StoryGeneratorTool-RQpvc",), 5, "es") == {"StoryGeneratorTool-RQpvc": {"learner_id": "5", "active_language": "es"}}


# --- the proxy -------------------------------------------------------------------------------------------------------------

class FakeResp:
    def __init__(self, status, body=b"", ctype="application/json"):
        self.status, self._body, self._ctype = status, body if isinstance(body, bytes) else json.dumps(body).encode(), ctype
        self._pos = 0

    def getheader(self, name):
        return self._ctype

    def read(self, n=-1):
        out = self._body[self._pos:] if n < 0 else self._body[self._pos:self._pos + n]
        self._pos += len(out)
        return out

    read1 = read


class FakeConn:
    def __init__(self, resp=None, error=None):
        self.resp, self.error, self.sent, self.closed = resp, error, None, False

    def __call__(self, host, ip, port, timeout):
        self.target = (host, ip, port)
        return self

    def request(self, method, path, body, headers):
        if self.error:
            raise self.error
        self.sent = (method, path, json.loads(body), headers)

    def getresponse(self):
        return self.resp

    def close(self):
        self.closed = True


REQ = json.dumps({"model": "whatever-langflow-sent", "messages": [{"role": "user", "content": "hi"}], "stream": True}).encode()


def up(conn, **kw):
    return open_upstream("gpt-x", "https://api.example.com/v1", KEY, kw.pop("body", REQ), resolver=resolver("93.184.216.34"), connection_factory=conn, **kw)


def test_the_request_goes_to_the_checked_ip_with_the_real_key_and_the_saved_model():
    conn = FakeConn(FakeResp(200, b"data: one\n\ndata: [DONE]\n\n", "text/event-stream"))
    upstream = up(conn)
    assert conn.target == ("api.example.com", "93.184.216.34", 443)
    method, path, body, headers = conn.sent
    assert (method, path) == ("POST", "/v1/chat/completions") and headers["Authorization"] == f"Bearer {KEY}"
    assert body["model"] == "gpt-x" and body["stream"] is True               # the saved model wins; the rest passes through
    assert upstream.content_type == "text/event-stream"
    assert b"".join(upstream.chunks()) == b"data: one\n\ndata: [DONE]\n\n" and conn.closed


def test_the_private_address_guard_applies_to_chat_too():
    with pytest.raises(ProxyError, match="private network"):
        open_upstream("gpt-x", "https://models.example.com/v1", KEY, REQ, resolver=resolver("10.0.0.5"), connection_factory=FakeConn())


@pytest.mark.parametrize("status,expect,hint", [(401, 401, "Check the key"), (404, 404, "Check the model name"), (429, 429, "answered 429"), (500, 502, "answered 500")])
def test_upstream_errors_keep_their_meaning_and_never_show_the_key(status, expect, hint):
    conn = FakeConn(FakeResp(status, {"error": {"message": f"bad key {KEY} given"}}))
    with pytest.raises(ProxyError) as e:
        up(conn)
    assert e.value.status == expect and hint in e.value.message and KEY not in e.value.message and conn.closed


def test_redirects_dead_servers_and_bad_requests_are_refused():
    with pytest.raises(ProxyError, match="redirect"):
        up(FakeConn(FakeResp(302)))
    with pytest.raises(ProxyError, match="did not answer") as e:
        up(FakeConn(error=ConnectionRefusedError(KEY)))
    assert KEY not in e.value.message
    for raw in (b"not json", b"[]", json.dumps({"model": "x"}).encode()):
        with pytest.raises(ProxyError) as e:
            prepare_body(raw, "gpt-x")
        assert e.value.status == 400
    with pytest.raises(ProxyError) as e:
        prepare_body(b"x" * (model_proxy.MAX_REQUEST_BYTES + 1), "gpt-x")
    assert e.value.status == 413


def test_a_stream_past_the_size_cap_just_ends(monkeypatch):
    monkeypatch.setattr(model_proxy, "MAX_RESPONSE_BYTES", 20)
    conn = FakeConn(FakeResp(200, b"x" * 100))
    assert len(b"".join(up(conn).chunks())) <= 8192 + 20 and conn.closed


# --- the internal route ----------------------------------------------------------------------------------------------------

@pytest.fixture
def on(app, monkeypatch):
    monkeypatch.setattr(app.state.settings, "model_key_secret", SECRET)
    monkeypatch.setattr(app.state.settings, "chat_own_model", True)
    monkeypatch.setattr(app.state.settings, "allow_private_model_urls", False)
    monkeypatch.setattr("app.services.model_settings.check_base_url", lambda url, allow=False, r=None: None)
    app.state.chat_model_limiter = RequestLimiter(60)
    app.state.turn_tokens = TurnTokens()
    return app


def learner(make_user, name="alice", model=True):
    c = make_user(name)
    with psycopg2.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute("UPDATE tutor.users SET custom_model_enabled = true WHERE email = %s", (f"{name}@example.com",))
    if model:
        r = c.put("/api/me/model", json={"model": "gpt-x", "base_url": "https://api.example.com/v1", "api_key": KEY})
        assert r.status_code == 200, r.text
    return c


@pytest.fixture
def upstream(monkeypatch):
    seen = {}

    def fake_open(model, base_url, key, raw, **kw):
        seen.update(model=model, base_url=base_url, key=key, raw=raw, **kw)
        if seen.get("error"):
            raise seen["error"]
        return model_proxy.Upstream(FakeConn(FakeResp(200, b'{"choices":[{"message":{"content":"hi"}}]}')), FakeResp(200, b'{"choices":[{"message":{"content":"hi"}}]}'))
    monkeypatch.setattr("app.routes.internal_model.open_upstream", fake_open)
    return seen


def internal(app, token, body=REQ, **headers):
    c = TestClient(app)             # no X-Requested-With: Langflow does not send it, and the route must not need it
    h = {"Authorization": f"Bearer {token}", "Content-Type": "application/json", **headers} if token is not None else {}
    return c.post("/internal/v1/chat/completions", content=body, headers=h)


def test_a_good_token_reaches_the_learners_model_with_the_stored_key(on, make_user, upstream):
    learner(make_user)
    token = on.state.turn_tokens.issue(1)
    r = internal(on, token)
    assert r.status_code == 200 and r.json()["choices"][0]["message"]["content"] == "hi"
    assert (upstream["model"], upstream["base_url"], upstream["key"]) == ("gpt-x", "https://api.example.com/v1", KEY)
    assert KEY not in r.text and KEY not in json.dumps(dict(r.headers))


@pytest.mark.parametrize("token", [None, "", "tt-unknown", "sk-" + "x" * 20])
def test_without_a_live_token_nothing_is_called(on, make_user, upstream, token):
    learner(make_user)
    assert internal(on, token).status_code == 401 and "key" not in upstream


def test_a_request_that_came_through_the_web_proxy_is_refused(on, make_user, upstream):
    learner(make_user)
    token = on.state.turn_tokens.issue(1)
    assert internal(on, token, **{"X-Forwarded-For": "1.2.3.4"}).status_code == 403 and "key" not in upstream


def test_the_route_is_not_under_api_so_nginx_does_not_publish_it(app):
    assert TestClient(app, headers=HEADERS).post("/api/internal/v1/chat/completions", content=REQ).status_code in (401, 403, 404)
    nginx = open(__file__.replace("api/tests/test_chat_own_model.py", "web/nginx.conf"), encoding="utf-8").read()
    assert "location /api/" in nginx and "/internal" not in nginx


def test_a_learner_without_a_saved_model_gets_a_plain_refusal(on, make_user, upstream):
    learner(make_user, model=False)
    token = on.state.turn_tokens.issue(1)
    r = internal(on, token)
    assert r.status_code == 409 and "My model" in r.json()["error"]["message"]


def test_the_per_learner_limit_and_the_noted_error(on, make_user, upstream):
    learner(make_user)
    on.state.chat_model_limiter = RequestLimiter(1)
    token = on.state.turn_tokens.issue(1)
    assert internal(on, token).status_code == 200
    r = internal(on, token)
    assert r.status_code == 429 and on.state.turn_tokens.last_error(token) == r.json()["error"]["message"]


def test_an_upstream_failure_is_noted_for_the_learner(on, make_user, upstream):
    learner(make_user)
    upstream["error"] = ProxyError(401, "The model server answered 401. Check the key. ***")
    token = on.state.turn_tokens.issue(1)
    assert internal(on, token).status_code == 401 and "Check the key" in on.state.turn_tokens.last_error(token)


def test_a_learner_who_is_switched_off_loses_the_route(on, make_user, upstream):
    learner(make_user)
    with psycopg2.connect(DB_URL) as conn, conn.cursor() as cur:
        cur.execute("UPDATE tutor.users SET custom_model_enabled = false")
    token = on.state.turn_tokens.issue(1)
    assert internal(on, token).status_code == 409 and "key" not in upstream


# --- the chat turn ---------------------------------------------------------------------------------------------------------

class OwnTutor:
    stores_chat = False
    calls_ai = True

    def __init__(self, app, error=None, note=""):
        self.app, self.calls, self.error, self.note, self.live = app, [], error, note, None

    def run(self, **kw):
        self.calls.append(kw)
        own = kw.get("own_model")
        if own:
            self.live = self.app.state.turn_tokens.use(own["token"])
            if self.note:
                self.app.state.turn_tokens.note_error(own["token"], self.note)
        if self.error:
            raise self.error
        return ChatResult("ok", tokens=900)


@pytest.fixture
def tutor(on):
    saved = on.state.chat, on.state.ai_gate
    on.state.chat, on.state.ai_gate = OwnTutor(on), AiGate(slots=2, wait_seconds=0.2, tokens_per_minute=8000)
    yield on.state.chat
    on.state.chat, on.state.ai_gate = saved


def say(c, message="hello"):
    return c.post("/api/chat", json={"message": message, "language": "es", "session_id": PART})


def test_a_learner_on_their_own_model_gets_the_token_and_it_ends_with_the_turn(on, make_user, tutor):
    c = learner(make_user)
    assert say(c).status_code == 200
    own = tutor.calls[0]["own_model"]
    assert own["model"] == "gpt-x" and own["url"] == on.state.settings.internal_api_url and own["node"] == on.state.settings.langflow_model_node
    assert KEY not in json.dumps(own) and tutor.live == 1
    assert on.state.turn_tokens.use(own["token"]) is None and len(on.state.turn_tokens) == 0           # revoked after the turn


def test_the_shared_token_budget_is_not_charged_for_own_model_turns(on, make_user, tutor):
    c = learner(make_user)
    for _ in range(12):                      # the shared limit is 8000 tokens a minute; 12 turns of 900 would pass it
        assert say(c).status_code == 200


def test_everyone_else_stays_on_the_shared_model(on, make_user, tutor):
    c = make_user("bob")                                   # not switched on
    d = learner(make_user, "carol", model=False)           # switched on, nothing saved
    assert say(c).status_code == 200 and say(d).status_code == 200
    assert all("own_model" not in call for call in tutor.calls)


def test_the_flag_keeps_it_off_until_the_flow_is_ready(on, make_user, tutor, monkeypatch):
    c = learner(make_user)
    monkeypatch.setattr(on.state.settings, "chat_own_model", False)
    say(c)
    assert "own_model" not in tutor.calls[0]


def test_a_failed_turn_says_why_and_never_falls_back(on, make_user, tutor):
    c = learner(make_user)
    tutor.error, tutor.note = AppError("ai_failed", "The tutor couldn't answer just now.", 502), "The model server answered 401. Check the key."
    r = say(c)
    assert r.status_code == 502 and r.json()["error"]["code"] == "own_model_failed" and "Check the key" in r.json()["error"]["message"]
    assert len(on.state.turn_tokens) == 0 and len(tutor.calls) == 1


def test_a_failed_turn_without_a_noted_reason_keeps_the_usual_error(on, make_user, tutor):
    c = learner(make_user)
    tutor.error = AppError("ai_failed", "The tutor couldn't answer just now.", 502)
    assert say(c).json()["error"]["code"] == "ai_failed"
