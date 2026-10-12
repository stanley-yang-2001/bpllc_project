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
