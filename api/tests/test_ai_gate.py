"""The AI gate (design section 11): at most N AI calls at once across the app, and one per learner.

Every call that reaches Groq, directly or through Langflow, passes through it, because the free tier's
rate limit is shared by every learner. These tests use real threads: a lock that is never contended
proves nothing.
"""
import threading
import time

import pytest

from app.errors import AppError
from app.services.ai_gate import AiGate


def test_a_free_slot_runs_and_is_released():
    gate = AiGate(slots=2, wait_seconds=0.1)
    with gate.slot(1):
        assert gate.in_flight == 1 and gate.active_users == {1}
    assert gate.in_flight == 0 and gate.active_users == set()


def test_the_same_learner_cannot_run_two_at_once():
    gate = AiGate(slots=2, wait_seconds=0.1)
    with gate.slot(1):
        with pytest.raises(AppError) as err:
            with gate.slot(1):
                pass
    assert err.value.code == "tutor_busy" and err.value.status == 429
    assert "already" in err.value.message.lower()
    assert err.value.retry_after


def test_a_second_learner_is_not_blocked_by_the_first():
    gate = AiGate(slots=2, wait_seconds=0.1)
    with gate.slot(1):
        with gate.slot(2):
            assert gate.in_flight == 2


def test_a_full_gate_answers_tutor_busy_after_the_wait():
    gate = AiGate(slots=1, wait_seconds=0.15, retry_after=11)
    with gate.slot(1):
        started = time.monotonic()
        with pytest.raises(AppError) as err:
            with gate.slot(2):
                pass
        waited = time.monotonic() - started
    assert err.value.code == "tutor_busy" and err.value.status == 429 and err.value.retry_after == 11
    assert 0.1 <= waited < 1.0          # it waited, then gave up; it did not fail instantly or hang


def test_a_refused_learner_is_not_left_locked_out():
    gate = AiGate(slots=1, wait_seconds=0.05)
    with gate.slot(1):
        with pytest.raises(AppError):
            with gate.slot(2):
                pass
        assert 2 not in gate.active_users       # refused because the gate was full, not because 2 is "busy"
    with gate.slot(2):                          # and 2 can run as soon as there is room
        pass


def test_a_waiting_learner_gets_the_slot_when_it_frees_up():
    gate = AiGate(slots=1, wait_seconds=2.0)
    got_it = threading.Event()

    def second():
        with gate.slot(2):
            got_it.set()

    with gate.slot(1):
        t = threading.Thread(target=second)
        t.start()
        time.sleep(0.1)
        assert not got_it.is_set()              # still waiting while 1 holds the slot
    t.join(timeout=3)
    assert got_it.is_set()


def test_an_error_inside_the_slot_still_releases_everything():
    gate = AiGate(slots=1, wait_seconds=0.05)
    with pytest.raises(RuntimeError):
        with gate.slot(1):
            raise RuntimeError("boom")
    assert gate.in_flight == 0 and gate.active_users == set()
    with gate.slot(1):                          # usable again
        pass


def test_the_limit_holds_under_real_concurrency():
    gate = AiGate(slots=2, wait_seconds=5.0)
    lock, running, peak, finished = threading.Lock(), [0], [0], [0]

    def work(user):
        with gate.slot(user):
            with lock:
                running[0] += 1
                peak[0] = max(peak[0], running[0])
            time.sleep(0.05)
            with lock:
                running[0] -= 1
                finished[0] += 1

    threads = [threading.Thread(target=work, args=(u,)) for u in range(8)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert peak[0] == 2 and finished[0] == 8
    assert gate.in_flight == 0
