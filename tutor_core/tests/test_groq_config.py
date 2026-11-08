"""The Groq request takes its key and model from the environment (M3): nothing is hardcoded in the package."""
import json
from unittest.mock import MagicMock, patch

import pytest

from tutor_core import groq


def call(env, prompt="hi"):
    sent = {}

    def fake_urlopen(req, timeout=None):
        sent["body"] = json.loads(req.data.decode("utf-8"))
        sent["headers"] = {k.lower(): v for k, v in req.header_items()}
        resp = MagicMock()
        resp.read.return_value = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode("utf-8")
        resp.__enter__.return_value = resp
        return resp

    with patch.dict("os.environ", env, clear=True), patch("tutor_core.groq.urllib.request.urlopen", side_effect=fake_urlopen):
        assert groq.call_groq(prompt) == "ok"
    return sent


def test_the_model_defaults_to_the_one_step_10_measured():
    assert call({"GROQ_API_KEY": "k"})["body"]["model"] == "openai/gpt-oss-120b"


def test_the_model_can_be_changed_through_the_environment():
    assert call({"GROQ_API_KEY": "k", "GROQ_MODEL": "openai/gpt-oss-20b"})["body"]["model"] == "openai/gpt-oss-20b"
    assert call({"GROQ_API_KEY": "k", "GROQ_MODEL": "  "})["body"]["model"] == "openai/gpt-oss-120b"     # blank means default


def test_the_key_comes_from_the_environment_and_goes_only_in_the_header():
    sent = call({"GROQ_API_KEY": "secret-key"})
    assert sent["headers"]["authorization"] == "Bearer secret-key" and "secret-key" not in json.dumps(sent["body"])


@pytest.mark.parametrize("env", [{}, {"GROQ_API_KEY": ""}, {"GROQ_API_KEY": "your-groq-api-key-here"}])
def test_a_missing_or_placeholder_key_is_an_error_not_a_request(env):
    with patch.dict("os.environ", env, clear=True), patch("tutor_core.groq.urllib.request.urlopen") as opened:
        with pytest.raises(RuntimeError, match="GROQ_API_KEY"):
            groq.call_groq("hi")
    opened.assert_not_called()


# 7 Nov 2026: a step can use another model than the story (the judge and the grammar review must not mark their own work)
def call_with(env, **kwargs):
    sent = {}

    def fake_urlopen(req, timeout=None):
        sent["body"] = json.loads(req.data.decode("utf-8"))
        resp = MagicMock()
        resp.read.return_value = json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode("utf-8")
        resp.__enter__.return_value = resp
        return resp

    with patch.dict("os.environ", env, clear=True), patch("tutor_core.groq.urllib.request.urlopen", side_effect=fake_urlopen):
        groq.call_groq("hi", **kwargs)
    return sent["body"]


def test_a_step_can_name_its_own_model_and_effort():
    body = call_with({"GROQ_API_KEY": "k", "GROQ_MODEL": "openai/gpt-oss-120b"}, model="openai/gpt-oss-20b", effort="high")
    assert body["model"] == "openai/gpt-oss-20b" and body["reasoning_effort"] == "high"


def test_the_story_request_is_unchanged_without_the_new_arguments():
    body = call_with({"GROQ_API_KEY": "k"})
    assert body["model"] == "openai/gpt-oss-120b" and body["reasoning_effort"] == "low"


def test_a_model_that_is_not_gpt_oss_gets_no_reasoning_effort_and_a_bad_effort_means_low():
    assert "reasoning_effort" not in call_with({"GROQ_API_KEY": "k"}, model="llama-3.3-70b-versatile", effort="high")
    assert call_with({"GROQ_API_KEY": "k"}, model="openai/gpt-oss-20b", effort="extreme")["reasoning_effort"] == "low"


def test_make_model_call_reads_the_model_and_effort_from_the_environment():
    env = {"GROQ_API_KEY": "k", "GROQ_JUDGE_MODEL": "openai/gpt-oss-20b", "GROQ_JUDGE_EFFORT": "Medium"}
    sent = {}

    def fake_urlopen(req, timeout=None):
        sent["body"] = json.loads(req.data.decode("utf-8"))
        resp = MagicMock()
        resp.read.return_value = json.dumps({"choices": [{"message": {"content": "graded"}}]}).encode("utf-8")
        resp.__enter__.return_value = resp
        return resp

    with patch.dict("os.environ", env, clear=True), patch("tutor_core.groq.urllib.request.urlopen", side_effect=fake_urlopen):
        judge = groq.make_model_call("GROQ_JUDGE_MODEL", "GROQ_JUDGE_EFFORT")
        assert judge("rate this") == "graded"
    assert judge.model == "openai/gpt-oss-20b" and sent["body"]["model"] == "openai/gpt-oss-20b" and sent["body"]["reasoning_effort"] == "medium"


def test_make_model_call_is_none_when_the_model_is_not_set():
    with patch.dict("os.environ", {"GROQ_API_KEY": "k", "GROQ_MODEL": "x"}, clear=True):
        assert groq.make_model_call("GROQ_JUDGE_MODEL") is None
    with patch.dict("os.environ", {"GROQ_JUDGE_MODEL": "   "}, clear=True):
        assert groq.make_model_call("GROQ_JUDGE_MODEL", "GROQ_JUDGE_EFFORT") is None
