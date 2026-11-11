"""Key rotation with a fake clock and a fake call: nothing waits and nothing touches Groq (11 Nov 2026)."""
import pytest

from tutor_core.key_pool import KeyPool, key_vars, rotating

LIMIT = "Error 429: Rate limit reached for model. Please try again in 7m12.96s"
MINUTE = "Error 429: rate limit. Please try again in 2.5s"


class Clock:
    now = 0.0

    def __call__(self):
        return self.now


class Fake:
    """Answers with the key it was called with; a key listed in `limited` raises a rate limit."""

    def __init__(self, limited=None):
        self.limited, self.used = dict(limited or {}), []

    def __call__(self, prompt, key):
        self.used.append(key)
        if key in self.limited:
            raise RuntimeError(self.limited[key])
        return f"answer from {key}"


def test_key_vars_numbered_deduplicated_and_without_placeholders():
    env = {"GROQ_API_KEY": "aaaaaaaa", "GROQ_API_KEY_2": "bbbbbbbb", "GROQ_API_KEY_3": "aaaaaaaa", "GROQ_API_KEY_4": "your-groq-api-key-here", "GROQ_API_KEY_5": " "}
    assert key_vars(None, env) == [None, "GROQ_API_KEY_2"]
    assert key_vars("GROQ_QWEN_API_KEY", env) == [None, "GROQ_API_KEY_2"]              # no key of its own: the main family
    own = dict(env, GROQ_QWEN_API_KEY="qqqqqqqq", GROQ_QWEN_API_KEY_2="rrrrrrrr")
    assert key_vars("GROQ_QWEN_API_KEY", own) == ["GROQ_QWEN_API_KEY", "GROQ_QWEN_API_KEY_2"]
    assert key_vars(None, {}) == []


def test_one_key_behaves_as_before():
    fake = Fake({None: LIMIT})
    call = rotating(fake, KeyPool([None]))
    with pytest.raises(RuntimeError):
        call("hi")
    assert fake.used == [None]


def test_a_rate_limit_moves_on_to_the_next_key_at_once_and_stays_there():
    clock, fake = Clock(), Fake({None: LIMIT})
    pool = KeyPool([None, "K2"], clock=clock)
    call = rotating(fake, pool)
    assert call("hello") == "answer from K2" and fake.used == [None, "K2"]
    assert call("again") == "answer from K2" and fake.used == [None, "K2", "K2"]       # the blocked key is not tried again
    assert any("rate limited" in e for e in pool.events) and any("switching key" in e for e in pool.events)


def test_a_blocked_key_comes_back_after_its_time():
    clock, fake = Clock(), Fake({None: MINUTE})
    pool = KeyPool([None, "K2"], clock=clock)
    call = rotating(fake, pool)
    call("one")
    fake.limited = {}
    clock.now = 10.0
    call("two")
    assert fake.used[-1] == "K2"                     # keeps the working key; the first is simply free again
    pool.block("K2", 100)
    call("three")
    assert fake.used[-1] is None                     # K2 is blocked for 100 s, the first key is free again


def test_every_key_limited_raises_the_last_error_for_patient_to_handle():
    fake = Fake({None: LIMIT, "K2": LIMIT})
    call = rotating(fake, KeyPool([None, "K2"], clock=Clock()))
    with pytest.raises(RuntimeError, match="429"):
        call("x")
    assert fake.used == [None, "K2"]


def test_other_errors_are_not_swallowed():
    fake = Fake({None: "HTTP 500 server error"})
    with pytest.raises(RuntimeError, match="500"):
        rotating(fake, KeyPool([None, "K2"]))("x")
    assert fake.used == [None]


def test_the_budget_switches_before_the_limit():
    fake = Fake()
    pool = KeyPool([None, "K2"], budget=2000, clock=Clock())
    call = rotating(fake, pool)
    prompt = "x" * 600                               # about 900 estimated tokens a call
    for _ in range(4):
        call(prompt)
    assert fake.used[:2] == [None, None] and "K2" in fake.used[2:] and any("over its budget" in e for e in pool.events)


def test_the_budget_never_blocks_a_call_when_every_key_is_over_it():
    fake = Fake()
    pool = KeyPool([None, "K2"], budget=1, clock=Clock())
    assert rotating(fake, pool)("x") .startswith("answer from")


def test_records_say_whether_it_was_a_minute_or_a_day_limit():
    day = "Error 429: Rate limit reached for model `m` on tokens per day (TPD): Limit 200000, Used 199100, Requested 1500. Please try again in 6m0s"
    fake = Fake({None: day})
    pool = KeyPool([None, "K2"], clock=Clock())
    rotating(fake, pool)("x")
    assert pool.records == [{"key": "GROQ_API_KEY", "kind": "TPD", "limit": 200000, "used": 199100, "try_again_in": 360.0}]
    assert "[TPD]" in pool.events[0]
