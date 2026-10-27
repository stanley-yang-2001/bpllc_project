"""AiRunner: the model sources are tried in order, each one is a separate class, and a failure becomes the standard error."""
import pytest

from app.errors import AppError
from app.services.ai_runner import AiRunner, Chosen, OwnModelSource, SharedSource, StubSource
from app.services.user_model import RequestLimiter


class Gate:
    def __init__(self):
        self.tokens = []

    def slot(self, user_id, tokens=0):
        gate = self
        class Ctx:
            def __enter__(self_inner):
                gate.tokens.append(tokens)
                return object()
            def __exit__(self_inner, *a):
                return False
        return Ctx()


class FakeOwn:
    def __init__(self, found):
        self.found = found

    def find(self, user_id, conn=None):
        return self.found


def shared(prompt):
    return "shared:" + prompt


def runner(*sources, gate=None):
    return AiRunner(list(sources), gate or Gate())


def test_the_stub_answers_only_in_stub_mode_and_only_when_the_job_has_one():
    stub = lambda p: "stub:" + p
    assert runner(StubSource("stub"), SharedSource(shared)).choose(1, stub).call("x") == "stub:x"
    assert runner(StubSource("live"), SharedSource(shared)).choose(1, stub).call("x") == "shared:x"
    assert runner(StubSource("stub"), SharedSource(shared)).choose(1).call("x") == "shared:x"


def test_a_stand_in_is_never_charged_to_the_token_budget():
    gate = Gate()
    r = runner(StubSource("stub"), SharedSource(shared), gate=gate)
    r.run(1, "p", tokens=500, stub=lambda p: "ok", failed_message="no")
    r.run(1, "p", tokens=500, failed_message="no")
    assert gate.tokens == [0, 500]


def test_a_learners_own_model_comes_before_the_shared_one_and_is_not_charged_either(monkeypatch):
    own = {"model": "my-model", "base_url": "https://x.example/v1", "key": "k"}
    monkeypatch.setattr("app.services.ai_runner.make_call_fn", lambda *a, **k: _own_call)
    gate = Gate()
    r = runner(OwnModelSource(FakeOwn(own), RequestLimiter(5), False), SharedSource(shared), gate=gate)
    chosen = r.choose(1)
    assert chosen.own_model == "my-model" and chosen.call("p") == "own:p"
    r.run(1, "p", tokens=500, failed_message="no")
    assert gate.tokens == [0]


def _own_call(prompt):
    return "own:" + prompt


_own_call.calls_ai = False


def test_without_an_own_model_the_shared_one_answers():
    chosen = runner(OwnModelSource(FakeOwn(None), RequestLimiter(5), False), SharedSource(shared)).choose(1)
    assert chosen.own_model is None and chosen.call("p") == "shared:p"


def test_the_own_model_has_a_request_limit(monkeypatch):
    own = {"model": "m", "base_url": "https://x.example/v1", "key": "k"}
    monkeypatch.setattr("app.services.ai_runner.make_call_fn", lambda *a, **k: _own_call)
    r = runner(OwnModelSource(FakeOwn(own), RequestLimiter(1), False), SharedSource(shared))
    r.choose(1)
    with pytest.raises(AppError) as e:
        r.choose(1)
    assert e.value.code == "rate_limited" and e.value.status == 429


def test_no_source_at_all_is_a_clear_error():
    with pytest.raises(AppError) as e:
        runner().choose(1)
    assert e.value.code == "ai_failed"


def test_a_failing_shared_model_gives_the_standard_error_without_leaking_the_cause():
    def boom(prompt):
        raise RuntimeError("secret detail")
    with pytest.raises(AppError) as e:
        runner(SharedSource(boom)).run(1, "p", tokens=1, failed_message="Please try again.")
    assert e.value.code == "ai_failed" and e.value.message == "Please try again." and "secret" not in e.value.message


def test_a_failing_own_model_says_which_model_and_why():
    def boom(prompt):
        raise RuntimeError("x")
    boom.last_error = "The model server answered 401."
    boom.calls_ai = False
    err = AiRunner.failure(Chosen(boom, own_model="my-model"), "shared message", own_hint="Switch back in Settings.")
    assert err.code == "custom_model_failed"
    assert err.message == "Your model (my-model) didn't answer: The model server answered 401. Switch back in Settings."


def test_a_new_source_is_just_another_class_in_the_list():
    class Always:
        def pick(self, user_id, stub):
            return Chosen(lambda p: "always:" + p)
    assert runner(Always(), SharedSource(shared)).choose(1).call("x") == "always:x"
