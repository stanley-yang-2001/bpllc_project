"""The tokens-per-minute limiter (design 17A item 2 / risk 8).

Groq's free tier allows roughly 8000 tokens a minute for the whole app, however few calls that is. The AI gate
already limits how many calls run at once; this limits how many tokens they may use in any 60 seconds. A call
reserves an ESTIMATE before it runs and is corrected to the REAL count Langflow reports afterwards.
"""
import json
import threading
from pathlib import Path

import pytest

from app.config import ConfigError, load_settings
from app.errors import AppError
from app.services import langflow_client as lc
from app.services.ai_gate import AiGate, TokenBudget
from app.services.langflow_client import ChatResult
from conftest import register

PART = "d" * 32
FIX = Path(__file__).parent / "fixtures" / "langflow"


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def gate(limit=8000, clock=None, **kw):
    return AiGate(slots=4, wait_seconds=0.1, tokens_per_minute=limit, clock=clock or Clock(), **kw)


def refused(g, user, tokens):
    with pytest.raises(AppError) as err:
        with g.slot(user, tokens=tokens):
            pass
    return err.value


# --- the budget --------------------------------------------------------------------------------------

def test_calls_within_the_budget_run():
    g = gate()
    with g.slot(1, tokens=3000):
        pass
    with g.slot(2, tokens=3000):
        pass
    assert g.tokens_used == 6000


def test_a_call_that_would_pass_the_limit_is_refused_as_tutor_busy_with_a_wait():
    clock = Clock()
    g = gate(clock=clock)
    with g.slot(1, tokens=5000):
        pass
    clock.now += 20
    err = refused(g, 2, 4000)                       # 5000 + 4000 > 8000
    assert err.code == "tutor_busy" and err.status == 429
    assert err.retry_after == 40                    # the 5000 leave the window 60 s after they were used (20 s ago)
    assert "langflow" not in err.message.lower() and "token" not in err.message.lower()


def test_the_budget_frees_up_after_a_minute():
    clock = Clock()
    g = gate(clock=clock)
    with g.slot(1, tokens=7000):
        pass
    assert refused(g, 2, 2000).retry_after == 60
    clock.now += 60.5
    with g.slot(2, tokens=2000):
        pass
    assert g.tokens_used == 2000


def test_the_wait_is_until_enough_has_expired_not_until_everything_has():
    clock = Clock()
    g = gate(clock=clock)
    with g.slot(1, tokens=3000):
        pass
    clock.now += 30
    with g.slot(2, tokens=4000):
        pass
    clock.now += 10                                  # first use is 40 s old, second 10 s old; 7000 in the window
    assert refused(g, 3, 3000).retry_after == 20     # needs the first 3000 gone: 60 - 40
    assert refused(g, 3, 5000).retry_after == 50     # needs both gone: the second leaves in 60 - 10


def test_settling_replaces_the_estimate_with_the_real_count():
    g = gate()
    with g.slot(1, tokens=3000) as ticket:
        ticket.settle(600)
    assert g.tokens_used == 600
    with g.slot(2, tokens=3000) as ticket:
        ticket.settle(5000)                          # an estimate that was too low is corrected upward too
    assert g.tokens_used == 5600


def test_a_call_that_reports_nothing_keeps_its_estimate():
    g = gate()
    with g.slot(1, tokens=3000) as ticket:
        ticket.settle(None)
    assert g.tokens_used == 3000


def test_a_call_that_fails_keeps_its_estimate():
    g = gate()
    with pytest.raises(RuntimeError):
        with g.slot(1, tokens=3000):
            raise RuntimeError("langflow broke")
    assert g.tokens_used == 3000                     # Groq may well have counted it


def test_a_refused_call_reserves_nothing_and_leaves_the_learner_free():
    g = gate()
    with g.slot(1, tokens=7000):
        pass
    refused(g, 2, 4000)
    assert g.tokens_used == 7000 and g.in_flight == 0 and g.active_users == set()
    with g.slot(2, tokens=500):
        pass


def test_a_single_call_bigger_than_the_whole_budget_still_runs_when_nothing_else_has():
    g = gate(limit=1000)
    with g.slot(1, tokens=5000):
        pass
    assert refused(g, 2, 1).code == "tutor_busy"     # but it used the whole minute


def test_a_limit_of_zero_switches_the_limiter_off():
    g = gate(limit=0)
    for user in range(1, 6):
        with g.slot(user, tokens=10_000) as ticket:
            ticket.settle(10_000)
    assert g.tokens_used == 0


def test_a_slot_without_an_estimate_is_not_limited():
    g = gate(limit=100)
    for user in range(1, 4):
        with g.slot(user):
            pass


def test_exclusive_does_not_touch_the_budget():
    g = gate()
    with g.exclusive(1):
        pass
    assert g.tokens_used == 0


def test_many_threads_cannot_overspend_the_budget():
    g = AiGate(slots=20, wait_seconds=1, tokens_per_minute=8000)
    ok, busy, barrier = [], [], threading.Barrier(20)

    def worker(user):
        barrier.wait()
        try:
            with g.slot(user, tokens=1000):
                ok.append(user)
        except AppError:
            busy.append(user)

    threads = [threading.Thread(target=worker, args=(u,)) for u in range(1, 21)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert len(ok) == 8 and len(busy) == 12 and g.tokens_used == 8000


# --- reading the real count out of Langflow's answer ----------------------------------------------------

def test_the_real_greeting_run_reports_its_tokens():
    assert lc.parse_run_response(json.loads((FIX / "greeting_run.json").read_text())).tokens == 618


def test_the_real_story_run_reports_its_tokens():
    assert lc.parse_run_response(json.loads((FIX / "story_run.json").read_text())).tokens == 1344


@pytest.mark.parametrize("resp", [{}, {"usage": "x"}, {"usage": {"total_tokens": "12"}}, {"usage": {"total_tokens": -5}},
                                  {"usage": {"total_tokens": True}}, [], None])
def test_a_missing_or_odd_usage_is_none_not_a_crash(resp):
    assert lc.parse_run_response(resp).tokens is None


def test_total_tokens_is_preferred_and_input_plus_output_is_the_fallback():
    assert lc.find_tokens({"properties": {"usage": {"input_tokens": 10, "output_tokens": 5, "total_tokens": 20}}}) == 20
    assert lc.find_tokens({"properties": {"usage": {"input_tokens": 10, "output_tokens": 5}}}) == 15


# --- the chat route ------------------------------------------------------------------------------------

class Tutor:
    stores_chat = False
    calls_ai = True

    def __init__(self, tokens=None, error=None):
        self.calls, self.tokens, self.error = 0, tokens, error

    def run(self, **kw):
        self.calls += 1
        if self.error:
            raise self.error
        return ChatResult("ok", tokens=self.tokens)

    def delete_sessions(self, ids):
        pass

    def health(self):
        return {"ok": None, "status": "stub", "detail": None}


@pytest.fixture
def limited(app):
    saved = app.state.chat, app.state.ai_gate
    tutor = Tutor(tokens=500)
    app.state.chat = tutor
    app.state.ai_gate = AiGate(slots=2, wait_seconds=0.2, tokens_per_minute=8000)
    yield tutor, app.state.ai_gate
    app.state.chat, app.state.ai_gate = saved


def say(c, text="hi", part=PART):
    return c.post("/api/chat", json={"message": text, "language": "es", "session_id": part})


def test_a_chat_turn_is_charged_what_langflow_reports(client, limited):
    tutor, g = limited
    register(client, "alice")
    assert say(client).status_code == 200
    assert g.tokens_used == 500


def test_the_budget_is_shared_by_every_learner_and_refusal_is_a_429_with_retry_after(make_user, limited):
    tutor, g = limited
    tutor.tokens = None                                   # nothing reported: every turn keeps its estimate
    a, b = make_user("alice"), make_user("bob")
    answers = [say(a).status_code, say(b).status_code]
    for _ in range(10):
        answers.append(say(a).status_code)
    assert answers.count(200) == tutor.calls and 429 in answers
    r = say(b)
    assert r.status_code == 429 and r.json()["error"]["code"] == "tutor_busy" and int(r.headers["retry-after"]) >= 1
    calls = tutor.calls
    say(a)
    assert tutor.calls == calls                           # a refused turn never reaches the tutor


def test_real_counts_let_more_turns_through_than_the_estimate_would(client, limited):
    tutor, g = limited
    register(client, "alice")
    assert all(say(client).status_code == 200 for _ in range(12))     # 12 x 500 = 6000 < 8000
    assert g.tokens_used == 6000


def test_a_failed_turn_still_counts(client, limited):
    tutor, g = limited
    tutor.error = AppError("ai_failed", "x", 502)
    register(client, "alice")
    assert say(client).status_code == 502
    assert g.tokens_used > 0


def test_a_longer_message_is_estimated_higher(app):
    from app.routes.chat import estimate_tokens
    assert estimate_tokens("a" * 2000) > estimate_tokens("hi") > 0


def test_the_stub_tutor_is_never_limited(app, client):
    from app.services.chat_stub import StubChat
    saved = app.state.chat, app.state.ai_gate
    app.state.chat, app.state.ai_gate = StubChat(lambda: app.state.pool), AiGate(tokens_per_minute=10)
    try:
        register(client, "alice")
        assert all(say(client).status_code == 200 for _ in range(5))
    finally:
        app.state.chat, app.state.ai_gate = saved


# --- settings ------------------------------------------------------------------------------------------

BASE = {"DATABASE_URL": "postgresql://x", "JWT_SECRET": "s" * 40}


def test_the_default_is_groqs_free_tier_and_it_can_be_changed_or_switched_off():
    assert load_settings(BASE).ai_tokens_per_minute == 8000
    assert load_settings({**BASE, "AI_TOKENS_PER_MINUTE": "20000"}).ai_tokens_per_minute == 20000
    assert load_settings({**BASE, "AI_TOKENS_PER_MINUTE": "0"}).ai_tokens_per_minute == 0


def test_a_negative_limit_stops_the_app_starting():
    with pytest.raises(ConfigError):
        load_settings({**BASE, "AI_TOKENS_PER_MINUTE": "-1"})


def test_the_app_builds_its_gate_from_the_setting(app):
    assert app.state.settings.ai_tokens_per_minute == 8000
    assert app.state.ai_gate.tokens_per_minute == app.state.settings.ai_tokens_per_minute
