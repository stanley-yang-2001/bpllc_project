"""A learner's own model (docs/CUSTOM-MODEL-DESIGN.md, phase 1): the address guard, the key at rest, the routes, and stories."""
import json
import socket

import psycopg2
import pytest
from psycopg2 import errors

from app.services import model_secrets, user_model
from app.services.user_model import ModelError, RequestLimiter, call_model, check_base_url
from conftest import DB_URL, HEADERS

SECRET = "a-long-test-secret-for-model-keys"
WORDS = ["hello", "goodbye", "please", "water", "friend", "house", "today", "bread"]
DIALOGUE = "Ana: Hello, friend.\nBen: Hello, water please.\nAna: Thank you.\nBen: Goodbye, friend."


def resolver(*ips):
    def fake(host, port, type=0):
        return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port)) for ip in ips]
    return fake


# --- the address guard -----------------------------------------------------------------------------------------------

@pytest.mark.parametrize("url", ["http://api.example.com/v1", "ftp://x.com", "https://user:pw@api.example.com/v1", "https://api.example.com/v1?x=1",
                                 "https://", "not a url", "https://api.example.com:notaport/v1"])
def test_unusable_addresses_are_refused(url):
    with pytest.raises(ModelError):
        check_base_url(url, False, resolver("93.184.216.34"))


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.5", "192.168.1.9", "172.16.0.1", "169.254.169.254", "0.0.0.0", "::1", "fe80::1",
                                "fd00::1", "224.0.0.1", "::ffff:127.0.0.1", "100.64.0.1"])
def test_private_and_special_addresses_are_refused(ip):
    with pytest.raises(ModelError, match="private network"):
        check_base_url("https://models.example.com/v1", False, resolver(ip))


def test_a_name_with_one_private_answer_is_refused():
    with pytest.raises(ModelError):
        check_base_url("https://models.example.com/v1", False, resolver("93.184.216.34", "10.0.0.1"))


def test_a_public_address_is_accepted_and_the_checked_ip_is_returned():
    assert check_base_url("https://api.example.com/v1/", False, resolver("93.184.216.34")) == ("https", "api.example.com", 443, "/v1", "93.184.216.34")


def test_the_single_user_override_allows_http_and_private_addresses():
    scheme, host, port, path, ip = check_base_url("http://localhost:11434/v1", True, resolver("127.0.0.1"))
    assert (scheme, port, path, ip) == ("http", 11434, "/v1", "127.0.0.1")


def test_a_name_that_does_not_resolve_is_refused():
    def fail(*a, **k):
        raise socket.gaierror("no")
    with pytest.raises(ModelError, match="could not be found"):
        check_base_url("https://nope.example.com/v1", False, fail)


# --- the call --------------------------------------------------------------------------------------------------------

class FakeResponse:
    def __init__(self, status, body):
        self.status, self._body = status, body if isinstance(body, bytes) else json.dumps(body).encode()

    def read(self, n=-1):
        return self._body[:n] if n >= 0 else self._body


class FakeConn:
    last = None

    def __init__(self, response=None, error=None):
        self.response, self.error, self.sent = response, error, None

    def __call__(self, host, ip, port, timeout):
        FakeConn.last = self
        self.target = (host, ip, port)
        return self

    def request(self, method, path, body, headers):
        if self.error:
            raise self.error
        self.sent = (method, path, json.loads(body), headers)

    def getresponse(self):
        return self.response

    def close(self):
        pass


def call(response=None, error=None, key="sk-secret-1234", **kw):
    conn = FakeConn(response, error)
    out = call_model("gpt-x", "https://api.example.com/v1", key, "hi", resolver=resolver("93.184.216.34"), connection_factory=conn, **kw)
    return out, conn


def test_the_call_goes_to_the_checked_ip_with_the_key_and_returns_the_text():
    out, conn = call(FakeResponse(200, {"choices": [{"message": {"content": "OK"}}]}))
    assert out == "OK" and conn.target == ("api.example.com", "93.184.216.34", 443)
    method, path, body, headers = conn.sent
    assert (method, path) == ("POST", "/v1/chat/completions") and headers["Authorization"] == "Bearer sk-secret-1234"
    assert body["model"] == "gpt-x" and "reasoning_effort" not in body and body["max_tokens"] == 1500


def test_no_authorization_header_without_a_key():
    _, conn = call(FakeResponse(200, {"choices": [{"message": {"content": "x"}}]}), key="")
    assert "Authorization" not in conn.sent[3]


@pytest.mark.parametrize("status,hint", [(401, "Check the key"), (404, "Check the model name"), (500, "answered 500")])
def test_errors_say_what_happened_without_the_key(status, hint):
    with pytest.raises(ModelError) as e:
        call(FakeResponse(status, {"error": {"message": "bad key sk-secret-1234 given"}}))
    assert hint in str(e.value) and "sk-secret-1234" not in str(e.value) and "***" in str(e.value)


def test_redirects_oversize_and_odd_answers_are_refused():
    for resp, text in [(FakeResponse(302, b""), "redirect"), (FakeResponse(200, b"x" * 1_000_002), "too large"),
                       (FakeResponse(200, b"<html>"), "expected format"), (FakeResponse(200, {"choices": []}), "expected format"),
                       (FakeResponse(200, {"choices": [{"message": {"content": None}}]}), "expected format")]:
        with pytest.raises(ModelError, match=text):
            call(resp)


def test_a_dead_server_is_a_plain_message():
    with pytest.raises(ModelError, match="did not answer"):
        call(error=ConnectionRefusedError("sk-secret-1234"))


def test_the_request_limiter():
    now = [0.0]
    lim = RequestLimiter(2, 60, clock=lambda: now[0])
    assert lim.allow(1) and lim.allow(1) and not lim.allow(1) and lim.allow(2)
    now[0] = 61
    assert lim.allow(1)


# --- the key at rest -------------------------------------------------------------------------------------------------

def test_the_key_round_trips_and_is_not_stored_as_text():
    token = model_secrets.encrypt(SECRET, "sk-abc-12345678")
    assert "sk-abc" not in token and model_secrets.decrypt(SECRET, token) == "sk-abc-12345678"
    assert model_secrets.decrypt("another-secret-entirely", token) == "" and model_secrets.decrypt(SECRET, "") == ""
    assert model_secrets.last4("sk-abc-12345678") == "5678" and model_secrets.last4("abc") == ""


def test_no_secret_means_no_encryption():
    with pytest.raises(model_secrets.SecretsUnavailable):
        model_secrets.encrypt("", "key")


# --- the routes ------------------------------------------------------------------------------------------------------

@pytest.fixture
def on(app, monkeypatch):
    monkeypatch.setattr(app.state.settings, "model_key_secret", SECRET)
    monkeypatch.setattr(app.state.settings, "allow_private_model_urls", False)
    app.state.model_limiter = RequestLimiter(10)
    app.state.model_test_limiter = RequestLimiter(5)


@pytest.fixture
def fake_call(monkeypatch):
    seen = []

    def fake(model, base_url, key, prompt, **kw):
        seen.append({"model": model, "base_url": base_url, "key": key, "prompt": prompt, **kw})
        if fake.error:
            raise ModelError(fake.error)
        return fake.answer
    fake.error, fake.answer, fake.seen = None, "Plan: x\n===STORY===\n" + DIALOGUE, seen
    monkeypatch.setattr(user_model, "call_model", fake)
    monkeypatch.setattr("app.routes.model.call_model", fake)
    monkeypatch.setattr("app.routes.model.check_base_url", lambda url, allow=False, r=None: None)
    return fake


def enable(email="alice@example.com"):
    with psycopg2.connect(DB_URL) as c, c.cursor() as cur:
        cur.execute("UPDATE tutor.users SET custom_model_enabled = true WHERE email = %s", (email,))


BODY = {"model": "gpt-x", "base_url": "https://api.example.com/v1", "api_key": "sk-secret-1234"}


def test_an_account_that_is_not_switched_on_is_refused_everywhere(on, make_user, fake_call):
    c = make_user("alice")
    assert c.get("/api/me/model").json() == {"enabled": False, "configured": False, "model": None, "base_url": None, "key_last4": None, "has_key": False}
    for method, path in [("put", ""), ("post", "/test")]:
        r = getattr(c, method)("/api/me/model" + path, json=BODY)
        assert r.status_code == 403 and r.json()["error"]["code"] == "custom_model_disabled"
    assert c.delete("/api/me/model").status_code == 403


def test_without_a_server_secret_nobody_can_use_it(app, make_user, monkeypatch):
    monkeypatch.setattr(app.state.settings, "model_key_secret", "")
    c = make_user("alice")
    enable()
    assert c.get("/api/me/model").json()["enabled"] is False
    assert c.put("/api/me/model", json=BODY).status_code == 403


def test_save_show_replace_keep_and_remove(on, make_user, fake_call):
    c = make_user("alice")
    enable()
    r = c.put("/api/me/model", json=BODY)
    assert r.status_code == 200 and r.json() == {"enabled": True, "configured": True, "model": "gpt-x", "base_url": "https://api.example.com/v1",
                                                  "key_last4": "1234", "has_key": True}
    assert "sk-secret" not in c.get("/api/me/model").text
    with psycopg2.connect(DB_URL) as db, db.cursor() as cur:
        cur.execute("SELECT api_key_encrypted FROM tutor.user_models")
        assert "sk-secret" not in cur.fetchone()[0]
    r = c.put("/api/me/model", json={"model": "gpt-y", "base_url": "https://api.example.com/v1/"})        # no key sent: the saved one stays
    assert r.json()["model"] == "gpt-y" and r.json()["key_last4"] == "1234" and r.json()["base_url"] == "https://api.example.com/v1"
    r = c.put("/api/me/model", json={**BODY, "api_key": "sk-other-9999"})
    assert r.json()["key_last4"] == "9999"
    r = c.put("/api/me/model", json={"model": "llama", "base_url": "https://api.example.com/v1", "remove_key": True})
    assert r.json()["has_key"] is False and r.json()["key_last4"] is None
    assert c.delete("/api/me/model").status_code == 204
    assert c.get("/api/me/model").json()["configured"] is False


@pytest.mark.parametrize("bad", [{"model": ""}, {"model": "two words"}, {"model": "x" * 101}, {"base_url": ""}, {"base_url": "x" * 201},
                                 {"api_key": "has space"}, {"api_key": "k" * 301}])
def test_bad_fields_are_422(on, make_user, fake_call, bad):
    c = make_user("alice")
    enable()
    assert c.put("/api/me/model", json={**BODY, **bad}).status_code == 422


def test_a_private_address_is_refused_on_save(on, make_user, monkeypatch):
    monkeypatch.setattr(user_model.socket, "getaddrinfo", resolver("10.0.0.5"))
    c = make_user("alice")
    enable()
    r = c.put("/api/me/model", json=BODY)
    assert r.status_code == 422 and "private network" in r.json()["error"]["message"]


def test_test_uses_the_typed_values_or_the_saved_key_and_is_rate_limited(on, make_user, fake_call):
    c = make_user("alice")
    enable()
    assert c.post("/api/me/model/test", json=BODY).json() == {"ok": True}
    assert fake_call.seen[-1]["key"] == "sk-secret-1234"
    c.put("/api/me/model", json=BODY)
    c.post("/api/me/model/test", json={"model": "gpt-x", "base_url": BODY["base_url"]})
    assert fake_call.seen[-1]["key"] == "sk-secret-1234"                 # the saved key was used
    fake_call.error = "The model server answered 401. Check the key."
    r = c.post("/api/me/model/test", json=BODY)
    assert r.status_code == 422 and r.json()["error"]["code"] == "model_test_failed" and "Check the key" in r.json()["error"]["message"]
    for _ in range(3):
        last = c.post("/api/me/model/test", json=BODY)
    assert last.status_code == 429


def test_one_learner_never_sees_or_changes_another_learners_model(on, make_user, fake_call):
    a, b = make_user("alice"), make_user("bob")
    enable("alice@example.com"), enable("bob@example.com")
    a.put("/api/me/model", json=BODY)
    assert b.get("/api/me/model").json()["configured"] is False
    b.delete("/api/me/model")
    assert a.get("/api/me/model").json()["configured"] is True


def test_the_row_goes_with_the_account(on, make_user, fake_call):
    c = make_user("alice")
    enable()
    c.put("/api/me/model", json=BODY)
    with psycopg2.connect(DB_URL) as db, db.cursor() as cur:
        cur.execute("DELETE FROM tutor.users WHERE email = 'alice@example.com'")
        cur.execute("SELECT count(*) FROM tutor.user_models")
        assert cur.fetchone()[0] == 0


# --- stories ---------------------------------------------------------------------------------------------------------

def learner_with_model(make_user, fake_call):
    c = make_user("alice")
    for w in WORDS:
        assert c.post("/api/words", json={"language": "en", "word": w}).status_code == 201
    enable()
    c.put("/api/me/model", json=BODY)
    return c


def test_stories_use_the_learners_own_model_and_say_so(on, app, make_user, fake_call):
    c = learner_with_model(make_user, fake_call)
    r = c.post("/api/stories/generate", json={"language": "en"}, headers=HEADERS)
    assert r.status_code == 200, r.text
    assert r.json()["report"]["model"] == {"custom": True, "name": "gpt-x"}
    assert fake_call.seen[-1]["key"] == "sk-secret-1234" and fake_call.seen[-1]["model"] == "gpt-x"


def test_a_learner_without_a_model_uses_the_shared_one(on, app, make_user, fake_call):
    c = make_user("alice")
    for w in WORDS:
        c.post("/api/words", json={"language": "en", "word": w})
    shared = []
    app.state.story_llm, saved = (lambda p: shared.append(p) or "Plan\n===STORY===\n" + DIALOGUE), app.state.story_llm
    try:
        r = c.post("/api/stories/generate", json={"language": "en"}, headers=HEADERS)
    finally:
        app.state.story_llm = saved
    assert r.status_code == 200 and "model" not in r.json()["report"] and fake_call.seen == [] and len(shared) == 1


def test_a_failing_model_shows_the_error_and_never_falls_back(on, app, make_user, fake_call):
    c = learner_with_model(make_user, fake_call)
    fake_call.error = "The model server answered 401. Check the key."
    shared = []
    app.state.story_llm, saved = (lambda p: shared.append(p) or "Plan\n===STORY===\n" + DIALOGUE), app.state.story_llm
    try:
        r = c.post("/api/stories/generate", json={"language": "en"}, headers=HEADERS)
    finally:
        app.state.story_llm = saved
    assert r.status_code == 502 and r.json()["error"]["code"] == "custom_model_failed"
    assert "Check the key" in r.json()["error"]["message"] and "switch back" in r.json()["error"]["message"] and shared == []


def test_own_model_stories_skip_the_shared_token_budget_but_have_a_request_limit(on, app, make_user, fake_call):
    c = learner_with_model(make_user, fake_call)
    app.state.model_limiter = RequestLimiter(2)
    used_before = app.state.ai_gate.__dict__.copy()
    codes = [c.post("/api/stories/generate", json={"language": "en"}, headers=HEADERS).status_code for _ in range(3)]
    assert codes == [200, 200, 429]
    assert app.state.ai_gate.__dict__.get("_tokens") == used_before.get("_tokens")


def test_the_migration_defaults(make_user, conn):
    make_user("alice")
    with conn.cursor() as cur:
        cur.execute("SELECT custom_model_enabled FROM tutor.users")
        assert cur.fetchone()[0] is False
        with pytest.raises(errors.CheckViolation):
            cur.execute("INSERT INTO tutor.user_models (user_id, model, base_url) VALUES (1, '', 'https://x.example.com')")


def test_the_export_has_the_model_settings_but_never_the_key(on, make_user, fake_call):
    c = make_user("alice")
    enable()
    c.put("/api/me/model", json=BODY)
    data = c.get("/api/me/export").json()
    assert data["user_models"]["model"] == "gpt-x" and data["user_models"]["key_last4"] == "1234"
    assert "sk-secret" not in json.dumps(data) and "api_key_encrypted" not in json.dumps(data)


def test_the_admin_command_switches_an_account(make_user, capsys):
    from app import custom_model_admin as admin
    make_user("alice")
    assert admin.run(["list"], DB_URL) == 0 and "No account" in capsys.readouterr().out
    assert admin.run(["on", "Alice@Example.com"], DB_URL) == 0 and "on for" in capsys.readouterr().out
    assert admin.run(["list"], DB_URL) == 0 and "alice@example.com" in capsys.readouterr().out
    assert admin.run(["off", "alice@example.com"], DB_URL) == 0
    assert admin.run(["on", "nobody@example.com"], DB_URL) == 1
    assert admin.run(["on"], DB_URL) == 2 and admin.run([], DB_URL) == 2
