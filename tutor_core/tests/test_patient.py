from tutor_core.patient import is_rate_limit, patient, wait_hint


def test_hint_formats():
    assert wait_hint("Rate limit. Please try again in 7m12.96s. Need more") == 432.96
    assert wait_hint("try again in 2.5s") == 2.5
    assert wait_hint("try again in 850ms") == 0.85
    assert wait_hint("try again in 1h2m") == 3720.0
    assert wait_hint("nothing here") is None


def test_rate_limit_detected():
    assert is_rate_limit(RuntimeError("Groq API error 429: x")) and is_rate_limit("rate_limit_exceeded")
    assert not is_rate_limit(RuntimeError("Groq API error 500"))


def _flaky(fails, message="Groq API error 429: try again in 3s"):
    state = {"n": 0}

    def call(prompt):
        state["n"] += 1
        if state["n"] <= fails:
            raise RuntimeError(message)
        return "story"
    return call, state


def test_waits_then_succeeds():
    call, state = _flaky(2)
    slept = []
    out = patient(call, sleep=slept.append, clock=lambda: 0.0)("p")
    assert out == "story" and state["n"] == 3 and slept == [4.0, 4.0]


def test_other_errors_raise_at_once():
    call, state = _flaky(1, "Groq API error 500: boom")
    try:
        patient(call, sleep=lambda s: None, clock=lambda: 0.0)("p")
    except RuntimeError:
        assert state["n"] == 1
        return
    raise AssertionError


def test_gives_up_after_max_waits_and_on_long_hint():
    call, state = _flaky(99)
    try:
        patient(call, max_waits=2, sleep=lambda s: None, clock=lambda: 0.0)("p")
    except RuntimeError:
        assert state["n"] == 3
    call, state = _flaky(99, "429 try again in 20m3s")
    try:
        patient(call, sleep=lambda s: (_ for _ in ()).throw(AssertionError("should not wait")), clock=lambda: 0.0)("p")
    except RuntimeError:
        assert state["n"] == 1
        return
    raise AssertionError


def test_pacing_sleeps_before_going_over():
    t = {"now": 0.0}
    slept = []

    def sleep(s):
        slept.append(s)
        t["now"] += s
    wrapped = patient(lambda p: "ok", tpm=3000, sleep=sleep, clock=lambda: t["now"])
    wrapped("x" * 3000)         # about 2200 tokens
    wrapped("x" * 3000)         # would reach 4400 > 3000: waits for the first to leave the minute
    assert len(slept) == 1 and 59 < slept[0] < 62
