"""api/scripts/own_model_chat_check.py: the live check for chat on a learner's own model, run here against the REAL API (in this process, over
HTTP) with a stand-in for Langflow that behaves the way the flow does: it calls the API's internal model route with the throwaway token,
asks the model, calls the story tool's own model call, and returns the answer. What is NOT covered here is Langflow itself; that is what
the check is for when it runs on your stack."""
import json
import os
import socket
import sys
import threading
import time
import urllib.error
import urllib.request

import psycopg2
import pytest
import uvicorn

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import own_model_chat_check as chk  # noqa: E402

from app.config import Settings  # noqa: E402
from app.errors import AppError  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.ai_gate import AiGate  # noqa: E402
from app.services.langflow_client import ChatResult, ToolCall  # noqa: E402
from conftest import DB_URL  # noqa: E402

SECRET = "a-long-test-secret-for-model-keys"


# --- the pieces of the script ----------------------------------------------------------------------------------------------

def test_the_scripted_provider_decides_by_what_it_is_asked():
    tools = [{"type": "function", "function": {"name": "story_generator_tool_run"}}]
    assert chk.decide({"messages": [{"role": "user", "content": "hi"}]})["kind"] == "plain"
    assert chk.decide({"messages": [{"role": "user", "content": "Tell me a STORY"}], "tools": tools}) == {"kind": "tool_call", "tool": "story_generator_tool_run", "args": {"language": "English"}}
    assert chk.decide({"messages": [{"role": "user", "content": "Tell me a story"}], "tools": []})["kind"] == "plain"                 # no tool to call
    assert chk.decide({"messages": [{"role": "user", "content": "story"}, {"role": "tool", "content": "x"}], "tools": tools})["kind"] == "final"
    tool = chk.decide({"messages": [{"role": "user", "content": [{"type": "text", "text": "write ===STORY=== now"}]}]})
    assert tool["kind"] == "tool" and chk.DIALOGUE in tool["text"]


def post(url, key, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def test_the_fake_provider_checks_the_key_and_records_what_it_heard():
    with chk.FakeProvider("good") as fake:
        url = f"http://127.0.0.1:{fake.port}/v1/chat/completions"
        status, data = post(url, "good", {"model": "m", "messages": [{"role": "user", "content": "hi"}]})
        assert status == 200 and chk.MARKER in json.loads(data)["choices"][0]["message"]["content"]
        assert post(url, "bad", {"model": "m", "messages": []})[0] == 401
        status, data = post(url, "good", {"model": "m", "stream": True, "messages": [{"role": "user", "content": "story"}],
                                           "tools": [{"type": "function", "function": {"name": "story_tool"}}]})
        assert status == 200 and b"tool_calls" in data and data.rstrip().endswith(b"[DONE]")
        assert [c["authorization"] for c in fake.snapshot()] == ["Bearer good", "Bearer bad", "Bearer good"] and fake.snapshot()[2]["stream"] is True


def test_the_database_scan_finds_a_planted_key_and_nothing_else():
    connect = lambda: psycopg2.connect(DB_URL)      # noqa: E731
    needle = "own-model-check-key-planted-0001"
    assert chk.scan_for(connect, needle) == []
    with connect() as conn, conn.cursor() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS public.scan_probe (id serial, payload jsonb)")
        cur.execute("INSERT INTO public.scan_probe (payload) VALUES (%s)", (json.dumps({"api_key": needle}),))
    try:
        assert chk.scan_for(connect, needle) == ["public.scan_probe.payload"]
    finally:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("DROP TABLE public.scan_probe")


# --- the whole script against the real API, with a stand-in for Langflow --------------------------------------------------------

class FlowLikeTutor:
    """What the Langflow flow does with the tweaks it is given: the Agent asks the model through `own_model`'s address and token, may call
    the story tool, which asks the model again with the same address and token. A learner without `own_model` gets the shared model."""
    stores_chat = False
    calls_ai = True

    def __init__(self, tolerant=False):
        self.tolerant = tolerant

    def _ask(self, own, body):
        req = urllib.request.Request(own["url"] + "/chat/completions", data=json.dumps({"model": own["model"], **body}).encode(), method="POST",
                                     headers={"Authorization": f"Bearer {own['token']}", "Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=15) as r:
                return json.loads(r.read())["choices"][0]["message"]
        except urllib.error.HTTPError:
            raise AppError("ai_failed", "The tutor couldn't answer just now. Please try again.", 502)

    def run(self, *, user_id, language, message, session_id, reply_language=None, set_ids=None, own_model=None, on_delta=None):
        if not own_model:
            return ChatResult("A reply from the shared model.")
        tools = [{"type": "function", "function": {"name": "story_generator_tool_run"}}]
        first = self._ask(own_model, {"messages": [{"role": "user", "content": message}], "tools": tools})
        if not first.get("tool_calls"):
            return ChatResult(first["content"])
        written = self._ask(own_model, {"messages": [{"role": "user", "content": "Write it. " + chk.DELIMITER}]})["content"]
        story = written.split(chk.DELIMITER, 1)[1].strip()
        final = self._ask(own_model, {"messages": [{"role": "user", "content": message}, {"role": "tool", "content": story}], "tools": tools})
        return ChatResult(story, [ToolCall("Story Generator Tool", {"language": "English"}, story)])


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


@pytest.fixture
def live_api(app):
    """A second copy of the API, really listening on a port (the check talks to it over HTTP like it does in Docker)."""
    port = free_port()
    settings = Settings(database_url=DB_URL, jwt_secret="x" * 40, bcrypt_rounds=4, ai_mode="stub", model_key_secret=SECRET, chat_own_model=True,
                        allow_private_model_urls=True, internal_api_url=f"http://127.0.0.1:{port}/internal/v1", run_migrations=False)
    application = create_app(settings)
    server = uvicorn.Server(uvicorn.Config(application, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.1)
    application.state.chat = FlowLikeTutor()
    application.state.ai_gate = AiGate(slots=2, wait_seconds=1.0, tokens_per_minute=0)
    yield application, f"http://127.0.0.1:{port}"
    server.should_exit = True
    thread.join(10)


def run_check(base):
    return chk.run_checks(base, lambda: psycopg2.connect(DB_URL), settle=0, retry_delay=0)


def test_the_whole_check_passes_when_the_key_stays_in_the_api(live_api):
    _, base = live_api
    rep = run_check(base)
    assert rep.rows and not rep.failed, rep.failed
    assert len(rep.rows) >= 12


def test_the_check_fails_when_the_feature_is_off(live_api):
    application, base = live_api
    application.state.settings.chat_own_model = False
    rep = run_check(base)
    assert any(name.startswith("GREETING") for name in rep.failed)


def test_the_check_notices_a_stand_in_that_would_leak_the_real_key(live_api, monkeypatch):
    """If the flow somehow got the real key (here: written into a table the way Langflow's logs would), the AT REST check must fail."""
    application, base = live_api
    real = chk.sign_up

    def leaky(base_url, label):
        return real(base_url, label)
    original = chk.FakeProvider.__init__

    def planting(self, expected_key, *a, **k):
        original(self, expected_key, *a, **k)
        with psycopg2.connect(DB_URL) as conn, conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS public.leak_probe (id serial, note text)")
            cur.execute("INSERT INTO public.leak_probe (note) VALUES (%s)", ("saved " + expected_key,))
    monkeypatch.setattr(chk.FakeProvider, "__init__", planting)
    try:
        rep = run_check(base)
    finally:
        with psycopg2.connect(DB_URL) as conn, conn.cursor() as cur:
            cur.execute("DROP TABLE IF EXISTS public.leak_probe")
    assert [n for n in rep.failed] == [n for n in rep.failed if n.startswith("AT REST")] and rep.failed


def test_a_setup_that_cannot_save_the_provider_stops_with_one_failure(live_api):
    application, base = live_api
    application.state.settings.allow_private_model_urls = False
    rep = run_check(base)
    assert len(rep.failed) == 1 and rep.failed[0].startswith("SETUP")


def test_a_stack_with_live_chat_off_stops_with_one_clear_failure(live_api):
    """Live mode with LANGFLOW_PER_USER_TOOLS=0 answers chat with 503: say what to switch on instead of a row of confusing failures."""
    from app.services.chat import NotReadyChat
    application, base = live_api
    application.state.chat = NotReadyChat()
    rep = run_check(base)
    assert len(rep.failed) == 1 and "live chat is switched on" in rep.failed[0]
